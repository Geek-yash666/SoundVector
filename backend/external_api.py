#!/usr/bin/env python3
"""
SoundVector Live External API Integrations (Deezer, iTunes, Last.fm)
Optimized: parallel fetches, bounded caches, early-exit, retry logic.
"""

import json
import os
import re
import ssl
import urllib.parse
import urllib.request
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed, wait, FIRST_COMPLETED
from typing import Dict, List, Optional

import asyncio

# ---------------------------------------------------------------------------
# Bounded LRU Cache (thread-safe via OrderedDict + size cap)
# ---------------------------------------------------------------------------

class _BoundedCache:
    """Thread-unsafe bounded dict (GIL protects simple dict ops on CPython)."""
    def __init__(self, maxsize: int = 5000):
        self._data: OrderedDict = OrderedDict()
        self._maxsize = maxsize

    def get(self, key, default=None):
        if key in self._data:
            self._data.move_to_end(key)
            return self._data[key]
        return default

    def __contains__(self, key):
        return key in self._data

    def __getitem__(self, key):
        self._data.move_to_end(key)
        return self._data[key]

    def __setitem__(self, key, value):
        if key in self._data:
            self._data.move_to_end(key)
        self._data[key] = value
        if len(self._data) > self._maxsize:
            self._data.popitem(last=False)

    def __len__(self):
        return len(self._data)


_ARTIST_IMAGE_CACHE: _BoundedCache = _BoundedCache(maxsize=2000)
_ENRICH_CACHE: _BoundedCache = _BoundedCache(maxsize=5000)
_LIVE_SEARCH_CACHE: _BoundedCache = _BoundedCache(maxsize=1000)
_LIVE_ALBUM_CACHE: _BoundedCache = _BoundedCache(maxsize=500)

# Shared thread-pool for external HTTP calls — reuse across requests
_HTTP_POOL = ThreadPoolExecutor(max_workers=16, thread_name_prefix="sv_http")


# ---------------------------------------------------------------------------
# Low-level HTTP helper
# ---------------------------------------------------------------------------

def _fetch_json(url: str, timeout: int = 5, retries: int = 1) -> Optional[dict]:
    """Fetch a JSON URL with timeout + 1 retry; returns None on failure."""
    import time as _time
    ctx = ssl._create_unverified_context()
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/121.0.0.0 Safari/537.36"
        )
    }
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            if attempt < retries:
                _time.sleep(0.3)
    return None


# ---------------------------------------------------------------------------
# Artist Image
# ---------------------------------------------------------------------------

def get_artist_image(artist_name: str) -> str:
    """Fetch high-resolution artist image from Deezer/iTunes (CORS-proxy bypass)."""
    if not artist_name:
        return ""
    key = artist_name.lower().strip()
    cached = _ARTIST_IMAGE_CACHE.get(key)
    if cached is not None:
        return cached

    img = ""
    try:
        q = urllib.parse.quote(artist_name)
        d_data = _fetch_json(f"https://api.deezer.com/search/artist?q={q}&limit=1")
        if d_data and d_data.get("data") and d_data["data"][0].get("picture_big"):
            img = d_data["data"][0]["picture_big"]
    except Exception:
        pass

    if not img:
        try:
            q = urllib.parse.quote(artist_name)
            it_data = _fetch_json(f"https://itunes.apple.com/search?term={q}&entity=song&limit=1")
            if it_data and it_data.get("results") and it_data["results"][0].get("artworkUrl100"):
                img = it_data["results"][0]["artworkUrl100"].replace("100x100bb", "300x300bb")
        except Exception:
            pass

    _ARTIST_IMAGE_CACHE[key] = img
    return img


# ---------------------------------------------------------------------------
# Track Enrichment (Parallel Deezer + iTunes)
# ---------------------------------------------------------------------------

def _build_clean_names(track_name: str, artist_name: str):
    """Return (primary_artist, clean_track) ready for API queries."""
    primary_artist = re.split(r'[,&/]|feat\.?|ft\.?', artist_name, flags=re.IGNORECASE)[0].strip()
    primary_artist_clean = re.sub(r'[?!:;"\'`-]', ' ', primary_artist)
    primary_artist_clean = re.sub(r'\s+', ' ', primary_artist_clean).strip() or artist_name

    clean_track = track_name.split(' - ')[0].strip()
    clean_track = re.sub(r'\s*\([^)]*\)', '', clean_track)
    clean_track = re.sub(r'\s*\[[^\]]*\]', '', clean_track)
    if primary_artist and primary_artist.lower() in clean_track.lower():
        pattern = re.compile(r'\s*' + re.escape(primary_artist) + r'\s*$', re.IGNORECASE)
        clean_track = pattern.sub('', clean_track.strip()).strip()
    clean_track = re.sub(r'[?!:;"\'`-]', ' ', clean_track)
    clean_track = re.sub(r'\s+', ' ', clean_track).strip()
    if not clean_track:
        clean_track = track_name.split('(')[0].split('[')[0].split('-')[0].strip()

    return primary_artist_clean, clean_track


def _fetch_deezer_enrichment(primary_artist: str, clean_track: str) -> dict:
    """Fetch track metadata from Deezer (preview, link, album art)."""
    result = {}
    try:
        deezer_q = urllib.parse.quote(f"{primary_artist} {clean_track}")
        deezer_data = _fetch_json(f"https://api.deezer.com/search?q={deezer_q}&limit=5&output=json")
        if not (deezer_data and deezer_data.get("data")):
            deezer_q2 = urllib.parse.quote(clean_track)
            deezer_data = _fetch_json(f"https://api.deezer.com/search?q={deezer_q2}&limit=5&output=json")
        if deezer_data and deezer_data.get("data"):
            hit = deezer_data["data"][0]
            for h in deezer_data["data"]:
                if h.get("preview"):
                    hit = h
                    break
            result["deezer_preview_url"] = hit.get("preview") or ""
            result["deezer_link"] = hit.get("link") or ""
            result["deezer_album_art"] = (hit.get("album") or {}).get("cover_medium") or ""
            result["deezer_album_name"] = (hit.get("album") or {}).get("title") or ""
            result["deezer_id"] = hit.get("id") or ""
    except Exception:
        pass
    return result


def _fetch_itunes_enrichment(primary_artist: str, clean_track: str) -> dict:
    """Fetch track metadata from iTunes (preview URL, album art, store link)."""
    result = {}
    try:
        it_q = urllib.parse.quote(f"{primary_artist} {clean_track}")
        it_data = _fetch_json(f"https://itunes.apple.com/search?term={it_q}&entity=song&limit=5")
        if not (it_data and it_data.get("results")):
            it_q2 = urllib.parse.quote(clean_track)
            it_data = _fetch_json(f"https://itunes.apple.com/search?term={it_q2}&entity=song&limit=5")
        if it_data and it_data.get("results"):
            for h in it_data["results"]:
                if h.get("previewUrl"):
                    result["itunes_preview_url"] = h["previewUrl"]
                    break
            best = it_data["results"][0]
            result["itunes_album_art"] = (best.get("artworkUrl100") or "").replace("100x100bb", "300x300bb")
            result["itunes_link"] = best.get("trackViewUrl") or ""
    except Exception:
        pass
    return result


def enrich_track(track_name: str, artist_name: str, lastfm_key: Optional[str] = None) -> dict:
    """Enrich a track with Deezer preview, YouTube Music link, and iTunes data.
    Runs Deezer + iTunes fetches in PARALLEL for 2x speedup.
    Always caches result (even partial) to prevent repeat calls.
    """
    if not track_name or not artist_name:
        return {}
    cache_key = f"{track_name.lower().strip()}||{artist_name.lower().strip()}"
    cached = _ENRICH_CACHE.get(cache_key)
    if cached is not None:
        return cached

    primary_artist, clean_track = _build_clean_names(track_name, artist_name)

    # YouTube Music URL is always free to compute — no network needed
    yt_q = urllib.parse.quote(f"{primary_artist} {clean_track}")
    result: dict = {
        "youtube_music_url": f"https://music.youtube.com/search?q={yt_q}",
        "youtube_url": f"https://www.youtube.com/results?search_query={yt_q}",
    }

    # Fetch Deezer + iTunes in PARALLEL
    futures = {
        _HTTP_POOL.submit(_fetch_deezer_enrichment, primary_artist, clean_track): "deezer",
        _HTTP_POOL.submit(_fetch_itunes_enrichment, primary_artist, clean_track): "itunes",
    }
    deezer_result = {}
    itunes_result = {}
    for future in as_completed(futures, timeout=6):
        src = futures[future]
        try:
            data = future.result()
            if src == "deezer":
                deezer_result = data
            else:
                itunes_result = data
        except Exception:
            pass

    # Merge: prefer Deezer, fall back to iTunes for missing fields
    result.update(deezer_result)
    if not result.get("deezer_preview_url") and itunes_result.get("itunes_preview_url"):
        result["deezer_preview_url"] = itunes_result["itunes_preview_url"]
    if not result.get("deezer_album_art") and itunes_result.get("itunes_album_art"):
        result["deezer_album_art"] = itunes_result["itunes_album_art"]
    if not result.get("deezer_link") and itunes_result.get("itunes_link"):
        result["deezer_link"] = itunes_result["itunes_link"]

    # Always cache (even if only YouTube link) to prevent repeat network calls
    _ENRICH_CACHE[cache_key] = result
    return result


# ---------------------------------------------------------------------------
# Async Batch Enrichment
# ---------------------------------------------------------------------------

async def async_enrich_track(track: dict, lastfm_key: Optional[str] = None) -> dict:
    """Asynchronously enrich a single track object in threadpool."""
    if not track or not isinstance(track, dict):
        return track
    if track.get("deezer_album_art") and track.get("deezer_preview_url"):
        return track

    tname = track.get("name", "")
    aname = track.get("artist", "")
    if not tname or not aname:
        return track

    loop = asyncio.get_event_loop()
    try:
        enriched = await loop.run_in_executor(_HTTP_POOL, enrich_track, tname, aname, lastfm_key)
        if enriched and isinstance(enriched, dict):
            for k, v in enriched.items():
                if v and not track.get(k):
                    track[k] = v
    except Exception:
        pass
    return track


async def async_batch_enrich(tracks: List[dict], lastfm_key: Optional[str] = None) -> List[dict]:
    """Concurrently batch-enrich a list of tracks in 1 single pass.
    Skips tracks that are already fully enriched (cache hit).
    """
    if not tracks:
        return []

    # Only enrich tracks that actually need it
    needs_enrich = [t for t in tracks if isinstance(t, dict) and not (
        t.get("deezer_album_art") and t.get("deezer_preview_url")
    )]

    if needs_enrich:
        tasks = [async_enrich_track(t, lastfm_key) for t in needs_enrich]
        await asyncio.gather(*tasks, return_exceptions=True)

    return tracks


# ---------------------------------------------------------------------------
# Search Query Cleaner
# ---------------------------------------------------------------------------

def _clean_search_query(query: str) -> str:
    """Strip 4-digit release years and fluff words for fallback API searches."""
    if not query:
        return ""
    q = re.sub(r'\b(19|20)\d{2}\b', '', query, flags=re.IGNORECASE)
    q = re.sub(r'\b(movie|album|soundtrack|ost|songs|song|track|tracks|full)\b', '', q, flags=re.IGNORECASE)
    q = re.sub(r'\s+', ' ', q).strip()
    return q


# ---------------------------------------------------------------------------
# Live Track Search (Parallel iTunes + Deezer + LastFM)
# ---------------------------------------------------------------------------

def _search_itunes_tracks(q_str: str, limit: int) -> List[dict]:
    """Search iTunes for tracks matching query."""
    hits = []
    try:
        it_q = urllib.parse.quote(q_str)
        it_data = _fetch_json(f"https://itunes.apple.com/search?term={it_q}&entity=song&limit={limit}")
        if it_data and it_data.get("results"):
            for item in it_data["results"]:
                tname = item.get("trackName", "")
                aname = item.get("artistName", "")
                if not tname or not aname:
                    continue
                art = (item.get("artworkUrl100") or "").replace("100x100bb", "300x300bb")
                yt_q = urllib.parse.quote(f"{aname} {tname}")
                hits.append({
                    "row": -1,
                    "track_id": f"live_itunes_{item.get('trackId')}",
                    "name": tname,
                    "artist": aname,
                    "year": str(item.get("releaseDate", "2024"))[:4],
                    "popularity_pct": 95,
                    "base_genres": [(item.get("primaryGenreName") or "pop").lower()],
                    "energy": 0.70, "valence": 0.65, "danceability": 0.70, "tempo_bpm": 120,
                    "deezer_preview_url": item.get("previewUrl") or "",
                    "deezer_album_art": art,
                    "deezer_link": item.get("trackViewUrl") or "",
                    "youtube_music_url": f"https://music.youtube.com/search?q={yt_q}",
                    "is_live_external": True
                })
    except Exception:
        pass
    return hits


def _search_deezer_tracks(q_str: str, limit: int) -> List[dict]:
    """Search Deezer for tracks matching query."""
    hits = []
    try:
        dz_q = urllib.parse.quote(q_str)
        dz_data = _fetch_json(f"https://api.deezer.com/search?q={dz_q}&limit={limit}")
        if dz_data and dz_data.get("data"):
            for item in dz_data["data"]:
                tname = item.get("title", "")
                aname = (item.get("artist") or {}).get("name", "")
                if not tname or not aname:
                    continue
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
                    "energy": 0.70, "valence": 0.65, "danceability": 0.70, "tempo_bpm": 120,
                    "deezer_preview_url": item.get("preview") or "",
                    "deezer_album_art": art,
                    "deezer_link": item.get("link") or "",
                    "youtube_music_url": f"https://music.youtube.com/search?q={yt_q}",
                    "is_live_external": True
                })
    except Exception:
        pass
    return hits


def _search_lastfm_tracks(q_str: str, limit: int, lfm_key: str) -> List[dict]:
    """Search Last.fm for tracks matching query."""
    hits = []
    try:
        lf_q = urllib.parse.quote(q_str)
        lf_data = _fetch_json(
            f"http://ws.audioscrobbler.com/2.0/?method=track.search&track={lf_q}"
            f"&api_key={lfm_key}&format=json&limit={limit}"
        )
        if lf_data and (lf_data.get("results") or {}).get("trackmatches", {}).get("track"):
            for item in lf_data["results"]["trackmatches"]["track"]:
                tname = item.get("name", "")
                aname = item.get("artist", "")
                if not tname or not aname:
                    continue
                yt_q = urllib.parse.quote(f"{aname} {tname}")
                img_url = ""
                imgs = item.get("image")
                if isinstance(imgs, list) and imgs:
                    img_url = imgs[-1].get("#text", "")
                hits.append({
                    "row": -1,
                    "track_id": f"live_lastfm_{urllib.parse.quote(tname)}",
                    "name": tname,
                    "artist": aname,
                    "year": "2024",
                    "popularity_pct": 85,
                    "base_genres": ["pop"],
                    "energy": 0.70, "valence": 0.65, "danceability": 0.70, "tempo_bpm": 120,
                    "deezer_preview_url": "",
                    "deezer_album_art": img_url,
                    "deezer_link": item.get("url") or "",
                    "youtube_music_url": f"https://music.youtube.com/search?q={yt_q}",
                    "is_live_external": True,
                    "source": "lastfm"
                })
    except Exception:
        pass
    return hits


def search_live_apis(query: str, limit: int = 5) -> List[dict]:
    """Search iTunes & Deezer & Last.fm in PARALLEL for out-of-index songs."""
    if not query or len(query.strip()) < 2:
        return []
    q_clean = query.strip()
    cache_key = f"{q_clean.lower()}||{limit}"
    cached = _LIVE_SEARCH_CACHE.get(cache_key)
    if cached is not None:
        return cached

    lfm_key = os.environ.get("LASTFM_API_KEY", "")

    # Submit all 3 searches in parallel
    futures = [
        _HTTP_POOL.submit(_search_itunes_tracks, q_clean, limit),
        _HTTP_POOL.submit(_search_deezer_tracks, q_clean, limit),
    ]
    if lfm_key:
        futures.append(_HTTP_POOL.submit(_search_lastfm_tracks, q_clean, limit, lfm_key))

    all_hits: List[dict] = []
    seen: set = set()
    for future in as_completed(futures, timeout=5):
        try:
            for hit in future.result():
                key = f"{hit['name'].lower().strip()}||{hit['artist'].lower().strip()}"
                if key not in seen:
                    seen.add(key)
                    all_hits.append(hit)
        except Exception:
            pass

    out_hits = all_hits[:limit]
    _LIVE_SEARCH_CACHE[cache_key] = out_hits
    return out_hits


# ---------------------------------------------------------------------------
# Live Album Search (Parallel Deezer + iTunes + LastFM)
# ---------------------------------------------------------------------------

def _search_deezer_albums(q_str: str, limit: int) -> List[dict]:
    albums = []
    try:
        d_q = urllib.parse.quote(q_str)
        d_data = _fetch_json(f"https://api.deezer.com/search/album?q={d_q}&limit={limit}")
        if d_data and d_data.get("data"):
            for item in d_data["data"]:
                atitle = item.get("title", "")
                if not atitle:
                    continue
                aname = (item.get("artist") or {}).get("name", "")
                aid = item.get("id")
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
    return albums


def _search_itunes_albums(q_str: str, limit: int) -> List[dict]:
    albums = []
    try:
        it_q = urllib.parse.quote(q_str)
        it_data = _fetch_json(f"https://itunes.apple.com/search?term={it_q}&entity=album&limit={limit}")
        if it_data and it_data.get("results"):
            for item in it_data["results"]:
                atitle = item.get("collectionName", "")
                if not atitle:
                    continue
                aname = item.get("artistName", "")
                aid = item.get("collectionId")
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
    return albums


def _search_lastfm_albums(q_str: str, limit: int, lfm_key: str) -> List[dict]:
    albums = []
    try:
        lf_q = urllib.parse.quote(q_str)
        lf_data = _fetch_json(
            f"http://ws.audioscrobbler.com/2.0/?method=album.search&album={lf_q}"
            f"&api_key={lfm_key}&format=json&limit={limit}"
        )
        if lf_data and (lf_data.get("results") or {}).get("albummatches", {}).get("album"):
            for item in lf_data["results"]["albummatches"]["album"]:
                atitle = item.get("name", "")
                if not atitle:
                    continue
                aname = item.get("artist", "")
                img_url = ""
                imgs = item.get("image")
                if isinstance(imgs, list) and imgs:
                    img_url = imgs[-1].get("#text", "")
                albums.append({
                    "id": f"lfm_{urllib.parse.quote(atitle)}",
                    "title": atitle,
                    "artist": aname,
                    "cover_art": img_url,
                    "track_count": 0,
                    "year": "2024",
                    "source": "lastfm"
                })
    except Exception:
        pass
    return albums


def search_live_albums(query: str, limit: int = 4) -> List[dict]:
    """Search iTunes & Deezer for album/soundtrack releases matching query (PARALLEL)."""
    if not query or len(query.strip()) < 2:
        return []
    q_clean = query.strip()
    cache_key = f"{q_clean.lower()}||{limit}"
    cached = _LIVE_ALBUM_CACHE.get(cache_key)
    if cached is not None:
        return cached

    lfm_key = os.environ.get("LASTFM_API_KEY", "")
    futures = [
        _HTTP_POOL.submit(_search_deezer_albums, q_clean, limit),
        _HTTP_POOL.submit(_search_itunes_albums, q_clean, limit),
    ]
    if lfm_key:
        futures.append(_HTTP_POOL.submit(_search_lastfm_albums, q_clean, limit, lfm_key))

    albums: List[dict] = []
    seen: set = set()
    for future in as_completed(futures, timeout=5):
        try:
            for alb in future.result():
                key = alb["title"].lower().strip()
                if key not in seen:
                    seen.add(key)
                    albums.append(alb)
        except Exception:
            pass

    if not albums:
        cleaned_q = _clean_search_query(q_clean)
        if cleaned_q and cleaned_q.lower() != q_clean.lower():
            return search_live_albums(cleaned_q, limit)

    out_albums = albums[:limit]
    _LIVE_ALBUM_CACHE[cache_key] = out_albums
    return out_albums


# ---------------------------------------------------------------------------
# Album Tracks Fetcher
# ---------------------------------------------------------------------------

def fetch_album_tracks(album_title: str, artist_name: str = "", album_id: str = "",
                       source: str = "", engine=None) -> dict:
    """Fetch all tracks for a specific album/movie soundtrack."""
    tracks = []
    cover_art = ""
    artist = artist_name or "Various Artists"

    if album_id and (source == "deezer" or not source):
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
                        "row": -1, "name": tname, "artist": tar,
                        "year": str(d_data.get("release_date", ""))[:4] or "2024",
                        "popularity_pct": 88,
                        "base_genres": ["soundtrack", "pop"],
                        "energy": 0.65, "valence": 0.60, "danceability": 0.65, "tempo_bpm": 120,
                        "deezer_preview_url": tr.get("preview") or "",
                        "deezer_album_art": cover_art,
                        "deezer_link": tr.get("link") or "",
                        "youtube_music_url": f"https://music.youtube.com/search?q={yt_q}",
                        "is_live_external": True
                    })
        except Exception:
            pass

    if len(tracks) < 2:
        try:
            if source == "itunes" and album_id:
                it_data = _fetch_json(f"https://itunes.apple.com/lookup?id={album_id}&entity=song")
            else:
                it_q = urllib.parse.quote(f"{album_title} {artist_name}".strip())
                it_data = _fetch_json(f"https://itunes.apple.com/search?term={it_q}&entity=song&limit=25")

            if it_data and it_data.get("results"):
                for tr in it_data["results"]:
                    tname = tr.get("trackName", "")
                    if not tname:
                        continue
                    col_name = (tr.get("collectionName") or "").lower()
                    if source == "itunes" or album_title.lower() in col_name or not cover_art:
                        if not cover_art:
                            cover_art = (tr.get("artworkUrl100") or "").replace("100x100bb", "300x300bb")
                        tar = tr.get("artistName", "")
                        yt_q = urllib.parse.quote(f"{tar} {tname}")
                        tracks.append({
                            "row": -1, "name": tname, "artist": tar,
                            "year": str(tr.get("releaseDate", ""))[:4] or "2024",
                            "popularity_pct": 85,
                            "base_genres": [(tr.get("primaryGenreName") or "pop").lower()],
                            "energy": 0.65, "valence": 0.60, "danceability": 0.65, "tempo_bpm": 120,
                            "deezer_preview_url": tr.get("previewUrl") or "",
                            "deezer_album_art": (tr.get("artworkUrl100") or "").replace("100x100bb", "300x300bb"),
                            "deezer_link": tr.get("trackViewUrl") or "",
                            "youtube_music_url": f"https://music.youtube.com/search?q={yt_q}",
                            "is_live_external": True
                        })
        except Exception:
            pass

    if len(tracks) < 2:
        try:
            lfm_key = os.environ.get("LASTFM_API_KEY")
            if lfm_key:
                lf_q = urllib.parse.quote(f"{artist_name}".strip())
                lf_a = urllib.parse.quote(f"{album_title}".strip())
                lf_data = _fetch_json(
                    f"http://ws.audioscrobbler.com/2.0/?method=album.getinfo"
                    f"&api_key={lfm_key}&artist={lf_q}&album={lf_a}&format=json"
                )
                if lf_data and lf_data.get("album") and lf_data["album"].get("tracks") and \
                        lf_data["album"]["tracks"].get("track"):
                    for tr in lf_data["album"]["tracks"]["track"]:
                        tname = tr.get("name", "")
                        if not tname:
                            continue
                        tar = (tr.get("artist") or {}).get("name") or artist_name
                        yt_q = urllib.parse.quote(f"{tar} {tname}")
                        tracks.append({
                            "row": -1, "name": tname, "artist": tar,
                            "year": "2024", "popularity_pct": 80,
                            "base_genres": ["pop"],
                            "energy": 0.65, "valence": 0.60, "danceability": 0.65, "tempo_bpm": 120,
                            "deezer_preview_url": "",
                            "deezer_album_art": cover_art,
                            "deezer_link": tr.get("url") or "",
                            "youtube_music_url": f"https://music.youtube.com/search?q={yt_q}",
                            "is_live_external": True, "source": "lastfm"
                        })
        except Exception:
            pass

    return {"title": album_title, "artist": artist, "cover_art": cover_art, "tracks": tracks}


# ---------------------------------------------------------------------------
# Artist Last.fm Info (Parallel artist.getinfo + artist.gettoptracks)
# ---------------------------------------------------------------------------

def enrich_artist_lastfm(artist_name: str, lastfm_key: str = "") -> dict:
    """Fetch artist bio, tags, listeners, similar artists, and top tracks from Last.fm.
    Runs getinfo + gettoptracks in PARALLEL for 2x speedup.
    """
    if not artist_name:
        return {}

    key = lastfm_key or os.environ.get("LASTFM_API_KEY")
    if not key:
        return {}
    cache_key = f"artist_lfm_v3_{artist_name.lower().strip()}"
    cached = _ENRICH_CACHE.get(cache_key)
    if cached is not None:
        return cached

    a_q = urllib.parse.quote(artist_name)

    def _get_info():
        return _fetch_json(
            f"http://ws.audioscrobbler.com/2.0/?method=artist.getinfo"
            f"&api_key={key}&artist={a_q}&format=json&autocorrect=1"
        )

    def _get_top_tracks():
        return _fetch_json(
            f"http://ws.audioscrobbler.com/2.0/?method=artist.gettoptracks"
            f"&api_key={key}&artist={a_q}&format=json&limit=20"
        )

    # Run both Last.fm calls in parallel
    f_info = _HTTP_POOL.submit(_get_info)
    f_tracks = _HTTP_POOL.submit(_get_top_tracks)

    result = {}
    tags_list = []

    try:
        data = f_info.result(timeout=6)
        if data and data.get("artist"):
            art = data["artist"]
            bio = (art.get("bio") or {}).get("summary") or ""
            bio_clean = re.sub(r'<[^>]+>', '', bio)
            if "Read more on Last.fm" in bio_clean:
                bio_clean = bio_clean.split("Read more on Last.fm")[0].strip()
            stats = art.get("stats") or {}
            listeners = int(stats.get("listeners") or 0)
            playcount = int(stats.get("playcount") or 0)
            tags_list = [t["name"] for t in (art.get("tags") or {}).get("tag", [])[:6]]
            similar = [s["name"] for s in (art.get("similar") or {}).get("artist", [])[:8]]
            result = {
                "bio": bio_clean,
                "listeners": listeners,
                "playcount": playcount,
                "tags": tags_list,
                "similar": similar,
                "url": art.get("url") or "",
                "top_tracks": []
            }
    except Exception:
        pass

    try:
        t_data = f_tracks.result(timeout=6)
        if t_data and (t_data.get("toptracks") or {}).get("track"):
            lfm_tracks = []
            for tr in t_data["toptracks"]["track"]:
                tname = tr.get("name", "")
                aname = (tr.get("artist") or {}).get("name") or artist_name
                yt_q = urllib.parse.quote(f"{aname} {tname}")
                lfm_tracks.append({
                    "row": -1, "name": tname, "artist": aname,
                    "year": "2024", "popularity_pct": 85,
                    "base_genres": tags_list[:2] or ["pop"],
                    "energy": 0.70, "valence": 0.65, "danceability": 0.70, "tempo_bpm": 120,
                    "deezer_preview_url": "", "deezer_album_art": "", "deezer_link": "",
                    "youtube_music_url": f"https://music.youtube.com/search?q={yt_q}",
                    "is_live_external": True, "source": "lastfm"
                })
            if result:
                result["top_tracks"] = lfm_tracks
    except Exception:
        pass

    if result:
        _ENRICH_CACHE[cache_key] = result
    return result
