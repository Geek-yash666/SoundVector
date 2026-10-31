"""Read genuine public Apple Music playlists without borrowing website credentials.

Only public, anonymous page data is used. No user tokens, cookies or sign-in data
are extracted. If Apple's page format is unavailable, callers can use another
provider rather than inventing playlist contents.
"""
import json
import os
import re
import urllib.parse
from html.parser import HTMLParser

import requests

from .external_api import _BoundedCache
from .media import itunes_track, merge_metadata
from .metadata import recording_match

_CACHE = _BoundedCache(maxsize=120, ttl=900)
_MISSES = _BoundedCache(maxsize=120, ttl=60)
_URLS = _BoundedCache(maxsize=512, ttl=3600)
_ID = re.compile(r'pl\.[A-Za-z0-9._-]+\Z')
_MAX_PAGE = 4 * 1024 * 1024


def storefront():
    value = os.environ.get('APPLE_MUSIC_STOREFRONT', 'us').lower()
    return value if re.fullmatch(r'[a-z]{2}', value) else 'us'


def playlist_url(url, playlist_id=None):
    """Accept only canonical Apple playlist paths; client URLs cannot select hosts."""
    try:
        parsed = urllib.parse.urlsplit(str(url or ''))
        if parsed.scheme != 'https' or parsed.hostname != 'music.apple.com' or parsed.port not in (None, 443) or parsed.username:
            return ''
        match = re.fullmatch(r'/[a-z]{2}/playlist/[^/]+/(pl\.[A-Za-z0-9._-]+)', parsed.path)
        if not match or (playlist_id and match[1] != str(playlist_id)):
            return ''
        return urllib.parse.urlunsplit(parsed._replace(fragment=''))
    except ValueError:
        return ''


def _download(url, host='music.apple.com'):
    """Bounded, certificate-verified reads; redirects stay on the expected host."""
    for _ in range(4):
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != 'https' or parsed.hostname != host or parsed.port not in (None, 443) or parsed.username:
            return None
        try:
            with requests.get(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'text/html,application/json'},
                              timeout=(3, 5), allow_redirects=False, stream=True) as response:
                if response.is_redirect:
                    url = urllib.parse.urljoin(url, response.headers.get('Location', ''))
                    continue
                response.raise_for_status()
                content = bytearray()
                for chunk in response.iter_content(65536):
                    content.extend(chunk)
                    if len(content) > _MAX_PAGE:
                        return None
                return content.decode('utf-8')
        except (requests.RequestException, UnicodeError):
            return None
    return None


class _ServerData(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.active = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == 'script' and dict(attrs).get('id') == 'serialized-server-data':
            self.active = True

    def handle_data(self, data):
        if self.active:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == 'script':
            self.active = False


def _pages(html):
    if not html:
        return []
    parser = _ServerData()
    try:
        parser.feed(html)
        payload = json.loads(''.join(parser.parts))
        if not isinstance(payload,dict) or not isinstance(payload.get('data'),list):
            return []
        return [entry['data'] for entry in payload.get('data', [])
                if isinstance(entry, dict) and isinstance(entry.get('data'), dict) and isinstance(entry['data'].get('sections'),list)]
    except (ValueError, TypeError, KeyError):
        return []


def _descriptor(item):
    value=item.get('contentDescriptor')
    return value if isinstance(value,dict) else {}


def _sections(page):
    return [s for s in page.get('sections') or [] if isinstance(s,dict)]


def _items(section):
    value=section.get('items')
    return [item for item in value if isinstance(item,dict)] if isinstance(value,list) else []


def _link_descriptor(link):
    action = link.get('segue')
    destination = action.get('destination') if isinstance(action,dict) else None
    value = destination.get('contentDescriptor') if isinstance(destination,dict) else None
    return value if isinstance(value,dict) else {}


def _art(value):
    template = (value.get('dictionary') or value).get('url', '') if isinstance(value, dict) else ''
    for key, replacement in {'w': '600', 'h': '600', 'f': 'jpg', 'c': 'bb'}.items():
        template = template.replace('{' + key + '}', replacement)
    return template if template.startswith('https://') and '{' not in template else ''


def _titles(links):
    return [link['title'] for link in links or [] if isinstance(link,dict) and isinstance(link.get('title'),str)]


def parse_search(html):
    unique = {}
    for page in _pages(html):
        for section in _sections(page):
            for item in _items(section):
                descriptor = _descriptor(item)
                if descriptor.get('kind') != 'playlist':
                    continue
                identity = str((descriptor.get('identifiers') or {}).get('storeAdamID') or '')
                url = playlist_url(descriptor.get('url'), identity)
                title = item.get('title') or next(iter(_titles(item.get('titleLinks'))), '')
                if not _ID.fullmatch(identity) or not url or not isinstance(title,str) or not title:
                    continue
                creator = ', '.join(_titles(item.get('subtitleLinks'))) or str(item.get('subtitle') or '').split('·')[-1].strip()
                curator = any('/curator/' in str(_link_descriptor(link).get('url') or '') for link in item.get('subtitleLinks') or [])
                card = {'id': identity, 'source': 'apple_music', 'title': title, 'creator': creator or 'Apple Music',
                        'cover_art': _art(item.get('artwork')), 'track_count': item.get('trackCount'),
                        'url': url, 'editorial': True if curator else None, 'metadata_source': 'apple_music.public_page'}
                previous = unique.get(identity)
                if previous:
                    card = {**previous, **{k: v for k, v in card.items() if v not in (None, '')}}
                unique[identity] = card
    return sorted(unique.values(), key=lambda card: not card['editorial'])


def search_playlists(query, limit=3):
    query = str(query or '').strip()[:200]
    if not query:
        return []
    key = 'search:' + storefront() + ':' + query.casefold()
    cached = _CACHE.get(key)
    if cached is not None:
        return cached[:limit]
    if _MISSES.get(key):
        return []
    url = 'https://music.apple.com/' + storefront() + '/search?' + urllib.parse.urlencode({'term': query})
    try:
        result = parse_search(_download(url))
    except (ValueError,TypeError,AttributeError):
        result = []
    if result:
        _CACHE[key] = result
        for card in result:
            _URLS[card['id']] = card['url']
    else:
        _MISSES[key] = True
    return result[:limit]


def _song(item):
    descriptor = _descriptor(item)
    identity = str((descriptor.get('identifiers') or {}).get('storeAdamID') or '')
    if descriptor.get('kind') != 'song' or not identity.isdigit():
        return None
    names = _titles(item.get('subtitleLinks'))
    name, artist = item.get('title'), item.get('artistName') or ', '.join(names)
    if not name or not artist:
        return None
    album_link = next((link for link in item.get('tertiaryLinks') or [] if _link_descriptor(link).get('kind') == 'album'), {})
    album = _link_descriptor(album_link)
    result = itunes_track({'trackId': identity, 'trackName': name, 'artistName': artist,
                           'collectionId': (album.get('identifiers') or {}).get('storeAdamID'),
                           'collectionName': album_link.get('title'), 'trackTimeMillis': item.get('duration'),
                           'artworkUrl100': _art(item.get('artwork')), 'trackViewUrl': descriptor.get('url'),
                           'collectionViewUrl': album.get('url'),
                           'trackExplicitness': 'explicit' if item.get('showExplicitBadge') else 'notExplicit'})
    if names:
        result['artists'] = [{'name': link['title'], 'role': 'Artist',
                              'id': str((_link_descriptor(link).get('identifiers') or {}).get('storeAdamID') or '')}
                             for link in item.get('subtitleLinks') or [] if link.get('title')]
    else:
        result['artists'] = [{'name': artist, 'role': 'Artist'}]
    result.update(metadata_source='apple_music.public_page', composer_name=item.get('composer') or '',
                  readable=not item.get('isDisabled', False))
    return result


def parse_playlist(html, identity):
    for page in _pages(html):
        sections = _sections(page)
        header = next((item for section in sections if str(section.get('id', '')).startswith('playlist-detail-header-section')
                       for item in _items(section) if str((_descriptor(item).get('identifiers') or {}).get('storeAdamID')) == identity), None)
        if not header:
            continue
        url = playlist_url(page.get('canonicalURL') or _descriptor(header).get('url'), identity)
        if not url:
            continue
        # Playlist positions are significant: repeated recordings stay in their positions.
        tracks = [track for section in sections if str(section.get('id', '')).startswith('track-list - ')
                  for item in _items(section) if (track := _song(item))]
        count = header.get('trackCount')
        count = count if type(count) is int and count >= 0 else None
        complete = len(tracks) == count if count is not None else None
        return {'id': identity, 'source': 'apple_music', 'title': header.get('title') or '',
                'artist': ', '.join(_titles(header.get('subtitleLinks'))) or 'Apple Music',
                'cover_art': _art(header.get('artwork')), 'url': url, 'tracks': tracks,
                'track_count': count, 'loaded_count': len(tracks), 'complete': complete,
                'duration_seconds': sum(t['duration_seconds'] for t in tracks) if complete and all(t.get('duration_seconds') for t in tracks) else None,
                'metadata_source': 'apple_music.public_page'}
    return None


def _previews(tracks, country):
    ids = list(dict.fromkeys(t['itunes_id'] for t in tracks if t.get('itunes_id', '').isdigit()))[:200]
    if not ids:
        return tracks
    url = 'https://itunes.apple.com/lookup?' + urllib.parse.urlencode({'id': ','.join(ids), 'country': country, 'entity': 'song', 'limit': 200})
    try:
        response = json.loads(_download(url, host='itunes.apple.com') or '{}')
    except ValueError:
        return tracks
    found = {str(item.get('trackId')): item for item in response.get('results', []) if item.get('trackName')}
    for track in tracks:
        item = found.get(track.get('itunes_id'))
        if item:
            card = itunes_track(item)
            if recording_match(track, card):
                track.update(merge_metadata(track, {k: v for k, v in card.items() if k not in {'artists', 'artist_id'}}))
    return tracks


def playlist(identity, url=''):
    identity = str(identity or '')
    if not _ID.fullmatch(identity):
        return None
    url = playlist_url(url or _URLS.get(identity), identity)
    if not url:
        return None
    key = 'playlist:' + url
    cached = _CACHE.get(key)
    if cached is not None:
        return cached
    result = parse_playlist(_download(url), identity)
    if result:
        _previews(result['tracks'], urllib.parse.urlsplit(url).path.split('/')[1])
        from .catalog_cache import remember
        remember(result['tracks'])
        _CACHE[key] = result
    return result
