#!/usr/bin/env python3
"""
SoundVector FastAPI App Initialization & REST API Endpoint Routes
"""

import asyncio
import os
import re
import threading
import urllib.parse
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
import gradio as gr
import sys
from rapidfuzz import fuzz


_script_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.abspath(os.path.join(_script_dir, ".."))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

try:

    from .config import BASE_GENRE_MAP, C, resolve_artifacts_dir, s
    from .engine import RecommendationEngine
    from .external_api import (
        _clean_search_query,
        async_batch_enrich,
        enrich_artist_lastfm,
        enrich_track,
        fetch_album_tracks,
        get_artist_image,
        search_live_albums,
        search_live_apis,
    )
    from .models import AIIntelRequest, BatchEnrichRequest, FeedbackRequest, PlaylistGenRequest, PreferencesRequest, RecommendRequest, ListeningRequest
    from .mood import MoodToVector
    from .pipeline import safe_run_pipeline
    from .profiles import ProfileStore
    from .home import build_home
    from .discovery import discovery_context, recommend_track, mood_tracks
    from .metadata import public_track, recording_match, trusted_language
    from .rag_dj import GroundednessChecker, RAGDJ
except ImportError:
    from config import BASE_GENRE_MAP, C, resolve_artifacts_dir, s
    from engine import RecommendationEngine
    from external_api import (
        _clean_search_query,
        async_batch_enrich,
        enrich_artist_lastfm,
        enrich_track,
        fetch_album_tracks,
        get_artist_image,
        search_live_albums,
        search_live_apis,
    )
    from models import AIIntelRequest, BatchEnrichRequest, FeedbackRequest, PlaylistGenRequest, PreferencesRequest, RecommendRequest, ListeningRequest
    from mood import MoodToVector
    from pipeline import safe_run_pipeline
    from profiles import ProfileStore
    from backend.home import build_home
    from backend.discovery import discovery_context, recommend_track, mood_tracks
    from backend.metadata import public_track, recording_match, trusted_language
    from rag_dj import GroundednessChecker, RAGDJ



_COMPONENTS = None

# Cache the LASTFM key once at module load to avoid os.environ.get on every request
_LASTFM_KEY: str = ""

from fastapi.middleware.gzip import GZipMiddleware

app = FastAPI(title="SoundVector API", version="1.0")

app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_app_components(artifacts_dir: str = "artifacts"):
    global _COMPONENTS, _LASTFM_KEY
    if _COMPONENTS is None:
        resolved_dir = resolve_artifacts_dir(artifacts_dir)
        print(s("  📥 Initializing SoundVector Engine & Models...", C.CY))
        engine = RecommendationEngine(resolved_dir)
        mood_model = MoodToVector.load(os.path.join(resolved_dir, "mood_model.pkl"))
        dj = RAGDJ()
        checker = GroundednessChecker()
        store = ProfileStore(engine)
        _COMPONENTS = (engine, mood_model, dj, checker, store)
        from backend.search import index_for
        from backend.catalog_cache import remember
        index_for(engine)
        for name in store.list_profiles():
            remember(store.history(store.load(name)))
        # Cache API key once at startup
        _LASTFM_KEY = os.environ.get("LASTFM_API_KEY", "")
    return _COMPONENTS


@app.get("/")
@app.get("/index.html")
async def get_index():
    possible_paths = [
        os.path.join(os.path.dirname(__file__), "..", "src", "static", "index.html"),
        "src/static/index.html",
        "static/index.html",
        "index.html"
    ]
    for p in possible_paths:
        if os.path.exists(p):
            resp = FileResponse(p, media_type="text/html")
            resp.headers["Cache-Control"] = "no-store"  # Always fetch fresh HTML — contains versioned asset URLs
            return resp
    return HTMLResponse("<h2>SoundVector API is running. API endpoints available under /api/*</h2>")


@app.get("/style.css")
async def get_style():
    possible_paths = [
        os.path.join(os.path.dirname(__file__), "..", "src", "static", "style.css"),
        "src/static/style.css",
        "style.css"
    ]
    for p in possible_paths:
        if os.path.exists(p):
            resp = FileResponse(p, media_type="text/css")
            resp.headers["Cache-Control"] = "no-cache"
            return resp
    raise HTTPException(status_code=404, detail="style.css not found")


@app.get("/script.js")
async def get_script():
    possible_paths = [
        os.path.join(os.path.dirname(__file__), "..", "src", "static", "script.js"),
        "src/static/script.js",
        "script.js"
    ]
    for p in possible_paths:
        if os.path.exists(p):
            resp = FileResponse(p, media_type="application/javascript")
            resp.headers["Cache-Control"] = "no-cache"
            return resp
    raise HTTPException(status_code=404, detail="script.js not found")


@app.get("/core.js")
async def get_core():
    return FileResponse(os.path.join(_parent_dir, "src", "static", "core.js"), media_type="application/javascript",
                        headers={"Cache-Control": "no-cache"})


@app.get("/favicon.ico")
@app.get("/mark.svg")
async def get_favicon():
    return FileResponse(os.path.join(_parent_dir,"src","static","mark.svg"),media_type="image/svg+xml")


@app.get("/api/users")
async def api_users():
    engine, mood_model, dj, checker, store = get_app_components()
    return store.list_profiles()


@app.delete("/api/users/{username}")
async def api_delete_user(username: str):
    engine, mood_model, dj, checker, store = get_app_components()
    store.delete_user(username)
    return {"status": "success", "user": username}


@app.get("/api/search")
async def api_search(q: str = "", quick: bool = False, live: bool = True):
    from backend.search import search
    engine, *_ = get_app_components()
    return await search(engine, q, quick=quick, live=live)


@app.post("/api/track_details")
def api_track_details(req: AIIntelRequest):
    from backend.details import track_details
    if not req.facts.get('name') or not req.facts.get('artist'):
        raise HTTPException(status_code=422,detail="A song name and artist are required.")
    return track_details(req.facts)


@app.get("/api/editorial")
async def api_editorial(user: str = "default"):
    from backend.curation import editorial
    *_,store=get_app_components()
    profile=await asyncio.to_thread(store.load,user)
    return await editorial(store,profile)


@app.get("/api/playlist")
def api_playlist(id: str = "", source: str = "deezer", url: str = ""):
    from backend.curation import playlist
    if source=='apple_music':
        from backend.apple_music import playlist as apple_playlist
        result=apple_playlist(id,url)
    else:
        result=playlist(id) if source=='deezer' else None
    if not result:raise HTTPException(status_code=404,detail="This playlist is not available right now.")
    return result


@app.get("/api/album_tracks")
async def api_album_tracks(title: str = "", artist: str = "", id: str = "", source: str = ""):
    engine, mood_model, dj, checker, store = get_app_components()
    data = await asyncio.to_thread(fetch_album_tracks, title, artist_name=artist, album_id=id, source=source, engine=engine)
    if data and data.get("tracks"):
        data["tracks"] = [public_track(t) for t in data["tracks"]]
    return data


@app.get("/api/artist_image")
async def api_artist_image(q: str = ""):
    q_clean = q.strip()
    if not q_clean or len(q_clean) < 3 or q_clean.lower() in ("unknown", "unknown artist", "various artists", "i", "ka", "yan"):
        return {"image_url": ""}
    img_url = await asyncio.to_thread(get_artist_image, q_clean)
    response = JSONResponse(content={"image_url": img_url})
    # Artist images are stable — cache aggressively
    response.headers["Cache-Control"] = "public, max-age=86400, stale-while-revalidate=604800"
    return response



@app.get("/api/enrich")
async def api_enrich(track: str = "", artist: str = ""):
    result = await asyncio.to_thread(enrich_track, track, artist, _LASTFM_KEY)
    # Cache for 1 hour — enrichment data (album art, previews) is stable
    response = JSONResponse(content=result)
    response.headers["Cache-Control"] = "public, max-age=3600, stale-while-revalidate=86400"
    return response


@app.post("/api/batch_enrich")
async def api_batch_enrich(body: BatchEnrichRequest):
    """Batch-enrich multiple tracks in one round-trip instead of N individual calls."""
    enriched_tracks = await async_batch_enrich(body.tracks, _LASTFM_KEY)
    return {"tracks": enriched_tracks}



@app.get("/api/artist")
def api_artist(name: str = "", sort: str = "popularity"):
    engine, mood_model, dj, checker, store = get_app_components()
    tracks = engine.artist_all_tracks(name, sort_by=sort, limit=1000) if engine else []
    albums = engine.artist_albums(name) if engine else []

    # Use cached key instead of os.environ.get on every request
    lastfm_info = enrich_artist_lastfm(name, _LASTFM_KEY)

    existing_names = {(t.get("name") or "").lower().strip() for t in tracks}
    
    # 1. Merge Last.fm top tracks if missing
    for ltr in lastfm_info.get("top_tracks", []):
        tn = (ltr.get("name") or "").lower().strip()
        if tn and tn not in existing_names:
            tracks.append(ltr)
            existing_names.add(tn)


    if name:
        try:
            live_tracks = search_live_apis(name, limit=100)
            all_live = []
            for tr in live_tracks:
                a_name = tr.get("artist", "").lower()
                n_lower = name.lower()
                if n_lower in a_name or a_name in n_lower:
                    all_live.append(tr)
            
            existing_tracks_by_name = { (t.get("name") or "").lower().strip(): t for t in tracks }
            for tr in all_live:
                tname = tr.get("name", "")
                if not tname:
                    continue
                tn = tname.lower().strip()
                if tn in existing_tracks_by_name:
                    # MERGE LIVE METADATA INTO THE INDEX TRACK!
                    idx_t = existing_tracks_by_name[tn]
                    if not idx_t.get("deezer_album_art") and tr.get("deezer_album_art"):
                        idx_t["deezer_album_art"] = tr["deezer_album_art"]
                    if not idx_t.get("deezer_preview_url") and tr.get("deezer_preview_url"):
                        idx_t["deezer_preview_url"] = tr["deezer_preview_url"]
                    if not idx_t.get("deezer_link") and tr.get("deezer_link"):
                        idx_t["deezer_link"] = tr["deezer_link"]
                    if tr.get("year") and (not idx_t.get("year") or str(idx_t.get("year")) in ["2024", "0", ""]):
                        idx_t["year"] = tr["year"]
                else:
                    existing_names.add(tn)
                    tracks.append(tr)
                    existing_tracks_by_name[tn] = tr
        except Exception:
            pass

    # 3. Always complement live albums from iTunes/Deezer
    if name:
        try:
            live_albs = search_live_albums(name, limit=20)
            existing_albs = {(a.get("title") or "").lower().strip() for a in albums}
            for la in live_albs:
                atitle = (la.get("title") or "").lower().strip()
                if atitle and atitle not in existing_albs:
                    existing_albs.add(atitle)
                    albums.append({
                        "id": la.get("id", ""), "source": la.get("source", ""),
                        "title": la.get("title"),
                        "year": la.get("year", "2024"),
                        "artist": la.get("artist", name),
                        "cover_art": la.get("cover_art") or la.get("deezer_album_art") or "",
                        "tracks": la.get("tracks", [])
                    })
        except Exception:
            pass

    # Sort tracks according to request
    if sort == "popularity":
        tracks.sort(key=lambda t: t.get("popularity_pct", 50), reverse=True)
    elif sort == "newest":
        tracks.sort(key=lambda t: int(str(t.get("year", "0"))[:4]) if str(t.get("year", "")).strip()[:4].isdigit() else 0, reverse=True)
    elif sort == "oldest":
        tracks.sort(key=lambda t: int(str(t.get("year", "9999"))[:4]) if str(t.get("year", "")).strip()[:4].isdigit() else 9999)
    elif sort == "title":
        tracks.sort(key=lambda t: (t.get("name") or "").lower())

    return {
        "artist": name,
        "tracks": tracks,
        "albums": albums,
        "lastfm": lastfm_info
    }


@app.get("/api/song_album")
def api_song_album(track: str = Query(min_length=1, max_length=500), artist: str = Query(min_length=1, max_length=500), album_id: str = "", album_source: str = ""):
    # Resolve by verified recording, never by a provider ID from a different catalog.
    from backend.albums import resolve_song_album
    result = resolve_song_album(track, artist, album_id=album_id, album_source=album_source)
    if not result:
        raise HTTPException(status_code=404, detail="An album could not be verified for this recording yet.")
    return result


@app.get("/api/track_intel")
def api_track_intel(row: int = -1, track: str = "", artist: str = "", refresh: bool = False, album_id: str = "", album_source: str = ""):
    engine, _, dj, _, _ = get_app_components()
    if not track.strip() or not artist.strip():
        raise HTTPException(status_code=422, detail="Choose a song to see its insights.")
    facts, recs = {"name": track[:500], "artist": artist[:500]}, []
    if row >= 0 and engine:
        try:
            card = engine.track_card(row)
            if recording_match(facts, card):
                facts = {key: card[key] for key in ("name", "artist", "year", "energy", "valence", "danceability", "acousticness", "tempo_bpm") if card.get(key) is not None}
                facts["metadata_source"] = "SoundVector catalog"
                recs = [engine.track_card(r["row"]) for r in engine.recommend([row], k=5)]
        except (IndexError, KeyError, ValueError):
            pass
    extra = enrich_track(track, artist, _LASTFM_KEY)
    if extra.get("recording_genres"):
        facts["genres"] = extra["recording_genres"]
    release = None
    if album_id and album_source in {"itunes", "deezer"}:
        from backend.albums import resolve_song_album
        release = resolve_song_album(track, artist, album_id=album_id, album_source=album_source)
    if release:
        facts["album"] = release["title"]
    elif extra.get("album"):
        facts["album"] = extra["album"]
    if trusted_language(extra):
        facts["language"] = extra["language"]
    from backend.insights import cached_insights
    intel = cached_insights(dj, facts, recs, refresh=refresh)
    return {"facts": facts, "intel": intel,
            "backend": intel.get("_source", "catalog"), "status": intel.get("_status", "unavailable"),
            "model": intel.get("_model", "")}


@app.get("/api/profile")
async def api_profile(user: str = "default"):
    _, _, _, _, store = get_app_components()
    profile = await asyncio.to_thread(store.load, user)
    history = store.history(profile)
    recent = sorted(profile.get("listening", {}).values(), key=lambda e: -e.get("ts", 0))[:30]
    return {"history": [public_track(event) for event in history],
            "recent": [public_track(event) for event in recent],
            "saved_count": len(profile.get("likes", []))}


@app.put("/api/preferences")
async def api_preferences(req: PreferencesRequest):
    raise HTTPException(status_code=410, detail="Home now learns automatically from saved songs and listening.")


@app.post("/api/listen")
async def api_listen(req: ListeningRequest):
    _, _, _, _, store = get_app_components()
    try:
        await asyncio.to_thread(store.record_listen, req.user, req.track.get("row", -1), req.track,
                                req.seconds, req.duration, req.event_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "ok"}


@app.get("/api/home")
async def api_home(user: str = "default"):
    engine, mood_model, _, _, store = get_app_components()
    profile = await asyncio.to_thread(store.load, user)
    seeds = store.taste_seeds(profile)
    pool = []
    if seeds:
        seeds, pool = await discovery_context(engine, store, profile)
        await asyncio.to_thread(store.enrich_feedback, user, seeds)
    data = await asyncio.to_thread(build_home, engine, mood_model, store, profile, None, seeds, pool if seeds else None)
    return data


@app.post("/api/recommend")
async def api_recommend(req: RecommendRequest):
    engine, mood_model, _, _, store = get_app_components()
    profile = await asyncio.to_thread(store.load, req.user)
    count = min(req.limit + req.offset, 100)
    if req.seed_track:
        facts, recs = await recommend_track(engine, store, profile, req.seed_track, count, req.mode)
        header = facts.get("name", req.query)
    elif req.search_type == "nlp":
        recs = await mood_tracks(engine, mood_model, req.query, count, profile, store)
        facts = {"name": req.query, "artist": "your vibe"}
        header = req.query
    else:
        hits = await asyncio.to_thread(engine.search, req.query, 1)
        if not hits:
            raise HTTPException(status_code=404, detail="Choose a song from search to find similar music.")
        facts, recs = await recommend_track(engine, store, profile, hits[0], count, req.mode)
        header = facts.get("name", req.query)
    return {"header": header, "facts": public_track(facts), "recs": recs[req.offset:req.offset + req.limit],
            "has_more": len(recs) >= count, "backend": "soundvector" if req.mode=='flow' else "catalog",
            "mode":req.mode}


@app.post("/api/ai_intel")
async def api_ai_intel(req: AIIntelRequest):
    engine, mood_model, dj, checker, store = get_app_components()
    rec_cards = []
    for r in req.recs[:5]:
        if "row" in r:
            try:
                rec_cards.append(engine.track_card(int(r["row"])))
            except Exception:
                rec_cards.append(r)
        else:
            rec_cards.append(r)
    intel = await asyncio.to_thread(dj.get_intel, req.facts, rec_cards)
    return intel


@app.post("/api/playlist_gen")
async def api_playlist_gen(req: PlaylistGenRequest):
    engine, mood_model, _, _, store = get_app_components()
    profile = await asyncio.to_thread(store.load, req.user)
    tracks = await mood_tracks(engine, mood_model, req.prompt.strip(), min(req.count, 50), profile, store)
    return {"playlist_name": req.prompt.strip(), "description": f"{len(tracks)} songs",
            "tracks": tracks, "ai_generated": False}


@app.post("/api/feedback")
async def api_feedback(req: FeedbackRequest):
    _, mood_model, _, _, store = get_app_components()
    ctx = req.model_dump(exclude_none=True, exclude={"user", "row", "signal"})
    try:
        await asyncio.to_thread(store.feedback, req.user, req.row, req.signal, ctx, mood_model)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "ok"}


def launch_server(port: int = 8000):
    get_app_components()
    port = int(os.environ.get("PORT", port))
    is_hf_space = bool(os.environ.get("SPACE_ID") or os.environ.get("HF_SPACE_ID") or os.environ.get("GRADIO_SERVER_PORT"))
    
    if is_hf_space:
        hf_port = 7860 if is_hf_space else port
        with gr.Blocks(title="SoundVector UI", css="footer {visibility: hidden}") as demo:
            gr.HTML(value='<iframe src="/index.html" style="width:100%; height:100vh; border:none;"></iframe>')

        gradio_fastapi, _, _ = demo.launch(
            server_name="0.0.0.0",
            server_port=hf_port,
            prevent_thread_lock=True,
            ssr_mode=False,
        )

        gradio_fastapi.include_router(app.router)
        print(s(f"\n🚀 SoundVector API (Gradio + FastAPI ZeroGPU) launched on port {hf_port}\n", C.B, C.GR))
        threading.Event().wait()
    else:
        import uvicorn
        print(s(f"\n🚀 SoundVector Web UI & API launched at http://localhost:{port}\n", C.B, C.GR))
        uvicorn.run(app, host="0.0.0.0", port=port)
