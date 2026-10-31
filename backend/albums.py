"""Recording-to-release resolution with explicit provider identity."""
from .external_api import _fetch_itunes_enrichment, _fetch_deezer_enrichment, _build_clean_names, _fetch_json
from .metadata import recording_match


def resolve_song_album(name, artist, album_id="", album_source=""):
    # Honor the selected edition only after checking that its track list contains
    # this recording. A stale/cross-provider collection ID cannot redirect it.
    if str(album_id).isdigit() and album_source == 'itunes':
        data = _fetch_json(f'https://itunes.apple.com/lookup?id={album_id}&entity=song') or {}
        for item in data.get('results', []):
            candidate = {'name': item.get('trackName'), 'artist': item.get('artistName')}
            if str(item.get('collectionId', '')) == str(album_id) and recording_match({'name': name, 'artist': artist}, candidate):
                return {'title': item.get('collectionName') or name, 'artist': item.get('artistName') or artist, 'id': str(album_id), 'source': 'itunes'}
    if str(album_id).isdigit() and album_source == 'deezer':
        data = _fetch_json(f'https://api.deezer.com/album/{album_id}') or {}
        if any(recording_match({'name': name, 'artist': artist}, {'name': item.get('title'), 'artist': (item.get('artist') or {}).get('name')}) for item in (data.get('tracks') or {}).get('data', [])):
            return {'title': data.get('title') or name, 'artist': (data.get('artist') or {}).get('name') or artist, 'id': str(album_id), 'source': 'deezer'}
    primary_artist, title = _build_clean_names(name, artist)
    matched = _fetch_itunes_enrichment(primary_artist, title)
    if matched.get('album') and matched.get('album_id'):
        return {'title': matched['album'], 'artist': artist, 'id': str(matched['album_id']), 'source': 'itunes'}
    # Deezer's track endpoint carries the release identity. Its recording was already
    # checked by title + artist by the enrichment helper.
    matched = _fetch_deezer_enrichment(primary_artist, title)
    track_id = str(matched.get('deezer_id') or '')
    if track_id.isdigit():
        data = _fetch_json(f'https://api.deezer.com/track/{track_id}') or {}
        album = data.get('album') or {}
        if album.get('id') and album.get('title'):
            return {'title': album['title'], 'artist': (data.get('artist') or {}).get('name') or artist, 'id': str(album['id']), 'source': 'deezer'}
    return None
