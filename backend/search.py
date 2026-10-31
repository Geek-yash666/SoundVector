"""Progressive search: render indexed candidates now; merge providers as each finishes."""
import asyncio
import bisect
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from rapidfuzz import fuzz,process
from . import catalog_cache
from .metadata import artist_parts,artist_signature,clean_title,public_track

_POOL=ThreadPoolExecutor(max_workers=6,thread_name_prefix='sv-search')
_INDEXES={}
_JOBS={}
_RESULTS={}

def fold(value):
    return ''.join(c for c in unicodedata.normalize('NFKD',str(value or '')).casefold() if c.isalnum())

def relevance(q,track):
    query=fold(q); title=fold(track.get('name')); artist=fold(track.get('artist'))
    if query==title:return 120
    if query==artist:return 115
    if len(query)>=3 and artist.startswith(query):return 100
    if title.startswith(query):return 106+min(len(query)/max(len(title),1),1)*8
    full=title+artist
    if query==full:return 125
    artist_score=fuzz.ratio(query,artist) if len(query)>=5 else 0
    return max(fuzz.ratio(query,title),fuzz.ratio(query,full),artist_score if artist_score>=80 else 0,fuzz.partial_ratio(query,title)*.92 if len(query)>=4 and len(title)>=len(query)*.65 else 0)

class SearchIndex:
    def __init__(self,engine):
        self.engine=engine
        rows=getattr(engine,'_catalog_rows',[])
        # One title entry retains the most popular recording for typo correction.
        best={}
        for row in rows:
            title=fold(engine._names[row])
            if title not in best or engine.pop[row]>engine.pop[best[title]]:best[title]=int(row)
        self.names=sorted(best)
        self.rows=[best[name] for name in self.names]
        self.best=best
        self.artists=list(getattr(engine,'_artist_names',[]))
        self.artist_names=[fold(a) for a in self.artists]
        self.artist_exact=dict(zip(self.artist_names,self.artists))
        self.artist_prefix=sorted(self.artist_exact)
        self.artist_pop=dict(zip(self.artist_names,getattr(engine,'_artist_maxpop',[0]*len(self.artists))))
    def find(self,query,limit=12):
        q=fold(query)
        if not q:return [],''
        candidates=[]
        left=bisect.bisect_left(self.names,q)
        for i in range(left,min(left+180,len(self.names))):
            if not self.names[i].startswith(q):break
            candidates.append((self.rows[i],120 if self.names[i]==q else 106))
        correction=''
        if len(candidates)<limit:
            matches=process.extract(q,self.names,scorer=fuzz.ratio,limit=limit,score_cutoff=76 if len(q)>5 else 85)
            for name,score,index in matches:
                candidates.append((self.rows[index],float(score)))
            if matches and matches[0][1]>=82 and matches[0][0]!=q:
                correction=str(self.engine._names[self.rows[matches[0][2]]])
        # Exact titles may have multiple original artists; use existing indexed exact lookup.
        if candidates and candidates[0][1]==120:
            candidates=[(hit['row'],hit.get('match',100)) for hit in self.engine.search(query,limit=limit)]+candidates
        tracks=[{**self.engine.track_card(row),'match':score} for row,score in dict(candidates).items()]
        cached=catalog_cache.all_tracks()
        cached=sorted(((relevance(query,t),t) for t in cached),key=lambda pair:-pair[0])
        tracks += [{**track,'match':score} for score,track in cached[:limit] if score>=76]
        tracks=merge_tracks(query,tracks,limit)
        artist_hits=process.extract(q,self.artist_names,scorer=fuzz.ratio,limit=4,score_cutoff=78)
        words=query.split()
        requested=[]
        if len(q)>=3:
            start=bisect.bisect_left(self.artist_prefix,q)
            prefix=[]
            for name in self.artist_prefix[start:start+80]:
                if not name.startswith(q):break
                prefix.append(name)
            requested.extend(self.artist_exact[name] for name in sorted(prefix,key=lambda name:-self.artist_pop[name])[:2])
        for boundary in range(1,len(words)+1):
            for text in (' '.join(words[:boundary]),' '.join(words[boundary:])):
                if fold(text) in self.artist_exact:requested.append(self.artist_exact[fold(text)])
        for name in dict.fromkeys(requested):
            for t in self.engine.artist_top_tracks(str(name),limit=30):tracks.append({**self.engine.track_card(t['row']),'match':relevance(query,t)})
        for _,_,idx in artist_hits:
            for t in self.engine.artist_top_tracks(str(self.artists[idx]),limit=limit):
                tracks.append({**self.engine.track_card(t['row']),'match':relevance(query,t)})
        return merge_tracks(query,tracks,limit),correction

def merge_tracks(query,tracks,limit=20):
    unique={}
    for t in tracks:
        if not t.get('name') or not t.get('artist') or t['artist'].casefold() in {'unknown','unknown artist'}:continue
        identity=catalog_cache.key(t)
        if identity in unique:
            from .media import merge_metadata
            a=unique[identity]; b=t
            # Prefer a provider's richer credit/artwork data, retain model row when it matches.
            merged=merge_metadata(a,b)
            if a.get('row',-1)<0<=b.get('row',-1):
                merged['row']=b['row'];merged.pop('is_live_external',None)
            unique[identity]=merged
        else:unique[identity]=dict(t)
    result=sorted(unique.values(),key=lambda t:(-relevance(query,t),-float(t.get('popularity',0) or 0),not bool(t.get('deezer_album_art'))))
    best=relevance(query,result[0]) if result else 0
    cutoff=max(70,best-(28 if best>=100 else 15))
    return [public_track(catalog_cache.hydrate(t)) for t in result[:limit] if relevance(query,t)>=cutoff]

def album_score(query,album):
    q=fold(query); title=fold(clean_title(album.get('title')))
    # Search a film by name: full official soundtracks precede covers and title-track singles.
    ratio=fuzz.ratio(q,title)
    contained=q in fold(album.get('title'))
    count=int(album.get('track_count') or 0)
    return ratio + (18 if contained else 0) + min(count,20)*1.1 + (35 if contained and count>=4 else 0)

def index_for(engine):
    identity=id(engine)
    if identity not in _INDEXES:_INDEXES[identity]=SearchIndex(engine)
    return _INDEXES[identity]

def pack(query,tracks,albums=(),correction='',pending=False):
    artists={}
    for t in tracks:
        for a in t.get('artists') or [{'name':n} for n in artist_parts(t.get('artist'))]:
            name=a.get('name','')
            if fuzz.ratio(fold(query),fold(name))>=76:
                artists.setdefault(artist_signature(name),{'artist':name,'image_url':a.get('image') or ''})
    unique={}
    for album in sorted(albums,key=lambda a:-album_score(query,a)):
        identity=(str(album.get('source')),str(album.get('id')))
        unique.setdefault(identity,album)
    releases=list(unique.values())[:12]
    preferred=next((a for a in releases if int(a.get('track_count') or 0)>=4 and fold(clean_title(a.get('title')))==fold(query)),None)
    results=merge_tracks(query,tracks,80)
    if preferred:
        # An independently returned full release provides stronger context than a
        # title collision. Keep the selected recording/edition identity intact.
        connected={catalog_cache.key(t) for t in tracks if str(t.get('album_id'))==str(preferred['id']) and t.get('album_source')==preferred.get('source')}
        results.sort(key=lambda t:-(relevance(query,t)+(30 if catalog_cache.key(t) in connected else 0)))
    return {'results':results[:20],'artists':list(artists.values())[:6], 'albums':releases,
            'correction':correction,'pending':pending,'query':query}

async def search(engine,query,quick=False,live=True):
    query=query.strip()[:300]
    if len(query)<2:return pack(query,[])
    cache_key=query.casefold()
    cached=_RESULTS.get(cache_key)
    if cached and time.monotonic()-cached['time']<900:
        if not cached['pending'] or quick:return cached['data']
    local,correction=await asyncio.to_thread(index_for(engine).find,query,16)
    if not live:return pack(query,local,correction=correction,pending=False)
    if cache_key not in _JOBS or _JOBS[cache_key].done():
        if not cached or time.monotonic()-cached['time']>=900:
            _RESULTS[cache_key]={'time':time.monotonic(),'pending':True,'data':pack(query,local,correction=correction,pending=True)}
            _JOBS[cache_key]=asyncio.create_task(_live(engine,query,local,correction))
    if not quick:
        try:await asyncio.wait_for(asyncio.shield(_JOBS[cache_key]),8)
        except (asyncio.TimeoutError,KeyError):pass
    return _RESULTS.get(cache_key,{'data':pack(query,local,correction=correction)})['data']

async def _live(engine,query,local,correction):
    from .external_api import _search_itunes_tracks,_search_deezer_tracks,_search_itunes_albums,_search_deezer_albums,fetch_album_tracks
    loop=asyncio.get_running_loop(); tracks=list(local); albums=[]; key=query.casefold()
    tasks=[loop.run_in_executor(_POOL,fn,query,50) for fn in (_search_itunes_tracks,_search_deezer_tracks,_search_itunes_albums,_search_deezer_albums)]
    try:
        for future in asyncio.as_completed(tasks,timeout=7):
            try:
                result=await future
                if result and 'title' in result[0] and 'name' not in result[0]:albums+=result
                else:tracks+=result or [];catalog_cache.remember(result or [])
                _RESULTS[key]={'time':time.monotonic(),'pending':True,'data':pack(query,tracks,albums,correction,True)}
            except Exception:continue
        preferred=next((a for a in sorted(albums,key=lambda a:-album_score(query,a)) if int(a.get('track_count') or 0)>=4 and fold(clean_title(a.get('title')))==fold(query)),None)
        if preferred:
            try:
                release=await asyncio.wait_for(asyncio.to_thread(fetch_album_tracks,preferred['title'],preferred.get('artist',''),str(preferred['id']),preferred['source']),2.5)
                tracks+=release.get('tracks') or []
                _RESULTS[key]={'time':time.monotonic(),'pending':True,'data':pack(query,tracks,albums,correction,True)}
            except Exception:pass
        live_quality=max((relevance(query,t) for t in tracks if t.get('source')),default=0)
        variants=[]
        if correction and live_quality<90:variants.append(correction)
        if live_quality<78:
            words=query.split();longest=max(words,key=len)
            if len(words)>1 and len(longest)>=5:variants.append(longest)
            if len(longest)>=6:variants.append(longest[:-1])
        for variant in list(dict.fromkeys(variants))[:2]:
            corrected=await loop.run_in_executor(_POOL,_search_itunes_tracks,variant,20)
            corrected=[t for t in corrected if relevance(query,t)>=78]
            tracks+=corrected;catalog_cache.remember(corrected)
    except asyncio.TimeoutError:pass
    finally:
        _RESULTS[key]={'time':time.monotonic(),'pending':False,'data':pack(query,tracks,albums,correction,False)}
        if len(_RESULTS)>120:
            for stale in list(_RESULTS)[:-100]:_RESULTS.pop(stale,None);_JOBS.pop(stale,None)
