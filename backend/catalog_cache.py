"""Small persistent metadata cache, separate from model artifacts and listening profiles."""
import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from .metadata import clean_title, artist_signature, recording_match, public_track, recording_version
from .media import merge_metadata

_LOCK=threading.RLock()
_DB=None
_REQUEST_FIELDS={'vector','context','signal','ts','user','seconds','event_id','completed',
                 'score','signals','explanation','reason','flow_reasons','flow_evidence',
                 'recommendation_source','listening_similarity','listening_source'}

def metadata_only(track):
    return {key:value for key,value in track.items() if key not in _REQUEST_FIELDS}

def key(track):return clean_title(track.get('name'))+'|'+recording_version(track.get('name'))+'||'+artist_signature(track.get('artist'))

def connection():
    global _DB
    with _LOCK:
        if _DB is None:
            folder=Path(os.environ.get('SOUNDVECTOR_CACHE_DIR') or Path(__file__).resolve().parent.parent/'.cache')
            folder.mkdir(parents=True,exist_ok=True)
            _DB=sqlite3.connect(folder/'metadata.sqlite',check_same_thread=False)
            _DB.execute('PRAGMA journal_mode=WAL')
            _DB.execute('CREATE TABLE IF NOT EXISTS tracks (identity TEXT PRIMARY KEY,data TEXT,updated REAL)')
        return _DB

def remember(tracks):
    with _LOCK:
        db=connection()
        for track in tracks:
            if not track.get('name') or not track.get('artist'):continue
            identity=key(track)
            previous=db.execute('SELECT data FROM tracks WHERE identity=?',(identity,)).fetchone()
            card=public_track(track)
            if previous:card=merge_metadata(json.loads(previous[0]),card)
            card=metadata_only(card)
            db.execute('INSERT OR REPLACE INTO tracks VALUES (?,?,?)',(identity,json.dumps(card,default=str),time.time()))
        db.execute('DELETE FROM tracks WHERE identity IN (SELECT identity FROM tracks ORDER BY updated DESC LIMIT -1 OFFSET 15000)')
        db.commit()

def all_tracks():
    # Legacy keys collapsed versions; only the version-aware namespace is reusable.
    with _LOCK:return [metadata_only(json.loads(row[0])) for row in connection().execute("SELECT data FROM tracks WHERE identity LIKE '%|%||%' ORDER BY updated DESC LIMIT 15000")]

def hydrate(track):
    with _LOCK:
        row=connection().execute('SELECT data FROM tracks WHERE identity=?',(key(track),)).fetchone()
    if not row:return dict(track)
    cached=metadata_only(json.loads(row[0]))
    return merge_metadata(track,cached) if recording_match(track,cached) else dict(track)
