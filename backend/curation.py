"""Public charts and real provider playlists, with explicit source and refresh time."""
import asyncio
import datetime
import urllib.parse
from collections import Counter
from .external_api import _fetch_json,_BoundedCache
from .media import deezer_track,artwork
from .metadata import artist_parts,trusted_language,representative_seeds

_CACHE=_BoundedCache(maxsize=80,ttl=900)

def chart():
    cached=_CACHE.get('chart')
    if cached:return cached
    data=_fetch_json('https://api.deezer.com/chart/0/tracks?limit=16') or {}
    result={'tracks':[deezer_track(t) for t in data.get('data',[])],
            'source':'Deezer chart','url':'https://www.deezer.com/channels/charts','updated_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    if result['tracks']:_CACHE['chart']=result
    return result

def playlists(query,limit=4):
    from .apple_music import search_playlists
    apple=search_playlists(query,limit)
    if apple:return apple
    cached=_CACHE.get('playlists:'+query.casefold())
    if cached is not None:return cached
    data=_fetch_json(f'https://api.deezer.com/search/playlist?q={urllib.parse.quote(query)}&limit={limit}') or {}
    result=[{'id':str(p['id']),'source':'deezer','title':p.get('title') or 'Playlist',
             'creator':(p.get('user') or {}).get('name') or 'Deezer','cover_art':artwork(p.get('picture_big') or p.get('picture_medium')),
             'track_count':p.get('nb_tracks'),'url':p.get('link') or ''} for p in data.get('data',[]) if p.get('id')]
    if result:_CACHE['playlists:'+query.casefold()]=result
    return result

async def editorial(store,profile):
    available=store.taste_seeds(profile)
    seeds=representative_seeds([t for t in available if not t.get('implicit')] or available)
    languages=Counter(trusted_language(t) for t in seeds if trusted_language(t))
    names=list(dict.fromkeys(parts[0] for seed in seeds if (parts:=artist_parts(seed.get('artist')))))
    queries=list(languages)+names[:2]
    groups=await asyncio.gather(*(asyncio.to_thread(playlists,q,3) for q in queries[:3]))
    unique={}
    for position in range(max((len(group) for group in groups),default=0)):
        for group in groups:
            if position<len(group):
                item=group[position]
                unique.setdefault((item['source'],str(item['id'])),item)
    return {'trending':await asyncio.to_thread(chart),'playlists':list(unique.values())[:6]}

def playlist(playlist_id):
    if not str(playlist_id).isdigit():return None
    cached=_CACHE.get('playlist:'+str(playlist_id))
    if cached:return cached
    data=_fetch_json(f'https://api.deezer.com/playlist/{playlist_id}') or {}
    if not data.get('id'):return None
    tracks=[];seen=set();page=data.get('tracks') or {};total=int(data.get('nb_tracks') or 0)
    for _ in range(20):
        before=len(tracks)
        for item in page.get('data',[]):
            if str(item.get('id')) in seen:continue
            seen.add(str(item.get('id')));tracks.append(deezer_track(item))
        if len(tracks)==before or len(tracks)>=total:break
        next_url=str(page.get('next') or '').replace('http:','https:',1)
        if not next_url.startswith('https://api.deezer.com/'):break
        page=_fetch_json(next_url) or {}
    result={'id':str(data['id']),'source':'deezer','title':data.get('title'),'artist':(data.get('creator') or {}).get('name') or 'Deezer',
            'cover_art':artwork(data.get('picture_big') or data.get('picture_medium')),'tracks':tracks,'track_count':total,
            'complete':len(tracks)>=total,'description':data.get('description') or '', 'url':data.get('link') or ''}
    if tracks:_CACHE['playlist:'+str(playlist_id)]=result
    return result
