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
    from .models import AIIntelRequest, BatchEnrichRequest, FeedbackRequest, PlaylistGenRequest, RecommendRequest
    from .mood import MoodToVector
    from .pipeline import safe_run_pipeline
    from .profiles import ProfileStore
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
    from models import AIIntelRequest, BatchEnrichRequest, FeedbackRequest, PlaylistGenRequest, RecommendRequest
    from mood import MoodToVector
    from pipeline import safe_run_pipeline
    from profiles import ProfileStore
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
            resp.headers["Cache-Control"] = "public, max-age=86400, stale-while-revalidate=604800"
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
            resp.headers["Cache-Control"] = "public, max-age=86400, stale-while-revalidate=604800"
            return resp
    raise HTTPException(status_code=404, detail="script.js not found")


@app.get("/favicon.ico")
async def get_favicon():
    svg_icon = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#1db954" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2 10v4M6 6v12M10 3v18M14 7v10M18 5v14M22 10v4"/></svg>'
    return HTMLResponse(content=svg_icon, media_type="image/svg+xml")


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
async def api_search(q: str = ""):
    engine, mood_model, dj, checker, store = get_app_components()
    results = engine.search(q, limit=8) if engine else []
    matching_artists = engine.match_artist(q, limit=4) if engine else []
    
    matching_albums = []
    q_clean = q.strip()
    
    # Only query live external APIs if query is at least 2 chars AND local catalog hits are sparse/low-match
    should_search_live = len(q_clean) >= 2 and (
        len(results) < 3 or (results and results[0].get("match", 0.0) < 85.0)
    )
    
    if should_search_live:
        loop = asyncio.get_event_loop()
        try:
            # 2.0s max timeout for external live APIs so live search returns reliably
            live_hits, matching_albums = await asyncio.wait_for(
                asyncio.gather(
                    loop.run_in_executor(None, search_live_apis, q_clean, 5),
                    loop.run_in_executor(None, search_live_albums, q_clean, 4)
                ),
                timeout=2.0
            )
            if live_hits:
                existing_keys = {f"{(r.get('name') or '').lower().strip()}||{(r.get('artist') or '').lower().strip()}" for r in results}
                valid_live = []
                for hit in live_hits:
                    hk = f"{(hit.get('name') or '').lower().strip()}||{(hit.get('artist') or '').lower().strip()}"
                    if hk not in existing_keys:
                        combo = f"{hit.get('name', '')} {hit.get('artist', '')}".lower()
                        clean_q = _clean_search_query(q_clean).lower()
                        score = fuzz.token_set_ratio(clean_q, combo)
                        if score >= 40:
                            hit["match"] = float(score)
                            valid_live.append(hit)
                            existing_keys.add(hk)
                
                # If local search had low match quality (< 70), prioritize live hits at top
                if results and results[0].get("match", 0.0) < 70.0 and valid_live:
                    results = valid_live + results
                else:
                    all_results = results + valid_live
                    all_results.sort(key=lambda x: x.get("match", 0.0), reverse=True)
                    results = all_results

                # Populate matching_artists from live hits if no local artist matches the query well
                live_artists = []
                for lh in valid_live:
                    l_art = lh.get("artist")
                    if l_art and l_art.lower() not in [a.get("artist", "").lower() for a in live_artists]:
                        live_artists.append({"artist": l_art, "max_pop": 0.95})
                
                best_local_sim = max([fuzz.token_set_ratio(q_clean.lower(), a.get("artist", "").lower()) for a in matching_artists], default=0)
                if live_artists:
                    if best_local_sim < 65:
                        matching_artists = live_artists + matching_artists
        except Exception:
            matching_albums = []

    final_results = results[:8]

    return {
        "results": final_results,
        "artists": matching_artists[:4],
        "albums": matching_albums[:4]
    }


@app.get("/api/album_tracks")
async def api_album_tracks(title: str = "", artist: str = "", id: str = "", source: str = ""):
    engine, mood_model, dj, checker, store = get_app_components()
    data = fetch_album_tracks(title, artist_name=artist, album_id=id, source=source, engine=engine)
    if data and data.get("tracks"):
        await async_batch_enrich(data["tracks"])
    return data


@app.get("/api/artist_image")
async def api_artist_image(q: str = ""):
    q_clean = q.strip()
    if not q_clean or len(q_clean) < 3 or q_clean.lower() in ("unknown", "unknown artist", "various artists", "i", "ka", "yan"):
        return {"image_url": ""}
    img_url = get_artist_image(q_clean)
    response = JSONResponse(content={"image_url": img_url})
    # Artist images are stable — cache aggressively
    response.headers["Cache-Control"] = "public, max-age=86400, stale-while-revalidate=604800"
    return response



@app.get("/api/enrich")
async def api_enrich(track: str = "", artist: str = ""):
    result = enrich_track(track, artist, _LASTFM_KEY)
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
async def api_artist(name: str = "", sort: str = "popularity"):
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


@app.get("/api/track_intel")
async def api_track_intel(row: int = -1, track: str = "", artist: str = ""):
    engine, mood_model, dj, checker, store = get_app_components()
    facts = {}
    recs = []
    if row >= 0 and engine:
        try:
            t_card = engine.track_card(row)
            facts = {
                "name": t_card.get("name"),
                "artist": t_card.get("artist"),
                "year": t_card.get("year"),
                "popularity": t_card.get("popularity_pct", 50) / 100.0,
                "genres": t_card.get("base_genres", []),
                "energy": round(float(t_card.get("energy", 0.5)), 2),
                "valence": round(float(t_card.get("valence", 0.5)), 2),
                "danceability": round(float(t_card.get("danceability", 0.5)), 2),
                "acousticness": round(float(t_card.get("acousticness", 0.5)), 2),
                "tempo_bpm": int(t_card.get("tempo_bpm", 120))
            }
            sim_recs = engine.recommend([row], k=5)
            recs = [engine.track_card(r["row"]) for r in sim_recs]
        except Exception:
            pass

    if not facts and track:
        facts = {"name": track, "artist": artist, "genres": ["music"], "energy": 0.6, "valence": 0.5, "danceability": 0.6, "tempo_bpm": 120}

    intel = dj.get_intel(facts, recs)
    return {
        "facts": facts,
        "intel": intel,
        "backend": dj.backend
    }


@app.get("/api/profile")
async def api_profile(user: str = "default"):
    import json
    engine, mood_model, dj, checker, store = get_app_components()
    profile = store.load(user)

    events_path = store._events_path(user)
    history = []
    if os.path.exists(events_path):
        latest_map = {}
        with open(events_path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    ev = json.loads(line)
                    tid = ev.get("track_id") or f"{(ev.get('name') or '').lower().strip()}||{(ev.get('artist') or '').lower().strip()}"
                    latest_map[tid] = ev
                except Exception:
                    pass
        
        active_events = [ev for ev in latest_map.values() if ev.get("signal") not in ("none", "remove_like", "remove_dislike")]
        active_events.sort(key=lambda x: x.get("ts", 0), reverse=True)
        history = active_events[:50]

    return {
        "top_genres": store.top_genres(profile, 3),
        "top_artists": store.top_artists(profile, 3),
        "history": history
    }



@app.get("/api/home")
async def api_home(user: str = "default"):
    import datetime
    import numpy as np
    engine, mood_model, dj, checker, store = get_app_components()
    profile = store.load(user)
    profile_vecs = store.vectors(profile) if profile.get("n_events") else None
    global_seen_rows = set()
    global_seen_keys = set()

    def _track_key(track):
        return f"{(track.get('name') or '').lower().strip()}||{(track.get('artist') or '').lower().strip()}"

    def _filter_unique(cards):
        unique = []
        for c in cards:
            r = c.get("row", -1)
            k = _track_key(c)
            if (r >= 0 and r in global_seen_rows) or (k in global_seen_keys):
                continue
            if r >= 0:
                global_seen_rows.add(r)
            global_seen_keys.add(k)
            unique.append(c)
        return unique

    hour = datetime.datetime.now().hour
    if hour < 12:
        greeting = "Good Morning"
    elif hour < 17:
        greeting = "Good Afternoon"
    elif hour < 21:
        greeting = "Good Evening"
    else:
        greeting = "Late Night Vibes"

    has_history = profile.get("n_events", 0) > 0
    sections = []

    if has_history and profile.get("long_term") is not None:
        lt_vec = np.asarray(profile["long_term"], np.float32)
        n = np.linalg.norm(lt_vec)
        if n > 0:
            lt_vec = lt_vec / n

        # Compute top_genres ONCE (was called twice before)
        top_genres_data = store.top_genres(profile, 5)
        quick_genres = [g[0] for g in top_genres_data] if top_genres_data else []
        top_genres_3 = quick_genres[:3]
        top_artists = store.top_artists(profile, 3)

        # --- Section builders (run concurrently) ---

        async def _build_vibe_section():
            try:
                recs = engine.recommend_by_vector(lt_vec, k=15, max_per_artist=1,
                                                   exclude_rows=global_seen_rows)
                cards = _filter_unique([engine.track_card(r["row"]) for r in recs])[:10]
                if cards:
                    await async_batch_enrich(cards)
                    return {"id": "your_vibe", "title": "Your Vibe",
                            "subtitle": "Based on your taste profile", "tracks": cards}
            except Exception as e:
                print("[Home Feed] Vibe section error:", e)
            return None

        async def _build_artist_section():
            if not top_artists:
                return None
            try:
                top_artist_name = top_artists[0][0]
                at = engine.artist_top_tracks(top_artist_name, limit=1)
                if at and at[0].get("row", -1) >= 0:
                    artist_recs = engine.recommend(
                        [at[0]["row"]], k=15, mode="similar",
                        profile_vectors=profile_vecs, max_per_artist=1,
                        exclude_rows=global_seen_rows
                    )
                else:
                    qv = mood_model.transform(f"{top_artist_name} music")["vector"]
                    artist_recs = engine.recommend_by_vector(
                        qv, k=15, max_per_artist=1, exclude_rows=global_seen_rows
                    )
                artist_cards = _filter_unique([engine.track_card(r["row"]) for r in artist_recs])[:10]
                if artist_cards:
                    await async_batch_enrich(artist_cards)
                    return {
                        "id": "because_artist",
                        "title": f"Because You Like {top_artist_name}",
                        "subtitle": f"Tracks similar to {top_artist_name}'s style",
                        "tracks": artist_cards,
                    }
            except Exception as e:
                print("[Home Feed] Artist section error:", e)
            return None

        async def _build_discover_section():
            try:
                all_genres = ["filmi", "hip hop", "rock", "edm", "r&b", "indie", "pop", "latin", "punjabi pop"]
                other_genres = [g for g in all_genres if g not in top_genres_3]
                target_disc_genres = set(other_genres[:4]) if other_genres else {"rock", "indie", "r&b", "edm"}
                disc_recs = engine.recommend_by_vector(
                    lt_vec, k=25, target_base_genres=target_disc_genres,
                    max_per_artist=1, exclude_rows=global_seen_rows
                )
                disc_cards = _filter_unique([engine.track_card(r["row"]) for r in disc_recs])[:10]
                if disc_cards:
                    await async_batch_enrich(disc_cards)
                    return {"id": "discover_new", "title": "Discover Something New",
                            "subtitle": "Step outside your comfort zone", "tracks": disc_cards}
            except Exception as e:
                print("[Home Feed] Discover section error:", e)
            return None

        # Run all 3 personalized sections CONCURRENTLY
        sec_results = await asyncio.gather(
            _build_vibe_section(),
            _build_artist_section(),
            _build_discover_section(),
            return_exceptions=True
        )
        sections = [s for s in sec_results if s and isinstance(s, dict)]

    else:
        quick_genres = ["pop", "hip hop", "rock", "edm", "r&b"]

        async def _build_trending_section():
            try:
                popular_seeds = engine.search("Shape of You", limit=1)
                if popular_seeds:
                    pop_recs = engine.recommend(
                        [popular_seeds[0]["row"]], k=15, mode="popular",
                        exclude_rows=global_seen_rows
                    )
                    pop_cards = [engine.track_card(r["row"]) for r in pop_recs][:10]
                    if pop_cards:
                        await async_batch_enrich(pop_cards)
                        return {"id": "trending", "title": "Trending Now",
                                "subtitle": "Popular tracks across genres", "tracks": pop_cards}
            except Exception:
                pass
            return None

        async def _build_chill_section():
            try:
                chill_t = mood_model.transform("chill lo-fi ambient relax")
                chill_recs = engine.recommend_by_vector(
                    chill_t["vector"], k=15, max_per_artist=1, exclude_rows=global_seen_rows
                )
                chill_cards = [engine.track_card(r["row"]) for r in chill_recs][:10]
                if chill_cards:
                    await async_batch_enrich(chill_cards)
                    return {"id": "chill_vibes", "title": "Chill Vibes",
                            "subtitle": "Relax and unwind", "tracks": chill_cards}
            except Exception:
                pass
            return None

        async def _build_energy_section():
            try:
                energy_t = mood_model.transform("workout edm energy dance")
                energy_recs = engine.recommend_by_vector(
                    energy_t["vector"], k=15, max_per_artist=1, exclude_rows=global_seen_rows
                )
                energy_cards = [engine.track_card(r["row"]) for r in energy_recs][:10]
                if energy_cards:
                    await async_batch_enrich(energy_cards)
                    return {"id": "energy_boost", "title": "Energy Boost",
                            "subtitle": "Get pumped up", "tracks": energy_cards}
            except Exception:
                pass
            return None

        # Run all 3 anonymous sections CONCURRENTLY
        sec_results = await asyncio.gather(
            _build_trending_section(),
            _build_chill_section(),
            _build_energy_section(),
            return_exceptions=True
        )
        sections = [s for s in sec_results if s and isinstance(s, dict)]

    return {
        "greeting": greeting,
        "user": user,
        "has_history": has_history,
        "sections": sections,
        "quick_genres": quick_genres,
    }


@app.post("/api/recommend")
async def api_recommend(req: RecommendRequest):
    engine, mood_model, dj, checker, store = get_app_components()
    profile = store.load(req.user)

    header, recs, blurb, ground, facts, intel = safe_run_pipeline(
        req.query, engine, mood_model, dj, checker, profile, store,
        mode=req.mode, search_type=req.search_type, seed_track=req.seed_track,
        k=req.limit + req.offset
    )
    sliced_recs = recs[req.offset : req.offset + req.limit]
    await async_batch_enrich(sliced_recs)
    return {
        "header": header,
        "recs": sliced_recs,
        "blurb": blurb,
        "grounded": ground,
        "facts": facts,
        "intel": intel,
        "backend": dj.backend,
    }


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
    intel = dj.get_intel(req.facts, rec_cards)
    return intel


@app.post("/api/playlist_gen")
async def api_playlist_gen(req: PlaylistGenRequest):
    import json
    engine, mood_model, dj, checker, store = get_app_components()
    prompt = req.prompt
    user = req.user
    count = int(req.count)
    if not prompt:
        raise HTTPException(status_code=400, detail="Missing prompt")

    prompt_clean = prompt.strip()
    p_lower = prompt_clean.lower()
    
    gen_params = None
    if dj._client:
        try:
            resp = dj._client.models.generate_content(
                model=dj.model,
                contents=dj.playlist_gen_prompt(prompt_clean, engine.genre_vocab, count)
            )
            text = (resp.text or "").strip()
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                gen_params = json.loads(m.group(0))
                print("\n================ [LLM PLAYLIST RESPONSE] ================")
                print(json.dumps(gen_params, indent=2))
                print("=========================================================\n")
        except Exception as e:
            print(f"[Playlist Gen] Gemini failed: {e}")

    if not gen_params:
        emoji = "🎵"
        if any(w in p_lower for w in ["sleep", "night", "rain", "calm", "relax", "melancholy"]):
            emoji = "🌙"
        elif any(w in p_lower for w in ["run", "workout", "gym", "hype", "energy"]):
            emoji = "⚡"
        elif any(w in p_lower for w in ["party", "dance", "club"]):
            emoji = "🎉"
        gen_params = {
            "playlist_name": f"{prompt_clean.title()} Mix",
            "playlist_emoji": emoji,
            "description": f"A curated selection of authentic {prompt_clean} tracks."
        }

    track_cards = []
    seen_keys = set()

    def _fetch_track_sync(q_obj):
        if not q_obj:
            return None
        
        if isinstance(q_obj, dict):
            tname = (q_obj.get("name") or "").strip()
            aname = (q_obj.get("artist") or "").strip()
            q_str = f"{tname} {aname}".strip()
        elif isinstance(q_obj, str):
            tname = q_obj.strip()
            aname = ""
            q_str = q_obj.strip()
        else:
            return None

        if not tname:
            return None
            
        # 1. Search local index first
        hits = engine.search(q_str, limit=1) if engine else []
        if hits and hits[0].get("match", 0) > 75.0:
            tc = engine.track_card(hits[0]["row"])
            if tc and tc.get("artist") and tc["artist"].lower() not in ["unknown", "unknown artist"]:
                return tc
            
        # 2. Search live APIs (iTunes/Deezer)
        live_hits = search_live_apis(q_str, limit=5)
        if live_hits:
            if not aname:
                return live_hits[0]
            for lh in live_hits:
                hit_art = (lh.get("artist") or "").lower()
                hit_title = (lh.get("name") or "").lower()
                art_score = fuzz.token_set_ratio(aname.lower(), hit_art)
                title_score = fuzz.token_set_ratio(tname.lower(), hit_title)
                if art_score > 30 and title_score > 25:
                    return lh
            return live_hits[0]

        # 3. Fallback: preserve LLM track object directly with correct artist name
        yt_q = urllib.parse.quote(f"{aname} {tname}".strip() if aname else tname)
        return {
            "row": -1,
            "name": tname,
            "artist": aname or prompt_clean.title(),
            "year": "2024",
            "popularity_pct": 85,
            "base_genres": ["pop"],
            "youtube_music_url": f"https://music.youtube.com/search?q={yt_q}",
            "is_llm_generated": True
        }

    specific_queries = gen_params.get("specific_tracks", []) if gen_params else []
    if specific_queries and isinstance(specific_queries, list):
        loop = asyncio.get_event_loop()
        tasks = [
            loop.run_in_executor(None, _fetch_track_sync, q_obj)
            for q_obj in specific_queries[:count + 5] if q_obj
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for found_card in results:
            if isinstance(found_card, Exception) or not found_card:
                continue
            k = f"{(found_card.get('name') or '').lower().strip()}||{(found_card.get('artist') or '').lower().strip()}"
            if k not in seen_keys:
                seen_keys.add(k)
                track_cards.append(found_card)
                if len(track_cards) >= count:
                    break

    if len(track_cards) < count:
        t = mood_model.transform(prompt_clean)
        tg = {BASE_GENRE_MAP.get(tok, tok) for tok in t["matched_tokens"]}
        p_low = prompt_clean.lower()
        strict_reg = False
        for reg_kw, mapped_genres in [
            ("telugu", ["filmi", "desi pop", "indian pop"]),
            ("hindi", ["filmi", "modern bollywood", "desi pop", "indian pop"]),
            ("bollywood", ["filmi", "modern bollywood", "desi pop"]),
            ("punjabi", ["punjabi pop", "desi pop", "filmi"]),
            ("tamil", ["filmi", "indian pop", "desi pop"]),
            ("desi", ["desi pop", "filmi", "indian pop"]),
            ("kpop", ["k-pop", "pop"]), ("k-pop", ["k-pop", "pop"]),
            ("anime", ["anime", "j-pop"]), ("japanese", ["j-pop", "anime"]),
            ("latin", ["latin", "reggaeton"]), ("spanish", ["latin", "reggaeton"]),
            ("afro", ["afrobeats", "afropop"]), ("afrobeats", ["afrobeats", "afropop"]),
        ]:
            if reg_kw in p_low:
                strict_reg = True
                for g in mapped_genres:
                    tg.add(g)
        
        vec_recs = engine.recommend_by_vector(t["vector"], k=count * 3, target_base_genres=tg if tg else None, max_per_artist=2, strict_genre=strict_reg)
        for r in vec_recs:
            if r.get("row", -1) >= 0:
                tc = engine.track_card(r["row"])
                artist_name = (tc.get("artist") or "").strip()
                if not artist_name or artist_name.lower() in ["unknown", "unknown artist"]:
                    continue
                k = f"{(tc.get('name') or '').lower().strip()}||{artist_name.lower()}"
                if k not in seen_keys:
                    seen_keys.add(k)
                    track_cards.append(tc)
                    if len(track_cards) >= count:
                        break

    final_tracks = track_cards[:count]
    await async_batch_enrich(final_tracks)

    return {
        "playlist_name": gen_params.get("playlist_name", f"{prompt_clean.title()} Mix"),
        "playlist_emoji": gen_params.get("playlist_emoji", "🎵"),
        "description": gen_params.get("description", f"A curated selection of {prompt_clean} tracks."),
        "tracks": final_tracks,
        "ai_generated": bool(dj._client)
    }


@app.post("/api/feedback")
async def api_feedback(req: FeedbackRequest):
    engine, mood_model, dj, checker, store = get_app_components()
    profile = store.load(req.user)

    ctx = {"mode": req.mode}
    if req.name:
        ctx["name"] = req.name
    if req.artist:
        ctx["artist"] = req.artist
    if req.deezer_album_art:
        ctx["deezer_album_art"] = req.deezer_album_art
    if req.deezer_preview_url:
        ctx["deezer_preview_url"] = req.deezer_preview_url
    if req.base_genres:
        ctx["base_genres"] = req.base_genres

    store.record(req.user, profile, req.row, req.signal, context=ctx, mood_model=mood_model)
    store.save(req.user, profile)

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
