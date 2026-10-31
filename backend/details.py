"""Recording details from provider records, preserving the selected song identity."""
from concurrent.futures import ThreadPoolExecutor
from .external_api import enrich_track,_fetch_json
from .metadata import recording_match,public_track
from .media import deezer_track,itunes_track,merge_metadata
from . import catalog_cache

_POOL=ThreadPoolExecutor(max_workers=4,thread_name_prefix='sv-details')

def track_details(track):
    result=catalog_cache.hydrate(track)
    result=merge_metadata(result,enrich_track(track.get('name',''),track.get('artist','')))
    tasks=[]
    deezer_id=str(result.get('deezer_id') or (result.get('provider_id') if result.get('source')=='deezer' else '') or '')
    itunes_id=str(result.get('itunes_id') or (result.get('provider_id') if result.get('source')=='itunes' else '') or '')
    if deezer_id.isdigit():tasks.append(('deezer',_POOL.submit(_fetch_json,f'https://api.deezer.com/track/{deezer_id}')))
    if itunes_id.isdigit():tasks.append(('itunes',_POOL.submit(_fetch_json,f'https://itunes.apple.com/lookup?id={itunes_id}')))
    for source,future in tasks:
        try:
            data=future.result(timeout=5) or {}
            card=deezer_track(data) if source=='deezer' else next((itunes_track(t) for t in data.get('results',[]) if t.get('trackName')),None)
            if card and recording_match(result,card):result=merge_metadata(result,card)
        except Exception:continue
    if result.get('album_id') and result.get('album_source')=='deezer':
        data=_fetch_json(f"https://api.deezer.com/album/{result['album_id']}") or {}
        if data.get('title')==result.get('album'):
            for key in ('label','release_date','upc'):
                if data.get(key):result[key]=data[key]
            result['album_artist']=(data.get('artist') or {}).get('name') or result.get('album_artist','')
    catalog_cache.remember([result])
    return public_track(result)
