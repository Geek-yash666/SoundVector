"""Optional listening-data neighbors; missing provider evidence adds no candidates."""
import os
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from .external_api import _fetch_json, _BoundedCache
from .metadata import artist_parts, artist_signature, clean_title, recording_match

_CACHE = _BoundedCache(maxsize=150, ttl=3600)


def _neighbors(seed):
    token = os.environ.get('LASTFM_API_KEY')
    if not token:
        return [], []
    identity = clean_title(seed.get('name')) + '||' + artist_signature(seed.get('artist'))
    cached = _CACHE.get(identity)
    if cached is not None:
        return cached

    def fetch(method):
        params = {'method': method, 'artist': seed['artist'], 'api_key': token,
                  'autocorrect': 1, 'limit': 24 if method.startswith('track.') else 12,
                  'format': 'json'}
        if method.startswith('track.'):
            params['track'] = clean_title(seed['name'])
        return _fetch_json('https://ws.audioscrobbler.com/2.0/?' + urllib.parse.urlencode(params)) or {}

    with ThreadPoolExecutor(max_workers=2) as pool:
        track_job = pool.submit(fetch, 'track.getsimilar')
        artist_job = pool.submit(fetch, 'artist.getsimilar')
        track_data, artist_data = track_job.result(), artist_job.result()
    result = ((track_data.get('similartracks') or {}).get('track') or [],
              (artist_data.get('similarartists') or {}).get('artist') or [])
    if any(result):
        _CACHE[identity] = result
    return result


def listening_neighbors(engine, seed):
    """Join provider neighbors to real catalog recordings; never invent audio features."""
    if not hasattr(engine, 'catalog'):
        return []
    tracks, artists = _neighbors(seed)
    candidates = []
    for item in tracks:
        identity = {'name': item.get('name'), 'artist': (item.get('artist') or {}).get('name')}
        if not all(identity.values()):
            continue
        from .engine import _norm_title
        matches = engine.catalog[engine.catalog['_title_key'] == _norm_title(identity['name'])]
        valid = [int(row) for row in matches['_row'] if recording_match(identity, engine.track_card(int(row)))]
        if valid:
            row = max(valid, key=lambda r: engine.pop[r])
            candidates.append({**engine.track_card(row), 'listening_similarity': float(item.get('match') or 0),
                               'listening_source': 'lastfm.track.getSimilar'})
    for item in artists:
        name = item.get('name')
        if not name:
            continue
        for hit in engine.artist_top_tracks(name, limit=12):
            if artist_signature(name) not in {artist_signature(a) for a in artist_parts(hit.get('artist'))}:
                continue
            candidates.append({**engine.track_card(hit['row']), 'listening_similarity': float(item.get('match') or 0) * .85,
                               'listening_source': 'lastfm.artist.getSimilar'})
    return candidates
