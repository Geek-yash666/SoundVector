#!/usr/bin/env python3
"""
SoundVector — All-in-One AI Music Recommender & RAG DJ App

A modular application combining:
  1. Two-Stage Recommendation Engine (ANN retrieval via HNSW + MMR reranking)
  2. MoodToVector NLP Model (TF-IDF + Ridge projection of NL text to sound vectors)
  3. Gemini RAG DJ & Groundedness Checker (fact-verified AI DJ commentary)
  4. User Profile Store (long-term/short-term taste vectors & feedback logging)
  5. Interactive Terminal UI & Web UI Dashboard (run with --web for browser interface)

Usage:
    python3 backend/app.py                        # Terminal interactive mode
    python3 backend/app.py --web                  # Launch Web UI Dashboard at http://localhost:8000
    python3 backend/app.py --user Yash             # Terminal interactive mode with profile 'Yash'
    python3 backend/app.py "sad rainy night"       # Terminal one-shot natural language query
"""

import argparse
import os
import sys

_script_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.abspath(os.path.join(_script_dir, ".."))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

# -----------------------------------------------------------------------------
# Module Imports & Re-exports for Backward Compatibility
# -----------------------------------------------------------------------------
try:

    from backend.config import (
        BASE_GENRE_MAP,
        DEFAULT_MOOD_MODEL_PATH,
        FEATURE_TERMS,
        GPU_USAGE,
        HAS_SPACES,
        LONG_TERM_DECAY,
        N_AUDIO_DIMS,
        SCORING_PRESETS,
        SHORT_TERM_DECAY,
        SYNONYMS,
        load_env,
        resolve_artifacts_dir,
    )
    from backend.engine import RecommendationEngine, _norm_title
    from backend.external_api import (
        _clean_search_query,
        _fetch_json,
        enrich_artist_lastfm,
        enrich_track,
        fetch_album_tracks,
        get_artist_image,
        search_live_albums,
        search_live_apis,
    )
    from backend.models import (
        AIIntelRequest,
        FeedbackRequest,
        PlaylistGenRequest,
        RecommendRequest,
    )
    from backend.mood import MoodToVector
    from backend.pipeline import (
        _raw_run_pipeline,
        is_song_query,
        run_pipeline,
        safe_run_pipeline,
    )
    from backend.profiles import ProfileStore
    from backend.rag_dj import GroundednessChecker, RAGDJ, _mood_word
    from backend.routes import app, get_app_components, launch_server
    from backend.terminal import C, ask, feedback_loop, print_profile, s, show_recs
except ImportError:
    from config import (
        BASE_GENRE_MAP,
        DEFAULT_MOOD_MODEL_PATH,
        FEATURE_TERMS,
        GPU_USAGE,
        HAS_SPACES,
        LONG_TERM_DECAY,
        N_AUDIO_DIMS,
        SCORING_PRESETS,
        SHORT_TERM_DECAY,
        SYNONYMS,
        load_env,
        resolve_artifacts_dir,
    )
    from engine import RecommendationEngine, _norm_title
    from external_api import (
        _clean_search_query,
        _fetch_json,
        enrich_artist_lastfm,
        enrich_track,
        fetch_album_tracks,
        get_artist_image,
        search_live_albums,
        search_live_apis,
    )
    from models import (
        AIIntelRequest,
        FeedbackRequest,
        PlaylistGenRequest,
        RecommendRequest,
    )
    from mood import MoodToVector
    from pipeline import (
        _raw_run_pipeline,
        is_song_query,
        run_pipeline,
        safe_run_pipeline,
    )
    from profiles import ProfileStore
    from rag_dj import GroundednessChecker, RAGDJ, _mood_word
    from routes import app, get_app_components, launch_server
    from terminal import C, ask, feedback_loop, print_profile, s, show_recs



# -----------------------------------------------------------------------------
# CLI Entry Point
# -----------------------------------------------------------------------------
def main():
    load_env()
    ap = argparse.ArgumentParser(description="SoundVector All-in-One AI Music Recommender & RAG DJ")
    ap.add_argument("query", nargs="*", help="Optional query string (song/artist or mood)")
    ap.add_argument("--user", default=None, help="User profile name")
    ap.add_argument("--artifacts", default="artifacts", help="Path to artifacts directory")
    ap.add_argument("--web", "-w", action="store_true", help="Launch Web UI / API server")
    ap.add_argument("--port", type=int, default=8000, help="Port for Web UI / API server")
    args = ap.parse_args()

    if os.environ.get("SPACE_ID") or os.environ.get("HF_SPACE_ID") or args.web:
        launch_server(port=args.port)
        return

    artifacts_dir = resolve_artifacts_dir(args.artifacts)

    print(s("\n" + "━" * 60, C.CY))
    print(s("  🎵  SoundVector — Unified AI Music Recommender & RAG DJ", C.B, C.CY))
    print(s("     Two-Stage ANN Retrieval · MoodToVector NLP · Gemini DJ", C.D, C.CY))
    print(s("━" * 60, C.CY))

    engine, mood_model, dj, checker, store = get_app_components(artifacts_dir)
    print(s("✓", C.GR, C.B))
    print(f"  {s(f'{len(engine.meta):,} tracks · {len(engine.catalog):,} unique songs · DJ backend: {dj.backend}', C.D)}")

    user = args.user or ask("\nYour name (for your taste profile): ") or "default"
    profile = store.load(user)
    print(f"\n  {s('👤 Profile:', C.GR)} {s(user, C.B, C.CY)}")
    print_profile(store, profile)

    one_shot = " ".join(args.query).strip()
    if one_shot:
        header, recs, blurb, ground, facts, intel = safe_run_pipeline(one_shot, engine, mood_model, dj, checker, profile, store)
        show_recs(recs, header)
        print(f"\n💬 DJ ({dj.backend}):\n   {blurb}")
        gcolor = "✅" if ground["groundedness"] >= 0.9 else ("⚠️" if ground["groundedness"] >= 0.7 else "❌")
        print(f"\n{gcolor} groundedness {ground['groundedness']:.0%} ({ground['grounded']}/{ground['total_claims']} claims verified)")
        return

    pending_row = None
    while True:
        print(s("\n" + "─" * 60, C.D))
        if pending_row is not None:
            seed_row = pending_row
            pending_row = None
            facts = engine.track_card(seed_row)
            query = f"{facts['name']} {facts['artist']}"
        else:
            query = ask("Search a song, artist, or mood vibe (or 'quit'): ")
            if query.lower() in ("quit", "exit", "q"):
                print(f"\n{s('Thanks for using SoundVector! 🎵', C.CY, C.B)}\n")
                break
            if not query:
                continue

        mode = ask(f"Mode {s('[similar]', C.D)} similar/vibe/popular/discover: ").lower() or "similar"
        if mode not in SCORING_PRESETS:
            mode = "similar"

        print(f"\n  {s('⏳ Retrieving + ranking + DJ commentary...', C.D)}", flush=True)
        header, recs, blurb, ground, facts, intel = safe_run_pipeline(query, engine, mood_model, dj, checker, profile, store, mode=mode)
        show_recs(recs, header)
        print(f"\n💬 DJ ({dj.backend}):\n   {blurb}")
        gcolor = "✅" if ground["groundedness"] >= 0.9 else ("⚠️" if ground["groundedness"] >= 0.7 else "❌")
        print(f"\n{gcolor} groundedness {ground['groundedness']:.0%} ({ground['grounded']}/{ground['total_claims']} claims verified)")
        if ground["violations"]:
            for v in ground["violations"]:
                print(f"     - {v}")

        pending_row = feedback_loop(engine, store, user, profile, recs, mode)


if __name__ == "__main__":
    if os.environ.get("SPACE_ID") or os.environ.get("HF_SPACE_ID"):
        launch_server()
    else:
        main()