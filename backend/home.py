"""Home is learned from the library and completed previews, with no setup form."""
from .discovery import rank_pool, blocked_keys
from .metadata import artist_parts, public_track, representative_seeds, recording_match
from .profiles import track_key


def build_home(engine, mood_model, store, profile, live_results=None, seeds=None, pool=None):
    seeds = representative_seeds(list(seeds if seeds is not None else store.taste_seeds(profile)))
    has_history = bool(seeds)
    blocked = blocked_keys(store, profile)
    blocked |= {track_key(event.get('name'), event.get('artist')) for event in store.history(profile) if event.get('signal') == 'like'}
    if pool is None:
        from .discovery import local_pool
        pool = local_pool(engine, seeds, profile, store)
        pool += [t for group in (live_results or {}).values() for t in group]
    saved=[event for event in store.history(profile) if event.get('signal')=='like']
    pool=[t for t in pool if not any(recording_match(event,t) for event in saved)]
    sections = []
    if seeds:
        rotation = rank_pool(engine, seeds, pool, blocked, limit=16, balance=True)
        if rotation:
            sections.append({'id': 'rotation', 'title': 'For your rotation',
                'subtitle': 'New finds connected to the songs you save and play.', 'tracks': rotation})
        used = {track_key(t['name'], t['artist']) for t in rotation}
        more = rank_pool(engine, seeds, pool, blocked | used, mode='discover', limit=16, balance=True)
        if more:
            sections.append({'id': 'discover', 'title': 'A little further out',
                'subtitle': 'A different side of your listening.', 'tracks': more})
    else:
        rows = sorted(engine._catalog_rows, key=lambda row: -engine.pop[row])[:300]
        candidates = [engine.track_card(int(row)) for row in rows]
        tracks = rank_pool(engine, [], candidates, blocked, mode='popular', limit=12)
        sections.append({'id': 'starting_points', 'title': 'Find your next favorite',
                         'subtitle': 'Save songs you love. Your home starts learning from the first one.', 'tracks': tracks})
    recent = [public_track(event) for event in store.history(profile) if event.get('signal') == 'like'][:8]
    return {'user': profile.get('user', 'Guest'), 'has_history': has_history, 'sections': sections,
            'recent': recent, 'saved_count': len(profile.get('likes', [])),
            'listening_count': len(profile.get('listening', {})),
            'learning_from': [{'name': t['name'], 'artist': t['artist']} for t in seeds[:6]],
            'taste_summary': (f"Inspired by {len(seeds)} songs in your listening" if seeds else 'Your music, your starting point')}
