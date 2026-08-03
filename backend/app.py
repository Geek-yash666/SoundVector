#!/usr/bin/env python3
"""
SoundVector — All-in-One AI Music Recommender & RAG DJ App

A completely self-contained application combining:
  1. Two-Stage Recommendation Engine (ANN retrieval via HNSW + MMR reranking)
  2. MoodToVector NLP Model (TF-IDF + Ridge projection of NL text to sound vectors)
  3. Gemini RAG DJ & Groundedness Checker (fact-verified AI DJ commentary)
  4. User Profile Store (long-term/short-term taste vectors & feedback logging)
  5. Interactive Terminal UI & Web UI Dashboard (run with --web for browser interface)

Usage:
    python3 src/app.py                        # Terminal interactive mode
    python3 src/app.py --web                  # Launch Web UI Dashboard at http://localhost:8000
    python3 src/app.py --user Yash             # Terminal interactive mode with profile 'Yash'
    python3 src/app.py "sad rainy night"       # Terminal one-shot natural language query
"""


import argparse
import json
import math
import os
import pickle
import re
import sys
import threading
import time
import urllib.parse
import urllib.request
from collections import Counter
from typing import Dict, List, Optional, Tuple, Set
from urllib.parse import parse_qs, urlparse

import numpy as np
import pandas as pd
from rapidfuzz import fuzz, process

import gradio as gr
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel

GPU_USAGE = int(os.environ.get("GPU_USAGE", "1"))
if GPU_USAGE:
    try:
        import spaces
        HAS_SPACES = True
    except ImportError:
        HAS_SPACES = False
else:
    HAS_SPACES = False

_COMPONENTS = None

app = FastAPI(title="SoundVector API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RecommendRequest(BaseModel):
    query: str = "Starboy"
    mode: str = "similar"
    user: str = "default"
    search_type: str = "auto"
    seed_track: Optional[dict] = None


class AIIntelRequest(BaseModel):
    facts: dict = {}
    recs: list = []


class PlaylistGenRequest(BaseModel):
    prompt: str
    user: str = "default"
    count: int = 15


class FeedbackRequest(BaseModel):
    user: str = "default"
    row: int = 0
    signal: str = "like"
    mode: str = "similar"


# -----------------------------------------------------------------------------
# Terminal Styling
# -----------------------------------------------------------------------------
class C:
    B = "\033[1m"
    D = "\033[2m"
    R = "\033[0m"
    CY = "\033[36m"
    GR = "\033[32m"
    YE = "\033[33m"
    RE = "\033[31m"
    WH = "\033[37m"


def s(t: str, *st) -> str:
    return f"{''.join(st)}{t}{C.R}"


def ask(prompt: str) -> str:
    try:
        return input(f"{s('❯', C.CY)} {s(prompt, C.B)}").strip()
    except (EOFError, KeyboardInterrupt):
        print(f"\n{s('Goodbye! 🎵', C.D)}")
        sys.exit(0)


def resolve_artifacts_dir(path: str) -> str:
    resolved = path
    if not (os.path.isabs(path) or os.path.exists(path)):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        candidate = os.path.normpath(os.path.join(script_dir, "..", path))
        resolved = candidate if os.path.exists(candidate) else path

    index_file = os.path.join(resolved, "index.bin")
    if not os.path.exists(index_file):
        hf_dataset = os.environ.get("HF_ARTIFACTS_DATASET")
        if hf_dataset:
            print(s(f"  📥 Artifacts not found locally. Downloading from HF Dataset '{hf_dataset}'...", C.CY))
            try:
                from huggingface_hub import snapshot_download
                os.makedirs(resolved, exist_ok=True)
                snapshot_download(repo_id=hf_dataset, repo_type="dataset", local_dir=resolved)
                print(s("  ✓ Download complete!", C.GR))
            except Exception as exc:
                print(s(f"  ⚠️ Could not download artifacts from HF Dataset: {exc}", C.YE))
    return resolved


# -----------------------------------------------------------------------------
# 1. Recommendation Engine (Two-Stage ANN Retrieval + MMR Ranking)
# -----------------------------------------------------------------------------
SCORING_PRESETS = {
    "similar":  {"embed": 0.30, "audio": 0.25, "genre": 0.25, "artist": 0.05, "popularity": 0.15, "era": 0.00},
    "vibe":     {"embed": 0.45, "audio": 0.35, "genre": 0.20, "artist": 0.00, "popularity": 0.00, "era": 0.00},
    "popular":  {"embed": 0.25, "audio": 0.10, "genre": 0.20, "artist": 0.00, "popularity": 0.45, "era": 0.00},
    "discover": {"embed": 0.25, "audio": 0.05, "genre": 0.30, "artist": 0.00, "popularity": 0.15, "era": 0.25},
}

N_AUDIO_DIMS = 8

BASE_GENRE_MAP = {
    'pop': 'pop', 'dance pop': 'pop', 'canadian pop': 'pop', 'viral pop': 'pop',
    'electropop': 'electro', 'art pop': 'pop', 'indie pop': 'pop', 'synth-pop': 'electro',
    'k-pop': 'pop', 'europop': 'pop', 'pop rock': 'pop rock', 'pop rap': 'pop',
    'chamber pop': 'pop', 'dream pop': 'pop', 'power pop': 'pop', 'neo mellow': 'pop',
    'rock': 'rock', 'alternative rock': 'rock', 'indie rock': 'rock', 'classic rock': 'rock',
    'garage rock': 'rock', 'punk rock': 'rock', 'modern rock': 'rock', 'permanent wave': 'rock',
    'new wave': 'rock', 'hip hop': 'hip hop', 'rap': 'hip hop', 'trap': 'hip hop',
    'conscious hip hop': 'hip hop', 'r&b': 'r&b', 'contemporary r&b': 'r&b',
    'urban contemporary': 'r&b', 'edm': 'edm', 'house': 'edm', 'tech house': 'edm',
    'deep house': 'edm', 'tropical house': 'edm', 'electronic': 'edm', 'electro house': 'edm',
    'country': 'country', 'classic country': 'country', 'country rock': 'country',
    'jazz': 'jazz', 'soul': 'soul', 'funk': 'soul', 'metal': 'metal', 'heavy metal': 'metal',
    'latin': 'latin', 'reggaeton': 'latin', 'urbano latino': 'latin', 'musica mexicana': 'latin',
    'norteno': 'latin', 'ranchera': 'latin', 'banda': 'latin', 'trap latino': 'latin',
    'latin pop': 'latin', 'classical': 'classical', 'lo-fi': 'lo-fi', 'lofi': 'lo-fi',
    'filmi': 'filmi', 'bollywood': 'filmi', 'modern bollywood': 'filmi', 'desi pop': 'filmi',
    'punjabi pop': 'filmi', 'indian pop': 'filmi', 'indian classical': 'indian classical',
    'afrobeats': 'afrobeats', 'afropop': 'afrobeats', 'j-pop': 'j-pop', 'anime': 'anime',
}


def _norm_title(t: str) -> str:
    t = str(t).lower().strip()
    t = re.sub(r'\s*[\(\[].*?[\)\]]', '', t)
    t = re.sub(r'\s*-\s*(remix|remaster|radio edit|live|deluxe|bonus|version).*', '', t, flags=re.I)
    return t.strip()


class RecommendationEngine:
    def __init__(self, artifacts_dir: str = "artifacts"):
        import hnswlib

        self.artifacts_dir = artifacts_dir
        self.embeddings = np.load(os.path.join(artifacts_dir, "embeddings.npy"), mmap_mode="r")
        self.audio = np.load(os.path.join(artifacts_dir, "features_dense.npy"), mmap_mode="r")
        self.meta = pd.read_parquet(os.path.join(artifacts_dir, "meta.parquet"))
        with open(os.path.join(artifacts_dir, "prep_meta.json")) as f:
            self.prep_meta = json.load(f)
        self.genre_vocab = self.prep_meta["genre_vocab"]
        self.embed_dim = self.embeddings.shape[1]

        self._genre_indices = np.load(os.path.join(artifacts_dir, "genre_indices.npy"))
        self._genre_offsets = np.load(os.path.join(artifacts_dir, "genre_offsets.npy"))

        with open(os.path.join(artifacts_dir, "index_meta.json")) as f:
            idx_meta = json.load(f)
        self.index = hnswlib.Index(space=idx_meta["space"], dim=idx_meta["dim"])
        self.index.load_index(os.path.join(artifacts_dir, "index.bin"), max_elements=idx_meta["n"])
        self.index.set_ef(max(idx_meta.get("ef_search", 100), 256))

        self.artist_gid = self.meta["artist_gid"].to_numpy()
        self.years = self.meta["release_year"].to_numpy().astype(np.float32)
        self.pop = (self.meta["popularity"].to_numpy().astype(np.float32) / 100.0).clip(0, 1)
        self._names = self.meta["name"].to_numpy()
        self._artists = self.meta["artist"].to_numpy()
        self._dfeat = {name: i for i, name in enumerate(self.prep_meta["dense_features"])}

        self._build_catalog()

    def _genre_ids(self, row: int) -> frozenset:
        s, e = self._genre_offsets[row], self._genre_offsets[row + 1]
        return frozenset(self._genre_indices[s:e].tolist())

    def _base_genres(self, genre_ids) -> set:
        out = set()
        for gid in genre_ids:
            label = self.genre_vocab[gid]
            out.add(BASE_GENRE_MAP.get(label, label))
        return out

    def genre_labels(self, row: int) -> List[str]:
        return [self.genre_vocab[g] for g in self._genre_ids(row)]

    def track_card(self, row: int) -> dict:
        d = self.audio
        f = self._dfeat
        tempo = float(d[row, f["tempo_norm"]]) * 150.0 + 50.0
        return {
            "row": row,
            "name": str(self._names[row]),
            "artist": str(self._artists[row]),
            "album_gid": int(self.meta.loc[row, "album_gid"]),
            "genres": self.genre_labels(row),
            "base_genres": sorted(self._base_genres(self._genre_ids(row))),
            "year": int(self.years[row]),
            "popularity": float(self.pop[row]),
            "popularity_pct": int(round(float(self.pop[row]) * 100)),
            "energy": round(float(d[row, f["energy"]]), 2),
            "valence": round(float(d[row, f["valence"]]), 2),
            "danceability": round(float(d[row, f["danceability"]]), 2),
            "acousticness": round(float(d[row, f["acousticness"]]), 2),
            "tempo_bpm": int(round(tempo)),
        }

    def _build_catalog(self):
        m = self.meta
        norm = np.array([_norm_title(n) for n in self._names])
        keys = pd.Series(norm).str.cat(pd.Series(self.artist_gid).astype(str), sep=" || ").to_numpy()
        order = np.argsort(-self.pop, kind="stable")
        self.canonical_row = np.empty(len(keys), dtype=np.int64)
        seen = {}
        for gi in order:
            k = keys[gi]
            best = seen.get(k)
            if best is None:
                seen[k] = best = gi
            self.canonical_row[gi] = best
        self._catalog_rows = np.array(sorted(seen.values()))
        cat = m.iloc[self._catalog_rows].copy()
        cat["_row"] = self._catalog_rows
        cat["_name_lower"] = cat["name"].str.lower()
        cat["_artist_lower"] = cat["artist"].str.lower()
        self.catalog = cat.reset_index(drop=True)

        named = cat[cat["artist"] != "Unknown Artist"]
        agg = named.groupby("artist")["popularity"].max()
        self._artist_names = agg.index.to_numpy()
        self._artist_maxpop = (agg.to_numpy().astype(np.float32) / 100.0).clip(0, 1)
        self._artist_names_lower = [a.lower() for a in self._artist_names]

    def match_artist(self, query: str, limit: int = 5) -> List[dict]:
        q = query.strip().lower()
        results = process.extract(q, self._artist_names_lower, scorer=fuzz.WRatio,
                                  limit=limit * 4, score_cutoff=80)
        scored = []
        for _, score, idx in results:
            scored.append({"artist": str(self._artist_names[idx]), "score": float(score),
                           "max_pop": float(self._artist_maxpop[idx]),
                           "_rank": score + 15.0 * self._artist_maxpop[idx]})
        scored.sort(key=lambda x: -x.pop("_rank"))
        return scored[:limit]

    def _row_to_track(self, row: int, extra: dict = None) -> dict:
        d = {
            "row": int(row),
            "track_id": str(self.meta.iat[row, 0]),
            "name": str(self._names[row]),
            "artist": str(self._artists[row]),
            "year": int(self.years[row]),
            "popularity": float(self.pop[row]),
        }
        if extra:
            d.update(extra)
        return d

    def search(self, query: str, limit: int = 15) -> List[dict]:
        q = query.strip().lower()
        cat = self.catalog
        out, seen = [], set()

        def take(mask, tier_score):
            hits = cat[mask & ~cat.index.isin(seen)].sort_values("popularity", ascending=False)
            for ci, r in hits.iterrows():
                if len(out) >= limit:
                    return
                seen.add(ci)
                out.append(self._row_to_track(int(r["_row"]), {"match": tier_score}))

        take(cat["_name_lower"] == q, 100.0)
        if len(out) < limit:
            take(cat["_name_lower"].str.startswith(q, na=False), 95.0)
        if len(out) < limit:
            mask = cat["_name_lower"].str.contains(q, regex=False, na=False)
            if not mask.any() and len(q.split()) > 1:
                combo = cat["_name_lower"] + " " + cat["_artist_lower"]
                mask = pd.Series(True, index=cat.index)
                for tok in set(re.findall(r"\w+", q)):
                    mask &= combo.str.contains(rf"\b{re.escape(tok)}\b", regex=True, na=False)
            take(mask, 90.0)

        if not out:
            combo = (cat["_name_lower"] + " " + cat["_artist_lower"]).tolist()
            scorer = fuzz.token_set_ratio if len(q.split()) > 1 else fuzz.WRatio
            results = process.extract(q, combo, scorer=scorer, limit=limit * 5, score_cutoff=55)
            fuzz_rows = set()
            for _, score, idx in sorted(results, key=lambda x: -x[1]):
                row = int(cat.iloc[idx]["_row"])
                if row in fuzz_rows:
                    continue
                fuzz_rows.add(row)
                out.append(self._row_to_track(row, {"match": float(score)}))
                if len(out) >= limit:
                    break
        return out

    def artist_top_tracks(self, artist_query: str, limit: int = 15) -> List[dict]:
        q = artist_query.strip().lower()
        cat = self.catalog
        mask = cat["_artist_lower"].str.contains(q, regex=False, na=False)
        hits = cat[mask].sort_values("popularity", ascending=False).head(limit)
        return [self._row_to_track(int(r["_row"])) for _, r in hits.iterrows()]

    def artist_all_tracks(self, artist_name: str, sort_by: str = "popularity", limit: int = 50) -> List[dict]:
        q = artist_name.strip().lower()
        cat = self.catalog
        mask = cat["_artist_lower"] == q
        if not mask.any():
            mask = cat["_artist_lower"].str.contains(q, regex=False, na=False)
        hits = cat[mask].copy()

        if sort_by == "newest":
            hits = hits.sort_values("release_year", ascending=False)
        elif sort_by == "oldest":
            hits = hits.sort_values("release_year", ascending=True)
        elif sort_by == "name":
            hits = hits.sort_values("name", ascending=True)
        else:
            hits = hits.sort_values("popularity", ascending=False)

        hits = hits.head(limit)
        return [self.track_card(int(r["_row"])) for _, r in hits.iterrows()]

    def artist_albums(self, artist_name: str) -> List[dict]:
        q = artist_name.strip().lower()
        cat = self.catalog
        mask = cat["_artist_lower"] == q
        if not mask.any():
            mask = cat["_artist_lower"].str.contains(q, regex=False, na=False)
        hits = cat[mask].copy()
        if hits.empty:
            return []

        groups = hits.groupby("album_gid")
        albums = []
        for gid, grp in groups:
            sorted_grp = grp.sort_values("popularity", ascending=False)
            lead = sorted_grp.iloc[0]
            year = int(lead["release_year"])
            track_cards = [self.track_card(int(r["_row"])) for _, r in sorted_grp.iterrows()]
            lead_name = str(lead["name"])
            album_title = f"{lead_name} (Single/Release)" if len(track_cards) == 1 else f"{lead_name} & Album Tracks"
            albums.append({
                "album_gid": int(gid),
                "title": album_title,
                "year": year,
                "track_count": len(track_cards),
                "tracks": track_cards
            })

        albums.sort(key=lambda a: (a["year"], a["track_count"]), reverse=True)
        return albums

    def query_vector(self, seed_rows: List[int], profile_vectors: Optional[dict] = None) -> np.ndarray:
        v = np.asarray(self.embeddings[seed_rows], dtype=np.float32).mean(axis=0)
        if profile_vectors:
            parts = [(0.6, v)]
            if profile_vectors.get("long_term") is not None:
                parts.append((0.25, np.asarray(profile_vectors["long_term"], np.float32)))
            if profile_vectors.get("short_term") is not None:
                parts.append((0.15, np.asarray(profile_vectors["short_term"], np.float32)))
            v = sum(w * p for w, p in parts)
        n = np.linalg.norm(v)
        return v / n if n > 0 else v

    def recommend(self, seed_rows: List[int], k: int = 15, mode: str = "similar",
                  candidates: int = 2000, max_per_artist: Optional[int] = None,
                  redundancy_cutoff: float = 0.97, exclude_rows: Optional[set] = None,
                  profile_vectors: Optional[dict] = None) -> List[dict]:
        weights = SCORING_PRESETS.get(mode, SCORING_PRESETS["similar"])
        if max_per_artist is None:
            max_per_artist = 1 if k <= 8 else 2
        qv = self.query_vector(seed_rows, profile_vectors)

        seed_genres = set()
        for r in seed_rows:
            seed_genres |= self._base_genres(self._genre_ids(r))
        seed_artists = set(self.artist_gid[seed_rows].tolist())
        seed_year = float(self.years[seed_rows].mean())
        seed_audio = np.asarray(self.audio[seed_rows, :N_AUDIO_DIMS], np.float32).mean(axis=0)
        seed_keys = {f"{_norm_title(self._names[r])}||{self.artist_gid[r]}" for r in seed_rows}
        excluded = {int(self.canonical_row[r]) for r in (exclude_rows or set())}

        def gather(pool: int):
            labels, distances = self.index.knn_query(qv, k=min(pool, len(self.meta)))
            raw = labels[0].astype(np.int64)
            raw_sim = 1.0 - distances[0]
            canon = self.canonical_row[raw]
            _, first = np.unique(canon, return_index=True)
            first.sort()
            cand, embed_sim = canon[first], raw_sim[first]

            genre_sim = np.zeros(len(cand))
            for i, r in enumerate(cand):
                cg = self._base_genres(self._genre_ids(int(r)))
                if seed_genres and cg:
                    genre_sim[i] = len(seed_genres & cg) / len(seed_genres | cg)
            audio_d = np.linalg.norm(
                np.asarray(self.audio[cand, :N_AUDIO_DIMS], np.float32) - seed_audio, axis=1)
            audio_sim = np.clip(1.0 - audio_d / np.sqrt(N_AUDIO_DIMS), 0, 1)
            artist_sim = np.isin(self.artist_gid[cand], list(seed_artists)).astype(np.float64)
            pop_score = self.pop[cand]
            era_sim = np.clip(1.0 - np.abs(self.years[cand] - seed_year) / 10.0, 0, 1)

            signals = {"embed": np.clip(embed_sim, 0, 1), "audio": audio_sim,
                       "genre": genre_sim, "artist": artist_sim,
                       "popularity": pop_score, "era": era_sim}
            base = sum(weights[s] * signals[s] for s in weights)

            picked, artist_counts, sel_vecs, keys_seen = [], {}, [], set(seed_keys)
            for pos in np.argsort(-base):
                if len(picked) >= k:
                    break
                r = int(cand[pos])
                if r in excluded:
                    continue
                key = f"{_norm_title(self._names[r])}||{self.artist_gid[r]}"
                if key in keys_seen:
                    continue
                keys_seen.add(key)
                ag = int(self.artist_gid[r])
                if ag >= 0 and artist_counts.get(ag, 0) >= max_per_artist:
                    continue
                vec = np.asarray(self.embeddings[r], np.float32)
                if sel_vecs and max(float(vec @ sv) for sv in sel_vecs) > redundancy_cutoff:
                    continue
                picked.append((float(base[pos]), r, {s: float(signals[s][pos]) for s in signals}))
                sel_vecs.append(vec)
                if ag >= 0:
                    artist_counts[ag] = artist_counts.get(ag, 0) + 1
            return picked

        pool = candidates
        picked = gather(pool)
        while len(picked) < k and pool < 32000:
            pool *= 4
            picked = gather(pool)

        out = []
        for score, r, sig in sorted(picked, key=lambda x: -x[0]):
            expl = (f"embed {sig['embed']:.2f} · audio {sig['audio']:.2f} · "
                    f"genre {sig['genre']:.2f} · artist {sig['artist']:.0f} · "
                    f"pop {sig['popularity']:.2f}")
            if weights.get("era", 0) > 0:
                expl += f" · era {sig['era']:.2f}"
            out.append(self._row_to_track(r, {"score": score, "signals": sig, "explanation": expl}))
        return out

    def recommend_by_vector(self, qv: np.ndarray, k: int = 15,
                            target_base_genres: Optional[set] = None,
                            target_audio: Optional[np.ndarray] = None,
                            candidates: int = 2000, max_per_artist: int = 1) -> List[dict]:
        qv = np.asarray(qv, np.float32)
        n = np.linalg.norm(qv)
        if n > 0:
            qv = qv / n
        w = {"embed": 0.55, "genre": 0.20, "audio": 0.10, "popularity": 0.15}
        tg = target_base_genres or set()

        def gather(pool):
            labels, dist = self.index.knn_query(qv, k=min(pool, len(self.meta)))
            raw = labels[0].astype(np.int64)
            raw_sim = 1.0 - dist[0]
            canon = self.canonical_row[raw]
            _, first = np.unique(canon, return_index=True)
            first.sort()
            cand, embed_sim = canon[first], raw_sim[first]

            genre_sim = np.zeros(len(cand))
            if tg:
                for i, r in enumerate(cand):
                    cg = self._base_genres(self._genre_ids(int(r)))
                    if cg:
                        genre_sim[i] = len(tg & cg) / len(tg | cg)
            if target_audio is not None:
                ad = np.linalg.norm(
                    np.asarray(self.audio[cand, :N_AUDIO_DIMS], np.float32) - target_audio, axis=1)
                audio_sim = np.clip(1.0 - ad / np.sqrt(N_AUDIO_DIMS), 0, 1)
            else:
                audio_sim = np.zeros(len(cand))
            pop = self.pop[cand]
            base = (w["embed"] * np.clip(embed_sim, 0, 1) + w["genre"] * genre_sim
                    + w["audio"] * audio_sim + w["popularity"] * pop)

            picked, artist_counts, keys_seen = [], {}, set()
            for pos in np.argsort(-base):
                if len(picked) >= k:
                    break
                r = int(cand[pos])
                key = f"{_norm_title(self._names[r])}||{self.artist_gid[r]}"
                if key in keys_seen:
                    continue
                keys_seen.add(key)
                ag = int(self.artist_gid[r])
                if ag >= 0 and artist_counts.get(ag, 0) >= max_per_artist:
                    continue
                sig = {"embed": float(embed_sim[pos]), "genre": float(genre_sim[pos]),
                       "audio": float(audio_sim[pos]), "popularity": float(pop[pos])}
                picked.append((float(base[pos]), r, sig))
                if ag >= 0:
                    artist_counts[ag] = artist_counts.get(ag, 0) + 1
            return picked

        pool = candidates
        picked = gather(pool)
        while len(picked) < k and pool < 32000:
            pool *= 4
            picked = gather(pool)

        out = []
        for score, r, sig in sorted(picked, key=lambda x: -x[0]):
            out.append(self._row_to_track(r, {"score": score, "signals": sig}))
        return out


# -----------------------------------------------------------------------------
# 2. MoodToVector NLP Model (TF-IDF + Ridge Regression)
# -----------------------------------------------------------------------------
SYNONYMS = {
    # Activity-based
    "gym": "workout edm dance energy hip hop trap phonk hardstyle",
    "workout": "workout edm dance energy hip hop phonk",
    "running": "workout edm run dance energy",
    "exercise": "workout edm dance energy",
    "jogging": "workout edm run dance",
    "lifting": "workout edm trap hip hop energy hardstyle",
    "yoga": "ambient chill acoustic meditation",
    "meditation": "ambient lo-fi chill acoustic",
    "study": "lo-fi study focus beats ambient chillhop",
    "studying": "lo-fi study focus ambient",
    "focus": "focus beats lo-fi study ambient instrumental",
    "homework": "lo-fi study focus beats",
    "coding": "lo-fi focus beats electronic ambient synthwave",
    "reading": "ambient acoustic lo-fi chill",
    "cooking": "jazz soul funk pop acoustic",
    "cleaning": "pop dance edm energy",
    "commute": "pop rock indie synthwave",
    "roadtrip": "rock pop indie classic rock driving",
    # Sleep/Relax
    "sleep": "sleep ambient lo-fi acoustic chill",
    "sleepy": "sleep ambient acoustic",
    "relax": "chill ambient acoustic lo-fi",
    "relaxing": "chill ambient acoustic",
    "chill": "chill lo-fi chillhop ambient bedroom pop",
    "unwind": "chill ambient acoustic lo-fi",
    "spa": "ambient acoustic chill",
    # Party/Social
    "party": "dance pop edm party trap house",
    "dancing": "dance pop edm house",
    "club": "edm house dance electronic techno",
    "pregame": "hip hop trap edm dance",
    "celebration": "pop dance edm happy",
    "wedding": "pop soul r&b dance romantic",
    # Emotions
    "sad": "sad lo-fi acoustic melancholy heartbreak moody",
    "cry": "sad acoustic melancholy heartbreak",
    "heartbreak": "sad acoustic r&b melancholy breakup",
    "breakup": "sad acoustic r&b pop melancholy",
    "lonely": "sad lo-fi acoustic ambient moody",
    "happy": "happy pop dance upbeat feel-good",
    "upbeat": "happy dance pop energy",
    "energetic": "edm dance workout energy hype",
    "hype": "edm trap hip hop energy dance rage",
    "rage": "trap phonk metal energy hype",
    "angry": "metal rock hard rock aggressive",
    "aggressive": "metal rock trap hard rock",
    "calm": "ambient acoustic chill lo-fi",
    "romantic": "r&b soul love pop romantic acoustic",
    "love": "r&b soul love pop romantic",
    "nostalgic": "classic rock pop soul retro 80s synthwave",
    "dark": "dark trap dark r&b electronic phonk",
    "moody": "dark r&b sad lo-fi ambient",
    "dreamy": "dream pop chillwave ambient shoegaze",
    "euphoric": "edm house dance trance synthwave",
    "melancholy": "sad lo-fi acoustic ambient moody",
    "confident": "hip hop rap pop energy hype",
    "motivation": "hip hop rap pop energy workout gym",
    "inspirational": "pop rock indie acoustic",
    # Weather/Time
    "rainy": "lo-fi acoustic ambient chill sad",
    "rain": "lo-fi ambient acoustic sad",
    "night": "dark lo-fi ambient r&b midnight",
    "midnight": "dark lo-fi r&b ambient",
    "morning": "acoustic happy folk pop sunrise",
    "sunrise": "ambient acoustic chill folk",
    "sunset": "chill lo-fi ambient synthwave",
    "summer": "tropical house dance pop reggaeton",
    "winter": "acoustic ambient lo-fi folk",
    "spring": "indie pop acoustic folk",
    "autumn": "folk acoustic indie lo-fi",
    # Regional / Language — maps to nearest available genres
    "telugu": "filmi desi pop indian pop tollywood telugu pop",
    "hindi": "modern bollywood filmi desi pop ghazal",
    "bollywood": "modern bollywood filmi desi pop",
    "tamil": "filmi indian pop desi pop kollywood",
    "kannada": "filmi indian pop desi pop",
    "malayalam": "filmi indian pop desi pop",
    "punjabi": "punjabi pop bhangra desi pop filmi",
    "desi": "desi pop filmi indian pop",
    "indian": "indian pop filmi desi pop",
    "korean": "k-pop pop dance",
    "kpop": "k-pop pop dance",
    "japanese": "j-pop anime pop",
    "anime": "anime j-pop pop",
    "latin": "latin reggaeton urbano latino",
    "spanish": "latin pop reggaeton urbano latino",
    "african": "afrobeats afropop amapiano",
    "afro": "afrobeats afropop amapiano",
    # Genre shortcuts & subgenres
    "phonk": "phonk trap edm workout energy rage",
    "synthwave": "synthwave electronic retro 80s dark",
    "lofi": "lo-fi chillhop ambient beats study",
    "lo-fi": "lo-fi chillhop ambient beats study",
    "hiphop": "hip hop rap trap",
    "rnb": "r&b contemporary r&b soul",
    "rock": "rock alternative rock indie rock",
    "metal": "metal heavy metal hard rock",
    "jazz": "jazz vocal jazz soul",
    "classical": "classical baroque",
    "country": "country classic country",
    "electronic": "electronic edm house techno",
    "folk": "folk acoustic singer-songwriter",
    "blues": "blues soul jazz",
    "reggae": "reggae dancehall",
    "punk": "punk rock pop punk",
    # Tempo/Style
    "fast": "edm dance electronic energy",
    "slow": "acoustic ambient lo-fi chill",
    "bass": "edm trap electronic bass",
    "beats": "lo-fi hip hop electronic beats",
    "songs": "",
    "music": "",
    "playlist": "",
    "tracks": "",
    "vibes": "chill lo-fi ambient",
    "drive": "synthwave pop rock indie driving",
    "driving": "synthwave rock pop energy",
}

DEFAULT_MOOD_MODEL_PATH = "artifacts/mood_model.pkl"


class MoodToVector:
    def __init__(self, tfidf, ridge_embed, ridge_audio, vocab_tokens):
        self.tfidf = tfidf
        self.ridge_embed = ridge_embed
        self.ridge_audio = ridge_audio
        self.vocab_tokens = vocab_tokens

    @classmethod
    def load(cls, path: str = DEFAULT_MOOD_MODEL_PATH):
        with open(path, "rb") as f:
            d = pickle.load(f)
        return cls(d["tfidf"], d["ridge_embed"], d["ridge_audio"], d["vocab_tokens"])

    def _expand(self, text: str) -> str:
        toks = text.lower().split()
        extra = [SYNONYMS[t] for t in toks if t in SYNONYMS]
        return " ".join(toks + extra)

    def transform(self, text: str) -> dict:
        from scipy.sparse import hstack, csr_matrix
        expanded = self._expand(text)
        X = self.tfidf.transform([expanded])
        Xi = hstack([X, csr_matrix(np.ones((1, 1)))]).tocsr()
        vec = self.ridge_embed.predict(Xi)[0].astype(np.float32)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        audio = np.clip(self.ridge_audio.predict(Xi)[0].astype(np.float32), 0, 1)

        # Smart audio attribute overrides based on explicit query intent
        low_text = text.lower()
        if any(w in low_text for w in ["sad", "cry", "melancholy", "heartbreak", "breakup", "somber"]):
            audio[1] = min(audio[1], 0.35)  # valence
            audio[0] = min(audio[0], 0.45)  # energy
        elif any(w in low_text for w in ["happy", "upbeat", "cheerful", "party", "celebration"]):
            audio[1] = max(audio[1], 0.70)  # valence
            audio[0] = max(audio[0], 0.65)  # energy

        if any(w in low_text for w in ["gym", "workout", "hype", "rage", "phonk", "pumping", "hardstyle"]):
            audio[0] = max(audio[0], 0.80)  # energy
            audio[2] = max(audio[2], 0.65)  # danceability
            audio[7] = max(audio[7], 0.50)  # tempo

        if any(w in low_text for w in ["chill", "relax", "lo-fi", "lofi", "sleep", "meditation", "unwind", "calm"]):
            audio[0] = min(audio[0], 0.38)  # energy
            audio[3] = max(audio[3], 0.55)  # acousticness

        matched = [t for t in expanded.split() if t in self.vocab_tokens]
        return {"vector": vec, "audio": audio, "matched_tokens": matched, "coverage": X.nnz > 0}


# -----------------------------------------------------------------------------
# 3. RAG DJ & Groundedness Checker (Gemini Commentary + Fact Verification)
# -----------------------------------------------------------------------------
FEATURE_TERMS = {
    "energetic": ("energy", ">=", 0.60), "high-energy": ("energy", ">=", 0.60),
    "driving": ("energy", ">=", 0.60), "intense": ("energy", ">=", 0.60),
    "pumping": ("energy", ">=", 0.60), "explosive": ("energy", ">=", 0.60),
    "mellow": ("energy", "<=", 0.45), "laid-back": ("energy", "<=", 0.45),
    "calm": ("energy", "<=", 0.45), "gentle": ("energy", "<=", 0.45),
    "soft": ("energy", "<=", 0.45), "relaxed": ("energy", "<=", 0.45),
    "happy": ("valence", ">=", 0.55), "upbeat": ("valence", ">=", 0.55),
    "bright": ("valence", ">=", 0.55), "cheerful": ("valence", ">=", 0.55),
    "joyful": ("valence", ">=", 0.55), "uplifting": ("valence", ">=", 0.55),
    "feel-good": ("valence", ">=", 0.55),
    "sad": ("valence", "<=", 0.45), "melancholy": ("valence", "<=", 0.45),
    "melancholic": ("valence", "<=", 0.45), "moody": ("valence", "<=", 0.45),
    "somber": ("valence", "<=", 0.45), "brooding": ("valence", "<=", 0.45),
    "wistful": ("valence", "<=", 0.45), "downbeat": ("valence", "<=", 0.45),
    "danceable": ("danceability", ">=", 0.60), "groovy": ("danceability", ">=", 0.60),
    "acoustic": ("acousticness", ">=", 0.50), "stripped-back": ("acousticness", ">=", 0.50),
    "unplugged": ("acousticness", ">=", 0.50),
    "fast": ("tempo_bpm", ">=", 120), "uptempo": ("tempo_bpm", ">=", 120),
    "slow": ("tempo_bpm", "<=", 100), "downtempo": ("tempo_bpm", "<=", 100),
}


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

    # ------ AI Intel (replaces old DJ commentary) ------

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

    # ------ Playlist Generator ------

    def playlist_gen_prompt(self, user_prompt: str, available_genres: List[str], count: int) -> str:
        return (
            "You are a world-class music curator AI. The user wants a custom playlist.\n"
            "Analyze their intent, mood, genre, language/country, and vibe, then generate structured parameters AND a list of specific famous track search queries matching their request.\n\n"
            "RULES:\n"
            "1. Output ONLY valid JSON, no markdown formatting.\n"
            "2. 'playlist_name' should be catchy and creative.\n"
            "3. 'description' should be a sleek 1-sentence summary.\n"
            "4. 'specific_tracks' MUST be an array of 12-20 specific famous song titles with artist names (e.g. [\"Song Name Artist Name\", ...]) that PERFECTLY match the user request. If a specific language (e.g. Telugu, Hindi, Tamil, Punjabi, K-Pop) or song reference (e.g. 'songs like Believer') is requested, return ONLY real, famous songs matching that exact language/style!\n\n"
            f"User Request: \"{user_prompt}\"\n"
            f"Tracks Requested: {count}\n\n"
            'Return JSON format:\n'
            '{\n'
            '  "playlist_name": "Creative Playlist Title",\n'
            '  "description": "1-sentence playlist summary",\n'
            '  "genres": ["genre1", "genre2"],\n'
            '  "specific_tracks": ["Track Title 1 Artist 1", "Track Title 2 Artist 2"]\n'
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
                # Ensure all expected keys exist
                for key in ["headline", "insights", "sound_profile", "mood_tags", "listen_if"]:
                    if key not in result:
                        result[key] = self._template_intel(facts, recs).get(key, "")
                return result
            return self._template_intel(facts, recs)
        except Exception as e:
            print(f"[RAGDJ] intel generation failed ({e}); using template.")
            return self._template_intel(facts, recs)

    # ------ Gemini Mood Fallback (for out-of-vocabulary queries) ------

    def mood_fallback(self, query: str, available_genres: List[str]) -> Optional[dict]:
        """When MoodToVector has zero TF-IDF coverage, use Gemini to interpret the query."""
        if not self._client:
            return None
        # Provide a curated subset of genres so the prompt isn't too long
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
                # Validate
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

    # ------ Legacy narrate for terminal mode compatibility ------

    def narrate(self, header: str, facts: dict, recs: List[dict]) -> str:
        intel = self.get_intel(facts, recs)
        headline = intel.get("headline", "")
        sound = intel.get("sound_profile", "")
        return f"{headline}. {sound}"


# -----------------------------------------------------------------------------
# 4. User Profile Store & Feedback Logging
# -----------------------------------------------------------------------------
LONG_TERM_DECAY = 0.9
SHORT_TERM_DECAY = 0.6


class ProfileStore:
    def __init__(self, engine: RecommendationEngine, profiles_dir: str = "profiles"):
        self.engine = engine
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.dir = os.path.normpath(os.path.join(script_dir, "..", profiles_dir))
        os.makedirs(self.dir, exist_ok=True)
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
            with open(path) as f:
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
        with open(self._path(user), "w") as f:
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

    def record(self, user: str, profile: dict, row: int, signal: str, context: Optional[dict] = None):
        vec = np.asarray(self.engine.embeddings[row], np.float32)
        track_id = str(self.engine.meta.iat[row, 0])

        if signal == "like":
            profile["long_term"] = self._blend(profile.get("long_term"), vec, LONG_TERM_DECAY)
            profile["short_term"] = self._blend(profile.get("short_term"), vec, SHORT_TERM_DECAY)
            profile["likes"] = (profile.get("likes", []) + [track_id])[-500:]
            for gid in self.engine._genre_ids(row):
                g = self.engine.genre_vocab[gid]
                profile["genre_counts"][g] = profile["genre_counts"].get(g, 0) + 1
            artist = str(self.engine._artists[row])
            profile["artist_counts"][artist] = profile["artist_counts"].get(artist, 0) + 1
        elif signal == "skip":
            if profile.get("short_term") is not None:
                cur = np.asarray(profile["short_term"], np.float32)
                pushed = cur - 0.15 * vec
                n = np.linalg.norm(pushed)
                profile["short_term"] = (pushed / n).tolist() if n > 0 else cur.tolist()
            profile["skips"] = (profile.get("skips", []) + [track_id])[-500:]

        profile["n_events"] = profile.get("n_events", 0) + 1
        event = {"ts": time.time(), "user": user, "track_id": track_id,
                 "signal": signal, "name": str(self.engine._names[row]),
                 "artist": str(self.engine._artists[row]), "row": int(row)}
        if context:
            event["context"] = context
        with open(self._events_path(user), "a") as f:
            f.write(json.dumps(event) + "\n")

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


# -----------------------------------------------------------------------------
# 5. Search Query Classifier
# -----------------------------------------------------------------------------
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
        # Filter out common stop words from missing
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
        # Check if live search finds an out-of-index song (skip for NLP mood queries)
        live_hits = search_live_apis(query, limit=1) if search_type != "nlp" else None
        if live_hits:
            hit = live_hits[0]
            t = mood_model.transform(f"{hit['name']} {hit['artist']} {' '.join(hit.get('base_genres', []))}")
            recs = engine.recommend_by_vector(t["vector"], k=k)
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

            # Live Deezer Mood Track Harvesting (Brings real-time hits & 30s preview audio for any mood query)
            live_mood_tracks = []
            try:
                d_q = urllib.parse.quote(query)
                dz_res = _fetch_json(f"https://api.deezer.com/search?q={d_q}&limit=3")
                if dz_res and dz_res.get("data"):
                    for item in dz_res["data"]:
                        tname = item.get("title", "")
                        aname = (item.get("artist") or {}).get("name", "")
                        if not tname or not aname:
                            continue
                        art = (item.get("album") or {}).get("cover_medium", "")
                        yt_q = urllib.parse.quote(f"{aname} {tname}")
                        live_mood_tracks.append({
                            "row": -1,
                            "track_id": f"live_dz_{item.get('id')}",
                            "name": tname,
                            "artist": aname,
                            "year": "2024",
                            "popularity_pct": 92,
                            "base_genres": list(tg) if 'tg' in locals() and tg else ["pop"],
                            "energy": round(float(a[0]), 2),
                            "valence": round(float(a[1]), 2),
                            "danceability": round(float(a[2]), 2),
                            "tempo_bpm": int(a[7] * 150 + 50),
                            "deezer_preview_url": item.get("preview") or "",
                            "deezer_album_art": art,
                            "deezer_link": item.get("link") or "",
                            "youtube_music_url": f"https://music.youtube.com/search?q={yt_q}",
                            "is_live_external": True,
                            "score": 0.95,
                        })
            except Exception:
                pass

            if live_mood_tracks:
                existing_names = {(r.get("name") or "").lower().strip() for r in recs}
                blended = []
                for live_t in live_mood_tracks:
                    tn = live_t["name"].lower().strip()
                    if tn not in existing_names:
                        blended.append(live_t)
                        existing_names.add(tn)
                blended.extend(recs)
                recs = blended[:k]

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
    def _gpu_run_pipeline(query: str, engine: RecommendationEngine, mood_model: MoodToVector,
                         dj: RAGDJ, checker: GroundednessChecker, profile: dict, store: ProfileStore,
                         mode: str = "similar", k: int = 10, search_type: str = "auto",
                         seed_track: Optional[dict] = None):
        return _raw_run_pipeline(query, engine, mood_model, dj, checker, profile, store, mode=mode, k=k, search_type=search_type, seed_track=seed_track)
else:
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



_ARTIST_IMAGE_CACHE: Dict[str, str] = {}

def get_artist_image(artist_name: str) -> str:
    """Fetch high-resolution artist image photo from Deezer/iTunes backend (bypassing browser CORS)."""
    if not artist_name:
        return ""
    key = artist_name.lower().strip()
    if key in _ARTIST_IMAGE_CACHE:
        return _ARTIST_IMAGE_CACHE[key]

    try:
        q = urllib.parse.quote(artist_name)
        d_data = _fetch_json(f"https://api.deezer.com/search/artist?q={q}&limit=1")
        if d_data and d_data.get("data") and d_data["data"][0].get("picture_big"):
            img = d_data["data"][0]["picture_big"]
            _ARTIST_IMAGE_CACHE[key] = img
            return img
    except Exception:
        pass

    try:
        q = urllib.parse.quote(artist_name)
        it_data = _fetch_json(f"https://itunes.apple.com/search?term={q}&entity=song&limit=1")
        if it_data and it_data.get("results") and it_data["results"][0].get("artworkUrl100"):
            img = it_data["results"][0]["artworkUrl100"].replace("100x100bb", "300x300bb")
            _ARTIST_IMAGE_CACHE[key] = img
            return img
    except Exception:
        pass

    _ARTIST_IMAGE_CACHE[key] = ""
    return ""
_ENRICH_CACHE: Dict[str, dict] = {}  # in-memory: "trackname||artist" -> enrichment


import ssl

def _fetch_json(url: str, timeout: int = 4) -> Optional[dict]:
    """Fetch a JSON URL with a timeout; returns None on failure."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"})
        ctx = ssl._create_unverified_context()
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def enrich_track(track_name: str, artist_name: str, lastfm_key: Optional[str] = None) -> dict:
    """Enrich a track with Deezer preview, YouTube Music link, and Last.fm data."""
    if not track_name or not artist_name:
        return {}
    cache_key = f"{track_name.lower().strip()}||{artist_name.lower().strip()}"
    if cache_key in _ENRICH_CACHE and _ENRICH_CACHE[cache_key].get("deezer_album_art"):
        return _ENRICH_CACHE[cache_key]

    primary_artist = re.split(r'[,&/]|feat\.?|ft\.?', artist_name, flags=re.IGNORECASE)[0].strip()
    primary_artist_clean = re.sub(r'[?!:;"\'-]', ' ', primary_artist)
    primary_artist_clean = re.sub(r'\s+', ' ', primary_artist_clean).strip()
    if not primary_artist_clean:
        primary_artist_clean = artist_name

    clean_track = track_name.split(' - ')[0].strip()
    clean_track = re.sub(r'\s*\([^)]*\)', '', clean_track)
    clean_track = re.sub(r'\s*\[[^\]]*\]', '', clean_track)
    
    if primary_artist and primary_artist.lower() in clean_track.lower():
        pattern = re.compile(r'\s*' + re.escape(primary_artist) + r'\s*$', re.IGNORECASE)
        clean_track = pattern.sub('', clean_track.strip()).strip()

    clean_track = re.sub(r'[?!:;"\'-]', ' ', clean_track)
    clean_track = re.sub(r'\s+', ' ', clean_track).strip()
    if not clean_track:
        clean_track = track_name.split('(')[0].split('[')[0].split('-')[0].strip()
        
    primary_artist = primary_artist_clean

    result: dict = {}
    try:
        # ---- Deezer Search API ----
        deezer_q = urllib.parse.quote(f"{primary_artist} {clean_track}")
        deezer_data = _fetch_json(f"https://api.deezer.com/search?q={deezer_q}&limit=1&output=json")
        if not (deezer_data and deezer_data.get("data")):
            deezer_q = urllib.parse.quote(clean_track)
            deezer_data = _fetch_json(f"https://api.deezer.com/search?q={deezer_q}&limit=1&output=json")

        if deezer_data and deezer_data.get("data"):
            hit = deezer_data["data"][0]
            result["deezer_preview_url"] = hit.get("preview") or ""
            result["deezer_link"] = hit.get("link") or ""
            result["deezer_album_art"] = (hit.get("album") or {}).get("cover_medium") or ""
            result["deezer_album_name"] = (hit.get("album") or {}).get("title") or ""
            result["deezer_id"] = hit.get("id") or ""
    except Exception:
        pass

    try:
        # ---- iTunes Search API Fallback (Guarantees cover art + 30s preview) ----
        if not result.get("deezer_preview_url") or not result.get("deezer_album_art"):
            it_q = urllib.parse.quote(f"{primary_artist} {clean_track}")
            it_data = _fetch_json(f"https://itunes.apple.com/search?term={it_q}&entity=song&limit=1")
            if not (it_data and it_data.get("results")):
                it_q = urllib.parse.quote(clean_track)
                it_data = _fetch_json(f"https://itunes.apple.com/search?term={it_q}&entity=song&limit=1")
            if it_data and it_data.get("results"):
                it_hit = it_data["results"][0]
                if not result.get("deezer_preview_url"):
                    result["deezer_preview_url"] = it_hit.get("previewUrl") or ""
                if not result.get("deezer_album_art"):
                    art = it_hit.get("artworkUrl100") or ""
                    result["deezer_album_art"] = art.replace("100x100bb", "300x300bb")
                if not result.get("deezer_link"):
                    result["deezer_link"] = it_hit.get("trackViewUrl") or ""
    except Exception:
        pass

    try:
        # ---- YouTube Music ----
        yt_q = urllib.parse.quote(f"{primary_artist} {clean_track}")
        result["youtube_music_url"] = f"https://music.youtube.com/search?q={yt_q}"
        result["youtube_url"] = f"https://www.youtube.com/results?search_query={yt_q}"
    except Exception:
        pass

    if result.get("deezer_album_art") or result.get("deezer_preview_url"):
        _ENRICH_CACHE[cache_key] = result

    return result


def search_live_apis(query: str, limit: int = 5) -> List[dict]:
    """Search iTunes & Deezer live APIs in real-time for out-of-index songs (e.g. brand new releases like 'Normal' by BTS)."""
    if not query or len(query.strip()) < 2:
        return []
    hits = []
    seen = set()
    q_clean = query.strip()
    
    try:
        # iTunes Search API
        it_q = urllib.parse.quote(q_clean)
        it_data = _fetch_json(f"https://itunes.apple.com/search?term={it_q}&entity=song&limit={limit}")
        if it_data and it_data.get("results"):
            for item in it_data["results"]:
                tname = item.get("trackName", "")
                aname = item.get("artistName", "")
                if not tname or not aname:
                    continue
                key = f"{tname.lower().strip()}||{aname.lower().strip()}"
                if key in seen:
                    continue
                seen.add(key)
                art = (item.get("artworkUrl100") or "").replace("100x100bb", "300x300bb")
                yt_q = urllib.parse.quote(f"{aname} {tname}")
                hits.append({
                    "row": -1,
                    "track_id": f"live_itunes_{item.get('trackId')}",
                    "name": tname,
                    "artist": aname,
                    "year": str(item.get("releaseDate", "2024"))[:4],
                    "popularity_pct": 95,
                    "base_genres": [item.get("primaryGenreName", "pop").lower()],
                    "energy": 0.70,
                    "valence": 0.65,
                    "danceability": 0.70,
                    "tempo_bpm": 120,
                    "deezer_preview_url": item.get("previewUrl") or "",
                    "deezer_album_art": art,
                    "deezer_link": item.get("trackViewUrl") or "",
                    "youtube_music_url": f"https://music.youtube.com/search?q={yt_q}",
                    "is_live_external": True
                })
    except Exception:
        pass

    if len(hits) < limit:
        try:
            # Deezer Search API
            dz_q = urllib.parse.quote(q_clean)
            dz_data = _fetch_json(f"https://api.deezer.com/search?q={dz_q}&limit={limit}")
            if dz_data and dz_data.get("data"):
                for item in dz_data["data"]:
                    tname = item.get("title", "")
                    aname = (item.get("artist") or {}).get("name", "")
                    if not tname or not aname:
                        continue
                    key = f"{tname.lower().strip()}||{aname.lower().strip()}"
                    if key in seen:
                        continue
                    seen.add(key)
                    art = (item.get("album") or {}).get("cover_medium", "")
                    yt_q = urllib.parse.quote(f"{aname} {tname}")
                    hits.append({
                        "row": -1,
                        "track_id": f"live_deezer_{item.get('id')}",
                        "name": tname,
                        "artist": aname,
                        "year": "2024",
                        "popularity_pct": 90,
                        "base_genres": ["pop"],
                        "energy": 0.70,
                        "valence": 0.65,
                        "danceability": 0.70,
                        "tempo_bpm": 120,
                        "deezer_preview_url": item.get("preview") or "",
                        "deezer_album_art": art,
                        "deezer_link": item.get("link") or "",
                        "youtube_music_url": f"https://music.youtube.com/search?q={yt_q}",
                        "is_live_external": True
                    })
        except Exception:
            pass

    return hits[:limit]


def search_live_albums(query: str, limit: int = 4) -> List[dict]:
    """Search iTunes & Deezer for album/movie soundtrack releases matching query."""
    if not query or len(query.strip()) < 2:
        return []
    albums = []
    seen = set()
    q_clean = query.strip()

    try:
        # 1. Deezer Album Search
        d_q = urllib.parse.quote(q_clean)
        d_data = _fetch_json(f"https://api.deezer.com/search/album?q={d_q}&limit={limit}")
        if d_data and d_data.get("data"):
            for item in d_data["data"]:
                atitle = item.get("title", "")
                aname = (item.get("artist") or {}).get("name", "")
                aid = item.get("id")
                if not atitle:
                    continue
                key = atitle.lower().strip()
                if key in seen:
                    continue
                seen.add(key)
                art = item.get("cover_medium") or item.get("cover_big") or ""
                albums.append({
                    "id": str(aid),
                    "title": atitle,
                    "artist": aname,
                    "cover_art": art,
                    "track_count": item.get("nb_tracks", 0),
                    "source": "deezer"
                })
    except Exception:
        pass

    try:
        # 2. iTunes Album Fallback
        if len(albums) < limit:
            it_q = urllib.parse.quote(q_clean)
            it_data = _fetch_json(f"https://itunes.apple.com/search?term={it_q}&entity=album&limit={limit}")
            if it_data and it_data.get("results"):
                for item in it_data["results"]:
                    atitle = item.get("collectionName", "")
                    aname = item.get("artistName", "")
                    aid = item.get("collectionId")
                    if not atitle:
                        continue
                    key = atitle.lower().strip()
                    if key in seen:
                        continue
                    seen.add(key)
                    art = (item.get("artworkUrl100") or "").replace("100x100bb", "300x300bb")
                    albums.append({
                        "id": str(aid),
                        "title": atitle,
                        "artist": aname,
                        "cover_art": art,
                        "track_count": item.get("trackCount", 0),
                        "year": str(item.get("releaseDate", ""))[:4],
                        "source": "itunes"
                    })
    except Exception:
        pass

    return albums[:limit]


def fetch_album_tracks(album_title: str, artist_name: str = "", album_id: str = "", engine = None) -> dict:
    """Fetch all tracks for a specific album/movie soundtrack."""
    tracks = []
    cover_art = ""
    artist = artist_name or "Various Artists"

    # 1. Search local dataset first for matching album or movie name
    if engine and hasattr(engine, 'df') and 'album' in engine.df.columns:
        df = engine.df
        q_clean = album_title.lower().strip()
        matching = df[df['album'].str.lower().str.contains(q_clean, na=False, regex=False)]
        if not matching.empty:
            for idx, r in matching.head(30).iterrows():
                tracks.append(engine.track_card(idx))

    # 2. If dataset has few/no tracks, fetch from Deezer/iTunes Live Album Lookup!
    if len(tracks) < 2 and album_id:
        try:
            d_data = _fetch_json(f"https://api.deezer.com/album/{album_id}")
            if d_data:
                cover_art = d_data.get("cover_big") or d_data.get("cover_medium") or ""
                artist = (d_data.get("artist") or {}).get("name") or artist
                track_list = (d_data.get("tracks") or {}).get("data") or []
                for tr in track_list:
                    tname = tr.get("title", "")
                    tar = (tr.get("artist") or {}).get("name") or artist
                    yt_q = urllib.parse.quote(f"{tar} {tname}")
                    tracks.append({
                        "row": -1,
                        "name": tname,
                        "artist": tar,
                        "year": str(d_data.get("release_date", ""))[:4] or "2024",
                        "popularity_pct": 88,
                        "base_genres": ["soundtrack", "pop"],
                        "energy": 0.65,
                        "valence": 0.60,
                        "danceability": 0.65,
                        "tempo_bpm": 120,
                        "deezer_preview_url": tr.get("preview") or "",
                        "deezer_album_art": cover_art,
                        "deezer_link": tr.get("link") or "",
                        "youtube_music_url": f"https://music.youtube.com/search?q={yt_q}",
                        "is_live_external": True
                    })
        except Exception:
            pass

    # 3. iTunes Album Lookup fallback
    if len(tracks) < 2:
        try:
            it_q = urllib.parse.quote(f"{album_title} {artist_name}".strip())
            it_data = _fetch_json(f"https://itunes.apple.com/search?term={it_q}&entity=song&limit=25")
            if it_data and it_data.get("results"):
                for tr in it_data["results"]:
                    col_name = (tr.get("collectionName") or "").lower()
                    if album_title.lower() in col_name or not cover_art:
                        if not cover_art:
                            cover_art = (tr.get("artworkUrl100") or "").replace("100x100bb", "300x300bb")
                        tname = tr.get("trackName", "")
                        tar = tr.get("artistName", "")
                        yt_q = urllib.parse.quote(f"{tar} {tname}")
                        tracks.append({
                            "row": -1,
                            "name": tname,
                            "artist": tar,
                            "year": str(tr.get("releaseDate", ""))[:4] or "2024",
                            "popularity_pct": 85,
                            "base_genres": [tr.get("primaryGenreName", "pop").lower()],
                            "energy": 0.65,
                            "valence": 0.60,
                            "danceability": 0.65,
                            "tempo_bpm": 120,
                            "deezer_preview_url": tr.get("previewUrl") or "",
                            "deezer_album_art": (tr.get("artworkUrl100") or "").replace("100x100bb", "300x300bb"),
                            "deezer_link": tr.get("trackViewUrl") or "",
                            "youtube_music_url": f"https://music.youtube.com/search?q={yt_q}",
                            "is_live_external": True
                        })
        except Exception:
            pass

    return {
        "title": album_title,
        "artist": artist,
        "cover_art": cover_art,
        "tracks": tracks
    }


def enrich_artist_lastfm(artist_name: str, lastfm_key: str = "") -> dict:
    """Fetch artist bio, tags, listener count, similar artists, and top tracks from Last.fm."""
    if not artist_name:
        return {}
    
    key = lastfm_key or os.environ.get("LASTFM_API_KEY")
    if not key:
        return {}
    cache_key = f"artist_lfm_v2_{artist_name.lower().strip()}"
    if cache_key in _ENRICH_CACHE:
        return _ENRICH_CACHE[cache_key]

    result = {}
    try:
        a_q = urllib.parse.quote(artist_name)
        # 1. Artist GetInfo
        data = _fetch_json(
            f"http://ws.audioscrobbler.com/2.0/?method=artist.getinfo"
            f"&api_key={key}&artist={a_q}&format=json&autocorrect=1"
        )
        if data and data.get("artist"):
            art = data["artist"]
            bio = (art.get("bio") or {}).get("summary") or ""
            bio_clean = re.sub(r'<[^>]+>', '', bio)
            if "Read more on Last.fm" in bio_clean:
                bio_clean = bio_clean.split("Read more on Last.fm")[0].strip()
            
            stats = art.get("stats") or {}
            listeners = int(stats.get("listeners") or 0)
            playcount = int(stats.get("playcount") or 0)
            tags = [t["name"] for t in (art.get("tags") or {}).get("tag", [])[:6]]
            similar = [s["name"] for s in (art.get("similar") or {}).get("artist", [])[:8]]

            result = {
                "bio": bio_clean,
                "listeners": listeners,
                "playcount": playcount,
                "tags": tags,
                "similar": similar,
                "url": art.get("url") or "",
                "top_tracks": []
            }

        # 2. Artist Top Tracks from Last.fm
        t_data = _fetch_json(
            f"http://ws.audioscrobbler.com/2.0/?method=artist.gettoptracks"
            f"&api_key={key}&artist={a_q}&format=json&limit=20"
        )
        if t_data and (t_data.get("toptracks") or {}).get("track"):
            lfm_tracks = []
            for tr in t_data["toptracks"]["track"]:
                tname = tr.get("name", "")
                aname = (tr.get("artist") or {}).get("name") or artist_name
                yt_q = urllib.parse.quote(f"{aname} {tname}")
                lfm_tracks.append({
                    "row": -1,
                    "name": tname,
                    "artist": aname,
                    "year": "2024",
                    "popularity_pct": 85,
                    "base_genres": result.get("tags", ["pop"])[:2],
                    "energy": 0.70,
                    "valence": 0.65,
                    "danceability": 0.70,
                    "tempo_bpm": 120,
                    "deezer_preview_url": "",
                    "deezer_album_art": "",
                    "deezer_link": "",
                    "youtube_music_url": f"https://music.youtube.com/search?q={yt_q}",
                    "is_live_external": True,
                    "source": "lastfm"
                })
            result["top_tracks"] = lfm_tracks

        _ENRICH_CACHE[cache_key] = result
    except Exception:
        pass

    return result


def get_app_components(artifacts_dir: str = "artifacts"):

    global _COMPONENTS
    if _COMPONENTS is None:
        resolved_dir = resolve_artifacts_dir(artifacts_dir)
        print(s("  📥 Initializing SoundVector Engine & Models...", C.CY))
        engine = RecommendationEngine(resolved_dir)
        mood_model = MoodToVector.load(os.path.join(resolved_dir, "mood_model.pkl"))
        dj = RAGDJ()
        checker = GroundednessChecker()
        store = ProfileStore(engine)
        _COMPONENTS = (engine, mood_model, dj, checker, store)
    return _COMPONENTS


@app.get("/")
@app.get("/index.html")
async def get_index():
    possible_paths = [
        os.path.join(os.path.dirname(__file__), "..", "src", "static", "index.html"),
        "src/static/index.html",
        "static/index.html",
        "index.html"
    ]
    for p in possible_paths:
        if os.path.exists(p):
            return FileResponse(p, media_type="text/html")
    return HTMLResponse("<h2>SoundVector API is running. API endpoints available under /api/*</h2>")


@app.get("/style.css")
async def get_style():
    possible_paths = [
        os.path.join(os.path.dirname(__file__), "..", "src", "static", "style.css"),
        "src/static/style.css",
        "style.css"
    ]
    for p in possible_paths:
        if os.path.exists(p):
            return FileResponse(p, media_type="text/css")
    raise HTTPException(status_code=404, detail="style.css not found")


@app.get("/script.js")
async def get_script():
    possible_paths = [
        os.path.join(os.path.dirname(__file__), "..", "src", "static", "script.js"),
        "src/static/script.js",
        "script.js"
    ]
    for p in possible_paths:
        if os.path.exists(p):
            return FileResponse(p, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="script.js not found")



@app.get("/api/users")
async def api_users():
    engine, mood_model, dj, checker, store = get_app_components()
    return store.list_profiles()


@app.delete("/api/users/{username}")
async def api_delete_user(username: str):
    engine, mood_model, dj, checker, store = get_app_components()
    store.delete_user(username)
    return {"status": "success", "user": username}


@app.get("/api/search")
async def api_search(q: str = ""):
    engine, mood_model, dj, checker, store = get_app_components()
    results = engine.search(q, limit=8)
    matching_artists = engine.match_artist(q, limit=4)
    matching_albums = search_live_albums(q, limit=4)
    
    if q and len(q.strip()) >= 2:
        try:
            live_hits = search_live_apis(q, limit=3)
            if live_hits:
                existing_keys = {f"{(r.get('name') or '').lower().strip()}||{(r.get('artist') or '').lower().strip()}" for r in results}
                for hit in reversed(live_hits):
                    hk = f"{(hit.get('name') or '').lower().strip()}||{(hit.get('artist') or '').lower().strip()}"
                    if hk not in existing_keys:
                        results.insert(0, hit)
                        existing_keys.add(hk)
        except Exception:
            pass

    return {
        "results": results[:8],
        "artists": matching_artists,
        "albums": matching_albums
    }


@app.get("/api/album_tracks")
async def api_album_tracks(title: str = "", artist: str = "", id: str = ""):
    engine, mood_model, dj, checker, store = get_app_components()
    data = fetch_album_tracks(title, artist_name=artist, album_id=id, engine=engine)
    return data


@app.get("/api/artist_image")
async def api_artist_image(q: str = ""):
    img_url = get_artist_image(q)
    return {"image_url": img_url}


@app.get("/api/enrich")
async def api_enrich(track: str = "", artist: str = ""):
    lastfm_key = os.environ.get("LASTFM_API_KEY")
    return enrich_track(track, artist, lastfm_key)


@app.get("/api/artist")
async def api_artist(name: str = "", sort: str = "popularity"):
    engine, mood_model, dj, checker, store = get_app_components()
    tracks = engine.artist_all_tracks(name, sort_by=sort, limit=50)
    albums = engine.artist_albums(name)
    
    lastfm_key = os.environ.get("LASTFM_API_KEY") or ""
    lastfm_info = enrich_artist_lastfm(name, lastfm_key)

    existing_names = {(t.get("name") or "").lower().strip() for t in tracks}
    
    for ltr in lastfm_info.get("top_tracks", []):
        tn = ltr["name"].lower().strip()
        if tn not in existing_names:
            tracks.append(ltr)
            existing_names.add(tn)

    if len(tracks) < 15 and name:
        try:
            it_q = urllib.parse.quote(name)
            it_data = _fetch_json(f"https://itunes.apple.com/search?term={it_q}&entity=song&limit=25")
            if it_data and it_data.get("results"):
                for tr in it_data["results"]:
                    tname = tr.get("trackName", "")
                    tar = tr.get("artistName", "")
                    if not tname or name.lower() not in tar.lower():
                        continue
                    tn = tname.lower().strip()
                    if tn not in existing_names:
                        existing_names.add(tn)
                        yt_q = urllib.parse.quote(f"{tar} {tname}")
                        art = (tr.get("artworkUrl100") or "").replace("100x100bb", "300x300bb")
                        tracks.append({
                            "row": -1,
                            "name": tname,
                            "artist": tar,
                            "year": str(tr.get("releaseDate", ""))[:4] or "2024",
                            "popularity_pct": 85,
                            "base_genres": [tr.get("primaryGenreName", "pop").lower()],
                            "energy": 0.65,
                            "valence": 0.60,
                            "danceability": 0.65,
                            "tempo_bpm": 120,
                            "deezer_preview_url": tr.get("previewUrl") or "",
                            "deezer_album_art": art,
                            "deezer_link": tr.get("trackViewUrl") or "",
                            "youtube_music_url": f"https://music.youtube.com/search?q={yt_q}",
                            "is_live_external": True
                        })
        except Exception:
            pass

    return {
        "artist": name, "tracks": tracks, "albums": albums,
        "lastfm": lastfm_info
    }


@app.get("/api/track_intel")
async def api_track_intel(row: int = -1, track: str = "", artist: str = ""):
    engine, mood_model, dj, checker, store = get_app_components()
    facts = {}
    recs = []
    if row >= 0 and engine:
        try:
            t_card = engine.track_card(row)
            facts = {
                "name": t_card.get("name"),
                "artist": t_card.get("artist"),
                "year": t_card.get("year"),
                "popularity": t_card.get("popularity_pct", 50) / 100.0,
                "genres": t_card.get("base_genres", []),
                "energy": round(float(t_card.get("energy", 0.5)), 2),
                "valence": round(float(t_card.get("valence", 0.5)), 2),
                "danceability": round(float(t_card.get("danceability", 0.5)), 2),
                "acousticness": round(float(t_card.get("acousticness", 0.5)), 2),
                "tempo_bpm": int(t_card.get("tempo_bpm", 120))
            }
            sim_recs = engine.recommend([row], k=5)
            recs = [engine.track_card(r["row"]) for r in sim_recs]
        except Exception:
            pass

    if not facts and track:
        facts = {"name": track, "artist": artist, "genres": ["music"], "energy": 0.6, "valence": 0.5, "danceability": 0.6, "tempo_bpm": 120}

    intel = dj.get_intel(facts, recs)
    return {
        "facts": facts,
        "intel": intel,
        "backend": dj.backend
    }


@app.get("/api/profile")
async def api_profile(user: str = "default"):
    engine, mood_model, dj, checker, store = get_app_components()
    profile = store.load(user)

    events_path = store._events_path(user)
    history = []
    if os.path.exists(events_path):
        with open(events_path, 'r') as f:
            history = [json.loads(line) for line in f.readlines()][-50:]
            for ev in history:
                if "row" not in ev:
                    tid = ev.get("track_id")
                    ev["row"] = engine.track_idx.get(tid, -1) if hasattr(engine, 'track_idx') else -1
            history.reverse()

    return {
        "top_genres": store.top_genres(profile, 3),
        "top_artists": store.top_artists(profile, 3),
        "history": history
    }


@app.get("/api/home")
async def api_home(user: str = "default"):
    engine, mood_model, dj, checker, store = get_app_components()
    profile = store.load(user)
    profile_vecs = store.vectors(profile) if profile.get("n_events") else None
    sections = []

    import datetime
    hour = datetime.datetime.now().hour
    if hour < 12:
        greeting = "Good Morning"
    elif hour < 17:
        greeting = "Good Afternoon"
    elif hour < 21:
        greeting = "Good Evening"
    else:
        greeting = "Late Night Vibes"

    has_history = profile.get("n_events", 0) > 0

    if has_history and profile.get("long_term") is not None:
        try:
            lt_vec = np.asarray(profile["long_term"], np.float32)
            n = np.linalg.norm(lt_vec)
            if n > 0:
                lt_vec = lt_vec / n
            vibe_recs = engine.recommend_by_vector(lt_vec, k=10, max_per_artist=1)
            vibe_cards = [engine.track_card(r["row"]) for r in vibe_recs]
            sections.append({
                "id": "your_vibe",
                "title": "Your Vibe",
                "subtitle": "Based on your taste profile",
                "tracks": vibe_cards,
            })
        except Exception:
            pass

        top_artists = store.top_artists(profile, 3)
        if top_artists:
            top_artist_name = top_artists[0][0]
            try:
                at = engine.artist_top_tracks(top_artist_name, limit=1)
                if at:
                    artist_recs = engine.recommend(
                        [at[0]["row"]], k=10, mode="similar",
                        profile_vectors=profile_vecs, max_per_artist=1
                    )
                    artist_cards = [engine.track_card(r["row"]) for r in artist_recs]
                    sections.append({
                        "id": "because_artist",
                        "title": f"Because You Like {top_artist_name}",
                        "subtitle": f"Tracks similar to {top_artist_name}'s style",
                        "tracks": artist_cards,
                    })
            except Exception:
                pass

        try:
            lt_vec2 = np.asarray(profile["long_term"], np.float32)
            n2 = np.linalg.norm(lt_vec2)
            if n2 > 0:
                lt_vec2 = lt_vec2 / n2
            discover_recs = engine.recommend_by_vector(
                lt_vec2, k=10, max_per_artist=1
            )
            discover_recs = discover_recs[::-1][:10]
            discover_cards = [engine.track_card(r["row"]) for r in discover_recs]
            sections.append({
                "id": "discover_new",
                "title": "Discover Something New",
                "subtitle": "Step outside your comfort zone",
                "tracks": discover_cards,
            })
        except Exception:
            pass

        top_genres = store.top_genres(profile, 5)
        quick_genres = [g[0] for g in top_genres] if top_genres else []
    else:
        quick_genres = ["pop", "hip hop", "rock", "edm", "r&b"]

        try:
            popular_seeds = engine.search("Shape of You", limit=1)
            if popular_seeds:
                pop_recs = engine.recommend(
                    [popular_seeds[0]["row"]], k=10, mode="popular"
                )
                pop_cards = [engine.track_card(r["row"]) for r in pop_recs]
                sections.append({
                    "id": "trending",
                    "title": "Trending Now",
                    "subtitle": "Popular tracks across genres",
                    "tracks": pop_cards,
                })
        except Exception:
            pass

        try:
            chill_t = mood_model.transform("chill lo-fi ambient relax")
            chill_recs = engine.recommend_by_vector(
                chill_t["vector"], k=10, max_per_artist=1
            )
            chill_cards = [engine.track_card(r["row"]) for r in chill_recs]
            sections.append({
                "id": "chill_vibes",
                "title": "Chill Vibes",
                "subtitle": "Relax and unwind",
                "tracks": chill_cards,
            })
        except Exception:
            pass

        try:
            energy_t = mood_model.transform("workout edm energy dance")
            energy_recs = engine.recommend_by_vector(
                energy_t["vector"], k=10, max_per_artist=1
            )
            energy_cards = [engine.track_card(r["row"]) for r in energy_recs]
            sections.append({
                "id": "energy_boost",
                "title": "Energy Boost",
                "subtitle": "Get pumped up",
                "tracks": energy_cards,
            })
        except Exception:
            pass

    return {
        "greeting": greeting,
        "user": user,
        "has_history": has_history,
        "sections": sections,
        "quick_genres": quick_genres,
    }


@app.post("/api/recommend")
async def api_recommend(req: RecommendRequest):
    engine, mood_model, dj, checker, store = get_app_components()
    profile = store.load(req.user)

    header, recs, blurb, ground, facts, intel = safe_run_pipeline(
        req.query, engine, mood_model, dj, checker, profile, store,
        mode=req.mode, search_type=req.search_type, seed_track=req.seed_track
    )
    return {
        "header": header,
        "recs": recs,
        "blurb": blurb,
        "grounded": ground,
        "facts": facts,
        "intel": intel,
        "backend": dj.backend,
    }


@app.post("/api/ai_intel")
async def api_ai_intel(req: AIIntelRequest):
    engine, mood_model, dj, checker, store = get_app_components()
    rec_cards = []
    for r in req.recs[:5]:
        if "row" in r:
            try:
                rec_cards.append(engine.track_card(int(r["row"])))
            except Exception:
                rec_cards.append(r)
        else:
            rec_cards.append(r)
    intel = dj.get_intel(req.facts, rec_cards)
    return intel


@app.post("/api/playlist_gen")
async def api_playlist_gen(req: PlaylistGenRequest):
    engine, mood_model, dj, checker, store = get_app_components()
    prompt = req.prompt
    user = req.user
    count = int(req.count)
    if not prompt:
        raise HTTPException(status_code=400, detail="Missing prompt")

    prompt_clean = prompt.strip()
    p_lower = prompt_clean.lower()
    
    gen_params = None
    if dj._client:
        try:
            resp = dj._client.models.generate_content(
                model=dj.model,
                contents=dj.playlist_gen_prompt(prompt_clean, engine.genre_vocab, count)
            )
            text = (resp.text or "").strip()
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                gen_params = json.loads(m.group(0))
        except Exception as e:
            print(f"[Playlist Gen] Gemini failed: {e}")

    if not gen_params:
        emoji = "🎵"
        if any(w in p_lower for w in ["sleep", "night", "rain", "calm", "relax", "melancholy"]):
            emoji = "🌙"
        elif any(w in p_lower for w in ["run", "workout", "gym", "hype", "energy"]):
            emoji = "⚡"
        elif any(w in p_lower for w in ["party", "dance", "club"]):
            emoji = "🎉"
        gen_params = {
            "playlist_name": f"{prompt_clean.title()} Mix",
            "playlist_emoji": emoji,
            "description": f"A curated selection of authentic {prompt_clean} tracks."
        }

    track_cards = []
    seen_keys = set()

    specific_queries = gen_params.get("specific_tracks", []) if gen_params else []
    if specific_queries and isinstance(specific_queries, list):
        for q_str in specific_queries[:count + 5]:
            if not q_str or not isinstance(q_str, str):
                continue
            found_card = None
            hits = engine.search(q_str, limit=1)
            if hits:
                h = hits[0]
                k = f"{(h.get('name') or '').lower().strip()}||{(h.get('artist') or '').lower().strip()}"
                if k not in seen_keys:
                    found_card = engine.track_card(h["row"])
            
            if not found_card:
                live_hits = search_live_apis(q_str, limit=1)
                if live_hits:
                    lh = live_hits[0]
                    k = f"{(lh.get('name') or '').lower().strip()}||{(lh.get('artist') or '').lower().strip()}"
                    if k not in seen_keys:
                        found_card = lh

            if found_card:
                k = f"{(found_card.get('name') or '').lower().strip()}||{(found_card.get('artist') or '').lower().strip()}"
                seen_keys.add(k)
                track_cards.append(found_card)
                if len(track_cards) >= count:
                    break

    if len(track_cards) < count:
        try:
            live_items = search_live_apis(prompt_clean, limit=count)
            if live_items:
                for item in live_items:
                    k = f"{(item.get('name') or '').lower().strip()}||{(item.get('artist') or '').lower().strip()}"
                    if k not in seen_keys:
                        seen_keys.add(k)
                        track_cards.append(item)
                        if len(track_cards) >= count:
                            break
        except Exception:
            pass

    if len(track_cards) < count:
        t = mood_model.transform(prompt_clean)
        tg = {BASE_GENRE_MAP.get(tok, tok) for tok in t["matched_tokens"]}
        vec_recs = engine.recommend_by_vector(t["vector"], k=count * 2, target_base_genres=tg, max_per_artist=2)
        for r in vec_recs:
            if r.get("row", -1) >= 0:
                tc = engine.track_card(r["row"])
                k = f"{(tc.get('name') or '').lower().strip()}||{(tc.get('artist') or '').lower().strip()}"
                if k not in seen_keys:
                    seen_keys.add(k)
                    track_cards.append(tc)
                    if len(track_cards) >= count:
                        break

    return {
        "playlist_name": gen_params.get("playlist_name", f"{prompt_clean.title()} Mix"),
        "playlist_emoji": gen_params.get("playlist_emoji", "🎵"),
        "description": gen_params.get("description", f"A curated selection of {prompt_clean} tracks."),
        "tracks": track_cards[:count],
        "ai_generated": bool(dj._client)
    }


@app.post("/api/feedback")
async def api_feedback(req: FeedbackRequest):
    engine, mood_model, dj, checker, store = get_app_components()
    profile = store.load(req.user)

    store.record(req.user, profile, req.row, req.signal, {"mode": req.mode})
    store.save(req.user, profile)

    return {"status": "ok"}


def launch_server(port: int = 8000):
    get_app_components()
    port = int(os.environ.get("PORT", port))
    is_hf_space = bool(os.environ.get("SPACE_ID") or os.environ.get("HF_SPACE_ID") or os.environ.get("GRADIO_SERVER_PORT"))
    
    if is_hf_space:
        hf_port = 7860 if is_hf_space else port
        with gr.Blocks(title="SoundVector UI", css="footer {visibility: hidden}") as demo:
            gr.HTML(value='<iframe src="/index.html" style="width:100%; height:100vh; border:none;"></iframe>')

        gradio_fastapi, _, _ = demo.launch(
            server_name="0.0.0.0",
            server_port=hf_port,
            prevent_thread_lock=True,
            ssr_mode=False,
        )

        gradio_fastapi.include_router(app.router)
        print(s(f"\n🚀 SoundVector API (Gradio + FastAPI ZeroGPU) launched on port {hf_port}\n", C.B, C.GR))
        threading.Event().wait()
    else:
        import uvicorn
        print(s(f"\n🚀 SoundVector Web UI & API launched at http://localhost:{port}\n", C.B, C.GR))
        uvicorn.run(app, host="0.0.0.0", port=port)


def load_env(path: str = ".env"):
    if os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


# -----------------------------------------------------------------------------
# 7. Main Entry Point
# -----------------------------------------------------------------------------
def main():
    load_env()
    ap = argparse.ArgumentParser(description="SoundVector All-in-One AI Music Recommender & RAG DJ")
    ap.add_argument("query", nargs="*", help="Optional query string (song/artist or mood)")
    ap.add_argument("--user", default=None, help="User profile name")
    ap.add_argument("--artifacts", default="artifacts", help="Path to artifacts directory")
    ap.add_argument("--web", "-w", action="store_true", help="Launch Web UI / API server")
    ap.add_argument("--port", type=int, default=8000, help="Port for Web UI / API server")
    args = ap.parse_args()

    if os.environ.get("SPACE_ID") or os.environ.get("HF_SPACE_ID") or args.web:
        launch_server(port=args.port)
        return

    artifacts_dir = resolve_artifacts_dir(args.artifacts)

    print(s("\n" + "━" * 60, C.CY))
    print(s("  🎵  SoundVector — Unified AI Music Recommender & RAG DJ", C.B, C.CY))
    print(s("     Two-Stage ANN Retrieval · MoodToVector NLP · Gemini DJ", C.D, C.CY))
    print(s("━" * 60, C.CY))

    engine, mood_model, dj, checker, store = get_app_components(artifacts_dir)
    print(s("✓", C.GR, C.B))
    print(f"  {s(f'{len(engine.meta):,} tracks · {len(engine.catalog):,} unique songs · DJ backend: {dj.backend}', C.D)}")

    user = args.user or ask("\nYour name (for your taste profile): ") or "default"
    profile = store.load(user)
    print(f"\n  {s('👤 Profile:', C.GR)} {s(user, C.B, C.CY)}")
    print_profile(store, profile)

    one_shot = " ".join(args.query).strip()
    if one_shot:
        header, recs, blurb, ground, facts, intel = safe_run_pipeline(one_shot, engine, mood_model, dj, checker, profile, store)
        show_recs(recs, header)
        print(f"\n💬 DJ ({dj.backend}):\n   {blurb}")
        gcolor = "✅" if ground["groundedness"] >= 0.9 else ("⚠️" if ground["groundedness"] >= 0.7 else "❌")
        print(f"\n{gcolor} groundedness {ground['groundedness']:.0%} ({ground['grounded']}/{ground['total_claims']} claims verified)")
        return

    pending_row = None
    while True:
        print(s("\n" + "─" * 60, C.D))
        if pending_row is not None:
            seed_row = pending_row
            pending_row = None
            facts = engine.track_card(seed_row)
            query = f"{facts['name']} {facts['artist']}"
        else:
            query = ask("Search a song, artist, or mood vibe (or 'quit'): ")
            if query.lower() in ("quit", "exit", "q"):
                print(f"\n{s('Thanks for using SoundVector! 🎵', C.CY, C.B)}\n")
                break
            if not query:
                continue

        mode = ask(f"Mode {s('[similar]', C.D)} similar/vibe/popular/discover: ").lower() or "similar"
        if mode not in SCORING_PRESETS:
            mode = "similar"

        print(f"\n  {s('⏳ Retrieving + ranking + DJ commentary...', C.D)}", flush=True)
        header, recs, blurb, ground, facts, intel = safe_run_pipeline(query, engine, mood_model, dj, checker, profile, store, mode=mode)
        show_recs(recs, header)
        print(f"\n💬 DJ ({dj.backend}):\n   {blurb}")
        gcolor = "✅" if ground["groundedness"] >= 0.9 else ("⚠️" if ground["groundedness"] >= 0.7 else "❌")
        print(f"\n{gcolor} groundedness {ground['groundedness']:.0%} ({ground['grounded']}/{ground['total_claims']} claims verified)")
        if ground["violations"]:
            for v in ground["violations"]:
                print(f"     - {v}")

        pending_row = feedback_loop(engine, store, user, profile, recs, mode)


def print_profile(store: ProfileStore, profile: dict):
    n = profile.get("n_events", 0)
    if n == 0:
        print(f"  {s('New profile — no taste history yet. Like tracks to personalize.', C.D)}")
        return
    genres = ", ".join(f"{g} ({c})" for g, c in store.top_genres(profile))
    artists = ", ".join(f"{a} ({c})" for a, c in store.top_artists(profile))
    print(f"  {s('Your taste so far', C.B, C.WH)} ({n} events):")
    print(f"     {s('Top genres:', C.D)} {genres or '—'}")
    print(f"     {s('Top artists:', C.D)} {artists or '—'}")


def show_recs(recs: List[dict], header: str):
    print(f"\n{s('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', C.CY)}")
    print(s(f"  🎧 Recommendations seeded by {header}", C.B, C.CY))
    print(s("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", C.CY))
    for i, r in enumerate(recs, 1):
        line = f"   {s(f'{i:>2}.', C.YE)} {s(r['name'], C.B, C.WH)} — {s(r['artist'], C.CY)}  [{r['score']*100:4.1f}%]"
        sig = r.get("signals", {})
        sig_parts = []
        if "embed" in sig: sig_parts.append(f"embed {sig['embed']:.2f}")
        if "audio" in sig: sig_parts.append(f"audio {sig['audio']:.2f}")
        if "genre" in sig: sig_parts.append(f"genre {sig['genre']:.2f}")
        if "artist" in sig: sig_parts.append(f"artist {int(sig['artist'])}")
        if "popularity" in sig: sig_parts.append(f"pop {sig['popularity']:.2f}")
        print(line)
        if sig_parts:
            print(f"      {s(' · '.join(sig_parts), C.D)}")


def feedback_loop(engine: RecommendationEngine, store: ProfileStore, user: str,
                  profile: dict, recs: List[dict], mode: str) -> Optional[int]:
    print(s("\n  Feedback: l N = like #N · s N = skip #N · N = get recs from #N · Enter = new search", C.D))
    while True:
        cmd = ask("Feedback / next: ").strip().lower()
        if not cmd:
            return None
        parts = cmd.split()
        if parts[0] in ("l", "s") and len(parts) == 2 and parts[1].isdigit():
            i = int(parts[1]) - 1
            if 0 <= i < len(recs):
                sig = "like" if parts[0] == "l" else "skip"
                store.record(user, profile, recs[i]["row"], sig, {"mode": mode})
                store.save(user, profile)
                verb = "👍 Liked" if sig == "like" else "👎 Skipped"
                print(f"  {s(verb, C.GR if sig=='like' else C.RE)}: {recs[i]['name']} — {recs[i]['artist']} (Profile updated!)")
            else:
                print(f"  {s('Out of range.', C.YE)}")
        elif parts[0].isdigit():
            i = int(parts[0]) - 1
            if 0 <= i < len(recs):
                return recs[i]["row"]
            print(f"  {s('Out of range.', C.YE)}")
        elif parts[0] in ("quit", "exit", "q"):
            print(f"\n{s('Thanks for using SoundVector! 🎵', C.CY, C.B)}\n")
            sys.exit(0)
        else:
            print(f"  {s('Commands: l N | s N | N | Enter', C.D)}")


if __name__ == "__main__":
    if os.environ.get("SPACE_ID") or os.environ.get("HF_SPACE_ID"):
        launch_server()
    else:
        main()