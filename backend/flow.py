"""SoundVector's personal listening continuation, independent of an LLM.

Retrieve before diversifying: a near-identical embedding is not a duplicate song.
The current recording supplies context; distinct active tastes supply familiarity.
Provider listening evidence is a bounded supporting signal, never the ranker.
"""
from collections import Counter
from functools import lru_cache
import time
import weakref

import numpy as np

from .metadata import (artist_parts, artist_signature, album_context, clean_title,
                       public_track, recording_match, recording_version, representative_seeds, trusted_language)
from .profiles import track_key

_INDEX = weakref.WeakKeyDictionary()


def artists(track):
    names = artist_parts(track.get('artist'))
    names += [item.get('name', '') for item in track.get('artists', []) if isinstance(item, dict)]
    return {artist_signature(name) for name in names if name}


def row_of(engine, track):
    row = track.get('row', -1)
    if not isinstance(row, (int, np.integer)) or row < 0 or row >= len(engine.embeddings):
        return None
    model = engine.track_card(int(row))
    identity = {**track, 'artist': ', '.join(artists(track))}
    return int(row) if recording_match(identity, model) else None


class Catalog:
    def __init__(self, engine):
        rows = np.asarray(getattr(engine, '_catalog_rows', np.arange(len(engine.embeddings))), dtype=int)
        # An independent acoustic/popular retrieval lane reaches beyond ANN's
        # narrow artist cluster; popularity alone cannot enter the final queue.
        count = min(20000, len(rows))
        self.popular = rows[np.argsort(-np.asarray(engine.pop[rows]))[:count]]
        self.engine = weakref.ref(engine)

    @lru_cache(maxsize=50000)
    def genres(self, row):
        engine = self.engine()
        return frozenset(engine._base_genres(engine._genre_ids(row)))


def catalog_for(engine):
    if engine not in _INDEX:
        _INDEX[engine] = Catalog(engine)
    return _INDEX[engine]


def audio_similarity(audio, target):
    # Speech/instrumental character matter more than concert crowd noise.
    weights = np.array([1.2, 1., 1.2, 1., 1.5, .35, 1.5, .8])
    distance = np.average((np.asarray(audio)[..., :8] - target[:8]) ** 2, weights=weights, axis=-1)
    return np.exp(-distance / .09)


def genre_similarity(a, b):
    return 2 * len(a & b) / (len(a) + len(b)) if a and b else 0.


def anchor_rows(engine, seed, pool):
    row = row_of(engine, seed)
    if row is not None:
        return [row], 'recording'
    names = artists(seed)
    rows = [row_of(engine, t) for t in pool if names & artists(t)
            and not (trusted_language(seed) and trusted_language(t) and trusted_language(seed) != trusted_language(t))]
    rows = list(dict.fromkeys(r for r in rows if r is not None))[:4]
    # These recordings provide an artist context, not measured audio for the seed.
    return rows, 'artist_context' if rows else 'metadata'


def candidate_pool(engine, seed, taste, pool):
    index = catalog_for(engine)
    anchors, kind = anchor_rows(engine, seed, pool)
    rows = set()
    if anchors:
        vector = np.asarray(engine.embeddings[anchors]).mean(axis=0)
        norm = np.linalg.norm(vector)
        if norm:
            vector = vector / norm
            labels, _ = engine.index.knn_query(vector, k=min(5000, len(engine.embeddings)))
            rows.update(int(engine.canonical_row[r]) for r in labels[0])
        target = np.asarray(engine.audio[anchors, :8]).mean(axis=0)
        genres = frozenset().union(*(index.genres(r) for r in anchors))
        common = np.array([genre_similarity(index.genres(int(r)), genres) for r in index.popular])
        sound = audio_similarity(engine.audio[index.popular, :8], target)
        eligible = (common > 0) & (sound >= .45)
        candidates = index.popular[eligible]
        scores = .50 * sound[eligible] + .25 * common[eligible] + .25 * engine.pop[candidates]
        rows.update(int(r) for r in candidates[np.argsort(-scores)[:400]])
    favorites = representative_seeds(taste, 12)
    for saved in favorites:
        row = row_of(engine, saved)
        if row is not None:
            rows.add(row)
            labels, _ = engine.index.knn_query(engine.embeddings[row], k=min(180, len(engine.embeddings)))
            rows.update(int(engine.canonical_row[r]) for r in labels[0])
    # Familiar artists are a separate retrieval lane: a liked dance/pop artist
    # can be a good next listen without sharing the seed's embedding cluster.
    favorite_names = list(dict.fromkeys(name for saved in favorites for name in artist_parts(saved.get('artist'))))
    for name in favorite_names[:16]:
        for track in engine.artist_top_tracks(name, limit=18):
            if artist_signature(name) in artists(track):
                rows.add(track['row'])
    # Keep candidates from the current artist even when its embeddings nearly
    # coincide. Sequence spacing below prevents an artist/album takeover.
    primary = artist_parts(seed.get('artist'))
    if primary:
        for track in engine.artist_top_tracks(primary[0], limit=35):
            if artists(track) & artists(seed):
                rows.add(track['row'])
    return [engine.track_card(row) for row in sorted(rows)] + list(pool), anchors, kind


def rank_flow(engine, seed, taste, pool, history=(), recent=(), limit=24, anchors=None, anchor_kind=None):
    from .catalog_cache import hydrate
    index = catalog_for(engine)
    anchors, anchor_kind = (anchor_rows(engine, seed, pool) if anchors is None else (anchors, anchor_kind))
    seed_names = artists(seed)
    seed_language = trusted_language(seed)
    seed_genres = frozenset().union(*(index.genres(r) for r in anchors))
    vector = np.asarray(engine.embeddings[anchors]).mean(axis=0) if anchors else None
    if vector is not None:
        vector /= max(float(np.linalg.norm(vector)), 1e-9)
    target_audio = np.asarray(engine.audio[anchors, :8]).mean(axis=0) if anchors and anchor_kind == 'recording' else None
    selected_taste = representative_seeds(taste, 18)
    taste_rows = [(row_of(engine, t), .4 if t.get('implicit') else 1.) for t in selected_taste]
    taste_rows = [(r, w) for r, w in taste_rows if r is not None]
    taste_artists = Counter()
    for saved in selected_taste:
        for name in artists(saved):
            taste_artists[name] += .4 if saved.get('implicit') else 1.
    blocked = [t for t in history if t.get('signal') in ('dislike', 'skip')]
    blocked_keys = {track_key(t.get('name'), t.get('artist')) for t in blocked}
    saved_keys = {track_key(t.get('name'), t.get('artist')) for t in selected_taste if not t.get('implicit')}
    recent_keys = {track_key(t.get('name'), t.get('artist')) for t in recent if t.get('completed') and time.time()-t.get('ts', 0) < 6*3600}
    # Merge sources without duplicating collaborative credits for one recording.
    unique = {}
    for item in pool:
        if not item.get('name') or not artists(item) or item.get('artist', '').casefold() == 'unknown artist':
            continue
        row = row_of(engine, item)
        key = ('row', int(engine.canonical_row[row])) if row is not None else ('title', track_key(item['name'], item['artist']))
        if key in unique:
            from .media import merge_metadata
            unique[key] = merge_metadata(unique[key], item)
        else:
            unique[key] = dict(item)
    candidates = []
    for item in unique.values():
        row = row_of(engine, item)
        key = track_key(item['name'], item['artist'])
        if key in blocked_keys or recording_match(seed, item) or any(recording_match(t, item) for t in blocked):
            continue
        names = artists(item)
        same_artist = bool(seed_names & names)
        language = trusted_language(item)
        embed = max(0., float(engine.embeddings[row] @ vector)) if row is not None and vector is not None else 0.
        audio = float(audio_similarity(engine.audio[row, :8], target_audio)) if row is not None and target_audio is not None else 0.
        genre = genre_similarity(index.genres(row), seed_genres) if row is not None else 0.
        language_match = bool(language and language == seed_language)
        mismatch = bool(language and seed_language and language != seed_language)
        provider = min(1., max(0., float(item.get('listening_similarity') or 0)))
        # Artist-wide Last.fm similarity supports discovery but does not assert
        # that this particular song is a close listening neighbor.
        provider *= .35 if item.get('listening_source') == 'lastfm.artist.getSimilar' else 1.
        if anchor_kind == 'recording' and row is not None:
            context = .46*embed + .32*audio + .22*genre
        else:
            context = .42*embed + .38*same_artist + .20*language_match
        familiar = max((min(1., taste_artists[n]/2) for n in names), default=0.)
        affinity = 0.
        if row is not None and taste_rows:
            dots = np.array([max(0., float(engine.embeddings[row] @ engine.embeddings[r])) * w for r,w in taste_rows])
            affinity = float(np.mean(np.sort(dots)[-min(2, len(dots)):]))
        personal = .60*familiar + .24*affinity + .16*(key in saved_keys)
        # A personal continuation may take a small step toward another interest,
        # but neither a global hit nor an unrelated saved artist bypasses context.
        familiar_transition = familiar > 0 and genre > 0 and audio >= .65
        supported = (context >= .30 and (embed >= .18 or genre >= .40 or familiar_transition)) if anchors and row is not None else (same_artist or language_match or provider >= .25)
        if not supported:
            continue
        length = item.get('duration_seconds')
        if seed.get('duration_seconds') and length and length < min(90, float(seed['duration_seconds'])*.4):
            continue
        if anchor_kind == 'recording' and row is not None:
            # Do not make a vocal recording flow into an instrumental or spoken
            # cue merely because its composer, genre or popularity matches.
            if abs(float(engine.audio[row, 6]-target_audio[6])) > .65 or float(engine.audio[row,4]-target_audio[4]) > .45:
                continue
        pop = min(1., max(0., float(engine.pop[row] if row is not None else item.get('popularity') or 0)))
        if selected_taste:
            score = .36*context + .19*pop + .07*same_artist + .03*provider
            score += .45*personal*min(1., context/.5)
        else:
            score = .49*context + .23*pop + .12*same_artist + .04*provider
        score -= .12*mismatch + .10*(key in recent_keys)
        if recording_version(item['name']) and not recording_version(seed.get('name')):
            score -= .07
        why = []
        if familiar:
            why.append('An artist in your saved music' if any(names & artists(t) for t in selected_taste if not t.get('implicit')) else 'An artist you have been listening to')
        if same_artist:
            why.append('More from this song’s artist')
        if audio >= .65:
            why.append('Similar energy and rhythm')
        if embed >= .60:
            why.append('A similar musical style')
        if language_match:
            why.append('Matches this recording’s language')
        if not why:
            why.append('From a related artist' if provider else 'A related recording')
        candidates.append({'track':item, 'row':row, 'score':score, 'artists':names, 'primary':artist_signature(artist_parts(item['artist'])[0]),
                           'album':album_context(item), 'same':same_artist, 'reasons':why,
                           'evidence':{'anchor':anchor_kind, 'context':round(context,4), 'embedding':round(embed,4),
                                       'audio':round(audio,4) if target_audio is not None and row is not None else None,
                                       'taste':round(personal,4), 'listener_support':round(provider,4)}})
    # Bounded greedy sequencing, with a stable prefix regardless of page size.
    candidates.sort(key=lambda c:(-c['score'],track_key(c['track']['name'],c['track']['artist'])))
    candidates = candidates[:450]
    selected=[];counts=Counter();albums=Counter();last_names=set();previous=None;seen_titles=set()
    while candidates and len(selected)<limit:
        def sequence_score(c):
            transition = max(0., float(engine.embeddings[c['row']] @ engine.embeddings[previous])) if previous is not None and c['row'] is not None else 0.
            return c['score'] + .025*transition - .13*counts[c['primary']] - .09*albums[c['album']]*(bool(c['album'])) - .22*bool(last_names & c['artists'])
        # Defer recurring artists until a later position instead of discarding
        # their best songs while their early-queue quota is full.
        eligible=[c for c in candidates if counts[c['primary']] < (1+len(selected)//4 if c['same'] else 1+len(selected)//9)]
        if not eligible:
            # A narrow catalog may only offer a few artists. Fill from reliable
            # remaining recordings; spacing still penalizes repetition.
            eligible=candidates
        candidate=max(eligible,key=sequence_score);candidates.remove(candidate)
        identity=(clean_title(candidate['track']['name']),recording_version(candidate['track']['name']))
        if any(identity==old and candidate['artists'] & old_names for old,old_names in seen_titles):
            continue
        seen_titles.add((identity,frozenset(candidate['artists'])))
        track=public_track(hydrate(candidate['track']))
        track.update(recommendation_source='soundvector',flow_reasons=candidate['reasons'],flow_evidence=candidate['evidence'],reason=candidate['reasons'][0])
        selected.append(track);counts[candidate['primary']]+=1
        if candidate['album']:albums[candidate['album']]+=1
        last_names=candidate['artists'];previous=candidate['row']
    return selected
