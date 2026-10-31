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
import threading
import time
from .media import itunes_track, deezer_track, artwork, merge_metadata
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed, wait, FIRST_COMPLETED
from typing import Dict, List, Optional

import asyncio
from rapidfuzz import fuzz
from .metadata import recording_metadata, artist_signature, clean_title, LANGUAGE_NAMES

# ---------------------------------------------------------------------------
# Bounded LRU Cache (thread-safe via OrderedDict + size cap)
# ---------------------------------------------------------------------------

class _BoundedCache:
    def __init__(self, maxsize=5000, ttl=3600):
        self._data=OrderedDict();self._maxsize=maxsize;self.ttl=ttl;self._lock=threading.RLock()
    def get(self,key,default=None):
        with self._lock:
            entry=self._data.get(key)
            if entry is None:return default
            value,expiry=entry
            if expiry<time.monotonic():self._data.pop(key,None);return default
            self._data.move_to_end(key);return value
    def __contains__(self,key):return self.get(key) is not None
    def __getitem__(self,key):
        value=self.get(key)
        if value is None:raise KeyError(key)
        return value
    def __setitem__(self,key,value):
        with self._lock:
            self._data[key]=(value,time.monotonic()+self.ttl)
            self._data.move_to_end(key)
            while len(self._data)>self._maxsize:self._data.popitem(last=False)
    def __len__(self):return len(self._data)


_ARTIST_IMAGE_CACHE: _BoundedCache = _BoundedCache(maxsize=2000)
_ENRICH_CACHE: _BoundedCache = _BoundedCache(maxsize=5000)
_LIVE_SEARCH_CACHE: _BoundedCache = _BoundedCache(maxsize=1000)
_LIVE_ALBUM_CACHE: _BoundedCache = _BoundedCache(maxsize=500)

# Shared thread-pool for external HTTP calls — reuse across requests
_HTTP_POOL = ThreadPoolExecutor(max_workers=16, thread_name_prefix="sv_http")


# ---------------------------------------------------------------------------
# Low-level HTTP helper
# ---------------------------------------------------------------------------

def _fetch_json(url: str, timeout: int = 4, retries: int = 0) -> Optional[dict]:
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


def _completed_within(futures, timeout):
    """Keep completed provider results when another provider exceeds the deadline."""
    try:
        yield from as_completed(futures, timeout=timeout)
    except TimeoutError:
        for future in futures:
            if not future.done():
                future.cancel()


# ---------------------------------------------------------------------------
# Artist Image
# ---------------------------------------------------------------------------

def get_artist_image(artist_name):
    if not artist_name:return ""
    cached=_ARTIST_IMAGE_CACHE.get(artist_name.casefold())
    if cached is not None:return cached
    data=_fetch_json(f"https://api.deezer.com/search/artist?q={urllib.parse.quote(artist_name)}&limit=5") or {}
    hits=[item for item in data.get('data',[]) if artist_signature(item.get('name'))==artist_signature(artist_name) or fuzz.ratio(str(item.get('name','')).casefold(),artist_name.casefold())>=92]
    image=artwork((hits[0].get('picture_big') or hits[0].get('picture_medium')) if hits else '')
    if image:_ARTIST_IMAGE_CACHE[artist_name.casefold()]=image
    return image

def _build_clean_names(track_name: str, artist_name: str):
    """Return (primary_artist, clean_track) ready for API queries."""
    primary_artist = re.split(r'[,&/]|feat\.?|ft\.?', artist_name, flags=re.IGNORECASE)[0].strip()
    primary_artist_clean = re.sub(r'[?!:;"\'`-]', ' ', primary_artist)
    primary_artist_clean = re.sub(r'\s+', ' ', primary_artist_clean).strip() or artist_name

    from .metadata import recording_version
    clean_track = track_name.strip()
    clean_track = re.sub(r'\s*[\(\[]([^\)\]]*)[\)\]]', lambda m:m.group(0) if recording_version('Song ('+m.group(1)+')') else '', clean_track)
    if primary_artist and primary_artist.lower() in clean_track.lower():
        pattern = re.compile(r'\s*' + re.escape(primary_artist) + r'\s*$', re.IGNORECASE)
        clean_track = pattern.sub('', clean_track.strip()).strip()
    clean_track = re.sub(r'[?!:;"\'`-]', ' ', clean_track)
    clean_track = re.sub(r'\s+', ' ', clean_track).strip()
    if not clean_track:
        clean_track = track_name.split('(')[0].split('[')[0].split('-')[0].strip()

    return primary_artist_clean, clean_track


def _matching_recording(items, primary_artist, clean_track, source):
    """A title-only fallback must never attach another artist's recording."""
    if primary_artist.casefold() in ("unknown", "unknown artist"):
        return None
    def normalized(value):
        return re.sub(r"[\W_]+", " ", value.casefold()).strip()
    wanted_artist, wanted_title = normalized(primary_artist), normalized(clean_track)
    matches = []
    for item in items:
        artist = ((item.get("artist") or {}).get("name", "") if source == "deezer"
                  else item.get("artistName", ""))
        title = item.get("title", "") if source == "deezer" else item.get("trackName", "")
        from .metadata import recording_match
        if not recording_match({'name':clean_track,'artist':primary_artist},{'name':title,'artist':artist}):
            continue
        _, title = _build_clean_names(title, artist)
        artist_score = max(fuzz.token_set_ratio(wanted_artist, normalized(artist)),
                           fuzz.ratio(wanted_artist.replace(" ", ""), normalized(artist).replace(" ", "")))
        title_score = fuzz.ratio(wanted_title, normalized(title))
        if artist_score >= 85 and title_score >= 88:
            preview = item.get("preview") if source == "deezer" else item.get("previewUrl")
            matches.append((bool(preview), artist_score + title_score, item))
    return max(matches, key=lambda match: match[:2])[2] if matches else None


def _fetch_deezer_enrichment(primary_artist,clean_track):
    for query in (f"{primary_artist} {clean_track}",clean_track):
        data=_fetch_json(f"https://api.deezer.com/search?q={urllib.parse.quote(query)}&limit=12") or {}
        hit=_matching_recording(data.get('data',[]),primary_artist,clean_track,'deezer')
        if hit:
            card=deezer_track(hit)
            result={k:v for k,v in card.items() if k not in {'row','name','artist','track_id','source','provider_id','is_live_external'}}
            result['deezer_album_name']=card.get('album','')
            return result
    return {}

def _fetch_itunes_enrichment(primary_artist,clean_track):
    for query in (f"{primary_artist} {clean_track}",clean_track):
        data=_fetch_json(f"https://itunes.apple.com/search?term={urllib.parse.quote(query)}&entity=song&limit=12") or {}
        hit=_matching_recording(data.get('results',[]),primary_artist,clean_track,'itunes')
        if hit:
            card=itunes_track(hit)
            result={k:v for k,v in card.items() if k not in {'row','name','artist','track_id','source','provider_id','is_live_external','deezer_preview_url','deezer_album_art','deezer_link'}}
            result.update(itunes_id=str(hit.get('trackId') or ''),itunes_preview_url=hit.get('previewUrl') or '',itunes_album_art=card['deezer_album_art'],itunes_link=hit.get('trackViewUrl') or '')
            return result
    return {}

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
    for future in _completed_within(futures, timeout=6):
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
    result = merge_metadata(result, itunes_result)
    if not result.get("deezer_preview_url") and itunes_result.get("itunes_preview_url"):
        result["deezer_preview_url"] = itunes_result["itunes_preview_url"]
    if not result.get("deezer_album_art") and itunes_result.get("itunes_album_art"):
        result["deezer_album_art"] = itunes_result["itunes_album_art"]
    if not result.get("deezer_link") and itunes_result.get("itunes_link"):
        result["deezer_link"] = itunes_result["itunes_link"]

    # Always cache (even if only YouTube link) to prevent repeat network calls
    if result.get("deezer_album_art") or result.get("deezer_preview_url"):
        _ENRICH_CACHE[cache_key] = result
    return result


# ---------------------------------------------------------------------------
# Async Batch Enrichment
# ---------------------------------------------------------------------------

async def async_enrich_track(track: dict, lastfm_key: Optional[str] = None) -> dict:
    """Asynchronously enrich a single track object in threadpool."""
    if not track or not isinstance(track, dict):
        return track
    from . import catalog_cache
    hydrated=catalog_cache.hydrate(track)
    track.update(hydrated)
    if track.get("deezer_album_art") and track.get("deezer_preview_url") and track.get("duration_seconds"):
        return track

    tname = track.get("name", "")
    aname = track.get("artist", "")
    if not tname or not aname:
        return track

    cache_key = f"{tname.lower().strip()}||{aname.lower().strip()}"
    cached = _ENRICH_CACHE.get(cache_key)
    if cached is not None:
        track.update(merge_metadata(track,cached))
        return track

    primary_artist, clean_track = _build_clean_names(tname, aname)
    
    yt_q = urllib.parse.quote(f"{primary_artist} {clean_track}")
    result = {
        "youtube_music_url": f"https://music.youtube.com/search?q={yt_q}",
        "youtube_url": f"https://www.youtube.com/results?search_query={yt_q}",
    }

    loop = asyncio.get_event_loop()
    try:
        deezer_task = loop.run_in_executor(_HTTP_POOL, _fetch_deezer_enrichment, primary_artist, clean_track)
        itunes_task = loop.run_in_executor(_HTTP_POOL, _fetch_itunes_enrichment, primary_artist, clean_track)
        
        deezer_result, itunes_result = await asyncio.gather(deezer_task, itunes_task, return_exceptions=True)
        
        if isinstance(deezer_result, dict):
            result.update(deezer_result)
        if isinstance(itunes_result, dict):
            result = merge_metadata(result, itunes_result)
            if not result.get("deezer_preview_url") and itunes_result.get("itunes_preview_url"):
                result["deezer_preview_url"] = itunes_result["itunes_preview_url"]
            if not result.get("deezer_album_art") and itunes_result.get("itunes_album_art"):
                result["deezer_album_art"] = itunes_result["itunes_album_art"]
            if not result.get("deezer_link") and itunes_result.get("itunes_link"):
                result["deezer_link"] = itunes_result["itunes_link"]

        # Only cache if we actually found artwork (meaning it was a success, not a rate limit failure)
        if result.get("deezer_album_art") or result.get("deezer_preview_url"):
            _ENRICH_CACHE[cache_key] = result

        track.update(merge_metadata(track,result))
        catalog_cache.remember([track])
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
        t.get("deezer_album_art") and t.get("deezer_preview_url") and t.get("duration_seconds")
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

def _search_itunes_tracks(q_str,limit):
    data=_fetch_json(f"https://itunes.apple.com/search?term={urllib.parse.quote(q_str)}&entity=song&limit={limit}") or {}
    return [itunes_track(item) for item in data.get('results',[]) if item.get('trackName') and item.get('artistName')]

def _search_deezer_tracks(q_str,limit):
    data=_fetch_json(f"https://api.deezer.com/search?q={urllib.parse.quote(q_str)}&limit={limit}") or {}
    return [deezer_track(item) for item in data.get('data',[]) if item.get('title') and (item.get('artist') or {}).get('name')]

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
                    "year": "",
                    "popularity_pct": 85,
                    "base_genres": [],
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

    hits_by_key: Dict[str, dict] = {}
    ordered_keys: List[str] = []
    for future in _completed_within(futures, timeout=5):
        try:
            for hit in future.result():
                key = f"{clean_title(hit['name'])}||{artist_signature(re.split(r'[,;&]', hit['artist'])[0])}"
                if key not in hits_by_key:
                    hits_by_key[key] = hit
                    ordered_keys.append(key)
                else:
                    # Merge metadata: prefer non-empty year, preview URL, cover art, links
                    existing = hits_by_key[key]
                    for field in ("recording_genres", "metadata_source", "language", "language_source", "album", "album_id", "album_source"):
                        if hit.get(field): existing[field] = hit[field]
                    existing["base_genres"] = list(dict.fromkeys(
                        existing.get("base_genres", []) + hit.get("base_genres", [])))
                    if not existing.get("year") and hit.get("year"):
                        existing["year"] = hit["year"]
                    if not existing.get("deezer_preview_url") and hit.get("deezer_preview_url"):
                        existing["deezer_preview_url"] = hit["deezer_preview_url"]
                    if not existing.get("deezer_album_art") and hit.get("deezer_album_art"):
                        existing["deezer_album_art"] = hit["deezer_album_art"]
                    if not existing.get("deezer_link") and hit.get("deezer_link"):
                        existing["deezer_link"] = hit["deezer_link"]
        except Exception:
            pass

    query_language = set(q_clean.casefold().split()) & LANGUAGE_NAMES
    def relevance(hit):
        language_match = bool(query_language & {hit.get("language")})
        blob = f"{hit.get('name', '')} {hit.get('artist', '')} {' '.join(hit.get('recording_genres', []))}"
        return language_match, fuzz.token_set_ratio(_clean_search_query(q_clean).casefold(), blob.casefold())
    out_hits = sorted(hits_by_key.values(), key=relevance, reverse=True)[:limit]
    _LIVE_SEARCH_CACHE[cache_key] = out_hits
    return out_hits


# ---------------------------------------------------------------------------
# Live Album Search (Parallel Deezer + iTunes + LastFM)
# ---------------------------------------------------------------------------

def _search_deezer_albums(q_str,limit):
    data=_fetch_json(f"https://api.deezer.com/search/album?q={urllib.parse.quote(q_str)}&limit={limit}") or {}
    return [{'id':str(item.get('id')),'title':item.get('title',''),'artist':(item.get('artist') or {}).get('name',''),
             'cover_art':artwork(item.get('cover_big') or item.get('cover_medium')),'track_count':item.get('nb_tracks'),
             'release_date':item.get('release_date'),'source':'deezer','url':item.get('link','')}
            for item in data.get('data',[]) if item.get('id')]

def _search_itunes_albums(q_str,limit):
    data=_fetch_json(f"https://itunes.apple.com/search?term={urllib.parse.quote(q_str)}&entity=album&limit={limit}") or {}
    return [{'id':str(item.get('collectionId')),'title':item.get('collectionName',''),'artist':item.get('artistName',''),
             'cover_art':artwork(item.get('artworkUrl100')),'track_count':item.get('trackCount'),
             'release_date':item.get('releaseDate'),'source':'itunes','url':item.get('collectionViewUrl','')}
            for item in data.get('results',[]) if item.get('collectionId')]

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
    deezer_fut = _HTTP_POOL.submit(_search_deezer_albums, q_clean, max(25,limit))
    itunes_fut = _HTTP_POOL.submit(_search_itunes_albums, q_clean, max(25,limit))
    lfm_fut = _HTTP_POOL.submit(_search_lastfm_albums, q_clean, limit, lfm_key) if lfm_key else None

    albums: List[dict] = []
    seen: set = set()
    
    # Process iTunes first (better for regional)
    try:
        for alb in itunes_fut.result(timeout=5):
            key = alb["title"].lower().strip()
            if key not in seen:
                seen.add(key)
                albums.append(alb)
    except Exception:
        pass

    # Process Deezer second
    try:
        for alb in deezer_fut.result(timeout=5):
            key = alb["title"].lower().strip()
            if key not in seen:
                seen.add(key)
                albums.append(alb)
    except Exception:
        pass

    # Process LastFM third
    if lfm_fut:
        try:
            for alb in lfm_fut.result(timeout=5):
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

    from .search import album_score
    out_albums = sorted(albums,key=lambda a:-album_score(query,a))[:limit]
    _LIVE_ALBUM_CACHE[cache_key] = out_albums
    return out_albums


# ---------------------------------------------------------------------------
# Album Tracks Fetcher
# ---------------------------------------------------------------------------

def fetch_album_tracks(album_title, artist_name="", album_id="", source="", engine=None):
    """Load a release by provider identity, including all advertised track pages."""
    tracks=[];cover="";artist=artist_name;expected=0;release_date="";label="";copyright="";url="";genres=[]
    if album_id and source in {'deezer',''}:
        data=_fetch_json(f"https://api.deezer.com/album/{album_id}") or {}
        if data.get('tracks'):
            album_title=data.get('title') or album_title;artist=(data.get('artist') or {}).get('name') or artist
            cover=artwork(data.get('cover_big') or data.get('cover_medium'));expected=int(data.get('nb_tracks') or 0)
            release_date=data.get('release_date') or '';label=data.get('label') or '';url=data.get('link') or ''
            genres=[g.get('name') for g in (data.get('genres') or {}).get('data',[]) if g.get('name')]
            page=data.get('tracks') or {};seen=set();pages=0
            while page and pages<20:
                before=len(tracks)
                for item in page.get('data',[]):
                    identity=str(item.get('id') or item.get('title'))
                    if identity in seen:continue
                    seen.add(identity);track=deezer_track(item,{**data,'id':album_id,'title':album_title})
                    track['track_number']=track.get('track_number') or len(tracks)+1;tracks.append(track)
                pages+=1
                if len(tracks)==before or (expected and len(tracks)>=expected):break
                next_url=page.get('next')
                if next_url and str(next_url).replace('http:','https:',1).startswith('https://api.deezer.com/'):
                    page=_fetch_json(str(next_url).replace('http:','https:',1)) or {}
                elif expected>len(tracks):
                    page=_fetch_json(f"https://api.deezer.com/album/{album_id}/tracks?index={len(tracks)}&limit=100") or {}
                else:break
    if not tracks and (source=='itunes' or not album_id):
        if album_id:
            data=_fetch_json(f"https://itunes.apple.com/lookup?id={album_id}&entity=song&limit=200") or {}
        else:
            data=_fetch_json(f"https://itunes.apple.com/search?term={urllib.parse.quote(album_title+' '+artist_name)}&entity=song&limit=200") or {}
        collection=next((x for x in data.get('results',[]) if x.get('wrapperType')=='collection' and (not album_id or str(x.get('collectionId'))==str(album_id))),{})
        album_title=collection.get('collectionName') or album_title;artist=collection.get('artistName') or artist
        expected=int(collection.get('trackCount') or 0);cover=artwork(collection.get('artworkUrl100'))
        release_date=collection.get('releaseDate') or '';copyright=collection.get('copyright') or '';url=collection.get('collectionViewUrl') or ''
        for item in data.get('results',[]):
            if not item.get('trackName'):continue
            if album_id and str(item.get('collectionId'))!=str(album_id):continue
            if not album_id and item.get('collectionName','').casefold()!=album_title.casefold():continue
            card=itunes_track(item);tracks.append(card);cover=cover or card.get('deezer_album_art')
        tracks.sort(key=lambda t:(t.get('disc_number') or 1,t.get('track_number') or 0))
    if tracks:
        from . import catalog_cache
        catalog_cache.remember(tracks)
        tracks=[catalog_cache.hydrate(t) for t in tracks]
    return {'id':str(album_id),'source':source,'title':album_title,'artist':artist or 'Various artists','cover_art':cover,
            'tracks':tracks,'track_count':expected or len(tracks),'loaded_count':len(tracks),'complete':len(tracks)>=(expected or len(tracks)),
            'release_date':release_date,'label':label,'copyright':copyright,'url':url,'genres':genres,
            'duration_seconds':sum(t.get('duration_seconds') or 0 for t in tracks)}


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
                    "base_genres": tags_list[:2],
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
