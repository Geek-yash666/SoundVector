"""Regression coverage for feedback transitions and home composition (no artifacts/network)."""
import json
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.home import build_home
from backend.profiles import ProfileStore
from backend import routes, discovery
from backend.metadata import recording_metadata, trusted_language, recording_match
from backend.discovery import rank_pool


class Catalog:
    embed_dim = 3
    embeddings = np.array([[1, 0, 0], [.9, .1, 0], [0, 1, 0], [0, .9, .1], [0, 0, 1]], np.float32)
    _names = np.array(['First', 'Second', 'Other', 'Fourth', 'Fifth'])
    _artists = np.array(['Artist A', 'Artist A', 'Artist B', 'Artist B', 'Artist C'])
    meta = pd.DataFrame({'track_id': ['a', 'b', 'c', 'd', 'e']})
    pop = np.array([.9, .8, .7, .6, .5])
    genre_vocab = ['telugu pop', 'rock']
    _genre_indices = np.array([0, 0, 1, 1, 1])
    _genre_offsets = np.arange(6)
    canonical_row = np.arange(5)
    _catalog_rows = np.arange(5)

    def genre_labels(self, row):
        return [self.genre_vocab[self._genre_indices[row]]]

    def track_card(self, row):
        return {'row': row, 'name': str(self._names[row]), 'artist': str(self._artists[row]),
                'genres': self.genre_labels(row), 'base_genres': self.genre_labels(row)}

    def _row_to_track(self, row):
        return self.track_card(row)

    def artist_top_tracks(self, artist, limit=15):
        return [self.track_card(i) for i, name in enumerate(self._artists) if name == artist][:limit]

    def recommend_by_vector(self, vec, **kwargs):
        # Deliberately include a skipped song; the feed must also filter it at composition.
        return [self.track_card(i) for i in np.argsort(-(self.embeddings @ vec))]


@pytest.fixture
def store(tmp_path):
    return ProfileStore(Catalog(), str(tmp_path))


class NoCoverage:
    def transform(self, text):
        return {'coverage': False, 'vector': np.array([0, 0, 1], np.float32), 'audio': np.zeros(8)}


def like(store, row=0, signal='like', user='Alice'):
    return store.feedback(user, row, signal)


def test_row_zero_likes_persist_and_home_uses_artist(store):
    like(store)
    profile = store.load('Alice')
    assert profile['likes'] == ['a']
    assert profile['artist_counts'] == {'Artist A': 1}
    assert profile['genre_counts'] == {'telugu pop': 1}
    assert profile['short_term'] is not None
    feed = build_home(store.engine, NoCoverage(), store, profile)
    assert feed['has_history']
    assert feed['sections'][0]['title'] == 'For your rotation'
    assert all(t['row'] != 0 for section in feed['sections'] for t in section['tracks'])
    assert len({t['artist'] for t in feed['sections'][0]['tracks']}) > 1
    assert 'preferences' not in feed


def test_repeat_like_does_not_double_count_and_dislike_removes_positive_taste(store):
    like(store); like(store)
    assert store.load('Alice')['artist_counts'] == {'Artist A': 1}
    profile = like(store, signal='dislike')
    assert profile['likes'] == [] and profile['skips'] == ['a']
    assert profile['genre_counts'] == {} and profile['artist_counts'] == {}
    assert profile['long_term'] is None


def test_unlike_rebuilds_vector_from_remaining_likes(store):
    like(store, 0); like(store, 2)
    profile = like(store, 0, 'none')
    np.testing.assert_allclose(profile['long_term'], [0, 1, 0])
    assert profile['genre_counts'] == {'rock': 1}
    assert profile['artist_counts'] == {'Artist B': 1}


def test_external_like_without_projection_still_personalizes(store):
    profile = store.feedback('Alice', -1, 'like', {'name': 'New Release', 'artist': 'New Artist'}, NoCoverage())
    assert profile['long_term'] is None
    live = {'New Artist': [{'row': -1, 'name': 'Another Release', 'artist': 'New Artist'}]}
    feed = build_home(store.engine, NoCoverage(), store, profile, live)
    assert feed['has_history']
    assert feed['sections'][0]['tracks'][0]['name'] == 'Another Release'


def test_external_like_uses_catalog_artist_metadata(store):
    profile = store.feedback('Alice', -1, 'like', {'name': 'New Release', 'artist': 'Artist A'}, NoCoverage())
    assert profile['long_term'] is not None
    assert profile['genre_counts'] == {}
    assert store.history(profile)[0]['vector_source'] == 'artist_anchor'


def test_valid_row_with_wrong_artist_is_not_another_catalog_song(store):
    profile = store.feedback('Alice', 0, 'like', {'name': 'First', 'artist': 'New Artist'}, NoCoverage())
    assert store.history(profile)[0]['row'] == -1
    assert profile['artist_counts'] == {'New Artist': 1}
    assert profile['long_term'] is None


def test_disliked_songs_and_cross_section_duplicates_are_excluded(store):
    like(store, 0); profile = like(store, 1, 'dislike')
    feed = build_home(store.engine, NoCoverage(), store, profile)
    tracks = [t for s in feed['sections'] for t in s['tracks']]
    assert all(t['row'] != 1 for t in tracks)
    assert len({t['row'] for t in tracks}) == len(tracks)


def test_manual_preferences_do_not_replace_song_evidence(store):
    store.set_preferences('Alice', ['Artist A'], ['Telugu'])
    feed = build_home(store.engine, NoCoverage(), store, store.load('Alice'))
    assert not feed['has_history']
    assert 'preferences' not in feed
    assert not store.load('Bob').get('likes')


def test_artist_genres_cannot_prove_recording_language():
    assert trusted_language({'genres': ['tamil pop'], 'language': 'tamil'}) is None
    assert trusted_language(recording_metadata('Telugu')) == 'telugu'
    assert trusted_language(recording_metadata('Soundtrack')) is None


def test_old_inherited_external_genres_are_repaired_on_load(store):
    profile = store.feedback('Alice', -1, 'like', {'name': 'New Release', 'artist': 'Artist A', 'base_genres': ['soundtrack']}, NoCoverage())
    profile['schema_version'] = 2
    next(iter(profile['feedback'].values()))['genres'] = ['soundtrack', 'tamil pop']
    store.save('Alice', profile)
    restored = store.load('Alice')
    assert next(iter(restored['feedback'].values()))['genres'] == ['soundtrack']
    assert restored['genre_counts'] == {'soundtrack': 1}
    assert len(restored['likes']) == 1


def test_legacy_event_migration_uses_latest_signal(store):
    Path = __import__('pathlib').Path
    Path(store._path('Alice')).write_text(json.dumps({'user': 'Alice', 'n_events': 4, 'likes': ['a'], 'long_term': [1, 0, 0]}))
    events = [dict(name='First', artist='Artist A', row=0, track_id='a', signal=s, ts=i)
              for i, s in enumerate(['like', 'like', 'dislike', 'none'])]
    Path(store._events_path('Alice')).write_text(''.join(json.dumps(e) + '\n' for e in events))
    profile = store.load('Alice')
    assert profile['likes'] == [] and profile['skips'] == []
    assert profile['long_term'] is None


def test_concurrent_feedback_does_not_lose_likes(store):
    with ThreadPoolExecutor(max_workers=5) as pool:
        list(pool.map(lambda row: like(store, row), range(5)))
    profile = store.load('Alice')
    assert len(profile['likes']) == 5
    assert sum(profile['artist_counts'].values()) == 5


def test_feedback_validation_and_profile_api(store, monkeypatch):
    monkeypatch.setattr(routes, 'get_app_components', lambda: (store.engine, NoCoverage(), None, None, store))
    with TestClient(routes.app) as client:
        assert client.post('/api/feedback', json={'user': 'Alice', 'row': 0}).status_code == 200
        data = client.get('/api/profile?user=Alice').json()
        assert data['history'][0]['name'] == 'First'
        assert client.post('/api/feedback', json={'signal': 'oops', 'row': 0}).status_code == 422
        assert client.get('/api/search?q=   ').json()['results'] == []
        assert client.put('/api/preferences', json={'user': 'Alice', 'artists': ['Artist A'], 'languages': ['Telugu']}).status_code == 410
        assert 'preferences' not in client.get('/api/profile?user=Alice').json()


def test_recording_alias_is_matched_without_artist_allowlists():
    original = {'name': 'A Song (From "A Film")', 'artist': 'Composer S'}
    alias = {'name': 'A Song', 'artist': 'S.S. Composer & Singer'}
    assert recording_match(original, alias)
    assert not recording_match(original, {**alias, 'artist': 'A Cover Band'})


def test_verified_recording_language_prevents_wrong_language_and_unknown_filler(store):
    seed = {'name': 'Saved', 'artist': 'Composer S', 'row': -1, **recording_metadata('Telugu')}
    pool = [{'name': 'Correct', 'artist': 'Other Artist', 'row': -1, **recording_metadata('Telugu')},
            {'name': 'Wrong Language', 'artist': 'Composer S', 'row': -1, **recording_metadata('Tamil')},
            {'name': 'Unverified', 'artist': 'Composer S', 'row': -1, 'genres': ['telugu pop']}]
    ranked = rank_pool(store.engine, [seed], pool)
    assert [t['name'] for t in ranked] == ['Correct']


def test_home_resolves_language_from_saved_recording_without_manual_setup(store, monkeypatch):
    store.feedback('Alice', -1, 'like', {'name': 'New Song', 'artist': 'Unlisted Artist'}, NoCoverage())
    queries = []
    async def lookup(query, limit):
        queries.append(query)
        if 'new song' in query.casefold():
            return [{'row': -1, 'name': 'New Song', 'artist': 'Unlisted Artist', **recording_metadata('Telugu')}]
        return [{'row': -1, 'name': 'Regional Pick', 'artist': 'Another Artist', **recording_metadata('Telugu')}]
    monkeypatch.setattr(routes, 'get_app_components', lambda: (store.engine, NoCoverage(), None, None, store))
    monkeypatch.setattr(discovery, 'lookup', lookup)
    with TestClient(routes.app) as client:
        response = client.get('/api/home?user=Alice')
    assert response.status_code == 200
    assert 'telugu songs' in queries
    data = response.json()
    assert data['has_history']
    assert data['sections'][0]['tracks'][0]['name'] == 'Regional Pick'
    assert trusted_language(store.history(store.load('Alice'))[0]) == 'telugu'


def test_completed_previews_are_weak_signals_without_becoming_likes(store):
    first = store.record_listen('Alice', 0, {}, 3, 30, 'one')
    assert store.taste_seeds(first) == []
    partial = store.record_listen('Alice', 0, {}, 8, 30, 'one')
    assert store.taste_seeds(partial) == []
    completed = store.record_listen('Alice', 0, {}, 25, 30, 'one')
    assert len(store.taste_seeds(completed)) == 1
    assert store.taste_seeds(completed)[0]['implicit']
    assert completed['likes'] == []
    assert len(completed['listening']) == 1
    again = store.record_listen('Alice', 0, {}, 25, 30, 'one')
    assert len(again['listening']) == 1


def test_hidden_songs_do_not_return_as_implicit_listening_seeds(store):
    store.record_listen('Alice', 0, {}, 25, 30, 'one')
    profile = like(store, 0, 'dislike')
    assert store.taste_seeds(profile) == []


def test_multiple_recordings_drive_home_without_recommending_saved_tracks(store):
    like(store, 0);profile = like(store, 2)
    feed = build_home(store.engine, NoCoverage(), store, profile)
    tracks = [track for section in feed['sections'] for track in section['tracks']]
    assert all(track['row'] not in (0, 2) for track in tracks)
    assert len(feed['learning_from']) == 2


def test_duplicate_recording_aliases_do_not_return_as_new_discoveries(store):
    seed = {'row': -1, 'name': 'A Song (From "Movie")', 'artist': 'Composer S'}
    duplicate = {'row': -1, 'name': 'A Song', 'artist': 'S.S. Composer & Singer'}
    assert rank_pool(store.engine, [seed], [duplicate]) == []


def test_album_and_artist_caps_limit_repetition(store):
    pool = [{'row': -1, 'name': f'Track {i} (From "Same Film")', 'artist': f'Artist {i}'} for i in range(10)]
    result = rank_pool(store.engine, [], pool)
    assert len(result) == 2


def test_catalog_bridge_uses_real_audio_and_keeps_recording_metadata(store):
    from backend.discovery import bridge_catalog
    engine = store.engine
    engine.catalog = pd.DataFrame({'_title_key': ['first'], '_row': [0]})
    original_card = engine.track_card
    engine.track_card = lambda row: {**original_card(row), 'energy': .12}
    live = {'row': -1, 'name': 'First (From "Movie")', 'artist': 'Artist A', 'energy': .70,
            'is_live_external': True, **recording_metadata('Telugu')}
    result = bridge_catalog(engine, [live])[0]
    assert result['row'] == 0
    assert result['energy'] == .12
    assert result['language'] == 'telugu'
    assert result['embedding_source'] == 'matched_catalog_recording'


def test_different_artist_initials_are_not_a_recording_alias():
    assert not recording_match({'name': 'Song', 'artist': 'Artist A'}, {'name': 'Song', 'artist': 'Artist B'})


def test_mood_uses_learned_recording_language_and_excludes_hidden_songs(store, monkeypatch):
    import asyncio
    profile = store.feedback('Alice', -1, 'like', {'name': 'Saved Song', 'artist': 'Singer', **recording_metadata('Telugu')}, NoCoverage())
    queries = []
    async def lookup(query, limit):
        queries.append(query)
        return [{'row': -1, 'name': 'Right Match', 'artist': 'Artist One', **recording_metadata('Telugu')},
                {'row': -1, 'name': 'Wrong Match', 'artist': 'Artist Two', **recording_metadata('Tamil')}]
    monkeypatch.setattr(discovery, 'lookup', lookup)
    result = asyncio.run(discovery.mood_tracks(store.engine, NoCoverage(), 'relaxing acoustic', 10, profile, store))
    assert queries == ['telugu relaxing acoustic']
    assert [t['name'] for t in result] == ['Right Match']


def test_explicit_language_request_overrides_learned_language(store, monkeypatch):
    import asyncio
    profile = store.feedback('Alice', -1, 'like', {'name': 'Saved Song', 'artist': 'Singer', **recording_metadata('Telugu')}, NoCoverage())
    queries = []
    async def lookup(query, limit):
        queries.append(query)
        return []
    monkeypatch.setattr(discovery, 'lookup', lookup)
    result = asyncio.run(discovery.mood_tracks(store.engine, NoCoverage(), 'tamil songs', 10, profile, store))
    assert queries == ['tamil songs']
    assert result == []


def test_partial_language_evidence_does_not_erase_other_saved_tastes(store):
    regional = {'row': 0, 'name': 'First', 'artist': 'Artist A', **recording_metadata('Telugu')}
    other = {'row': 2, 'name': 'Other', 'artist': 'Artist B'}
    pool = [store.engine.track_card(3), {'row': -1, 'name': 'Regional Pick', 'artist': 'Artist C', **recording_metadata('Telugu')}]
    result = rank_pool(store.engine, [regional, other], pool)
    assert {track['name'] for track in result} == {'Fourth', 'Regional Pick'}


def test_recent_completed_listens_are_not_buried_below_older_likes(store):
    profile = like(store, 0)
    next(iter(profile['feedback'].values()))['ts'] = 1
    store.save('Alice', profile)
    profile = store.record_listen('Alice', 2, {}, 25, 30, 'new-listen')
    seeds = store.taste_seeds(profile)
    assert seeds[0]['name'] == 'Other' and seeds[0]['implicit']
    assert len(profile['likes']) == 1


def test_replaying_a_saved_song_refreshes_taste_without_duplicating_or_editing_feedback(store):
    profile = like(store, 0)
    event = next(iter(profile['feedback'].values()))
    event['ts'] = 1
    store.save('Alice', profile)
    profile = store.record_listen('Alice', 0, {}, 25, 30, 'new-listen')
    seeds = store.taste_seeds(profile)
    assert len(seeds) == 1 and not seeds[0].get('implicit')
    assert seeds[0]['ts'] > 1
    assert next(iter(profile['feedback'].values()))['ts'] == 1


def test_recently_played_does_not_claim_to_be_a_saved_collection(store):
    profile = store.record_listen('Alice', 2, {}, 25, 30, 'new-listen')
    feed = build_home(store.engine, NoCoverage(), store, profile)
    assert feed['has_history']
    assert feed['recent'] == []


def test_mood_can_rank_a_verified_regional_pool_when_provider_mood_search_is_empty(store, monkeypatch):
    import asyncio
    profile=store.feedback('Alice',-1,'like',{'name':'Saved','artist':'Singer',**recording_metadata('Telugu')},NoCoverage())
    class CoveredMood:
        def transform(self,text):
            return {'coverage':True,'vector':np.array([1,0,0],np.float32),'audio':np.zeros(8,np.float32)}
    queries=[]
    async def lookup(query,limit):
        queries.append(query)
        if query=='telugu songs':
            return [{'row':0,'name':'Calmer','artist':'Another singer',**recording_metadata('Telugu')},
                    {'row':2,'name':'Louder','artist':'Second singer',**recording_metadata('Telugu')},
                    {'row':3,'name':'Wrong language','artist':'Third singer',**recording_metadata('Tamil')}]
        return []
    monkeypatch.setattr(discovery,'lookup',lookup)
    monkeypatch.setattr(discovery,'bridge_catalog',lambda engine,tracks:tracks)
    monkeypatch.setattr(store.engine,'audio',np.array([[.1]*8,[.3]*8,[.9]*8,[0]*8,[0]*8]),raising=False)
    result=asyncio.run(discovery.mood_tracks(store.engine,CoveredMood(),'relaxing acoustic',10,profile,store))
    assert 'telugu songs' in queries
    assert [t['name'] for t in result]==['Calmer','Louder']
    assert all(trusted_language(t)=='telugu' for t in result)


def test_unknown_mood_does_not_produce_arbitrary_catalog_recommendations(store,monkeypatch):
    import asyncio
    monkeypatch.setattr(store.engine,'recommend_by_vector',lambda *args,**kwargs: (_ for _ in ()).throw(AssertionError('unknown prompt must not retrieve')),raising=False)
    assert asyncio.run(discovery.mood_tracks(store.engine,NoCoverage(),'unrecognized tokens',10))==[]


def test_regional_mood_backfill_never_presents_unmeasured_popular_songs_as_mood_matches(store,monkeypatch):
    import asyncio
    profile=store.feedback('Alice',-1,'like',{'name':'Saved','artist':'Singer',**recording_metadata('Telugu')},NoCoverage())
    class CoveredMood:
        def transform(self,text):return {**NoCoverage().transform(text),'coverage':True}
    async def lookup(query,limit):
        return [] if query=='telugu relaxing acoustic' else [{'row':-1,'name':'Unmeasured song','artist':'Singer',**recording_metadata('Telugu')}]
    monkeypatch.setattr(discovery,'lookup',lookup)
    result=asyncio.run(discovery.mood_tracks(store.engine,CoveredMood(),'relaxing acoustic',10,profile,store))
    assert result==[]
