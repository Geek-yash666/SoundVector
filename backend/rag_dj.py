#!/usr/bin/env python3
"""
SoundVector RAG DJ & Groundedness Checker (Gemini Commentary + Fact Verification)
"""

import json
import os
import re
from typing import Dict, List, Optional, Tuple

try:
    from .config import FEATURE_TERMS
except ImportError:
    from config import FEATURE_TERMS



def _mood_word(valence: float, energy: float) -> Tuple[str, str]:
    v = "melancholy" if valence <= 0.45 else ("upbeat" if valence >= 0.55 else "balanced")
    e = "high-energy" if energy >= 0.60 else ("laid-back" if energy <= 0.45 else "mid-tempo")
    return v, e


class GroundednessChecker:
    def __init__(self):
        self.genre_words = {"pop", "rock", "hip hop", "rap", "r&b", "edm", "house",
                            "country", "jazz", "soul", "metal", "latin", "indie",
                            "acoustic", "lo-fi", "folk", "funk", "electronic", "dance",
                            "trap", "afrobeats", "k-pop", "reggaeton", "classical"}

    def check(self, text: str, facts: dict, recs: List[dict]) -> dict:
        low = text.lower()
        violations, total, grounded = [], 0, 0

        for term, (feat, cmp, thr) in FEATURE_TERMS.items():
            if re.search(rf"\b{re.escape(term)}\b", low):
                val = facts.get(feat)
                if val is None:
                    continue
                total += 1
                ok = (val >= thr) if cmp == ">=" else (val <= thr)
                if ok:
                    grounded += 1
                else:
                    violations.append(f"'{term}' implies {feat}{cmp}{thr}, but {feat}={val}")

        descriptive = low
        for nm in [facts.get("name", ""), facts.get("artist", "")] + \
                  [r.get("name", "") for r in recs] + [r.get("artist", "") for r in recs]:
            if nm:
                descriptive = descriptive.replace(nm.lower(), " ")

        all_genres = set(g.lower() for g in facts.get("genres", []))
        for r in recs:
            all_genres |= set(g.lower() for g in r.get("genres", []))
        genre_blob = " ".join(all_genres)

        for gw in self.genre_words:
            if re.search(rf"\b{re.escape(gw)}\b", descriptive):
                total += 1
                if gw in genre_blob:
                    grounded += 1
                else:
                    violations.append(f"genre '{gw}' mentioned but not in any retrieved track")

        known_artists = {facts.get("artist", ""), facts.get("name", "")}
        known_artists |= {r.get("artist", "") for r in recs}
        known_artists |= {r.get("name", "") for r in recs}
        known_artists = {a.lower() for a in known_artists if a and a != "Unknown Artist"}

        for m in re.finditer(r"\bby ([A-Z][A-Za-z0-9.\-]+(?: [A-Z][A-Za-z0-9.\-]+){0,3})", text):
            name = m.group(1).strip().lower()
            if name.startswith("unknown"):
                continue
            total += 1
            if any(name in a or a in name for a in known_artists):
                grounded += 1
            else:
                violations.append(f"artist 'by {m.group(1)}' not among retrieved tracks")

        rate = 1.0 if total == 0 else grounded / total
        return {"groundedness": round(rate, 3), "total_claims": total,
                "grounded": grounded, "violations": violations}


class RAGDJ:
    def __init__(self, model: str = "gemini-3.1-flash-lite", api_key: Optional[str] = None):
        self.model = model
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self._client = None
        if self.api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            except Exception as e:
                print(f"[RAGDJ] Gemini unavailable ({e}); using template narrator.")

    @property
    def backend(self) -> str:
        return f"gemini:{self.model}" if self._client else "template"

    def _intel_prompt(self, facts: dict, recs: List[dict]) -> str:
        is_mood = facts.get("artist") == "your vibe"
        if is_mood:
            context = f"The user searched for the mood/vibe: \"{facts.get('name', '')}\""
            context += f"\nTop genres in results: {', '.join(facts.get('genres', []))}"
        else:
            context = f"Song: \"{facts.get('name', '')}\" by {facts.get('artist', 'Unknown')}"
            context += f"\nYear: {facts.get('year', 'unknown')}"
            context += f"\nGenres: {', '.join(facts.get('genres', [])[:5])}"
            context += f"\nAudio: energy={facts.get('energy', 0.5)}, valence={facts.get('valence', 0.5)}, danceability={facts.get('danceability', 0.5)}, {facts.get('tempo_bpm', 120)} BPM"

        rec_names = ", ".join(f"\"{r.get('name', '')}\" by {r.get('artist', '')}" for r in recs[:5])

        return (
            "You are a music expert assistant. Given a song/artist or mood query with its audio attributes, "
            "provide interesting, factual insights.\n\n"
            "RULES:\n"
            "1. Output ONLY valid JSON, no markdown fences.\n"
            "2. Do NOT invent chart positions, sales numbers, or specific dates you're unsure about.\n"
            "3. Focus on production style, musical influences, cultural significance, and primary artist background.\n"
            "4. Make sure at least one insight point specifically highlights the primary artist's legacy, signature sound, or discography impact.\n"
            "5. Keep each fact to 1-2 sentences.\n\n"
            f"CONTEXT:\n{context}\n"
            f"Similar tracks found: {rec_names}\n\n"
            'Return JSON: {"headline": "A catchy 5-8 word summary of the vibe", '
            '"insights": ["artist/track fact 1", "fact 2", "fact 3"], '
            '"sound_profile": "1-2 sentence description of the sonic characteristics", '
            '"mood_tags": ["tag1", "tag2", "tag3"], '
            '"listen_if": "You\'ll love this if you enjoy..."}'
        )

    def _template_intel(self, facts: dict, recs: List[dict]) -> dict:
        """Data-derived insights when Gemini is unavailable."""
        name = facts.get('name', 'This')
        artist = facts.get('artist', '')
        v, e = _mood_word(facts.get("valence", 0.5), facts.get("energy", 0.5))
        genres = facts.get("genres", [])
        genre_str = genres[0] if genres else "mixed"
        energy = facts.get("energy", 0.5)
        valence = facts.get("valence", 0.5)
        dance = facts.get("danceability", 0.5)
        tempo = facts.get("tempo_bpm", 120)
        year = facts.get("year", 0)
        pop = facts.get("popularity", 0)
        is_mood = artist == "your vibe"

        insights = []
        if not is_mood:
            if pop > 0.8:
                insights.append(f"This track ranks in the top {int((1-pop)*100)+1}% of popularity in our catalog of 899K+ tracks.")
            elif pop > 0.5:
                insights.append(f"A well-known track sitting at {int(pop*100)}% popularity in our catalog.")
            else:
                insights.append(f"A hidden gem — this track sits below the mainstream radar at {int(pop*100)}% popularity.")

        if energy >= 0.75:
            insights.append(f"High-octane energy ({energy:.2f}) — this hits harder than 75% of tracks in the catalog.")
        elif energy <= 0.3:
            insights.append(f"Ultra-low energy ({energy:.2f}) — perfect for winding down or introspective moments.")

        if dance >= 0.7:
            insights.append(f"Danceability score of {dance:.2f} puts this firmly in groove territory — built for movement.")

        if tempo >= 140:
            insights.append(f"At {tempo} BPM, this runs at a high tempo — great for high-intensity activities.")
        elif tempo <= 85:
            insights.append(f"A slow {tempo} BPM tempo creates a laid-back, atmospheric feel.")

        if year and year > 0 and not is_mood:
            decade = (year // 10) * 10
            insights.append(f"Released in {year}, carrying the sonic signature of the {decade}s era.")

        if artist and artist != "your vibe" and artist != "Unknown Artist":
            insights.append(f"{artist} is a prominent voice in the {genre_str} landscape with a distinct musical identity.")

        if len(genres) >= 2:
            insights.append(f"Sits at the crossroads of {' and '.join(genres[:3])}, blending multiple sonic worlds.")

        if not insights:
            insights.append(f"A {v}, {e} track in the {genre_str} space.")

        # Sound profile
        parts = []
        if energy >= 0.6:
            parts.append("driving")
        elif energy <= 0.4:
            parts.append("gentle")
        if valence >= 0.6:
            parts.append("bright")
        elif valence <= 0.4:
            parts.append("dark")
        if dance >= 0.6:
            parts.append("rhythmic")
        sound_profile = f"A {', '.join(parts) if parts else 'balanced'} sound at {tempo} BPM with {genre_str} foundations."

        # Mood tags
        mood_tags = []
        if energy >= 0.6: mood_tags.append("energetic")
        if energy <= 0.4: mood_tags.append("calm")
        if valence >= 0.6: mood_tags.append("uplifting")
        if valence <= 0.4: mood_tags.append("introspective")
        if dance >= 0.6: mood_tags.append("groovy")
        mood_tags.append(genre_str)
        if not mood_tags:
            mood_tags = ["balanced", genre_str]

        # Listen-if
        rec_artists = list(set(r.get("artist", "") for r in recs[:5] if r.get("artist") != "Unknown Artist"))
        listen_if = f"You'll love this if you enjoy {', '.join(rec_artists[:3]) if rec_artists else genre_str} and similar vibes."

        headline = f"{name} — {v} {genre_str} energy" if not is_mood else f"{name} — {v} {e} vibes"

        return {
            "headline": headline,
            "insights": insights[:4],
            "sound_profile": sound_profile,
            "mood_tags": mood_tags[:5],
            "listen_if": listen_if,
        }

    def playlist_gen_prompt(self, user_prompt: str, available_genres: List[str], count: int) -> str:
        lang_directive = ""
        p_low = user_prompt.lower()
        for lang in ["telugu", "hindi", "tamil", "punjabi", "spanish", "korean", "japanese", "kannada", "malayalam", "marathi", "bengali"]:
            if lang in p_low:
                lang_name = lang.capitalize()
                lang_directive = f"\nCRITICAL LANGUAGE DIRECTIVE: The user requested {lang_name} music. You MUST ONLY return authentic {lang_name} songs by {lang_name} artists. If you return ANY songs in other languages (like English or Hindi), the system will break. ONLY output genuine {lang_name} tracks."
                break

        return (
            "You are a world-class music curator AI. The user wants a custom playlist.\n"
            "Analyze their intent, mood, genre, language/country, and vibe, then generate structured parameters AND a list of specific famous track search queries matching their request.\n\n"
            "RULES:\n"
            "1. Output ONLY valid JSON, no markdown formatting.\n"
            "2. 'playlist_name' should be catchy and creative.\n"
            "3. 'description' should be a sleek 1-sentence summary.\n"
            "4. 'specific_tracks' MUST be an array of 12-20 specific famous song objects (e.g. [{\"name\": \"Song Name\", \"artist\": \"Artist Name\"}, ...]) that PERFECTLY match the user request."
            f"{lang_directive}\n\n"
            f"User Request: \"{user_prompt}\"\n"
            f"Tracks Requested: {count}\n\n"
            'Return JSON format:\n'
            '{\n'
            '  "playlist_name": "Creative Playlist Title",\n'
            '  "description": "1-sentence playlist summary",\n'
            '  "genres": ["genre1", "genre2"],\n'
            '  "specific_tracks": [{"name": "Track Title 1", "artist": "Artist 1"}]\n'
            '}'
        )

    def get_intel(self, facts: dict, recs: List[dict]) -> dict:
        """Get AI-powered insights about a track/mood."""
        if not self._client:
            return self._template_intel(facts, recs)
        try:
            resp = self._client.models.generate_content(
                model=self.model,
                contents=self._intel_prompt(facts, recs)
            )
            text = (resp.text or "").strip()
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                result = json.loads(match.group(0))
                for key in ["headline", "insights", "sound_profile", "mood_tags", "listen_if"]:
                    if key not in result:
                        result[key] = self._template_intel(facts, recs).get(key, "")
                return result
            return self._template_intel(facts, recs)
        except Exception as e:
            print(f"[RAGDJ] intel generation failed ({e}); using template.")
            return self._template_intel(facts, recs)

    def mood_fallback(self, query: str, available_genres: List[str]) -> Optional[dict]:
        """When MoodToVector has zero TF-IDF coverage, use Gemini to interpret the query."""
        if not self._client:
            return None
        top_genres = available_genres[:80] if len(available_genres) > 80 else available_genres
        genre_list = ", ".join(top_genres)
        prompt = (
            f"A user wants music recommendations for: \"{query}\"\n\n"
            f"Map this request to audio attributes and genre keywords.\n"
            f"Available genres in our catalog: [{genre_list}]\n\n"
            "Output ONLY valid JSON (no markdown):\n"
            '{"energy": 0.0-1.0, "valence": 0.0-1.0, "danceability": 0.0-1.0, '
            '"acousticness": 0.0-1.0, "tempo_bpm": 60-200, '
            '"genres": ["genre1", "genre2", "genre3"], '
            '"explanation": "brief explanation of the mapping"}\n\n'
            "Rules:\n"
            "- Only use genres from the provided list above\n"
            "- Set audio values that match what the user wants (e.g., gym = high energy)\n"
            "- Consider cultural context (e.g., telugu → filmi/bollywood genres)\n"
        )
        try:
            resp = self._client.models.generate_content(model=self.model, contents=prompt)
            text = (resp.text or "").strip()
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                result = json.loads(match.group(0))
                for k in ["energy", "valence", "danceability", "acousticness"]:
                    if k in result:
                        result[k] = max(0.0, min(1.0, float(result[k])))
                if "tempo_bpm" in result:
                    result["tempo_bpm"] = max(60, min(200, int(result["tempo_bpm"])))
                if "genres" not in result or not result["genres"]:
                    result["genres"] = ["pop"]
                return result
        except Exception as e:
            print(f"[RAGDJ] mood fallback failed ({e})")
        return None

    def narrate(self, header: str, facts: dict, recs: List[dict]) -> str:
        intel = self.get_intel(facts, recs)
        headline = intel.get("headline", "")
        sound = intel.get("sound_profile", "")
        return f"{headline}. {sound}"
