import os
from typing import List, Dict


class ProductionRecommender:
    """
    Music recommender using five-signal, 8D Euclidean scoring:
      - Audio similarity
      - Genre overlap
      - Artist affinity
      - Hybrid track and artist popularity
      - Era / release year proximity

    Operates on the full parquet dataset (~900K tracks) with smart indexing.
    """

    SCORING_PRESETS = {
        # 1. "similar" (Balanced): Reduced popularity bias so tracks match sound and vibe first
        "similar": {"audio": 0.40, "genre": 0.30, "artist": 0.15, "popularity": 0.15, "era": 0.0},

        # 2. "vibe" (Strict / Deep Cuts): Ignores song popularity entirely to find true sonic matches
        "vibe": {"audio": 0.50, "genre": 0.35, "artist": 0.15, "popularity": 0.00, "era": 0.0},

        # 3. "popular" (Radio Hits): Keeps songs high-charting while maintaining baseline audio & genre fit
        "popular": {"audio": 0.35, "popularity": 0.45, "genre": 0.20, "artist": 0.00, "era": 0.0},

        # 4. "discover" (Era & Popularity): Prioritizes tracks from the same era and genre, minimizing audio
        "discover": {"audio": 0.05, "genre": 0.35, "popularity": 0.30, "era": 0.30, "artist": 0.00},
    }

    AUDIO_FEATURES = [
        "energy", "valence", "danceability", "acousticness",
        "speechiness", "liveness", "instrumentalness", "tempo_norm"
    ]

    # Base genre mapping: normalizes subgenres to parent categories
    BASE_GENRE_MAP = {
        'pop': 'pop', 'dance pop': 'pop', 'canadian pop': 'pop',
        'viral pop': 'pop', 'electropop': 'electro', 'art pop': 'pop',
        'indie pop': 'pop', 'synth-pop': 'electro', 'k-pop': 'pop',
        'europop': 'pop', 'pop rock': 'pop rock', 'pop rap': 'pop',
        'chamber pop': 'pop', 'dream pop': 'pop', 'power pop': 'pop',
        'neo mellow': 'pop', 'acoustic cover': 'pop',
        'rock': 'rock', 'alternative rock': 'rock', 'indie rock': 'rock',
        'classic rock': 'rock', 'garage rock': 'rock', 'punk rock': 'rock',
        'modern rock': 'rock', 'irish rock': 'rock',
        'permanent wave': 'rock', 'new wave': 'rock',
        'hip hop': 'hip hop', 'rap': 'hip hop', 'trap': 'hip hop',
        'conscious hip hop': 'hip hop', 'north carolina hip hop': 'hip hop',
        'r&b': 'r&b', 'contemporary r&b': 'r&b',
        'canadian contemporary r&b': 'r&b', 'urban contemporary': 'r&b',
        'edm': 'edm', 'house': 'edm', 'tech house': 'edm',
        'deep house': 'edm', 'tropical house': 'edm',
        'electronic': 'edm', 'electro house': 'edm',
        'country': 'country', 'classic country': 'country',
        'country rock': 'country',
        'jazz': 'jazz', 'soul': 'soul', 'funk': 'soul',
        'metal': 'metal', 'heavy metal': 'metal',
        'latin': 'latin', 'reggaeton': 'latin', 'urbano latino': 'latin',
        'musica mexicana': 'latin', 'norteno': 'latin', 'ranchera': 'latin',
        'banda': 'latin', 'trap latino': 'latin', 'latin pop': 'latin',
        'classical': 'classical', 'lo-fi': 'lo-fi',
        'lofi': 'lo-fi', 'lo-fi cover': 'lo-fi',
        # Indian / South Asian / Bollywood genres
        'filmi': 'filmi', 'bollywood': 'filmi', 'modern bollywood': 'filmi',
        'classic bollywood': 'filmi', 'desi pop': 'filmi', 'desi hip hop': 'hip hop',
        'punjabi pop': 'filmi', 'punjabi hip hop': 'hip hop', 'indian pop': 'filmi',
        'indian classical': 'indian classical', 'hindustani classical': 'indian classical',
        'indian instrumental': 'filmi', 'ghazal': 'filmi', 'sufi': 'filmi',
        'qawwali': 'filmi', 'bhangra': 'filmi', 'punjabi': 'filmi',
        'tamil pop': 'filmi', 'telugu pop': 'filmi', 'marathi pop': 'filmi',
        'carnatic': 'indian classical', 'hindustani': 'indian classical',
        'indian indie': 'filmi', 'indian folk': 'filmi', 'indian rock': 'rock',
        'indian edm': 'edm', 'indian lo-fi': 'lo-fi', 'desi trap': 'hip hop',
        'desibeats': 'filmi',
        # Global regional genres
        'afrobeats': 'afrobeats', 'afropop': 'afrobeats', 'nigerian pop': 'afrobeats',
        'j-pop': 'j-pop', 'anime': 'anime', 'anime score': 'anime',
    }


    def __init__(self, parquet_path: str = "../data/tracks.parquet"):
        import pandas as pd
        import numpy as np
        import ast
        import re

        self._pd = pd
        self._np = np

        def resolve_path(path: str) -> str:
            if os.path.isabs(path) or os.path.exists(path):
                return path
            base_dir = os.path.dirname(os.path.abspath(__file__))
            candidates = [
                os.path.normpath(os.path.join(base_dir, path)),
                os.path.normpath(os.path.join(base_dir, "..", path)),
                os.path.normpath(os.path.join(base_dir, "..", "..", path)),
            ]
            for candidate in candidates:
                if os.path.exists(candidate):
                    return candidate
            return path

        parquet_path = resolve_path(parquet_path)

        # Load dataset
        if not os.path.exists(parquet_path):
            data_dir = os.path.dirname(parquet_path)
            part1 = os.path.join(data_dir, "tracks_part1.parquet")
            part2 = os.path.join(data_dir, "tracks_part2.parquet")
            if os.path.exists(part1) and os.path.exists(part2):
                df1 = pd.read_parquet(part1)
                df2 = pd.read_parquet(part2)
                df = pd.concat([df1, df2], ignore_index=True)
            else:
                raise FileNotFoundError(f"Cannot find {parquet_path} or split parts")
        else:
            df = pd.read_parquet(parquet_path)

        # Drop rows missing audio features (only ~478 out of 900K)
        df = df.dropna(subset=["energy", "valence", "danceability", "acousticness"])

        # --- Resolve artist names ---
        #Build a lookup table from tracks that DO have track_artists.
        # Key = (artist_popularity, genres, artist_followers) → artist name.
        # This resolves ~71% of the 800K tracks missing track_artists.
        has_artist_mask = df["track_artists"].notna()
        if has_artist_mask.any():
            has_artist_df = df[has_artist_mask].copy()
            has_artist_df["_artist_key"] = (
                has_artist_df["artist_popularity"].astype(str) + "|" +
                has_artist_df["genres"].astype(str) + "|" +
                has_artist_df["artist_followers"].astype(str)
            )
            # Build lookup: for each key, take the most common artist name, but only
            # trust it when that name is a clear majority of the bucket. Degenerate
            # keys (e.g. artist_popularity=0 + empty genres) collapse hundreds of
            # unrelated artists together, so blindly taking the mode there mislabels
            # every track sharing that key with whichever unrelated artist happens to
            # be most common.
            def resolve_bucket(names):
                counts = names.value_counts()
                winner, winner_count = counts.index[0], counts.iloc[0]
                if len(names) <= 3 or (winner_count / len(names)) >= 0.5:
                    return winner
                return None

            artist_lookup = has_artist_df.groupby("_artist_key")["track_artists"].agg(resolve_bucket)

            # Apply lookup to tracks missing track_artists
            no_artist_mask = df["track_artists"].isna()
            df.loc[no_artist_mask, "_artist_key"] = (
                df.loc[no_artist_mask, "artist_popularity"].astype(str) + "|" +
                df.loc[no_artist_mask, "genres"].astype(str) + "|" +
                df.loc[no_artist_mask, "artist_followers"].astype(str)
            )
            df.loc[no_artist_mask, "resolved_artist"] = (
                df.loc[no_artist_mask, "_artist_key"].map(artist_lookup)
            )
            df["resolved_artist"] = df["resolved_artist"].fillna(df["track_artists"])
            # Tracks that still can't be confidently resolved stay "Unknown Artist"
            # rather than being mislabeled with the album name, which is sometimes a
            # single-word/letter title (e.g. "D", "ME") that reads as a bogus artist.
            df["resolved_artist"] = df["resolved_artist"].fillna("Unknown Artist")
        else:
            df["resolved_artist"] = df["track_artists"].fillna("Unknown Artist")

        df["resolved_artist"] = df["resolved_artist"].astype(str).str.strip()
        df.loc[df["resolved_artist"].str.lower().isin(["nan", "none", ""]), "resolved_artist"] = "Unknown Artist"
        df["artist_lower"] = df["resolved_artist"].str.lower()

        # --- Resolve track name ---
        df["resolved_name"] = df["name"].fillna("Unknown Title").astype(str).str.strip()
        df.loc[df["resolved_name"].str.lower().isin(["nan", "none", ""]), "resolved_name"] = "Unknown Title"
        df["name_lower"] = df["resolved_name"].str.lower()

        # --- Parse genres from stringified lists ---
        def parse_genres(g):
            if pd.isna(g) or not g or str(g).strip() in ("", "[]", "nan", "None"):
                return set()
            g = str(g).strip()
            if g.startswith("["):
                try:
                    return set(str(x).lower().strip() for x in ast.literal_eval(g))
                except:
                    return set(x.strip(" '\"").lower() for x in g[1:-1].split(",") if x.strip())
            return {g.lower()}

        df["genre_set"] = df["genres"].apply(parse_genres)

        # --- Parse release year ---
        def extract_year(d):
            if pd.isna(d) or not d:
                return 2020  # default
            d = str(d).strip()
            if len(d) >= 4 and d[:4].isdigit():
                return int(d[:4])
            return 2020

        df["release_year"] = df["album_release_date"].apply(extract_year)

        # --- Fill NaN audio features with 0.0 ---
        for feat in self.AUDIO_FEATURES:
            if feat == "tempo_norm":
                # Normalize tempo to 0-1 range (50-200 BPM → 0-1)
                raw_tempo = pd.to_numeric(df.get("tempo", 120.0), errors="coerce").fillna(120.0)
                df["tempo_norm"] = ((raw_tempo - 50.0) / 150.0).clip(0, 1)
            elif feat in df.columns:
                df[feat] = pd.to_numeric(df[feat], errors="coerce").fillna(0.0)
            else:
                df[feat] = 0.0

        # --- Normalize popularity (track-level, with artist fallback) ---
        # Track popularity is more indicative of actual hits than artist-level
        track_pop = pd.to_numeric(df.get("popularity", 0), errors="coerce").fillna(0.0)
        artist_pop = pd.to_numeric(df.get("artist_popularity", 50.0), errors="coerce").fillna(50.0)
        df["norm_track_popularity"] = (track_pop / 100.0).clip(0, 1)
        df["norm_artist_popularity"] = (artist_pop / 100.0).clip(0, 1)
        # Retained for catalog sorting, where either form of popularity is useful.
        df["norm_popularity"] = np.maximum(track_pop, artist_pop) / 100.0

        # --- Build audio feature matrix ---
        self.df = df.reset_index(drop=True)
        self.audio_matrix = self.df[self.AUDIO_FEATURES].values.astype(np.float64)

        # Build deduplicated lookup for fuzzy search (unique song+artist combos)
        self._build_search_catalog()

    def _build_search_catalog(self):
        """
        Build deduplicated catalogs for fast fuzzy search.
        Keeps only the highest-popularity version of each song+artist pair.
        """
        import re

        df = self.df
        np = self._np

        # Normalize title for dedup: strip parentheticals, remix tags, etc.
        def norm_title(t):
            t = str(t).lower().strip()
            t = re.sub(r'\s*[\(\[].*?[\)\]]', '', t)
            t = re.sub(r'\s*-\s*(remix|remaster|radio edit|live|deluxe|bonus).*', '', t, flags=re.IGNORECASE)
            return t.strip()

        df["_norm_title"] = df["resolved_name"].apply(norm_title)
        df["_dedup_key"] = df["_norm_title"] + " || " + df["artist_lower"]

        # Keep highest popularity version of each song
        idx = df.groupby("_dedup_key")["norm_popularity"].idxmax()
        self.catalog = df.loc[idx].reset_index(drop=True)

        # Rebuild name/artist search lists from catalog
        self._catalog_names = list(self.catalog["resolved_name"])
        self._catalog_artists = list(self.catalog["resolved_artist"])
        self._catalog_names_lower = list(self.catalog["name_lower"])
        self._catalog_artists_lower = list(self.catalog["artist_lower"])

        # Unique artist list for artist search
        unique_artists = self.catalog.drop_duplicates(subset=["artist_lower"])
        self._unique_artists = list(unique_artists["resolved_artist"])
        self._unique_artists_lower = list(unique_artists["artist_lower"])

    def fuzzy_search_songs(self, query: str, limit: int = 15, score_cutoff: int = 55) -> List[Dict]:
        """
        Two-pass song search:
          Pass 1: Fast exact/substring match against title OR title+artist combo
          Pass 2: Fuzzy fallback for misspellings via rapidfuzz

        Handles single titles ("Starboy") and title+artist queries ("blinding lights the weeknd").
        """
        import re
        from rapidfuzz import fuzz, process

        query_lower = query.strip().lower()
        query_len = len(query_lower)

        # --- Exact / Substring match ---
        # match title exact or substring
        exact_mask = (self.catalog["name_lower"] == query_lower) | \
                     self.catalog["name_lower"].str.contains(query_lower, na=False, regex=False)

        # If no direct title match, try title + artist combinations in either order.
        if not exact_mask.any():
            combo = self.catalog["name_lower"] + " " + self.catalog["artist_lower"]
            exact_mask = combo.str.contains(query_lower, na=False, regex=False)
            if not exact_mask.any() and len(query_lower.split()) > 1:
                # "the weeknd starboy" and "starboy the weeknd" should resolve identically.
                exact_mask = self._pd.Series(True, index=self.catalog.index)
                for token in set(re.findall(r"\w+", query_lower)):
                    exact_mask &= combo.str.contains(rf"\b{re.escape(token)}\b", na=False, regex=True)

        if exact_mask.any():
            exact_df = self.catalog[exact_mask].copy()
            # Sort by highest norm_popularity, then track popularity
            pop_col = "popularity" if "popularity" in exact_df.columns else "norm_popularity"
            exact_df.sort_values(by=["norm_popularity", pop_col], ascending=[False, False], inplace=True)
            exact_df = exact_df.head(limit)

            matches = []
            seen = set()
            for _, row in exact_df.iterrows():
                dedup_key = row["_dedup_key"]
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)
                matches.append({
                    "catalog_idx": row.name,  # pandas index = catalog position
                    "name": row["resolved_name"],
                    "artist": row["resolved_artist"],
                    "album": str(row.get("album_name", "")),
                    "genres": row["genre_set"],
                    "popularity": row["norm_popularity"],
                    "year": row["release_year"],
                    "match_score": 100.0,
                })
            if matches:
                return matches[:limit]

        # --- Fuzzy fallback for misspellings ---
        scorer = fuzz.token_sort_ratio if len(query_lower.split()) > 1 else fuzz.WRatio

        results = process.extract(
            query_lower,
            self._catalog_names_lower,
            scorer=scorer,
            limit=limit * 10,
            score_cutoff=max(score_cutoff - 10, 40)
        )

        seen = set()
        matches = []
        for match_str, score, idx in results:
            match_len = len(match_str)
            if query_len > 4 and match_len < query_len * 0.4:
                continue

            secondary_score = fuzz.token_set_ratio(query_lower, match_str)
            combined_score = (score * 0.6) + (secondary_score * 0.4)

            if combined_score < score_cutoff:
                continue

            row = self.catalog.iloc[idx]
            dedup_key = row["_dedup_key"]
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            matches.append({
                "catalog_idx": idx,
                "name": row["resolved_name"],
                "artist": row["resolved_artist"],
                "album": str(row.get("album_name", "")),
                "genres": row["genre_set"],
                "popularity": row["norm_popularity"],
                "year": row["release_year"],
                "match_score": combined_score,
            })
            if len(matches) >= limit * 3:
                break

        # Sort by fuzzy score desc, then popularity desc, then trim
        matches.sort(key=lambda x: (-x["match_score"], -x["popularity"]))

        # Post-pass: ensure highest popularity version is included
        if matches:
            top_names = set(m["name"].lower() for m in matches[:5])

            for name_lower in top_names:
                exact_mask = self.catalog["name_lower"] == name_lower
                if exact_mask.any():
                    best_row = self.catalog[exact_mask].sort_values(
                        "norm_popularity", ascending=False
                    ).iloc[0]
                    dedup_key = best_row["_dedup_key"]
                    if not any(m.get("_dk") == dedup_key or
                              (m["name"] == best_row["resolved_name"] and
                               m["artist"] == best_row["resolved_artist"])
                              for m in matches):
                        matches.append({
                            "catalog_idx": best_row.name,
                            "name": best_row["resolved_name"],
                            "artist": best_row["resolved_artist"],
                            "album": str(best_row.get("album_name", "")),
                            "genres": best_row["genre_set"],
                            "popularity": best_row["norm_popularity"],
                            "year": best_row["release_year"],
                            "match_score": matches[0]["match_score"],
                        })

            matches.sort(key=lambda x: (-x["match_score"], -x["popularity"]))

        return matches[:limit]

    def fuzzy_search_artists(self, query: str, limit: int = 10, score_cutoff: int = 55) -> List[str]:
        """
        Fuzzy search for artist names. Returns list of matched artist names.
        Uses partial_ratio to handle substring matching.
        """
        from rapidfuzz import process, fuzz

        query_lower = query.strip().lower()

        results = process.extract(
            query_lower,
            self._unique_artists_lower,
            scorer=fuzz.partial_ratio,
            limit=limit * 3,
            score_cutoff=score_cutoff
        )

        scored = []
        for match_str, partial_score, idx in results:
            wratio = fuzz.WRatio(query_lower, match_str)
            combined = (wratio * 0.4) + (partial_score * 0.6)
            len_ratio = min(len(query_lower), len(match_str)) / max(len(query_lower), len(match_str), 1)
            combined += len_ratio * 5
            scored.append((self._unique_artists[idx], combined))

        scored.sort(key=lambda x: -x[1])
        return [name for name, _ in scored[:limit]]

    def get_artist_tracks(self, artist_name: str, limit: int = 15) -> List[Dict]:
        """
        Get top tracks by a specific artist, sorted by track popularity.
        """
        artist_lower = artist_name.strip().lower()
        exact_mask = self.catalog["artist_lower"] == artist_lower
        contains_mask = self.catalog["artist_lower"].str.contains(artist_lower, regex=False, na=False)

        artist_df = self.catalog[exact_mask | contains_mask].copy()
        if artist_df.empty:
            return []

        # Sort by norm_popularity desc, then popularity desc
        pop_col = "popularity" if "popularity" in artist_df.columns else "norm_popularity"
        artist_df.sort_values(by=["norm_popularity", pop_col], ascending=[False, False], inplace=True)
        artist_df = artist_df.head(limit)

        tracks = []
        for _, row in artist_df.iterrows():
            tracks.append({
                "catalog_idx": row.name if hasattr(row, 'name') else 0,
                "name": row["resolved_name"],
                "artist": row["resolved_artist"],
                "album": str(row.get("album_name", "")),
                "genres": row["genre_set"],
                "popularity": row["norm_popularity"],
                "year": row["release_year"],
            })
        return tracks

    def recommend(self, seed_catalog_idx: int, k: int = 15, max_per_artist: int = 3,
                  max_per_other_artist: int = None, weights: Dict[str, float] = None,
                  exclude_seed_artists: bool = False,
                  cap_unknown_artists: bool = False) -> List[Dict]:
        """Generate recommendations from one selected catalog track."""
        return self.recommend_from_seeds(
            [seed_catalog_idx], k=k, max_per_artist=max_per_artist,
            max_per_other_artist=max_per_other_artist,
            weights=weights,
            exclude_seed_artists=exclude_seed_artists,
            cap_unknown_artists=cap_unknown_artists,
        )

    def recommend_from_seeds(self, seed_catalog_indices: List[int], k: int = 15,
                             max_per_artist: int = 3, max_per_other_artist: int = None,
                             weights: Dict[str, float] = None,
                             exclude_seed_artists: bool = False,
                             cap_unknown_artists: bool = False) -> List[Dict]:
        """Generate playlist radio from one or more catalog tracks.

        Seed vectors are averaged into an 8D centroid. Genre and artist affinity
        are calculated against the union of the selected seed metadata.

        max_per_artist caps tracks by the seed artist(s) themselves (deep cuts from
        the artist you searched for). max_per_other_artist caps every other artist;
        it defaults to max_per_artist when not given. Keeping it lower than
        max_per_artist (e.g. 1) prevents a couple of genre-clique artists from
        eating most of the result list and crowding out variety.
        """
        import re

        np = self._np
        if not seed_catalog_indices:
            raise ValueError("seed_catalog_indices cannot be empty")
        if k <= 0:
            return []

        seed_rows = self.catalog.iloc[seed_catalog_indices]
        if getattr(seed_rows, "ndim", 1) == 1:
            seed_rows = seed_rows.to_frame().T

        def main_index(seed_row):
            track_id = seed_row.get("track_id", None)
            if track_id is not None and str(track_id) != "nan":
                match = self.df["track_id"] == track_id
            else:
                match = ((self.df["name_lower"] == seed_row["name_lower"]) &
                         (self.df["artist_lower"] == seed_row["artist_lower"]))
            if not match.any():
                raise ValueError("Selected seed track is not present in the full catalog")
            return int(self.df[match].index[0])

        seed_df_indices = [main_index(row) for _, row in seed_rows.iterrows()]
        seed_vector = self.audio_matrix[seed_df_indices].mean(axis=0, keepdims=True)
        seed_genres = set().union(*seed_rows["genre_set"])
        seed_artists = set(seed_rows["artist_lower"])

        selected_weights = dict(self.SCORING_PRESETS["similar"])
        if weights:
            unknown = set(weights) - set(selected_weights)
            if unknown:
                raise ValueError(f"Unknown scoring weights: {sorted(unknown)}")
            selected_weights.update(weights)
        total_weight = sum(selected_weights.values())
        if total_weight <= 0:
            raise ValueError("At least one scoring weight must be positive")
        selected_weights = {key: value / total_weight for key, value in selected_weights.items()}

        distances = np.sqrt(np.sum((self.audio_matrix - seed_vector) ** 2, axis=1))
        audio_sims = np.clip(1.0 - distances / np.sqrt(len(self.AUDIO_FEATURES)), 0, 1)

        def base_genres(genre_set):
            result = set()
            for genre in genre_set:
                label = genre.lower().strip()
                if label in self.BASE_GENRE_MAP:
                    result.add(self.BASE_GENRE_MAP[label])
                    continue
                matched = False
                for subgenre, parent in self.BASE_GENRE_MAP.items():
                    if subgenre == label or f" {subgenre}" in label or f"{subgenre} " in label:
                        result.add(parent)
                        matched = True
                        break
                if not matched:
                    result.add(label)
            return result

        seed_base_genres = base_genres(seed_genres)
        genre_sims = np.zeros(len(self.df), dtype=np.float64)
        for i, candidate_genres in enumerate(self.df["genre_set"]):
            candidate_base = base_genres(candidate_genres)
            if (seed_base_genres & candidate_base) or (seed_genres & candidate_genres):
                # Base-genre bucket match is a floor (0.55); the rest is earned by how
                # many exact subgenre tags the candidate shares with the seed, so a
                # same-bucket-but-unrelated subgenre (e.g. dance pop vs. pop rock,
                # both -> "pop") doesn't score identically to a close subgenre match.
                union = seed_genres | candidate_genres
                jaccard = len(seed_genres & candidate_genres) / len(union) if union else 0.0
                genre_sims[i] = 0.55 + 0.45 * jaccard

        artist_values = self.df["artist_lower"].values
        artist_sims = np.isin(artist_values, list(seed_artists)).astype(np.float64)
        for i, artist in enumerate(artist_values):
            if artist_sims[i] == 0 and any(seed in str(artist) or str(artist) in seed for seed in seed_artists):
                artist_sims[i] = 0.5

        seed_years = seed_rows["release_year"].dropna().astype(float).values
        if len(seed_years) > 0:
            seed_year = np.mean(seed_years)
            candidate_years = self.df["release_year"].fillna(seed_year).astype(float).values
            year_diffs = np.abs(candidate_years - seed_year)
            era_sims = np.clip(1.0 - (year_diffs / 10.0), 0, 1)
        else:
            era_sims = np.zeros(len(self.df), dtype=np.float64)

        pop_scores = (
            self.df["norm_track_popularity"].values.astype(np.float64) * 0.75 +
            self.df["norm_artist_popularity"].values.astype(np.float64) * 0.25
        )
        contributions = {
            "audio": selected_weights.get("audio", 0) * audio_sims,
            "popularity": selected_weights.get("popularity", 0) * pop_scores,
            "genre": selected_weights.get("genre", 0) * genre_sims,
            "artist": selected_weights.get("artist", 0) * artist_sims,
            "era": selected_weights.get("era", 0) * era_sims,
        }
        final_scores = sum(contributions.values())

        def normalized_title(title):
            title = str(title).lower().strip()
            title = re.sub(r'\s*[\(\[].*?[\)\]]', '', title)
            return re.sub(r'\s*-\s*(remix|remaster|radio edit|live|deluxe|bonus).*', '', title, flags=re.I).strip()

        seed_keys = {
            f"{normalized_title(row['resolved_name'])} || {row['artist_lower']}"
            for _, row in seed_rows.iterrows()
        }
        seen_keys = set(seed_keys)
        artist_counts = {}
        results = []
        other_artist_cap = max_per_artist if max_per_other_artist is None else max_per_other_artist

        def add_result(index):
            row = self.df.iloc[int(index)]
            artist = str(row["artist_lower"])
            key = f"{normalized_title(row['resolved_name'])} || {artist}"
            if key in seen_keys:
                return False
            if exclude_seed_artists and artist in seed_artists:
                return False
            should_cap_artist = artist != "unknown artist" or cap_unknown_artists
            artist_cap = max_per_artist if artist in seed_artists else other_artist_cap
            if artist_cap > 0 and should_cap_artist and artist_counts.get(artist, 0) >= artist_cap:
                return False
            seen_keys.add(key)
            if should_cap_artist:
                artist_counts[artist] = artist_counts.get(artist, 0) + 1
            breakdown = {name: float(values[int(index)]) for name, values in contributions.items()}
            explanation = (
                f"Audio {audio_sims[int(index)]:.2f} ({breakdown['audio']:.2f}); "
                f"Popularity {pop_scores[int(index)]:.2f} ({breakdown['popularity']:.2f}); "
                f"Genre {genre_sims[int(index)]:.2f} ({breakdown['genre']:.2f}); "
                f"Artist {artist_sims[int(index)]:.2f} ({breakdown['artist']:.2f})"
            )
            if 'era' in breakdown and breakdown['era'] > 0:
                explanation += f"; Era {era_sims[int(index)]:.2f} ({breakdown['era']:.2f})"
            results.append({
                "name": str(row["resolved_name"]), "artist": str(row["resolved_artist"]),
                "album": str(row.get("album_name", "")), "score": float(final_scores[int(index)]),
                "explanation": explanation, "audio_sim": float(audio_sims[int(index)]),
                "genre_sim": float(genre_sims[int(index)]), "artist_sim": float(artist_sims[int(index)]),
                "pop_score": float(pop_scores[int(index)]), "contributions": breakdown,
            })
            return True

        for index in np.argsort(-final_scores):
            if len(results) >= k:
                break
            add_result(index)
        return results
