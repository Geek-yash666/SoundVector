"""Automatic discovery from saved recordings and meaningful preview listening."""
import asyncio
from collections import Counter

import numpy as np

from .metadata import artist_parts, clean_title, recording_match, trusted_language, public_track, LANGUAGE_NAMES, artist_signature, album_context, representative_seeds
from .profiles import track_key
from .external_api import search_live_apis


async def lookup(query, limit=24):
    try:
        return await asyncio.wait_for(asyncio.to_thread(search_live_apis, query, limit), 2.8)
    except Exception:
        return []


async def resolve_recordings(seeds):
    async def resolve(seed):
        if trusted_language(seed):
            return dict(seed)
        hits = await lookup(f"{clean_title(seed.get('name'))} {seed.get('artist', '')}", 6)
        match = next((hit for hit in hits if recording_match(seed, hit)), None)
        if match:
            # Keep the catalog identity and the user's feedback, add recording-level evidence.
            return {**seed, **{key: value for key, value in match.items() if key in {
                'recording_genres', 'metadata_source', 'language', 'language_source', 'album', 'album_id', 'album_source',
                'deezer_album_art', 'deezer_preview_url', 'deezer_link', 'youtube_music_url', 'artists', 'duration_seconds', 'release_date', 'provider_id', 'deezer_id', 'itunes_id'}}}
        return dict(seed)
    return await asyncio.gather(*(resolve(seed) for seed in representative_seeds(seeds)))


def blocked_keys(store, profile):
    return {track_key(e.get('name'), e.get('artist')) for e in store.history(profile)
            if e.get('signal') in ('dislike', 'skip')}


def rank_pool(engine, seeds, pool, blocked=(), mode='similar', limit=36, exclude_saved=True, balance=False):
    """Multi-seed relevance with bounded artist/album repetition and explicit provenance."""
    from .catalog_cache import hydrate
    seeds=[hydrate(seed) for seed in seeds]
    pool=[hydrate(track) for track in pool]
    lengths=[float(seed['duration_seconds']) for seed in seeds if seed.get('duration_seconds')]
    typical_length=float(np.median(lengths)) if lengths else None
    known_lengths={track_key(t.get('name'),t.get('artist')):float(t['duration_seconds']) for t in pool if t.get('duration_seconds')}
    seed_keys = {track_key(t.get('name'), t.get('artist')) for t in seeds}
    artists, languages = Counter(), Counter()
    for seed in seeds:
        weight = .35 if seed.get('implicit') else 1.0
        for artist in artist_parts(seed.get('artist')):
            artists[artist_signature(artist)] += weight
        if trusted_language(seed):
            languages[trusted_language(seed)] += weight
    language_complete = bool(seeds) and all(trusted_language(seed) for seed in seeds) and mode not in {'radio','discover'}
    vectors, vector_weights = [], []
    measured_rows=[]
    for seed in seeds:
        row = seed.get('row', -1)
        if row >= 0:
            measured_rows.append(row)
            vectors.append(np.asarray(engine.embeddings[row], np.float32))
            vector_weights.append(.35 if seed.get('implicit') else 1.0)
        elif seed.get('vector') is not None:
            vectors.append(np.asarray(seed['vector'], np.float32))
            vector_weights.append(.35 if seed.get('implicit') else 1.0)
    seed_audio = np.asarray(engine.audio[measured_rows, :8], np.float32).mean(axis=0) if measured_rows and hasattr(engine,'audio') else None
    seed_genres=set()
    if hasattr(engine,'_genre_ids') and hasattr(engine,'_base_genres'):
        for row in measured_rows:seed_genres |= engine._base_genres(engine._genre_ids(row))
    unique = {}
    for track in pool:
        key = track_key(track.get('name'), track.get('artist'))
        if key in blocked or (exclude_saved and (key in seed_keys or any(recording_match(seed, track) for seed in seeds))) or not track.get('name'):
            continue
        if track.get('artist', '').casefold() in ('', 'unknown', 'unknown artist'):
            continue
        length=known_lengths.get(key)
        # A full-song listening history should not turn into a shelf of short score cues.
        if mode!='related' and typical_length and length and length<min(90,typical_length*.4):
            continue
        language = trusted_language(track)
        if language_complete and (language not in languages):
            continue
        artist_affinity = max((artists[artist_signature(a)] / max(artists.values()) for a in artist_parts(track.get('artist')) if artist_signature(a) in artists), default=0)
        language_affinity = (languages[language] / max(languages.values())) if language in languages else 0
        similarity = 0
        row = track.get('row', -1)
        if row >= 0 and vectors:
            dots = np.asarray(vectors) @ np.asarray(engine.embeddings[row], np.float32)
            similarity = .65 * float(np.max(dots * np.asarray(vector_weights))) + .35 * float(np.average(dots, weights=vector_weights))
        # Provider tracks do not have measured audio or embeddings; don't fabricate either.
        if mode=='radio':
            signals=track.get('signals') or {}
            audio=float(signals.get('audio',0));genre=float(signals.get('genre',0))
            # Every candidate is compared with this song, including listener-neighbor joins.
            if row>=0 and seed_audio is not None:
                audio=max(0,1-float(np.linalg.norm(np.asarray(engine.audio[row,:8])-seed_audio))/np.sqrt(8))
            if row>=0 and seed_genres:
                genres=engine._base_genres(engine._genre_ids(row))
                genre=len(genres & seed_genres)/max(len(genres | seed_genres),1)
            relevance=.30*similarity+.15*audio+.08*genre+.14*float(track.get('popularity',0) or 0)+.31*float(track.get('listening_similarity',0) or 0)+.02*artist_affinity
        elif mode=='related':
            relevance=.35*similarity+.5*artist_affinity+.15*language_affinity
        elif mode=='vibe' and row>=0 and seed_audio is not None:
            from .flow import audio_similarity
            sound=float(audio_similarity(engine.audio[row,:8],seed_audio))
            genre=0.
            if seed_genres:
                genres=engine._base_genres(engine._genre_ids(row))
                genre=len(genres & seed_genres)/max(len(genres | seed_genres),1)
                if not genre:
                    continue
            relevance=.55*sound+.30*similarity+.15*genre
        else:
            relevance=.5*similarity+.22*artist_affinity+.28*language_affinity
        if language_complete and not language:
            relevance *= .35
        popularity = float(track.get('popularity', 0) or 0)
        if mode == 'popular': relevance = .7 * relevance + .3 * popularity
        if mode == 'discover': relevance += .12 * (1 - artist_affinity)
        card = dict(track)
        card['_relevance'] = relevance
        card['reason'] = ('More from this artist' if artist_affinity else
                          'A similar sound' if similarity else 'A new discovery')
        previous = unique.get(key)
        if previous is None or (bool(language), relevance) > (bool(trusted_language(previous)), previous['_relevance']):
            unique[key] = card
    selected, artist_counts, album_counts = [], Counter(), Counter()
    candidates = sorted(unique.values(), key=lambda track: (-track['_relevance'], track_key(track['name'], track['artist'])))
    if balance and seeds:
        cohorts={};cohort_weights=Counter()
        for seed in seeds:
            cohort=trusted_language(seed) or 'artist:'+artist_signature(artist_parts(seed.get('artist'))[0])
            cohorts.setdefault(cohort,set()).update(artist_signature(a) for a in artist_parts(seed.get('artist')))
            cohort_weights[cohort]+=.35 if seed.get('implicit') else 1
        buckets={cohort:[] for cohort in cohorts}
        for card in candidates:
            language=trusted_language(card)
            cohort=language if language in cohorts else next((c for c,names in cohorts.items() if c.startswith('artist:') and names & {artist_signature(a) for a in artist_parts(card.get('artist'))}),None)
            if cohort:buckets[cohort].append(card)
        # Cover each taste, then allocate space by saved evidence with diminishing returns.
        covered=[];seen_keys=set();allocated=Counter()
        for cohort,bucket in buckets.items():
            if bucket:
                card=bucket.pop(0);identity=track_key(card['name'],card['artist'])
                if identity not in seen_keys:covered.append(card);seen_keys.add(identity);allocated[cohort]+=1
        quota=max(len(covered),int(np.ceil(limit*.75)))
        while len(covered)<quota and any(buckets.values()):
            cohort=max((c for c in buckets if buckets[c]),key=lambda c:np.sqrt(cohort_weights[c])/(1+allocated[c]))
            card=buckets[cohort].pop(0);identity=track_key(card['name'],card['artist'])
            if identity not in seen_keys:covered.append(card);seen_keys.add(identity);allocated[cohort]+=1
        candidates=covered+[c for c in candidates if track_key(c['name'],c['artist']) not in seen_keys]
    # Diversity is applied after ranking; never fill a shelf with one composer or soundtrack.
    for card in candidates:
        primary = artist_signature(artist_parts(card['artist'])[0])
        album = album_context(card)
        if artist_counts[primary] >= (max(6,limit//2) if mode=='related' else 3 if mode=='similar' else 2):
            continue
        if album and album_counts[album] >= (4 if mode=='related' else 2):
            continue
        card.pop('_relevance', None)
        from .catalog_cache import hydrate
        selected.append(public_track(hydrate(card)))
        artist_counts[primary] += 1
        if album: album_counts[album] += 1
        if len(selected) >= limit: break
    return selected


def local_pool(engine, seeds, profile, store, mode='similar'):
    candidates = []
    excluded = {e['row'] for e in store.history(profile) if e.get('signal') in ('dislike', 'skip') and e.get('row', -1) >= 0}
    rows = list(dict.fromkeys(seed.get('row', -1) for seed in representative_seeds(seeds,12) if seed.get('row', -1) >= 0))
    for row in rows:
        if hasattr(engine, 'recommend'):
            candidates += engine.recommend([row], k=60 if mode=='radio' else 32, mode=mode, max_per_artist=2 if mode!='related' else 10, candidates=8000 if mode=='radio' else 2000, exclude_rows=excluded)
    vec = store._valid_vector(profile.get('long_term'))
    if vec is not None and mode not in {'radio','related'}:
        candidates += engine.recommend_by_vector(vec, k=60, max_per_artist=2, exclude_rows=excluded)
    return [{**engine.track_card(t['row']), **t} for t in candidates if t.get('row', -1) >= 0]


def bridge_catalog(engine, tracks):
    """Join provider recordings to learned embeddings by title AND matching artist identity."""
    if not hasattr(engine, 'catalog') or '_title_key' not in engine.catalog:
        return tracks
    from .engine import _norm_title
    wanted = {_norm_title(t.get('name', '')) for t in tracks}
    matches = engine.catalog[engine.catalog['_title_key'].isin(wanted)]
    by_title = {}
    for _, row in matches.iterrows():
        by_title.setdefault(row['_title_key'], []).append(int(row['_row']))
    bridged = []
    for track in tracks:
        rows = by_title.get(_norm_title(track.get('name', '')), [])
        # Verified provider credits can connect a vocalist selection to a catalog
        # that indexes this same recording under its composer.
        credit_names=[a.get('name','') for a in track.get('artists',[]) if isinstance(a,dict)]
        identity={**track,'artist':', '.join([track.get('artist',''),*credit_names])}
        valid = [row for row in rows if recording_match(identity, engine.track_card(row))]
        if valid:
            row = max(valid, key=lambda row: engine.pop[row])
            from .media import merge_metadata
            model=engine.track_card(row)
            card = merge_metadata(model,public_track(track))
            # Preserve the selected release and provider's full credited identity.
            card.update({key:track[key] for key in ('name','artist','source','track_id','album','album_id','album_source') if track.get(key)})
            card.update(row=row,embedding_source='matched_catalog_recording')
            card.pop('is_live_external', None)
            bridged.append(card)
        else:
            bridged.append(track)
    return bridged


async def discovery_context(engine, store, profile, seeds=None, mode='similar'):
    seeds = seeds if seeds is not None else store.taste_seeds(profile)
    seeds = await resolve_recordings(seeds)
    seeds = await asyncio.to_thread(bridge_catalog,engine,seeds)
    artist_counts = Counter(a for seed in seeds for a in artist_parts(seed.get('artist')))
    languages = Counter(trusted_language(seed) for seed in seeds if trusted_language(seed))
    queries = [artist for artist, _ in artist_counts.most_common(4)]
    queries += [f'{language} songs' for language, _ in languages.most_common(4)]
    live = await asyncio.gather(*(lookup(query, 30) for query in queries))
    pool = await asyncio.to_thread(bridge_catalog, engine, [track for group in live for track in group])
    pool += await asyncio.to_thread(local_pool, engine, seeds, profile, store, mode)
    if mode in {'radio','discover'}:
        # Model-ranked cross-artist candidates are a separate pool from artist exploration.
        rows=[s.get('row') for s in seeds if s.get('row',-1)>=0]
        if rows:
            more=await asyncio.to_thread(engine.recommend,rows[:4],k=100,mode='radio',max_per_artist=2,candidates=12000)
            pool += [{**engine.track_card(t['row']),**t} for t in more]
    if mode=='radio' and len(seeds)==1:
        from .neighbors import listening_neighbors
        pool += await asyncio.to_thread(listening_neighbors,engine,seeds[0])
    return seeds, pool


async def recommend_track(engine, store, profile, seed, limit=24, mode='similar'):
    if mode=='flow':
        from .flow import row_of
        if row_of(engine,seed) is None:
            seed={**seed,'row':-1}
    # Resolve an external selection back to the catalog only when both identities match.
    if seed.get('row', -1) < 0 and hasattr(engine, 'search'):
        hits = await asyncio.to_thread(engine.search, clean_title(seed.get('name')), 8)
        hit = next((h for h in hits if recording_match(seed, h)), None)
        if hit:
            from .media import merge_metadata
            model=engine.track_card(hit['row'])
            merged=merge_metadata(model,seed)
            merged.update({k:seed[k] for k in ('name','artist','source','track_id') if seed.get(k)})
            seed=merged
    seeds, pool = await discovery_context(engine, store, profile, [seed], 'radio' if mode=='flow' else mode)
    from .catalog_cache import hydrate
    if mode=='flow':
        from .flow import candidate_pool,rank_flow
        taste=await asyncio.to_thread(bridge_catalog,engine,[hydrate(t) for t in store.taste_seeds(profile)])
        selected_seed=hydrate(seeds[0] if seeds else seed)
        pool,anchors,kind=await asyncio.to_thread(candidate_pool,engine,selected_seed,taste,pool)
        recs=await asyncio.to_thread(rank_flow,engine,selected_seed,taste,pool,store.history(profile),
                                     list(profile.get('listening',{}).values()),limit,anchors,kind)
        return selected_seed,recs
    return hydrate(seeds[0] if seeds else seed), rank_pool(engine, seeds, pool, blocked_keys(store, profile), mode, limit)


async def mood_tracks(engine, mood_model, query, count=24, profile=None, store=None):
    words = set(query.casefold().split())
    requested_languages = words & LANGUAGE_NAMES
    if not requested_languages and profile and store:
        learned = Counter(trusted_language(seed) for seed in store.taste_seeds(profile) if trusted_language(seed))
        seeds = store.taste_seeds(profile)
        if learned and all(trusted_language(seed) for seed in seeds):
            requested_languages = {language for language, _ in learned.most_common(2)}
    projected = mood_model.transform(query)
    if profile and store and profile.get('long_term') is not None:
        taste = store._valid_vector(profile['long_term'])
        if taste is not None:
            vector = .8 * projected['vector'] + .2 * taste
            norm = np.linalg.norm(vector)
            projected['vector'] = vector / norm if norm else vector
    if requested_languages:
        groups = await asyncio.gather(*(lookup(query if language in words else f"{language} {query}", 50) for language in sorted(requested_languages)))
        candidates = [track for group in groups for track in group if trusted_language(track) in requested_languages]
        broadened = False
        if not candidates and projected.get('coverage'):
            # Providers search titles, not audio moods. When the mood words have no
            # title matches, gather a verified regional pool for the trained model.
            broadened = True
            queries = [f"{language} songs" for language in sorted(requested_languages)]
            if profile and store:
                artists = Counter(artist for seed in store.taste_seeds(profile) for artist in artist_parts(seed.get('artist')))
                queries += [artist for artist, _ in artists.most_common(2)]
            queries = list(dict.fromkeys(queries))
            regional = await asyncio.gather(*(lookup(term, 50) for term in queries))
            candidates = [track for group in regional for track in group if trusted_language(track) in requested_languages]
        candidates = await asyncio.to_thread(bridge_catalog, engine, candidates)
        if broadened:
            # Regional popularity alone is not evidence of the requested mood.
            candidates = [track for track in candidates if track.get('row', -1) >= 0 and hasattr(engine, 'audio')]
        unique = {track_key(t.get('name'), t.get('artist')): t for t in candidates}
        def distance(track):
            row = track.get('row', -1)
            if row >= 0 and hasattr(engine, 'audio'):
                return float(np.linalg.norm(np.asarray(engine.audio[row, :8]) - projected['audio']))
            return float('inf')
        tracks = sorted(unique.values(), key=distance)
    else:
        if not projected.get('coverage'):
            return []
        recs = await asyncio.to_thread(engine.recommend_by_vector, projected['vector'], k=count * 3,
                                      target_audio=projected.get('audio'), max_per_artist=2)
        tracks = [{**engine.track_card(t['row']), **t} for t in recs]
    blocked = blocked_keys(store, profile) if profile and store else set()
    tracks = [t for t in tracks if t.get('artist', '').casefold() not in ('', 'unknown', 'unknown artist')
              and track_key(t.get('name'), t.get('artist')) not in blocked]
    return [public_track(t) for t in tracks[:count]]
