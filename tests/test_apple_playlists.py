"""Public Apple Music catalog parsing, playlist identity, and provider behavior."""
import asyncio
import json
from fastapi.testclient import TestClient
import pytest
from backend import apple_music as apple, curation, catalog_cache, routes
from backend.external_api import _BoundedCache

URL='https://music.apple.com/us/playlist/example/pl.example'


def descriptor(kind, identity, url):
    return {'kind':kind,'identifiers':{'storeAdamID':identity},'url':url}


def page(sections, canonical=URL):
    data={'data':[{'data':{'sections':sections,'canonicalURL':canonical}}], 'userTokenHash':'ignored-anonymous-field'}
    return '<html><script id="serialized-server-data" type="application/json">'+json.dumps(data)+'</script></html>'


def card():
    return {'title':'Regional Essentials','subtitle':'Playlist · Apple Music Regional',
            'contentDescriptor':descriptor('playlist','pl.example',URL),
            'artwork':{'dictionary':{'url':'https://is1-ssl.mzstatic.com/image/{w}x{h}.{f}'}}}


def song(identity='1', title='Song', duration=180000):
    return {'title':title,'artistName':'Lead & Guest','duration':duration,'composer':'Composer',
            'contentDescriptor':descriptor('song',identity,'https://music.apple.com/us/album/song/50?i='+identity),
            'artwork':{'dictionary':{'url':'https://is1-ssl.mzstatic.com/image/{w}x{h}bb.{f}'}},
            'subtitleLinks':[{'title':'Lead'},{'title':'Guest'}],
            'tertiaryLinks':[{'title':'Album','segue':{'destination':{'contentDescriptor':descriptor('album','50','https://music.apple.com/us/album/album/50')}}}],
            'showExplicitBadge':False}


def playlist_page(count=3):
    header={**card(),'trackCount':count,'subtitleLinks':[{'title':'Apple Music Regional'}]}
    return page([{'id':'playlist-detail-header-section - pl.example','items':[header]},
                 {'id':'track-list - pl.example','items':[song(),song(),song('2','Another song',200000)]}])


@pytest.fixture(autouse=True)
def isolated(tmp_path,monkeypatch):
    for name in ['_CACHE','_MISSES','_URLS']:
        monkeypatch.setattr(apple,name,_BoundedCache(maxsize=30))
    monkeypatch.setattr(curation,'_CACHE',_BoundedCache(maxsize=30))
    monkeypatch.setattr(catalog_cache,'_DB',None)
    monkeypatch.setenv('SOUNDVECTOR_CACHE_DIR',str(tmp_path))
    yield
    if catalog_cache._DB is not None:catalog_cache._DB.close()


def test_public_search_uses_real_identity_artwork_and_full_names():
    item=card();duplicate={**item,'titleLinks':[{'title':item['title']}],'title':None,
                          'subtitleLinks':[{'title':'Apple Music Regional'}]}
    result=apple.parse_search(page([{'items':[item,duplicate,{'contentDescriptor':descriptor('album','5',URL)}]}]))
    assert len(result)==1 and result[0]['id']=='pl.example'
    assert result[0]['title']=='Regional Essentials' and result[0]['source']=='apple_music'
    assert result[0]['url']==URL and result[0]['track_count'] is None
    assert result[0]['cover_art'].endswith('600x600.jpg')
    assert 'userTokenHash' not in json.dumps(result)


def test_playlist_keeps_duplicate_positions_and_recording_metadata():
    result=apple.parse_playlist(playlist_page(),'pl.example')
    assert result['complete'] and result['loaded_count']==3
    assert [t['itunes_id'] for t in result['tracks']]==['1','1','2']
    first=result['tracks'][0]
    assert first['duration_seconds']==180 and first['album_id']=='50'
    assert [a['name'] for a in first['artists']]==['Lead','Guest']
    assert first['composer_name']=='Composer' and 'language' not in first
    assert first['deezer_link'].endswith('?i=1')


def test_partial_and_unknown_counts_are_not_reported_as_complete():
    result=apple.parse_playlist(playlist_page(10),'pl.example')
    assert result['complete'] is False and result['duration_seconds'] is None
    unknown=apple.parse_playlist(playlist_page(None),'pl.example')
    assert unknown['complete'] is None and unknown['track_count'] is None
    assert apple.parse_playlist(playlist_page(),'pl.other') is None


def test_source_urls_cannot_select_other_hosts_or_recordings(monkeypatch):
    calls=[];monkeypatch.setattr(apple,'_download',lambda *a,**k:calls.append(a) or None)
    invalid=['http://music.apple.com/us/playlist/example/pl.example',
             'https://music.apple.com.evil/us/playlist/example/pl.example',
             'https://user@music.apple.com/us/playlist/example/pl.example',
             'https://music.apple.com:8443/us/playlist/example/pl.example',
             'https://music.apple.com/us/album/example/pl.example',
             'https://music.apple.com/us/playlist/example/pl.other']
    assert all(apple.playlist('pl.example',url) is None for url in invalid)
    assert calls==[] and apple.playlist_url(URL,'pl.example')==URL


def test_redirects_do_not_follow_an_unexpected_host(monkeypatch):
    class Redirect:
        is_redirect=True
        headers={'Location':'https://example.invalid/other'}
        def __enter__(self):return self
        def __exit__(self,*a):pass
    calls=[]
    monkeypatch.setattr(apple.requests,'get',lambda *a,**k:calls.append(a) or Redirect())
    assert apple._download(URL) is None and len(calls)==1


def test_public_search_cache_avoids_repeated_network_reads(monkeypatch):
    calls=[]
    monkeypatch.setattr(apple,'_download',lambda url:calls.append(url) or page([{'items':[card()]}]))
    assert apple.search_playlists('Regional')==apple.search_playlists('Regional')
    assert len(calls)==1 and 'term=Regional' in calls[0]


def test_unavailable_public_schema_is_safe_and_negative_cached(monkeypatch):
    for content in ['not html','<script id="serialized-server-data">[]</script>', '<script id="serialized-server-data">{"data":null}</script>']:
        assert apple.parse_search(content)==[]
    calls=[];monkeypatch.setattr(apple,'_download',lambda url:calls.append(url) or '<html>Unavailable</html>')
    assert apple.search_playlists('Unknown')==[] and apple.search_playlists('Unknown')==[]
    assert len(calls)==1


def test_preview_hydration_matches_ids_and_preserves_page_credits(monkeypatch):
    tracks=apple.parse_playlist(playlist_page(),'pl.example')['tracks']
    response={'results':[{'trackId':1,'trackName':'Song','artistName':'Lead & Guest','previewUrl':'https://audio-ssl.itunes.apple.com/preview.m4a','primaryGenreName':'Telugu'},
                         {'trackId':999,'trackName':'Another song','artistName':'Lead & Guest','previewUrl':'wrong-recording'}]}
    monkeypatch.setattr(apple,'_download',lambda *a,**k:json.dumps(response))
    apple._previews(tracks,'us')
    assert tracks[0]['deezer_preview_url'].startswith('https://audio-ssl')
    assert tracks[1]['deezer_preview_url']==tracks[0]['deezer_preview_url']
    assert tracks[2]['deezer_preview_url']=='' and tracks[0]['language']=='telugu'
    assert [a['name'] for a in tracks[0]['artists']]==['Lead','Guest']


def test_home_prefers_apple_and_falls_back_when_apple_unavailable(monkeypatch):
    monkeypatch.setattr(apple,'search_playlists',lambda *a:[{'id':'pl.example','source':'apple_music'}])
    monkeypatch.setattr(curation,'_fetch_json',lambda *a:(_ for _ in ()).throw(AssertionError('Apple already supplied results')))
    assert curation.playlists('Regional')[0]['source']=='apple_music'
    monkeypatch.setattr(apple,'search_playlists',lambda *a:[])
    monkeypatch.setattr(curation,'_fetch_json',lambda *a:{'data':[{'id':10,'title':'Other list'}]})
    assert curation.playlists('Regional')[0]['source']=='deezer'


def test_editorial_interleaves_tastes_instead_of_using_only_the_first_artist(monkeypatch):
    store=type('Store',(),{'taste_seeds':lambda self,p:[{'name':'Saved A','artist':'Lead & Lyricist','language':'telugu','language_source':'itunes.track.primaryGenreName'},
                                                       {'name':'Saved B','artist':'Another Composer'}]})()
    calls=[]
    def lookup(query,limit):
        calls.append(query)
        return [{'id':query+str(i),'source':'apple_music','title':query} for i in range(3)]
    monkeypatch.setattr(curation,'playlists',lookup)
    monkeypatch.setattr(curation,'chart',lambda:{'tracks':[]})
    result=asyncio.run(curation.editorial(store,{}))
    expected=['telugu','lead','another composer']
    # Worker start order is nondeterministic; gather preserves query order.
    assert sorted(calls)==sorted(expected)
    assert [p['title'] for p in result['playlists'][:3]]==expected


def test_playlist_api_dispatches_apple_canonical_url(monkeypatch):
    calls=[]
    monkeypatch.setattr(apple,'playlist',lambda identity,url:calls.append((identity,url)) or {'title':'Example','source':'apple_music','tracks':[]})
    response=TestClient(routes.app).get('/api/playlist',params={'id':'pl.example','source':'apple_music','url':URL})
    assert response.status_code==200 and response.json()['source']=='apple_music'
    assert calls==[('pl.example',URL)]
    assert TestClient(routes.app).get('/api/playlist',params={'id':'1','source':'unrecognized'}).status_code==404
