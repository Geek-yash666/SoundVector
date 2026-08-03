#!/usr/bin/env python3
"""
SoundVector Terminal UI Helpers & Interactive Loop
"""

import sys
from typing import List, Optional

try:
    from .config import C, s
    from .engine import RecommendationEngine
    from .profiles import ProfileStore
except ImportError:
    from config import C, s
    from engine import RecommendationEngine
    from profiles import ProfileStore



def ask(prompt: str) -> str:
    try:
        return input(f"{s('❯', C.CY)} {s(prompt, C.B)}").strip()
    except (EOFError, KeyboardInterrupt):
        print(f"\n{s('Goodbye! 🎵', C.D)}")
        sys.exit(0)


def print_profile(store: ProfileStore, profile: dict):
    n = profile.get("n_events", 0)
    if n == 0:
        print(f"  {s('New profile — no taste history yet. Like tracks to personalize.', C.D)}")
        return
    genres = ", ".join(f"{g} ({c})" for g, c in store.top_genres(profile))
    artists = ", ".join(f"{a} ({c})" for a, c in store.top_artists(profile))
    print(f"  {s('Your taste so far', C.B, C.WH)} ({n} events):")
    print(f"     {s('Top genres:', C.D)} {genres or '—'}")
    print(f"     {s('Top artists:', C.D)} {artists or '—'}")


def show_recs(recs: List[dict], header: str):
    print(f"\n{s('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', C.CY)}")
    print(s(f"  🎧 Recommendations seeded by {header}", C.B, C.CY))
    print(s("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", C.CY))
    for i, r in enumerate(recs, 1):
        line = f"   {s(f'{i:>2}.', C.YE)} {s(r['name'], C.B, C.WH)} — {s(r['artist'], C.CY)}  [{r['score']*100:4.1f}%]"
        sig = r.get("signals", {})
        sig_parts = []
        if "embed" in sig: sig_parts.append(f"embed {sig['embed']:.2f}")
        if "audio" in sig: sig_parts.append(f"audio {sig['audio']:.2f}")
        if "genre" in sig: sig_parts.append(f"genre {sig['genre']:.2f}")
        if "artist" in sig: sig_parts.append(f"artist {int(sig['artist'])}")
        if "popularity" in sig: sig_parts.append(f"pop {sig['popularity']:.2f}")
        print(line)
        if sig_parts:
            print(f"      {s(' · '.join(sig_parts), C.D)}")


def feedback_loop(engine: RecommendationEngine, store: ProfileStore, user: str,
                  profile: dict, recs: List[dict], mode: str) -> Optional[int]:
    print(s("\n  Feedback: l N = like #N · s N = skip #N · N = get recs from #N · Enter = new search", C.D))
    while True:
        cmd = ask("Feedback / next: ").strip().lower()
        if not cmd:
            return None
        parts = cmd.split()
        if parts[0] in ("l", "s") and len(parts) == 2 and parts[1].isdigit():
            i = int(parts[1]) - 1
            if 0 <= i < len(recs):
                sig = "like" if parts[0] == "l" else "skip"
                store.record(user, profile, recs[i]["row"], sig, {"mode": mode})
                store.save(user, profile)
                verb = "👍 Liked" if sig == "like" else "👎 Skipped"
                print(f"  {s(verb, C.GR if sig=='like' else C.RE)}: {recs[i]['name']} — {recs[i]['artist']} (Profile updated!)")
            else:
                print(f"  {s('Out of range.', C.YE)}")
        elif parts[0].isdigit():
            i = int(parts[0]) - 1
            if 0 <= i < len(recs):
                return recs[i]["row"]
            print(f"  {s('Out of range.', C.YE)}")
        elif parts[0] in ("quit", "exit", "q"):
            print(f"\n{s('Thanks for using SoundVector! 🎵', C.CY, C.B)}\n")
            sys.exit(0)
        else:
            print(f"  {s('Commands: l N | s N | N | Enter', C.D)}")
