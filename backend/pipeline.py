#!/usr/bin/env python3
"""
SoundVector Recommendation Pipeline (Query classification, ANN retrieval, NLP vector fallback, ZeroGPU support)
"""

import re
from collections import Counter
from typing import Dict, List, Optional

import numpy as np
from rapidfuzz import fuzz

try:
    from .config import BASE_GENRE_MAP, GPU_USAGE, HAS_SPACES
    from .engine import RecommendationEngine
    from .external_api import search_live_apis
    from .mood import MoodToVector
    from .profiles import ProfileStore
    from .rag_dj import GroundednessChecker, RAGDJ
except ImportError:
    from config import BASE_GENRE_MAP, GPU_USAGE, HAS_SPACES
    from engine import RecommendationEngine
    from external_api import search_live_apis
    from mood import MoodToVector
    from profiles import ProfileStore
    from rag_dj import GroundednessChecker, RAGDJ


if HAS_SPACES and GPU_USAGE:
    import spaces


def is_song_query(engine: RecommendationEngine, query: str):
    clean_q = re.sub(
        r"^(?:songs?|tracks?|music|tunes?|anything)?\s*(?:like|similar\s+to|resembling|more\s+like|by|from)\s+",
        "", query, flags=re.IGNORECASE
    ).strip()
    target_q = clean_q if clean_q else query

    q_tokens = set(re.findall(r"\w+", target_q.lower()))
    hits = engine.search(target_q, limit=1)
    if hits and hits[0].get("match", 0) >= 55:
        top = hits[0]
        track_tokens = set(re.findall(r"\w+", (top["name"] + " " + top["artist"]).lower()))
        missing = q_tokens - track_tokens
        stopwords = {"song", "songs", "track", "tracks", "music", "by", "the", "a", "an", "feat", "ft"}
        missing_clean = {w for w in missing if w not in stopwords and len(w) > 1}
        
        if not missing_clean:
            overlap = len(q_tokens & track_tokens) / max(len(q_tokens), 1)
            if top.get("match", 0) >= 90 or overlap >= 0.4:
                return top

    am = engine.match_artist(target_q)
    if am and am[0]["max_pop"] >= 0.3 and fuzz.token_set_ratio(target_q.lower(), am[0]["artist"].lower()) >= 80:
        return "artist"
    return None


def run_pipeline(query: str, engine: RecommendationEngine, mood_model: MoodToVector,
                 dj: RAGDJ, checker: GroundednessChecker, profile: dict, store: ProfileStore,
                 mode: str = "similar", k: int = 10, search_type: str = "auto",
                 seed_track: Optional[dict] = None):
    profile_vecs = store.vectors(profile) if profile.get("n_events") else None

    # Priority 0: Explicit seed track object passed from frontend selection
    if seed_track and isinstance(seed_track, dict) and seed_track.get("name") and seed_track.get("artist"):
        facts = seed_track
        if seed_track.get("row", -1) >= 0:
            seed_row = seed_track["row"]
            recs = engine.recommend([seed_row], k=k, mode=mode, profile_vectors=profile_vecs)
            header = f"{facts['name']} — {facts['artist']}"
        else:
            t = mood_model.transform(f"{seed_track['name']} {seed_track['artist']} {' '.join(seed_track.get('base_genres', []))}")
            recs = engine.recommend_by_vector(t["vector"], k=k)
            header = f"{seed_track['name']} — {seed_track['artist']}"

        rec_cards = [engine.track_card(r["row"]) for r in recs if r.get("row", -1) >= 0]
        intel = dj.get_intel(facts, rec_cards)
        blurb = f"{intel.get('headline', '')}. {intel.get('sound_profile', '')}"
        ground = checker.check(blurb, facts, rec_cards)
        return header, recs, blurb, ground, facts, intel

    # Check if query specifies 'songs like X' or 'similar to X'
    like_match = re.search(r'^(?:songs?|tracks?)\s+(?:like|similar\s+to)\s+(.+)$', query.strip(), re.IGNORECASE)
    if like_match:
        target_song = like_match.group(1).strip()
        hits = engine.search(target_song, limit=1)
        if hits:
            seed = {"row": hits[0]["row"]}
        else:
            live = search_live_apis(target_song, limit=1)
            if live:
                seed_track = live[0]

    if search_type == "nlp":
        seed = None
    elif search_type == "track":
        if 'seed' not in locals():
            seed = is_song_query(engine, query)
            if not seed:
                hits = engine.search(query, limit=1)
                if hits:
                    q_words = set(re.findall(r'\w+', query.lower()))
                    h_art_words = set(re.findall(r'\w+', hits[0]["artist"].lower()))
                    h_name_words = set(re.findall(r'\w+', hits[0]["name"].lower()))
                    missing = q_words - h_art_words - h_name_words
                    if not missing:
                        seed = {"row": hits[0]["row"]}
    else:
        if 'seed' not in locals():
            seed = is_song_query(engine, query)

    if seed and seed != "artist" and seed.get("row", -1) >= 0:
        seed_row = seed["row"]
        recs = engine.recommend([seed_row], k=k, mode=mode, profile_vectors=profile_vecs)
        facts = engine.track_card(seed_row)
        header = f"{facts['name']} — {facts['artist']}"
    elif seed == "artist":
        name = engine.match_artist(query)[0]["artist"]
        tracks = engine.artist_top_tracks(name, limit=1)
        seed_row = tracks[0]["row"]
        recs = engine.recommend([seed_row], k=k, mode=mode, profile_vectors=profile_vecs)
        facts = engine.track_card(seed_row)
        header = f"{facts['name']} — {facts['artist']}"
    else:
        live_hits = search_live_apis(query, limit=1) if search_type != "nlp" else None
        if live_hits:
            hit = live_hits[0]
            hit_text = f"{hit['name']} {hit['artist']} {query}".lower()
            
            is_indian_regional = any(kw in hit_text for kw in [
                "raat", "stree", "aaj", "dil", "pyar", "ishq", "tera", "meri", "hindi", "telugu",
                "tamil", "punjabi", "bollywood", "bhattacharya", "arijit", "pritam", "shreya",
                "sachin", "jigar", "badshah", "diljit", "harris", "jayaraj", "devi sri", "thaman", "anirudh"
            ])

            tg = set()
            if is_indian_regional:
                tg = {"filmi", "modern bollywood", "desi pop", "indian pop", "punjabi pop"}
            
            t = mood_model.transform(f"{hit['name']} {hit['artist']} {' '.join(hit.get('base_genres', []))}")
            recs = engine.recommend_by_vector(t["vector"], k=k, target_base_genres=tg if tg else None, strict_genre=is_indian_regional)
            
            artist_live = search_live_apis(f"{hit['artist']} hits", limit=5)
            if artist_live:
                existing_names = {(r.get("name") or "").lower().strip() for r in recs}
                blended = []
                for al in artist_live:
                    an = (al.get("name") or "").lower().strip()
                    if an != hit["name"].lower().strip() and an not in existing_names:
                        al["score"] = 0.92 - len(blended) * 0.03
                        blended.append(al)
                        existing_names.add(an)
                recs = (blended + recs)[:k]

            facts = hit
            header = f"{hit['name']} — {hit['artist']}"
        else:
            t = mood_model.transform(query)
            used_fallback = False
            fallback = None

            if t["coverage"]:
                tg = {BASE_GENRE_MAP.get(tok, tok) for tok in t["matched_tokens"]}
                q_low = query.lower()
                for reg_kw, mapped_genres in [
                    ("telugu", ["filmi", "desi pop", "indian pop"]),
                    ("hindi", ["filmi", "modern bollywood", "desi pop", "indian pop"]),
                    ("bollywood", ["filmi", "modern bollywood", "desi pop"]),
                    ("punjabi", ["punjabi pop", "desi pop", "filmi"]),
                    ("tamil", ["filmi", "indian pop", "desi pop"]),
                    ("desi", ["desi pop", "filmi", "indian pop"]),
                    ("kpop", ["k-pop", "pop"]), ("k-pop", ["k-pop", "pop"]),
                    ("anime", ["anime", "j-pop"]), ("japanese", ["j-pop", "anime"]),
                    ("latin", ["latin", "reggaeton"]), ("spanish", ["latin", "reggaeton"]),
                    ("afro", ["afrobeats", "afropop"]), ("afrobeats", ["afrobeats", "afropop"]),
                    ("phonk", ["phonk", "hip hop", "trap", "edm"]),
                    ("lofi", ["lo-fi", "chillhop", "ambient"]), ("lo-fi", ["lo-fi", "chillhop", "ambient"]),
                ]:
                    if reg_kw in q_low:
                        for g in mapped_genres:
                            tg.add(g)

                recs = engine.recommend_by_vector(t["vector"], k=k, target_base_genres=tg, target_audio=t["audio"])
                a = t["audio"]
            else:
                fallback = dj.mood_fallback(query, engine.genre_vocab)
                if fallback:
                    used_fallback = True
                    a = np.array([
                        fallback.get("energy", 0.5),
                        fallback.get("valence", 0.5),
                        fallback.get("danceability", 0.5),
                        fallback.get("acousticness", 0.5),
                        0.0, 0.0, 0.0,
                        (fallback.get("tempo_bpm", 120) - 50) / 150.0,
                    ], dtype=np.float32)
                    tg = {BASE_GENRE_MAP.get(g, g) for g in fallback.get("genres", [])}
                    expanded_q = " ".join(fallback.get("genres", []))
                    t2 = mood_model.transform(expanded_q)
                    recs = engine.recommend_by_vector(t2["vector"], k=k, target_base_genres=tg, target_audio=a)
                else:
                    tg = {BASE_GENRE_MAP.get(tok, tok) for tok in t["matched_tokens"]}
                    recs = engine.recommend_by_vector(t["vector"], k=k, target_base_genres=tg, target_audio=t["audio"])
                    a = t["audio"]

            gc = Counter()
            for r in recs:
                if r.get("row", -1) >= 0:
                    gc.update(engine._base_genres(engine._genre_ids(r["row"])))
            dominant = [g for g, _ in gc.most_common(3)]

            if used_fallback and fallback:
                tg_display = {BASE_GENRE_MAP.get(g, g) for g in fallback.get("genres", [])}
            else:
                tg_display = {BASE_GENRE_MAP.get(tok, tok) for tok in t["matched_tokens"]}

            facts = {
                "name": query,
                "artist": "your vibe",
                "genres": dominant or sorted(tg_display) or ["mixed"],
                "energy": round(float(a[0]), 2),
                "valence": round(float(a[1]), 2),
                "danceability": round(float(a[2]), 2),
                "tempo_bpm": int(a[7] * 150 + 50),
            }
            header = f"AI DJ Mix: '{query}'"

    rec_cards = [engine.track_card(r["row"]) for r in recs if r.get("row", -1) >= 0]
    intel = dj.get_intel(facts, rec_cards)
    blurb = f"{intel.get('headline', '')}. {intel.get('sound_profile', '')}"
    ground = checker.check(blurb, facts, rec_cards)
    return header, recs, blurb, ground, facts, intel


def _raw_run_pipeline(query: str, engine: RecommendationEngine, mood_model: MoodToVector,
                     dj: RAGDJ, checker: GroundednessChecker, profile: dict, store: ProfileStore,
                     mode: str = "similar", k: int = 10, search_type: str = "auto",
                     seed_track: Optional[dict] = None):
    return run_pipeline(query, engine, mood_model, dj, checker, profile, store, mode=mode, k=k, search_type=search_type, seed_track=seed_track)


if HAS_SPACES and GPU_USAGE:
    @spaces.GPU
    def _dummy_gpu_function():
        pass

_gpu_run_pipeline = _raw_run_pipeline


def safe_run_pipeline(query: str, engine: RecommendationEngine, mood_model: MoodToVector,
                       dj: RAGDJ, checker: GroundednessChecker, profile: dict, store: ProfileStore,
                       mode: str = "similar", k: int = 10, search_type: str = "auto",
                       seed_track: Optional[dict] = None):
    try:
        return _gpu_run_pipeline(query, engine, mood_model, dj, checker, profile, store, mode=mode, k=k, search_type=search_type, seed_track=seed_track)
    except Exception as e:
        print(f"[ZeroGPU] Execution fallback to CPU: {e}")
        return _raw_run_pipeline(query, engine, mood_model, dj, checker, profile, store, mode=mode, k=k, search_type=search_type, seed_track=seed_track)
