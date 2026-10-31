"""Boundaries for optional Gemini notes and verified recording-to-release navigation."""
import json
from types import SimpleNamespace
from fastapi.testclient import TestClient
from backend import routes, albums, external_api, insights
from backend.rag_dj import RAGDJ


def narrator():
    dj = RAGDJ(api_key='')
    dj._client = None
    return dj


def test_external_notes_never_invent_audio_or_language():
    dj = narrator()
    facts = {'name':'Song', 'artist':'Artist'}
    result = dj.get_intel(facts, [])
    assert result['_source'] == 'catalog'
    assert result['_status'] == 'not_configured'
    assert not result['sound_profile'] and not result['mood_tags']
    assert '120' not in json.dumps(result)
    assert 'energy=' not in dj._intel_prompt(facts, [])
    assert 'Missing audio attributes are unknown' in dj._intel_prompt(facts, [])


def test_failed_gemini_is_reported_as_catalog_notes():
    dj = narrator()
    def unavailable(**kwargs):
        raise RuntimeError('provider failed')
    dj._client = SimpleNamespace(models=SimpleNamespace(generate_content=unavailable))
    result = dj.get_intel({'name':'Song','album':'Release'}, [])
    assert result['_source'] == 'catalog' and result['_status'] == 'unavailable'
    assert result['insights'] == ['Appears on Release.']


def test_successful_gemini_records_actual_provenance_and_handles_bad_fields():
    dj = narrator()
    dj._client = SimpleNamespace(models=SimpleNamespace(generate_content=lambda **kw: SimpleNamespace(text=json.dumps({'headline':'Song','insights':['Supplied fact.'],'sound_profile':{},'mood_tags':'wrong'}))))
    result = dj.get_intel({'name':'Song','artist':'Artist'}, [])
    assert result['_source'] == 'gemini' and result['_status'] == 'ready'
    assert result['sound_profile'] == '' and result['mood_tags'] == []


def test_track_notes_reject_a_mismatched_catalog_row(monkeypatch):
    class Engine:
        def track_card(self, row):
            return {'name':'Wrong song','artist':'Other artist','energy':.9,'tempo_bpm':180}
        def recommend(self, *args, **kwargs):
            raise AssertionError('wrong recording must never seed notes')
    monkeypatch.setattr(routes, 'get_app_components', lambda: (Engine(),None,narrator(),None,None))
    monkeypatch.setattr(routes, 'enrich_track', lambda *args: {})
    result = TestClient(routes.app).get('/api/track_intel',params={'row':0,'track':'Chosen song','artist':'Chosen artist'}).json()
    assert result['facts'] == {'name':'Chosen song','artist':'Chosen artist'}
    assert result['backend'] == 'catalog'


def test_itunes_album_identity_is_explicit_even_for_other_provider_songs(monkeypatch):
    monkeypatch.setattr(albums, '_fetch_itunes_enrichment', lambda *args: {'album':'A release','album_id':'101','album_source':'itunes'})
    monkeypatch.setattr(albums, '_fetch_deezer_enrichment', lambda *args: (_ for _ in ()).throw(AssertionError('do not mix providers')))
    assert albums.resolve_song_album('Song','Artist') == {'title':'A release','artist':'Artist','id':'101','source':'itunes'}


def test_unverified_album_returns_no_guessed_release(monkeypatch):
    monkeypatch.setattr(albums, '_fetch_itunes_enrichment', lambda *args: {})
    monkeypatch.setattr(albums, '_fetch_deezer_enrichment', lambda *args: {})
    assert albums.resolve_song_album('Song','Artist') is None
    response = TestClient(routes.app).get('/api/song_album',params={'track':'Song','artist':'Artist'})
    assert response.status_code == 404


def test_single_track_release_does_not_append_another_provider(monkeypatch):
    urls = []
    def fetch(url):
        urls.append(url)
        assert 'api.deezer.com/album/10' in url
        return {'artist':{'name':'Artist'}, 'tracks':{'data':[{'title':'Song','artist':{'name':'Artist'}}]}}
    monkeypatch.setattr(external_api, '_fetch_json', fetch)
    result = external_api.fetch_album_tracks('Single','Artist','10','deezer')
    assert len(result['tracks']) == 1 and len(urls) == 1
    assert result['tracks'][0]['album_source'] == 'deezer'


def test_itunes_album_lookup_rejects_other_collection_tracks(monkeypatch):
    monkeypatch.setattr(external_api, '_fetch_json', lambda url: {'results':[{'trackName':'Correct','artistName':'Artist','collectionId':10,'collectionName':'Release'},{'trackName':'Wrong','artistName':'Artist','collectionId':20,'collectionName':'Other'}]})
    result = external_api.fetch_album_tracks('Release','Artist','10','itunes')
    assert [t['name'] for t in result['tracks']] == ['Correct']


def test_notes_cache_reuses_identical_facts_but_invalidates_changed_context():
    calls=[]
    dj=SimpleNamespace(backend='test', get_intel=lambda facts,recs: calls.append(dict(facts)) or {'_status':'ready'})
    facts={'name':'Unique cache test'}
    insights.cached_insights(dj,facts,[])
    insights.cached_insights(dj,facts,[])
    insights.cached_insights(dj,{**facts,'album':'New metadata'},[])
    assert len(calls)==2


def test_refresh_retries_provider_instead_of_replaying_cached_failure():
    calls=[]
    dj=SimpleNamespace(backend='retry-test', get_intel=lambda facts,recs: calls.append(1) or {'_status':'unavailable'})
    insights.cached_insights(dj,{'name':'Retry'},[])
    insights.cached_insights(dj,{'name':'Retry'},[])
    insights.cached_insights(dj,{'name':'Retry'},[],refresh=True)
    assert len(calls)==2


def test_selected_release_is_preserved_after_track_list_verification(monkeypatch):
    monkeypatch.setattr(albums, '_fetch_json', lambda url: {'results':[{'collectionId':22,'collectionName':'Full soundtrack','trackName':'Song','artistName':'Artist'}]})
    monkeypatch.setattr(albums, '_fetch_itunes_enrichment', lambda *args: (_ for _ in ()).throw(AssertionError('do not replace verified edition')))
    result=albums.resolve_song_album('Song','Artist','22','itunes')
    assert result['id']=='22' and result['title']=='Full soundtrack'


def test_stale_release_id_cannot_redirect_to_another_recording(monkeypatch):
    monkeypatch.setattr(albums, '_fetch_json', lambda url: {'results':[{'collectionId':22,'collectionName':'Wrong release','trackName':'Wrong song','artistName':'Other'}]})
    monkeypatch.setattr(albums, '_fetch_itunes_enrichment', lambda *args: {'album':'Correct release','album_id':'33'})
    result=albums.resolve_song_album('Song','Artist','22','itunes')
    assert result['id']=='33' and result['title']=='Correct release'


def test_album_header_uses_release_artist_instead_of_selected_song_vocalist(monkeypatch):
    monkeypatch.setattr(external_api, '_fetch_json', lambda url: {'results':[{'wrapperType':'collection','collectionId':10,'collectionName':'Full soundtrack','artistName':'Composer'},{'wrapperType':'track','trackName':'Song','artistName':'Vocalist','collectionId':10,'collectionName':'Full soundtrack'}]})
    result=external_api.fetch_album_tracks('Full soundtrack','Vocalist','10','itunes')
    assert result['artist']=='Composer' and result['tracks'][0]['artist']=='Vocalist'


def test_insights_use_the_verified_selected_release_context(monkeypatch):
    monkeypatch.setattr(routes,'get_app_components',lambda:(None,None,narrator(),None,None))
    monkeypatch.setattr(routes,'enrich_track',lambda *args:{'album':'Earlier single'})
    monkeypatch.setattr(albums,'resolve_song_album',lambda *args,**kw:{'title':'Selected soundtrack','id':'22','source':'itunes'})
    response=TestClient(routes.app).get('/api/track_intel',params={'track':'Song','artist':'Artist','album_id':'22','album_source':'itunes'})
    assert response.json()['facts']['album']=='Selected soundtrack'
    assert response.json()['intel']['insights']==['Appears on Selected soundtrack.']


def test_insights_never_present_an_artist_genre_as_recording_classification(monkeypatch):
    class Engine:
        def track_card(self,row):return {'name':'Song','artist':'Artist','base_genres':['tamil pop'],'energy':.5}
        def recommend(self,*args,**kwargs):return []
    monkeypatch.setattr(routes,'get_app_components',lambda:(Engine(),None,narrator(),None,None))
    monkeypatch.setattr(routes,'enrich_track',lambda *args:{'recording_genres':['telugu'],'language':'telugu','language_source':'itunes.track.primaryGenreName'})
    response=TestClient(routes.app).get('/api/track_intel',params={'track':'Song','artist':'Artist','row':0})
    facts=response.json()['facts']
    assert facts['genres']==['telugu'] and facts['language']=='telugu'
    assert 'tamil pop' not in json.dumps(response.json())
