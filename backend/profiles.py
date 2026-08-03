#!/usr/bin/env python3
"""
SoundVector User Profile Store & Taste Vector Management
"""

import json
import os
import time
from typing import List, Optional

import numpy as np

try:
    from .config import LONG_TERM_DECAY, SHORT_TERM_DECAY
    from .engine import RecommendationEngine
except ImportError:
    from config import LONG_TERM_DECAY, SHORT_TERM_DECAY
    from engine import RecommendationEngine



class ProfileStore:
    def __init__(self, engine: RecommendationEngine, profiles_dir: str = "profiles"):
        self.engine = engine
        self.fs = None

        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.local_dir = os.path.normpath(os.path.join(script_dir, "..", profiles_dir))

        _data_mount = "/data"
        if os.path.isdir(_data_mount) and os.access(_data_mount, os.W_OK):
            self.dir = os.path.join(_data_mount, "profiles")
            os.makedirs(self.dir, exist_ok=True)
            print(f"✅ Using HF Bucket persistent storage at {self.dir}")
        else:
            os.makedirs(self.local_dir, exist_ok=True)
            self.dir = self.local_dir
            print(f"ℹ️ Using local profile storage at {self.dir}")

        self.dim = engine.embed_dim

    def _path(self, user: str) -> str:
        safe = "".join(c for c in user if c.isalnum() or c in "-_") or "default"
        return os.path.join(self.dir, f"{safe}.json")

    def _events_path(self, user: str) -> str:
        safe = "".join(c for c in user if c.isalnum() or c in "-_") or "default"
        return os.path.join(self.dir, f"{safe}.events.jsonl")

    def load(self, user: str) -> dict:
        path = self._path(user)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                p = json.load(f)
            p["short_term"] = None
            return p
        return {
            "user": user, "created": time.time(),
            "long_term": None, "short_term": None,
            "genre_counts": {}, "artist_counts": {},
            "likes": [], "skips": [], "n_events": 0,
        }

    def save(self, user: str, profile: dict):
        to_save = dict(profile)
        to_save["short_term"] = None
        with open(self._path(user), "w", encoding="utf-8") as f:
            json.dump(to_save, f)

    def delete_user(self, user: str):
        path = self._path(user)
        events_path = self._events_path(user)
        if os.path.exists(path):
            os.remove(path)
        if os.path.exists(events_path):
            os.remove(events_path)

    def vectors(self, profile: dict) -> dict:
        return {"long_term": profile.get("long_term"), "short_term": profile.get("short_term")}

    def _blend(self, current, new_vec, decay):
        if current is None:
            return new_vec.tolist()
        cur = np.asarray(current, np.float32)
        blended = decay * cur + (1 - decay) * new_vec
        n = np.linalg.norm(blended)
        return (blended / n).tolist() if n > 0 else blended.tolist()

    def record(self, user: str, profile: dict, row: Optional[int], signal: str, context: Optional[dict] = None, mood_model = None):
        context = context or {}
        r_val = int(row) if (row is not None and str(row).isdigit()) else -1

        name = context.get("name")
        artist = context.get("artist")
        art = context.get("deezer_album_art") or ""
        preview = context.get("deezer_preview_url") or ""
        genres = context.get("base_genres") or []

        vec = None
        track_id = ""

        # Validate in-index catalog row
        if 0 <= r_val < len(self.engine.embeddings):
            ds_name = str(self.engine._names[r_val])
            ds_artist = str(self.engine._artists[r_val])
            # Check for name mismatch (e.g. out-of-index track sent row 0 by default)
            if not name or name.lower().strip() in ds_name.lower() or ds_name.lower() in name.lower():
                vec = np.asarray(self.engine.embeddings[r_val], np.float32)
                track_id = str(self.engine.meta.iat[r_val, 0])
                name = ds_name
                artist = ds_artist
                genres = [self.engine.genre_vocab[gid] for gid in self.engine._genre_ids(r_val)]
            else:
                r_val = -1

        if r_val < 0 or vec is None:
            safe_name = (name or f"Track_{time.time()}").strip()
            safe_artist = (artist or "Unknown").strip()
            track_id = f"ext_{safe_name}_{safe_artist}".lower().replace(" ", "_")

            # Project out-of-index track to taste vector using mood model or text projection
            if mood_model and hasattr(mood_model, "transform"):
                try:
                    q_str = f"{safe_artist} {safe_name} {' '.join(genres)}"
                    vec = mood_model.transform(q_str)["vector"]
                except Exception:
                    vec = None

        if signal == "like":
            if vec is not None:
                profile["long_term"] = self._blend(profile.get("long_term"), vec, LONG_TERM_DECAY)
                profile["short_term"] = self._blend(profile.get("short_term"), vec, SHORT_TERM_DECAY)
            
            if track_id not in profile.get("likes", []):
                profile["likes"] = (profile.get("likes", []) + [track_id])[-500:]
            for g in genres:
                profile["genre_counts"][g] = profile["genre_counts"].get(g, 0) + 1
            if artist and artist.lower() not in ("unknown", "unknown artist"):
                profile["artist_counts"][artist] = profile["artist_counts"].get(artist, 0) + 1

        elif signal in ("skip", "dislike"):
            if vec is not None and profile.get("short_term") is not None:
                cur = np.asarray(profile["short_term"], np.float32)
                pushed = cur - 0.15 * vec
                n = np.linalg.norm(pushed)
                profile["short_term"] = (pushed / n).tolist() if n > 0 else cur.tolist()
            if track_id not in profile.get("skips", []):
                profile["skips"] = (profile.get("skips", []) + [track_id])[-500:]

        elif signal in ("none", "remove_like", "remove_dislike"):
            if track_id in profile.get("likes", []):
                profile["likes"].remove(track_id)
            if track_id in profile.get("skips", []):
                profile["skips"].remove(track_id)
            for g in genres:
                if g in profile.get("genre_counts", {}):
                    profile["genre_counts"][g] = max(0, profile["genre_counts"][g] - 1)
                    if profile["genre_counts"][g] == 0:
                        del profile["genre_counts"][g]
            if artist and artist in profile.get("artist_counts", {}):
                profile["artist_counts"][artist] = max(0, profile["artist_counts"][artist] - 1)
                if profile["artist_counts"][artist] == 0:
                    del profile["artist_counts"][artist]

        profile["n_events"] = profile.get("n_events", 0) + 1
        event = {
            "ts": time.time(),
            "user": user,
            "track_id": track_id,
            "signal": signal,
            "name": name or f"Track #{r_val}",
            "artist": artist or "Unknown Artist",
            "row": int(r_val),
            "deezer_album_art": art,
            "deezer_preview_url": preview,
            "base_genres": genres
        }
        if context:
            event["context"] = context

        event_str = json.dumps(event) + "\n"
        with open(self._events_path(user), "a", encoding="utf-8") as f:
            f.write(event_str)


    def top_genres(self, profile: dict, n: int = 3):
        return sorted(profile.get("genre_counts", {}).items(), key=lambda x: -x[1])[:n]

    def top_artists(self, profile: dict, n: int = 3):
        return sorted(profile.get("artist_counts", {}).items(), key=lambda x: -x[1])[:n]

    def list_profiles(self) -> List[str]:
        if not os.path.exists(self.dir):
            return []
        users = []
        for f in os.listdir(self.dir):
            if f.endswith(".json") and not f.endswith(".events.jsonl"):
                users.append(f[:-5])
        return sorted(list(set(users)))
