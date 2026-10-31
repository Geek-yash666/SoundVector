"""Behavioral boundaries for SoundVector's personal continuation ranker."""
import numpy as np
import pandas as pd
import pytest
from backend import catalog_cache
from backend.flow import rank_flow, row_of, candidate_pool
from backend.discovery import bridge_catalog, rank_pool
from backend.metadata import recording_match


@pytest.fixture(autouse=True)
def metadata_db(tmp_path, monkeypatch):
    monkeypatch.setenv('SOUNDVECTOR_CACHE_DIR',str(tmp_path))
    monkeypatch.setattr(catalog_cache,'_DB',None)
    yield
    if catalog_cache._DB is not None:
        catalog_cache._DB.close()


class Catalog:
    def __init__(self):
        self.names=['Seed','Close song','Another close song','Favorite A','Favorite B','Unrelated favorite','Instrumental','Spoken cue','Low evidence']
        self.artists=['Seed artist','Seed artist','Seed artist','Artist A','Artist B','Remote artist','Score artist','Spoken artist','Neighbor artist']
        self.embeddings=np.array([[1.,0.,0.],[1.,.001,0.],[1.,.002,0.],[.65,.76,0.],[.65,0.,.76],[-1.,0.,0.],[.9,.1,0.],[.9,.1,0.],[.1,.7,.7]])
        self.embeddings/=np.linalg.norm(self.embeddings,axis=1,keepdims=True)
        self.audio=np.full((len(self.names),8),.5);self.audio[:,4]=.05;self.audio[:,6]=.02
        self.audio[5]=1.;self.audio[6,6]=.99;self.audio[7,4]=.99
        self.pop=np.array([.8,.8,.8,.8,.8,1.,1.,1.,.99])
        self.canonical_row=np.arange(len(self.names));self._catalog_rows=self.canonical_row
        self.catalog=pd.DataFrame({'_row':self.canonical_row,'_title_key':[s.lower() for s in self.names]})
    def track_card(self,row):
        return dict(row=int(row),name=self.names[row],artist=self.artists[row],popularity=float(self.pop[row]),album_gid=int(row))
    def _genre_ids(self,row):return row
    def _base_genres(self,row):return {'pop'} if row!=5 else {'ambient'}


def run(c,taste=(),**kwargs):
    return rank_flow(c,c.track_card(0),taste,[c.track_card(i) for i in range(1,len(c.names))],**kwargs)


def test_same_seed_changes_with_active_taste():
    c=Catalog()
    a=run(c,[c.track_card(3)]); b=run(c,[c.track_card(4)])
    assert [t['row'] for t in a] != [t['row'] for t in b]
    assert next(i for i,t in enumerate(a) if t['row']==3) < next(i for i,t in enumerate(a) if t['row']==4)
    assert next(i for i,t in enumerate(b) if t['row']==4) < next(i for i,t in enumerate(b) if t['row']==3)
    assert 'An artist in your saved music' in next(t for t in a if t['row']==3)['flow_reasons']


def test_unrelated_saved_song_and_audio_mismatches_cannot_bypass_context():
    c=Catalog();result=run(c,[c.track_card(5),c.track_card(6),c.track_card(7)])
    assert not {5,6,7} & {t['row'] for t in result}


def test_nearly_identical_embeddings_are_not_duplicate_recordings():
    c=Catalog();result=run(c)
    assert {1,2} <= {t['row'] for t in result}
    assert len({t['artist'] for t in result[:3]})==3


def test_dislike_and_skip_exclude_recording_without_a_catalog_row():
    c=Catalog()
    blocked=[dict(c.track_card(3),row=-1,signal='dislike'),dict(c.track_card(4),row=-1,signal='skip')]
    assert not {3,4} & {t['row'] for t in run(c,history=blocked)}
    assert {3,4} <= {t['row'] for t in run(c,history=[])}


def test_listening_is_weaker_than_an_explicit_save_and_recent_repeats_are_penalized():
    import time
    c=Catalog();liked=run(c,[c.track_card(3)]);implicit=run(c,[dict(c.track_card(3),implicit=True)])
    a=next(t for t in liked if t['row']==3);b=next(t for t in implicit if t['row']==3)
    assert a['flow_evidence']['taste'] > b['flow_evidence']['taste']
    recent=run(c,[c.track_card(3)],recent=[dict(c.track_card(3),completed=True,ts=time.time())])
    assert next(i for i,t in enumerate(recent) if t['row']==3)>=next(i for i,t in enumerate(liked) if t['row']==3)


def test_artist_wide_provider_similarity_has_bounded_weight():
    c=Catalog();pool=[c.track_card(i) for i in range(1,6)]
    pool.append(dict(c.track_card(8),listening_similarity=1000,listening_source='lastfm.artist.getSimilar'))
    result=rank_flow(c,c.track_card(0),[],pool)
    track=next(t for t in result if t['row']==8)
    assert track['flow_evidence']['listener_support']==.35
    assert result[0]['row'] in {1,2}


def test_external_recording_never_claims_measured_audio():
    c=Catalog();seed=dict(row=-1,name='New release',artist='New singer')
    pool=[dict(row=-1,name='Other release',artist='New singer')]
    result=rank_flow(c,seed,[],pool)
    assert result[0]['flow_evidence']['anchor']=='metadata'
    assert result[0]['flow_evidence']['audio'] is None
    assert all('rhythm' not in reason for reason in result[0]['flow_reasons'])


def test_stable_prefix_and_repeated_recording_credit_deduplication():
    c=Catalog();seed=c.track_card(0);pool=[c.track_card(i) for i in range(1,6)]
    pool.append(dict(c.track_card(3),row=-1,artist='Artist A & Featured singer'))
    short=rank_flow(c,seed,[],pool,limit=3);long=rank_flow(c,seed,[],pool,limit=20)
    assert short==long[:3]
    assert sum(recording_match(c.track_card(3),t) for t in long)==1


def test_untrusted_row_does_not_supply_an_embedding():
    c=Catalog()
    assert row_of(c,dict(c.track_card(3),row=4)) is None
    assert row_of(c,dict(c.track_card(3),row=10000)) is None
    assert row_of(c,dict(c.track_card(3),row='3')) is None


def test_vibe_prioritizes_audio_without_a_global_genre_jump():
    c=Catalog();c.audio[1]=1.;c.audio[2]=1.;c.audio[5]=c.audio[0]
    pool=[c.track_card(i) for i in [1,3,4,5]]
    similar=rank_pool(c,[c.track_card(0)],pool,mode='similar')
    vibe=rank_pool(c,[c.track_card(0)],pool,mode='vibe')
    assert similar[0]['row']==1
    assert vibe[0]['row'] in (3,4)
    assert 5 not in {t['row'] for t in vibe}


def test_verified_credit_bridge_preserves_release_and_measured_features():
    c=Catalog();provider=dict(row=-1,name='Favorite A',artist='Vocalist',artists=[{'name':'Artist A','role':'Composer'}],
                            popularity=.001,album='Selected release',album_id='99',album_source='itunes',source='itunes',duration_seconds=213)
    joined=bridge_catalog(c,[provider])[0]
    assert joined['row']==3 and joined['artist']=='Vocalist'
    assert joined['popularity']==.8 and joined['duration_seconds']==213 and joined['album_id']=='99'
    assert row_of(c,joined)==3
    assert bridge_catalog(c,[dict(provider,artists=[])])[0]['row']==-1


def test_metadata_cache_cannot_transfer_listener_specific_reasons():
    track=dict(row=0,name='Song',artist='Artist',album='Release',album_id='1',album_source='itunes',flow_reasons=['Your saved artist'],
               flow_evidence={'taste':1},reason='Your favorite',listening_similarity=.9,signal='like')
    catalog_cache.remember([track])
    cached=catalog_cache.hydrate(dict(row=0,name='Song',artist='Artist'))
    assert cached['album']=='Release'
    assert not {'flow_reasons','flow_evidence','reason','listening_similarity','signal'} & cached.keys()
    assert not {'flow_reasons','flow_evidence','reason'} & catalog_cache.all_tracks()[0].keys()


def test_real_catalog_flow_can_retrieve_familiar_music_outside_seed_ann(engine):
    def pick(title,artist):
        return engine.track_card(next(t['row'] for t in engine.search(title,30) if recording_match({'name':title,'artist':artist},t)))
    seed=pick('After Hours','The Weeknd');favorite=pick('Let Me Love You','DJ Snake')
    pool,anchors,kind=candidate_pool(engine,seed,[favorite],[])
    assert any(recording_match(favorite,t) for t in pool)
    result=rank_flow(engine,seed,[favorite],pool,limit=24,anchors=anchors,anchor_kind=kind)
    assert any(recording_match(favorite,t) for t in result)
    assert all(t['recommendation_source']=='soundvector' for t in result)
