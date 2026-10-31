"""Search, metadata, taste coverage and optional-provider regression boundaries."""
import asyncio
import json
from types import SimpleNamespace
import numpy as np
import pandas as pd
import pytest
from backend import catalog_cache, search, external_api, neighbors, curation
from backend.media import merge_metadata, deezer_track, itunes_track
from backend.metadata import representative_seeds, recording_metadata
from backend.discovery import rank_pool
from backend.rag_dj import RAGDJ


@pytest.fixture(autouse=True)
def isolated_metadata(tmp_path, monkeypatch):
    monkeypatch.setenv('SOUNDVECTOR_CACHE_DIR', str(tmp_path))
    monkeypatch.setattr(catalog_cache, '_DB', None)
    yield
    if catalog_cache._DB is not None:
        catalog_cache._DB.close()


class TinyCatalog:
    _names = np.array(['Night Hours', 'Night Hours', 'Night House'])
    _artists = np.array(['Original Artist', 'Obscure Cover', 'Other Artist'])
    _artist_names = _artists
    _catalog_rows = np.arange(3)
    pop = np.array([.9, .1, .3])
    embeddings = np.array([[1., 0.], [.8, .2], [.7, .3]])
    def track_card(self, row):
        return {'row': int(row), 'name': self._names[row], 'artist': self._artists[row], 'popularity': float(self.pop[row])}
    def search(self, query, limit=12):
        return [self.track_card(i) for i in range(3) if self._names[i].casefold() == query.casefold()][:limit]
    def artist_top_tracks(self, query, limit=12):
        return [self.track_card(i) for i in range(3) if query.casefold() in self._artists[i].casefold()][:limit]


def test_typo_index_keeps_the_popular_recording_and_artist_query():
    index = search.SearchIndex(TinyCatalog())
    tracks, correction = index.find('night hurs')
    assert tracks[0]['artist'] == 'Original Artist'
    assert correction == 'Night Hours'
    tracks, _ = index.find('Night Hours Original Artist')
    assert tracks[0]['row'] == 0


def test_provider_rank_cannot_replace_model_popularity_or_selected_release():
    original = {'row': 0, 'name': 'Song', 'artist': 'Artist', 'popularity': .9,
                'album': 'Original release', 'album_id': '10', 'album_source': 'deezer', 'deezer_album_art': 'selected-art'}
    extra = {'popularity': .1, 'provider_rank': 100000, 'album': 'Compilation', 'album_id': '20', 'album_source': 'itunes', 'deezer_album_art': 'other-art'}
    result = merge_metadata(original, extra)
    assert result['popularity'] == .9 and result['provider_rank'] == 100000
    assert result['album_id'] == '10' and result['deezer_album_art'] == 'selected-art'


def test_progressive_search_does_not_wait_for_provider_completion(monkeypatch):
    async def check():
        finished = asyncio.Event()
        key = 'progressive test'
        monkeypatch.setattr(search, '_RESULTS', {})
        monkeypatch.setattr(search, '_JOBS', {})
        monkeypatch.setattr(search, 'index_for', lambda engine: SimpleNamespace(find=lambda *a: ([{'row': 0, 'name': 'Progressive test', 'artist': 'Artist'}], '')))
        async def provider(*args):
            await finished.wait()
            search._RESULTS[key] = {'time': 0, 'pending': False, 'data': {'pending': False, 'results': []}}
        monkeypatch.setattr(search, '_live', provider)
        result = await asyncio.wait_for(search.search(None, key, quick=True), timeout=.25)
        assert result['pending'] and result['results'][0]['name'] == 'Progressive test'
        finished.set()
        await search._JOBS[key]
    asyncio.run(check())


def test_album_pagination_keeps_all_tracks_and_provider_metadata(monkeypatch):
    urls = []
    def fetch(url):
        urls.append(url)
        if '/tracks?' in url:
            return {'data': [{'id': 3, 'title': 'Third', 'duration': 190, 'artist': {'name': 'Singer C'}}]}
        return {'id': 10, 'title': 'Film soundtrack', 'nb_tracks': 3, 'label': 'Label', 'artist': {'name': 'Composer'},
                'tracks': {'data': [{'id': 1, 'title': 'First', 'duration': 180, 'artist': {'name': 'Singer A'}},
                                    {'id': 2, 'title': 'Second', 'duration': 200, 'artist': {'name': 'Singer B'}}]}}
    monkeypatch.setattr(external_api, '_fetch_json', fetch)
    release = external_api.fetch_album_tracks('', album_id='10', source='deezer')
    assert release['complete'] and release['loaded_count'] == release['track_count'] == 3
    assert release['duration_seconds'] == 570 and len(urls) == 2
    assert release['tracks'][0]['duration_seconds'] == 180
    assert release['tracks'][0]['label'] == 'Label'


def test_itunes_lookup_explicitly_requests_the_complete_release(monkeypatch):
    urls = []
    monkeypatch.setattr(external_api, '_fetch_json', lambda url: urls.append(url) or {'results': []})
    external_api.fetch_album_tracks('Release', album_id='123', source='itunes')
    assert 'entity=song&limit=200' in urls[0]
    assert search.album_score('Film', {'title': 'Film (Original Motion Picture Soundtrack)', 'track_count': 12}) > search.album_score('Film', {'title': 'Film - Single', 'track_count': 1})


def test_provider_credits_duration_and_unknowns_are_preserved():
    card = deezer_track({'id': 1, 'title': 'Song', 'duration': 210, 'artist': {'name': 'Composer'},
                         'contributors': [{'name': 'Composer', 'role': 'Main'}, {'name': 'Vocalist', 'role': 'Featured'}]})
    assert [a['name'] for a in card['artists']] == ['Composer', 'Vocalist']
    assert card['artists'][1]['role'] == 'Featured' and card['duration_seconds'] == 210
    assert card['explicit'] is None and card['provider_bpm'] is None
    assert itunes_track({'trackName': 'Song', 'artistName': 'A & B', 'trackTimeMillis': 210000})['duration_seconds'] == 210


def test_recent_previews_and_one_new_album_do_not_erase_saved_language():
    seeds = [{'name': f'Preview {i}', 'artist': f'Preview artist {i}', 'implicit': True} for i in range(8)]
    seeds += [{'name': f'New song {i}', 'artist': 'New composer', 'album': 'One new album'} for i in range(6)]
    seeds += [{'name': 'Older favorite', 'artist': 'Favorite singer', **recording_metadata('telugu')}]
    selected = representative_seeds(seeds)
    assert any(t.get('language') == 'telugu' for t in selected[:2])
    assert all(not t.get('implicit') for t in selected[:2])
    assert sum(t.get('album') == 'One new album' for t in selected) <= 2


def test_verified_language_slot_cannot_be_filled_by_artist_guess():
    seeds = [{'name': 'Saved Telugu', 'artist': 'Multilingual Artist', **recording_metadata('telugu')},
             {'name': 'Saved Other', 'artist': 'Other Artist'}]
    pool = [{'row': -1, 'name': 'Unverified', 'artist': 'Multilingual Artist'},
            {'row': -1, 'name': 'Verified Telugu', 'artist': 'Different Singer', **recording_metadata('telugu')},
            {'row': -1, 'name': 'Another', 'artist': 'Other Artist'}]
    result = rank_pool(TinyCatalog(), seeds, pool, limit=3, balance=True)
    assert result[0]['name'] == 'Verified Telugu'


def test_radio_can_use_listening_evidence_without_overriding_related():
    engine = TinyCatalog()
    seed = engine.track_card(0)
    pool = [{'row': -1, 'name': f'Original {i}', 'artist': 'Original Artist'} for i in range(8)]
    pool += [{'row': -1, 'name': f'Neighbor {i}', 'artist': f'Neighbor artist {i}', 'listening_similarity': .9} for i in range(8)]
    radio = rank_pool(engine, [seed], pool, mode='radio', limit=8)
    related = rank_pool(engine, [seed], pool, mode='related', limit=8)
    assert len({t['artist'] for t in radio}) > len({t['artist'] for t in related})
    assert related[0]['artist'] == 'Original Artist'


def test_listening_neighbors_do_not_guess_tracks_when_unconfigured(monkeypatch):
    monkeypatch.delenv('LASTFM_API_KEY', raising=False)
    assert neighbors._neighbors({'name': 'Song', 'artist': 'Artist'}) == ([], [])


def test_grounded_fact_sources_and_quota_state_are_explicit():
    dj = RAGDJ(api_key='')
    metadata = SimpleNamespace(grounding_chunks=[SimpleNamespace(web=SimpleNamespace(uri='https://label.example/story', title='Session interview'))],
                               grounding_supports=[object()], search_entry_point=SimpleNamespace(rendered_content='<div>Search source</div>'))
    response = SimpleNamespace(text=json.dumps({'headline': 'Recording story', 'insights': ['A documented recording detail.']}), candidates=[SimpleNamespace(grounding_metadata=metadata)])
    dj._client = SimpleNamespace(models=SimpleNamespace(generate_content=lambda **kw: response))
    result = dj.get_intel({'name': 'Song', 'artist': 'Artist'}, [])
    assert result['fact_verified'] and result['sources'][0]['title'] == 'Session interview'
    assert result['search_html'] and not result['sound_profile']
    class QuotaError(RuntimeError):
        code = 429
    def quota(**kwargs):
        raise QuotaError('RESOURCE_EXHAUSTED')
    dj._client.models.generate_content = quota
    assert dj.get_intel({'name': 'Song'}, [])['_status'] == 'quota_exceeded'
    assert 'sample' in dj._intel_prompt({'name': 'Song'}, [])


def test_real_playlist_pagination_never_invents_missing_entries(monkeypatch):
    def fetch(url):
        if 'nextpage' in url:
            return {'data': [{'id': 2, 'title': 'Second', 'artist': {'name': 'B'}}]}
        return {'id': 999999, 'title': 'Public list', 'nb_tracks': 2,
                'tracks': {'data': [{'id': 1, 'title': 'First', 'artist': {'name': 'A'}}], 'next': 'https://api.deezer.com/nextpage'}}
    monkeypatch.setattr(curation, '_fetch_json', fetch)
    result = curation.playlist('999999')
    assert result['complete'] and len(result['tracks']) == 2
    assert result['source'] == 'deezer'


def test_original_recording_does_not_merge_live_or_remix_metadata():
    from backend.metadata import recording_match
    song = {'name': 'Night Hours', 'artist': 'Artist'}
    remix = {'name': 'Night Hours (Producer Remix)', 'artist': 'Artist'}
    live = {'name': 'Night Hours (Live)', 'artist': 'Artist'}
    assert not recording_match(song, remix) and not recording_match(song, live)
    assert catalog_cache.key(song) != catalog_cache.key(remix)
    result = external_api._matching_recording([
        {'title': 'Night Hours (Producer Remix)', 'artist': {'name': 'Artist'}, 'preview': 'remix'},
        {'title': 'Night Hours', 'artist': {'name': 'Artist'}, 'preview': 'original'},
    ], 'Artist', 'Night Hours', 'deezer')
    assert result['preview'] == 'original'


def test_enrichment_query_preserves_distinctive_title_after_a_dash():
    artist, title = external_api._build_clean_names('Film The Sequel - Opening Song', 'Composer')
    assert title == 'Film The Sequel Opening Song'
    assert external_api._matching_recording([
        {'title': 'Film The Sequel - Other Song', 'artist': {'name': artist}},
        {'title': 'Film The Sequel - Opening Song', 'artist': {'name': artist}},
    ], artist, title, 'deezer')['title'].endswith('Opening Song')


def test_feedback_for_a_remix_does_not_replace_original_feedback(tmp_path):
    from backend.profiles import ProfileStore
    engine=TinyCatalog()
    engine.embed_dim=2
    engine.meta=pd.DataFrame({'track_id':['a','b','c']})
    store=ProfileStore(engine,str(tmp_path))
    original={'name':'Song','artist':'External Singer'}
    remix={'name':'Song (Producer Remix)','artist':'External Singer'}
    store.feedback('Test',-1,'like',original)
    profile=store.feedback('Test',-1,'dislike',remix)
    assert len(store.history(profile))==2
    assert {t['signal'] for t in store.history(profile)}=={'like','dislike'}
    assert len(store.load('Test')['feedback'])==2


def test_artist_search_is_ranked_as_artist_intent_not_fuzzy_title():
    index=search.SearchIndex(TinyCatalog())
    tracks,_=index.find('Original Artist')
    assert tracks and tracks[0]['artist']=='Original Artist'
    assert search.relevance('Original Artist',tracks[0])==115
    partial,_=index.find('Orig')
    assert partial[0]['artist']=='Original Artist'
    typo,_=index.find('Original Artst')
    assert typo[0]['artist']=='Original Artist'
    assert search.relevance('Night Hours Original Artist',{'name':'K.','artist':'Other'})<65


def test_selected_provider_identity_and_rich_credit_roles_survive_enrichment():
    selected={'row':-1,'source':'deezer','provider_id':'1','deezer_id':'1','duration_seconds':362,'explicit':True,
              'artists':[{'name':'Composer','role':'Main'}]}
    extra={'source':'itunes','provider_id':'2','deezer_id':'9','itunes_id':'2','duration_seconds':361,'explicit':False,
           'artists':[{'name':'Composer','role':'Artist'},{'name':'Vocalist','role':'Artist'}]}
    result=merge_metadata(selected,extra)
    assert result['provider_id']=='1' and result['deezer_id']=='1' and result['itunes_id']=='2'
    assert result['duration_seconds']==362 and result['explicit'] is True
    assert result['artists'][0]['role']=='Main' and len(result['artists'])==2


def test_full_song_taste_avoids_short_score_cues_but_short_seeds_keep_them():
    seed={'row':-1,'name':'Full song','artist':'Artist','duration_seconds':240}
    cue={'row':-1,'name':'Short cue','artist':'Artist','duration_seconds':41}
    song={'row':-1,'name':'Another song','artist':'Artist','duration_seconds':200}
    assert [t['name'] for t in rank_pool(TinyCatalog(),[seed],[cue,song])]==['Another song']
    short_seed={**seed,'duration_seconds':45}
    assert any(t['name']=='Short cue' for t in rank_pool(TinyCatalog(),[short_seed],[cue,song]))


def test_matching_full_release_promotes_its_recording_over_title_collisions():
    official={'row':-1,'name':'Film - Title Track','artist':'Film Composer','album':'Film (Original Motion Picture Soundtrack)',
              'album_id':'10','album_source':'deezer'}
    unrelated={'row':-1,'name':'Film','artist':'Another Artist','album_id':'20','album_source':'deezer'}
    album={'id':'10','source':'deezer','title':'Film (Original Motion Picture Soundtrack)','track_count':11}
    data=search.pack('Film',[unrelated,official],[album])
    assert data['results'][0]['artist']=='Film Composer'
    assert data['results'][0]['album_id']=='10'


def test_live_release_context_adds_verified_recordings_before_finishing(monkeypatch):
    from backend import external_api
    album={'id':'10','source':'deezer','title':'Film (Original Motion Picture Soundtrack)','track_count':11}
    monkeypatch.setattr(external_api,'_search_itunes_tracks',lambda *a:[])
    monkeypatch.setattr(external_api,'_search_deezer_tracks',lambda *a:[{'name':'Film','artist':'Unrelated performer','row':-1}])
    monkeypatch.setattr(external_api,'_search_itunes_albums',lambda *a:[])
    monkeypatch.setattr(external_api,'_search_deezer_albums',lambda *a:[album])
    monkeypatch.setattr(external_api,'fetch_album_tracks',lambda *a:{'tracks':[{'name':'Film - Title Track','artist':'Composer','row':-1,'album_id':'10','album_source':'deezer'}]})
    monkeypatch.setattr(search,'_RESULTS',{})
    asyncio.run(search._live(None,'Film',[],''))
    result=search._RESULTS['film']['data']
    assert not result['pending'] and result['results'][0]['artist']=='Composer'
