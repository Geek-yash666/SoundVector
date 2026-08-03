#!/usr/bin/env python3
"""
SoundVector Recommendation Engine (Two-Stage ANN Retrieval + MMR Ranking)
"""

import functools
import json
import os
import re
from typing import Dict, List, Optional, Set

import numpy as np
import pandas as pd
from rapidfuzz import fuzz, process

try:
    from .config import BASE_GENRE_MAP, N_AUDIO_DIMS, SCORING_PRESETS
except ImportError:
    from config import BASE_GENRE_MAP, N_AUDIO_DIMS, SCORING_PRESETS



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

    @functools.lru_cache(maxsize=16384)
    def _genre_ids(self, row: int) -> frozenset:
        s, e = self._genre_offsets[row], self._genre_offsets[row + 1]
        return frozenset(self._genre_indices[s:e].tolist())

    @functools.lru_cache(maxsize=16384)
    def _base_genres_cached(self, genre_ids: frozenset) -> frozenset:
        """Cached base-genre mapping — called O(candidates) times per recommendation."""
        out = set()
        for gid in genre_ids:
            label = self.genre_vocab[gid]
            out.add(BASE_GENRE_MAP.get(label, label))
        return frozenset(out)

    def _base_genres(self, genre_ids) -> set:
        return set(self._base_genres_cached(frozenset(genre_ids)))

    def genre_labels(self, row: int) -> List[str]:
        return [self.genre_vocab[g] for g in self._genre_ids(row)]

    @functools.lru_cache(maxsize=8192)
    def track_card(self, row: int) -> dict:
        """Return a fully-populated track dict for a given catalog row.
        LRU-cached (8192 entries) since this is called repeatedly for the same rows.
        """
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
                            candidates: int = 2000, max_per_artist: int = 1,
                            exclude_rows: Optional[set] = None,
                            strict_genre: bool = False) -> List[dict]:
        qv = np.asarray(qv, np.float32)
        n = np.linalg.norm(qv)
        if n > 0:
            qv = qv / n
        w = {"embed": 0.55, "genre": 0.20, "audio": 0.10, "popularity": 0.15}
        tg = target_base_genres or set()
        excluded = {int(self.canonical_row[r]) for r in (exclude_rows or set())}

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
            
            if strict_genre and tg:
                base = base * (genre_sim > 0)

            picked, artist_counts, keys_seen = [], {}, set()
            for pos in np.argsort(-base):
                if len(picked) >= k:
                    break
                if strict_genre and tg and base[pos] <= 0:
                    continue
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
