#!/usr/bin/env python3
"""Persistent feedback and taste profiles, derived from the user's active likes."""

import json
import os
import tempfile
import threading
import time
from typing import List, Optional
from .metadata import artist_parts, clean_title, public_track, recording_match, recording_version

import numpy as np

try:
    from .config import SHORT_TERM_DECAY
    from .engine import RecommendationEngine, _norm_title
except ImportError:
    from config import SHORT_TERM_DECAY
    from engine import RecommendationEngine, _norm_title


def track_key(name, artist):
    version=recording_version(name)
    title=_norm_title(name or '') + ('|version:'+version if version else '')
    return f"{title}||{str(artist or '').strip().casefold()}"


class ProfileStore:
    def __init__(self, engine: RecommendationEngine, profiles_dir: str = "profiles"):
        self.engine = engine
        self.local_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", profiles_dir))
        self.dir = (os.path.join("/data", "profiles") if profiles_dir == "profiles"
                    and os.path.isdir("/data") and os.access("/data", os.W_OK) else self.local_dir)
        os.makedirs(self.dir, exist_ok=True)
        self.dim = engine.embed_dim
        self._lock = threading.RLock()

    def _path(self, user):
        safe = "".join(c for c in user if c.isalnum() or c in "-_") or "default"
        return os.path.join(self.dir, f"{safe}.json")

    def _events_path(self, user):
        return self._path(user).removesuffix(".json") + ".events.jsonl"

    def load(self, user):
        path = self._path(user)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                profile = json.load(f)
        else:
            profile = {"user": user, "created": time.time(), "n_events": 0}
        profile.setdefault("preferences", {"artists": [], "languages": []})
        if profile.get("schema_version") not in (2, 3):
            feedback = {}
            events_path = self._events_path(user)
            if os.path.exists(events_path):
                with open(events_path, encoding="utf-8") as f:
                    for line in f:
                        try:
                            event = json.loads(line)
                        except (ValueError, TypeError):
                            continue
                        key = track_key(event.get("name"), event.get("artist"))
                        if event.get("signal") in ("like", "dislike", "skip"):
                            feedback[key] = event
                        else:
                            feedback.pop(key, None)
            # Retain legacy metadata when an old installation has no event log.
            profile["feedback"] = feedback
            if feedback or profile.get("n_events", 0) == 0 or os.path.exists(events_path):
                self._rebuild(profile)
            profile["schema_version"] = 3
        if profile.get("schema_version") != 3:
            # Repair artist tags copied into external songs by earlier versions.
            for event in profile.get("feedback", {}).values():
                if event.get("row", -1) < 0:
                    event["genres"] = list(event.get("recording_genres") or event.get("base_genres") or [])
                    event.pop("language", None)
                    event.pop("language_source", None)
                    event["vector_source"] = "artist_anchor" if event.get("vector") else None
            self._rebuild(profile)
            profile["schema_version"] = 3
        profile.setdefault("listening", {})
        profile['feedback']={track_key(event.get('name'),event.get('artist')):event for event in profile.get('feedback',{}).values()}
        return profile

    def save(self, user, profile):
        with self._lock:
            fd, temporary = tempfile.mkstemp(dir=self.dir, suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(profile, f, ensure_ascii=False)
                os.replace(temporary, self._path(user))
            finally:
                if os.path.exists(temporary):
                    os.remove(temporary)

    def delete_user(self, user):
        with self._lock:
            for path in (self._path(user), self._events_path(user)):
                if os.path.exists(path):
                    os.remove(path)

    def vectors(self, profile):
        return {"long_term": profile.get("long_term"), "short_term": profile.get("short_term")}

    def history(self, profile):
        return sorted(profile.get("feedback", {}).values(), key=lambda ev: ev.get("ts", 0), reverse=True)

    def _valid_vector(self, value):
        if value is None:
            return None
        vec = np.asarray(value, np.float32)
        if vec.shape != (self.dim,) or not np.all(np.isfinite(vec)):
            return None
        norm = np.linalg.norm(vec)
        return vec / norm if norm > 0 else None

    def _resolve_track(self, row, context, mood_model=None):
        try:
            row = int(row) if row is not None else -1
        except (ValueError, TypeError):
            row = -1
        name, artist = context.get("name"), context.get("artist")
        if 0 <= row < len(self.engine.embeddings):
            ds_name, ds_artist = str(self.engine._names[row]), str(self.engine._artists[row])
            if ((not name and not artist) or recording_match(
                    {"name": name or ds_name, "artist": artist or ds_artist}, {"name": ds_name, "artist": ds_artist})):
                card = dict(self.engine.track_card(row))
                card.update(track_id=str(self.engine.meta.iat[row, 0]), row=row)
                return {**context, **card, "vector_source": "catalog_recording"}
        if not name or not artist:
            raise ValueError("Track name and artist are required for tracks outside the catalog")
        genres = list(dict.fromkeys(context.get("recording_genres") or context.get("base_genres") or []))
        entry = {**context, "row": -1, "name": name.strip(), "artist": artist.strip(),
                 "track_id": f"ext_{name.strip()}_{artist.strip()}".lower().replace(" ", "_"),
                 "genres": genres}
        # An artist's catalog is a stronger signal than projecting an unknown song title.
        artist_tracks = self.engine.artist_top_tracks(artist, limit=8)
        artist_rows = [t["row"] for t in artist_tracks
                       if t.get("artist", "").strip().casefold() == artist.strip().casefold()]
        if artist_rows:
            vec = self._valid_vector(np.asarray(self.engine.embeddings[artist_rows]).mean(axis=0))
            entry["vector_source"] = "artist_anchor"
        elif mood_model is not None:
            projected = mood_model.transform(" ".join([name, artist] + genres))
            vec = self._valid_vector(projected.get("vector")) if projected.get("coverage") else None
            entry["vector_source"] = "text_projection" if vec is not None else None
        else:
            vec = None
        if vec is not None:
            entry["vector"] = vec.tolist()
        return entry

    def _rebuild(self, profile):
        likes, skips, vectors = [], [], []
        genre_counts, artist_counts = {}, {}
        for event in reversed(self.history(profile)):
            if event.get("signal") != "like":
                skips.append(event.get("track_id", track_key(event.get("name"), event.get("artist"))))
                continue
            likes.append(event.get("track_id", track_key(event.get("name"), event.get("artist"))))
            row = event.get("row", -1)
            if isinstance(row, int) and 0 <= row < len(self.engine.embeddings):
                vec = self._valid_vector(self.engine.embeddings[row])
                genres = self.engine.genre_labels(row)
            else:
                vec = self._valid_vector(event.get("vector"))
                genres = event.get("genres") or event.get("base_genres") or []
            if vec is not None:
                vectors.append(vec if event.get("vector_source") != "artist_anchor" else vec * 0.35)
            for genre in set(genres):
                genre_counts[genre] = genre_counts.get(genre, 0) + 1
            artist = event.get("artist")
            if artist and artist.casefold() not in ("unknown", "unknown artist"):
                artist_counts[artist] = artist_counts.get(artist, 0) + 1
        long_term = self._valid_vector(np.mean(vectors, axis=0)) if vectors else None
        short_term = None
        for vec in vectors[-20:]:
            short_term = vec if short_term is None else self._valid_vector(
                SHORT_TERM_DECAY * short_term + (1 - SHORT_TERM_DECAY) * vec)
        profile.update(likes=likes, skips=skips, genre_counts=genre_counts, artist_counts=artist_counts,
                       long_term=long_term.tolist() if long_term is not None else None,
                       short_term=short_term.tolist() if short_term is not None else None)

    def record(self, user, profile, row: Optional[int], signal: str,
               context: Optional[dict] = None, mood_model=None):
        if signal not in ("like", "dislike", "skip", "none", "remove_like", "remove_dislike"):
            raise ValueError("Unknown feedback signal")
        event = self._resolve_track(row, context or {}, mood_model)
        event.update(user=user, signal=signal, ts=time.time())
        key = track_key(event["name"], event["artist"])
        feedback = profile.setdefault("feedback", {})
        if signal in ("like", "dislike", "skip"):
            feedback[key] = event
        else:
            feedback.pop(key, None)
        profile["n_events"] = profile.get("n_events", 0) + 1
        profile["schema_version"] = 3
        self._rebuild(profile)
        with open(self._events_path(user), "a", encoding="utf-8") as f:
            json.dump(event, f, ensure_ascii=False)
            f.write("\n")

    def feedback(self, user, row, signal, context=None, mood_model=None):
        # Keep load/modify/save together, including simultaneous requests from multiple tabs.
        with self._lock:
            profile = self.load(user)
            self.record(user, profile, row, signal, context, mood_model)
            self.save(user, profile)
            return profile

    def enrich_feedback(self, user, resolved):
        fields = {"recording_genres", "metadata_source", "language", "language_source", "album", "album_id", "album_source"}
        with self._lock:
            profile = self.load(user)
            changed = False
            for seed in resolved:
                key = track_key(seed.get("name"), seed.get("artist"))
                event = profile.get("feedback", {}).get(key)
                if event is None:
                    continue
                updates = {field: seed[field] for field in fields if seed.get(field)}
                if updates and any(event.get(k) != v for k, v in updates.items()):
                    event.update(updates)
                    event["genres"] = list(event.get("recording_genres") or event.get("base_genres") or [])
                    changed = True
            if changed:
                self._rebuild(profile)
                self.save(user, profile)

    def record_listen(self, user, row, context, seconds, duration, event_id):
        if seconds < 5:
            return self.load(user)
        with self._lock:
            profile = self.load(user)
            events = profile.setdefault("listening", {})
            if event_id in events and seconds <= events[event_id].get("seconds", 0):
                return profile
            event = self._resolve_track(row, context)
            event.update(ts=time.time(), seconds=min(seconds, duration or seconds), duration=duration,
                         event_id=event_id, completed=bool(duration and seconds / duration >= .7))
            events[event_id] = event
            profile["listening"] = dict(sorted(events.items(), key=lambda pair: pair[1]["ts"])[-200:])
            self.save(user, profile)
            return profile

    def taste_seeds(self, profile):
        selected = {track_key(event.get("name"), event.get("artist")): dict(event)
                    for event in self.history(profile) if event.get("signal") == "like"}
        blocked = {track_key(event.get("name"), event.get("artist")) for event in self.history(profile)
                   if event.get("signal") in ("skip", "dislike")}
        for event in sorted(profile.get("listening", {}).values(), key=lambda event: -event.get("ts", 0)):
            key = track_key(event.get("name"), event.get("artist"))
            if not event.get("completed") or key in blocked:
                continue
            if key in selected:
                selected[key]["ts"] = max(selected[key].get("ts", 0), event.get("ts", 0))
            else:
                selected[key] = {**event, "implicit": True}
        return sorted(selected.values(), key=lambda event: -event.get("ts", 0))[:30]

    def set_preferences(self, user, artists, languages):
        def clean(values):
            return list(dict.fromkeys(v.strip() for v in values if v.strip()))[:10]
        with self._lock:
            profile = self.load(user)
            profile["preferences"] = {"artists": clean(artists), "languages": clean(languages)}
            self.save(user, profile)
            return profile["preferences"]

    def top_genres(self, profile, n=3):
        return sorted(profile.get("genre_counts", {}).items(), key=lambda x: -x[1])[:n]

    def top_artists(self, profile, n=3):
        return sorted(profile.get("artist_counts", {}).items(), key=lambda x: -x[1])[:n]

    def list_profiles(self) -> List[str]:
        return sorted(f[:-5] for f in os.listdir(self.dir) if f.endswith(".json"))
