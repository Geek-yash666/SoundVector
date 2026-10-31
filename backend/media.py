"""Canonical provider metadata. Unknown fields stay unknown; credits retain their roles."""
import re
from .metadata import recording_metadata, artist_signature


def artists(value):
    return [{'name':name.strip(), 'role':'Artist'} for name in re.split(r'\s*(?:,|&|;| feat\.? | featuring )\s*', str(value or '')) if name.strip()]


def artwork(value):
    value=str(value or '')
    if not value or '2a96cbd8b46e442fc41c2b86b821562f' in value or value.endswith('/star.png'):
        return ''
    return value.replace('100x100bb','600x600bb').replace('http:','https:',1)


def itunes_track(item):
    date=item.get('releaseDate') or ''
    return {'row':-1,'track_id':f"live_itunes_{item.get('trackId','')}", 'provider_id':str(item.get('trackId') or ''), 'itunes_id':str(item.get('trackId') or ''),
            'name':item.get('trackName') or '', 'artist':item.get('artistName') or '',
            'artists':artists(item.get('artistName')), 'artist_id':str(item.get('artistId') or ''),
            'album':item.get('collectionName') or '', 'album_id':str(item.get('collectionId') or ''),
            'album_source':'itunes', 'source':'itunes','is_live_external':True,
            'year':date[:4], 'release_date':date, 'duration_seconds':round(item['trackTimeMillis']/1000) if item.get('trackTimeMillis') else None,
            'track_number':item.get('trackNumber'), 'track_count':item.get('trackCount'),
            'disc_number':item.get('discNumber'), 'disc_count':item.get('discCount'),
            'explicit':(item.get('trackExplicitness')=='explicit') if item.get('trackExplicitness') else None, 'copyright':item.get('copyright') or '',
            'country':item.get('country') or '', 'base_genres':[], **recording_metadata(item.get('primaryGenreName')),
            'deezer_album_art':artwork(item.get('artworkUrl100') or item.get('artworkUrl60')),
            'deezer_preview_url':item.get('previewUrl') or '', 'deezer_link':item.get('trackViewUrl') or '',
            'album_url':item.get('collectionViewUrl') or '', 'provider_url':item.get('trackViewUrl') or ''}


def deezer_track(item, album=None):
    album={**(album or {}),**(item.get('album') or {})}
    primary=item.get('artist') or {}
    contributors=item.get('contributors') or ([primary] if primary.get('name') else [])
    credits=[{'name':c.get('name'), 'id':str(c.get('id') or ''), 'role':c.get('role') or 'Artist',
              'image':artwork(c.get('picture_medium') or c.get('picture_big'))} for c in contributors if c.get('name')]
    date=item.get('release_date') or album.get('release_date') or ''
    return {'row':-1,'track_id':f"live_deezer_{item.get('id','')}", 'provider_id':str(item.get('id') or ''),
            'deezer_id':str(item.get('id') or ''),'name':item.get('title') or '', 'artist':primary.get('name') or '',
            'artists':credits, 'artist_id':str(primary.get('id') or ''),
            'album':album.get('title') or '', 'album_id':str(album.get('id') or ''), 'album_source':'deezer',
            'album_artist':(album.get('artist') or {}).get('name') or '', 'source':'deezer','is_live_external':True,
            'year':date[:4], 'release_date':date,'duration_seconds':item.get('duration'),
            'track_number':item.get('track_position'), 'disc_number':item.get('disk_number'),
            'explicit':bool(item.get('explicit_lyrics')) if 'explicit_lyrics' in item else None, 'isrc':item.get('isrc') or '',
            'label':album.get('label') or '', 'provider_rank':item.get('rank'), 'popularity':float(item.get('rank') or 0)/1_000_000,
            'provider_bpm':item.get('bpm') or None, 'readable':item.get('readable'), 'base_genres':[],
            'deezer_album_art':artwork(album.get('cover_big') or album.get('cover_medium') or album.get('cover')),
            'deezer_preview_url':item.get('preview') or '', 'deezer_link':item.get('link') or '',
            'album_url':album.get('link') or '', 'provider_url':item.get('link') or ''}


def merge_metadata(original, extra):
    """Keep identity stable while merging a complete release identity as one unit."""
    result=dict(original)
    selected_provider=original.get('source') in {'deezer','itunes'} and original.get('provider_id')
    keep_release=all(original.get(k) for k in ('album','album_id','album_source')) and any(
        original.get(k)!=extra.get(k) for k in ('album_id','album_source'))
    for key,value in extra.items():
        if key in {'provider_id','deezer_id','itunes_id'} and original.get(key):
            continue
        if selected_provider and key in {'duration_seconds','explicit','provider_url','deezer_link'} and original.get(key) not in (None,''):
            continue
        # Provider rank is a different scale from trained catalog popularity.
        if original.get('row',-1)>=0 and key in {'popularity','popularity_pct','energy','valence','danceability','acousticness','tempo_bpm','genres','base_genres'}:
            continue
        if keep_release and key in {'deezer_album_art','album_url','album_artist','label','upc','track_number','track_count','disc_number','disc_count'}:
            continue
        if value not in (None,'',[],{}) and key not in {'row','name','artist','track_id','source','is_live_external','album','album_id','album_source'}:
            if key=='artists':
                credits={artist_signature(a.get('name')):dict(a) for a in result.get('artists') or [] if a.get('name')}
                for artist in value:
                    identity=artist_signature(artist.get('name'))
                    if not identity:continue
                    previous=credits.get(identity,{})
                    merged={**previous,**{k:v for k,v in artist.items() if v not in (None,'')}}
                    if previous.get('role') not in (None,'','Artist') and artist.get('role') in (None,'','Artist'):
                        merged['role']=previous['role']
                    credits[identity]=merged
                result['artists']=list(credits.values())
                continue
            result[key]=value
    if not keep_release and all(extra.get(k) for k in ('album','album_id','album_source')):
        result.update({k:extra[k] for k in ('album','album_id','album_source')})
    return result
