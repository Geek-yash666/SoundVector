"""Recording identity and metadata provenance. Artist genres are never song languages."""
import re
from rapidfuzz import fuzz

LANGUAGE_NAMES = frozenset({
    'telugu', 'tamil', 'hindi', 'kannada', 'malayalam', 'punjabi', 'bengali', 'marathi',
    'gujarati', 'urdu', 'english', 'spanish', 'french', 'german', 'italian', 'portuguese',
    'korean', 'japanese', 'mandarin', 'cantonese', 'arabic', 'turkish', 'russian', 'bhojpuri',
})


def clean_title(value):
    value = re.sub(r'\s*[\(\[].*?[\)\]]', '', str(value or '').casefold())
    value = re.sub(r'\s+-\s+(?:from|remaster|remix|live|radio|version).*', '', value)
    return re.sub(r'[^\w]+', ' ', value).strip()


def artist_parts(value):
    return [part.strip().casefold() for part in re.split(r'\s*(?:,|&|;| feat\.? | featuring )\s*', str(value or '')) if part.strip()]


def artist_signature(value):
    # Normalize initial order and punctuation without discarding different initials.
    words = re.findall(r"\w+", str(value or '').casefold())
    return ' '.join(sorted(set(words)))


def recording_version(value):
    """Preserve performance/mix identity while allowing film and featured-credit suffixes."""
    value=str(value or '').casefold()
    variant=r'\b(?:remix|mix|live|acoustic|instrumental|karaoke|sped|slowed|reverb|edit|version|remaster(?:ed)?)\b'
    parts=re.findall(r'[\(\[]([^\)\]]+)[\)\]]',value)
    parts += re.split(r'\s+-\s+',value)[1:]
    return '|'.join(sorted(re.sub(r'\W+',' ',part).strip() for part in parts if re.search(variant,part)))


def album_context(track):
    match = re.search(r'from\s+["\']([^"\']+)', str(track.get('name') or ''), re.IGNORECASE)
    return clean_title(match.group(1)) if match else str(track.get('album') or track.get('album_gid') or '')


def recording_match(seed, candidate):
    if recording_version(seed.get('name'))!=recording_version(candidate.get('name')):
        return False
    title = fuzz.ratio(clean_title(seed.get('name')), clean_title(candidate.get('name')))
    artists = [100 if artist_signature(a) == artist_signature(b) else fuzz.ratio(re.sub(r'\W', '', a), re.sub(r'\W', '', b))
               for a in artist_parts(seed.get('artist')) for b in artist_parts(candidate.get('artist'))]
    return title >= 92 and max(artists, default=0) >= 92


def recording_metadata(genre, source='itunes.track.primaryGenreName'):
    label = str(genre or '').strip().casefold()
    result = {'recording_genres': [label] if label else [], 'metadata_source': source}
    # Only an explicit recording-level language tag is language evidence.
    if label in LANGUAGE_NAMES:
        result.update(language=label, language_source=source)
    return result


def trusted_language(track):
    if track.get('language_source') in {'itunes.track.primaryGenreName', 'musicbrainz.recording.language'}:
        language = str(track.get('language') or '').casefold()
        return language if language in LANGUAGE_NAMES else None
    return None


def public_track(track):
    card = {key: value for key, value in track.items() if key not in {'vector', 'context'}}
    # Keep catalog genre features for ranking, but never expose them as recording classification.
    if not trusted_language(card):
        card.pop('language', None)
        card.pop('language_source', None)
    art=str(card.get('deezer_album_art') or '')
    if '2a96cbd8b46e442fc41c2b86b821562f' in art or art.endswith('/star.png'):
        card.pop('deezer_album_art',None)
    if card.get('is_live_external'):
        for key in ('energy', 'valence', 'danceability', 'acousticness', 'tempo_bpm', 'popularity_pct'):
            card.pop(key, None)
    return card


def representative_seeds(seeds,limit=18):
    """Round-robin taste cohorts; a new album must not erase older languages/artists."""
    from collections import OrderedDict,Counter
    groups=OrderedDict()
    for seed in seeds:
        group=trusted_language(seed) or 'artist:'+artist_signature(artist_parts(seed.get('artist'))[0] if artist_parts(seed.get('artist')) else '')
        groups.setdefault(group,[]).append(seed)
    # Explicit saves lead; completed previews remain a weaker, secondary signal.
    groups=OrderedDict(sorted(groups.items(),key=lambda pair:(
        not any(not t.get('implicit') for t in pair[1]),
        pair[0].startswith('artist:'))))
    selected=[];artist_counts=Counter();album_counts=Counter()
    while groups and len(selected)<limit:
        progressed=False
        for key in list(groups):
            queue=groups[key]
            pick=next((i for i,t in enumerate(queue) if artist_counts[artist_signature(t.get('artist'))]<3 and (not album_context(t) or album_counts[album_context(t)]<2)),None)
            if pick is None:
                groups.pop(key);continue
            seed=queue.pop(pick);selected.append(seed);progressed=True
            artist_counts[artist_signature(seed.get('artist'))]+=1
            if album_context(seed):album_counts[album_context(seed)]+=1
            if not queue:groups.pop(key)
            if len(selected)>=limit:break
        if not progressed:break
    return selected
