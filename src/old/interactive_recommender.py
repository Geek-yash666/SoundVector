#!/usr/bin/env python3
"""
Interactive Music Recommender CLI
=================================
 recommendation engine with fuzzy search on 899K+ tracks.

Usage:
    python3 src/interactive_recommender.py

Features:
    - Fuzzy search (handles misspellings like "blidning ligths" → "Blinding Lights")
    - Auto-detects artist vs song name queries
    - Artist search: shows up to 15 tracks by that artist
    - Song search: shows matched songs, lets user pick one
    - Generates top 15 recommendations using four-signal, 8D Euclidean scoring
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from recommender import ProductionRecommender


# ─── ANSI Color Helpers ──────────────────────────────────────────────────────

class Colors:
    BOLD      = "\033[1m"
    DIM       = "\033[2m"
    ITALIC    = "\033[3m"
    UNDERLINE = "\033[4m"
    RESET     = "\033[0m"
    CYAN      = "\033[96m"
    GREEN     = "\033[92m"
    YELLOW    = "\033[93m"
    MAGENTA   = "\033[95m"
    RED       = "\033[91m"
    BLUE      = "\033[94m"
    WHITE     = "\033[97m"
    GRAY      = "\033[90m"


def styled(text, *styles):
    """Apply multiple ANSI styles to text."""
    prefix = "".join(styles)
    return f"{prefix}{text}{Colors.RESET}"


# ─── Display Helpers ─────────────────────────────────────────────────────────

BANNER = f"""
{styled("━" * 60, Colors.CYAN)}
{styled("  🎵  Music Recommender — Interactive Search", Colors.BOLD, Colors.CYAN)}
{styled("   8D Euclidean similarity on 899K+ tracks", Colors.DIM, Colors.CYAN)}
{styled("━" * 60, Colors.CYAN)}
"""

def print_track_list(tracks, title="Results", show_album=False, numbered=True):
    """Pretty-print a list of tracks."""
    print(f"\n{styled(title, Colors.BOLD, Colors.GREEN)}")
    print(styled("─" * 56, Colors.DIM))

    for i, t in enumerate(tracks, 1):
        num = f"{styled(f'{i:>2}.', Colors.YELLOW)} " if numbered else "    "
        name = styled(t["name"], Colors.BOLD, Colors.WHITE)
        artist = styled(t["artist"], Colors.CYAN)
        line = f"  {num}{name} — {artist}"

        if show_album and t.get("album") and t["album"] not in ("nan", "None", ""):
            album_name = t["album"]
            line += f"  {styled(f'({album_name})', Colors.DIM)}"
        print(line)

    print()


def print_recommendations(recs, seed_name, seed_artist):
    """Pretty-print recommendation results with scores and explanations."""
    print(f"\n{styled('━' * 60, Colors.MAGENTA)}")
    print(f"  {styled('🎧', Colors.MAGENTA)} {styled('Recommendations based on', Colors.BOLD)} "
          f"{styled(f'\"{seed_name}\"', Colors.BOLD, Colors.YELLOW)} "
          f"{styled('by', Colors.BOLD)} {styled(seed_artist, Colors.BOLD, Colors.CYAN)}")
    print(f"{styled('━' * 60, Colors.MAGENTA)}\n")

    for i, rec in enumerate(recs, 1):
        score_pct = rec["score"] * 100
        # Color score bar based on value
        if score_pct >= 70:
            score_color = Colors.GREEN
        elif score_pct >= 50:
            score_color = Colors.YELLOW
        else:
            score_color = Colors.RED

        score_str = styled(f"[{score_pct:5.1f}%]", Colors.BOLD, score_color)
        name = styled(rec["name"], Colors.BOLD, Colors.WHITE)
        artist = styled(rec["artist"], Colors.CYAN)
        album = rec.get("album", "")

        print(f"  {styled(f'{i:>2}.', Colors.YELLOW)} {name} — {artist}  {score_str}")

        if album and album not in ("nan", "None", ""):
            print(f"      {styled(f'💿 {album}', Colors.DIM)}")

        print(f"      {styled(rec['explanation'], Colors.DIM, Colors.ITALIC)}")
        print()


def get_user_input(prompt):
    """Get user input with styled prompt."""
    try:
        return input(f"{styled('❯', Colors.CYAN)} {styled(prompt, Colors.BOLD)}")
    except (EOFError, KeyboardInterrupt):
        print(f"\n{styled('Goodbye! 🎵', Colors.DIM)}")
        sys.exit(0)


def get_recommendation_settings():
    """Collect the requested ranking mode from the user."""
    mode = get_user_input("Mode: similar, vibe, popular, or discover [similar]: ").strip().lower() or "similar"
    if mode not in ProductionRecommender.SCORING_PRESETS:
        print(f"  {styled('Unknown mode; using similar.', Colors.YELLOW)}")
        mode = "similar"
    return mode


# ─── Search Logic ────────────────────────────────────────────────────────────

def classify_query(recommender, query):
    """
    Determine if a query is an artist search or a song search.
    Returns: ("artist", artist_name) or ("song", song_matches)
    """
    query_lower = query.strip().lower()

    # Song search gets first priority for an exact title. This avoids treating
    # a song title such as "Blinding Lights" as an artist merely because a
    # different catalog artist happens to use that name.
    song_matches = recommender.fuzzy_search_songs(query, limit=20)
    has_exact_title = any(match["name"].lower() == query_lower for match in song_matches)
    if has_exact_title:
        return ("song", song_matches)

    # Exact artist match (e.g. "the weeknd", "coldplay", "drake")
    exact_artists = [a for a in recommender._unique_artists if a.lower() == query_lower]
    if exact_artists:
        return ("artist", exact_artists[0])

    # Partial artist match only takes precedence when there is no direct title.
    artist_matches = recommender.fuzzy_search_artists(query, limit=5)
    if artist_matches:
        top_artist = artist_matches[0]
        if query_lower in top_artist.lower():
            tracks = recommender.get_artist_tracks(top_artist, limit=5)
            if tracks and max(t["popularity"] for t in tracks) >= 0.70:
                return ("artist", top_artist)

    if song_matches:
        return ("song", song_matches)

    if artist_matches:
        return ("artist", artist_matches[0])

    return ("none", [])


def choose_playlist_seed(recommender):
    """Search for and select one additional playlist-radio seed track."""
    while True:
        query = get_user_input("Add a seed: search by song or artist (Enter when done): ").strip()
        if not query:
            return None

        query_type, result = classify_query(recommender, query)
        if query_type == "none":
            print(f"  {styled('No matches found. Try another search.', Colors.RED)}")
            continue

        if query_type == "artist":
            options = recommender.get_artist_tracks(result, limit=15)
            title = f"Top {len(options)} tracks by {result}"
        else:
            options = result
            title = f"Search results for \"{query}\""
        if not options:
            print(f"  {styled('No selectable tracks found.', Colors.RED)}")
            continue

        print_track_list(options, title=title, show_album=True)
        selection = get_user_input(f"Select a playlist seed (1-{len(options)}): ").strip()
        try:
            index = int(selection) - 1
            if 0 <= index < len(options):
                return options[index]
        except ValueError:
            pass
        print(f"  {styled('Invalid selection. Search again or press Enter to finish.', Colors.YELLOW)}")


# ─── Main Interactive Loop ───────────────────────────────────────────────────

def main():
    print(BANNER)
    print(f"  {styled('Loading 899K+ track dataset...', Colors.DIM)} ", end="", flush=True)

    recommender = ProductionRecommender()
    track_count = len(recommender.df)
    catalog_count = len(recommender.catalog)
    artist_count = len(recommender._unique_artists)

    print(f"{styled('✓', Colors.GREEN, Colors.BOLD)}")
    print(f"  {styled(f'{track_count:,} tracks | {catalog_count:,} unique songs | {artist_count:,} artists', Colors.DIM)}")
    print()

    pending_query = None

    while True:
        print(styled("─" * 60, Colors.DIM))
        if pending_query:
            query = pending_query
            pending_query = None
        else:
            query = get_user_input("Search by song name or artist (or 'quit' to exit): ").strip()

        if not query:
            continue
        if query.lower() in ("quit", "exit", "q"):
            print(f"\n{styled('Thanks for using Music Recommender! 🎵', Colors.CYAN, Colors.BOLD)}\n")
            break

        # Classify the query
        query_type, result = classify_query(recommender, query)

        if query_type == "none":
            print(f"\n  {styled('❌ No matches found for', Colors.RED)} {styled(f'\"{query}\"', Colors.BOLD)}")
            print(f"  {styled('Try a different spelling or search term.', Colors.DIM)}")
            continue

        selected = None

        # ─── Artist Mode ─────────────────────────────────────────────
        if query_type == "artist":
            artist_name = result
            print(f"\n  {styled('🎤 Artist found:', Colors.GREEN)} {styled(artist_name, Colors.BOLD, Colors.CYAN)}")

            tracks = recommender.get_artist_tracks(artist_name, limit=15)
            if not tracks:
                print(f"  {styled('No tracks found for this artist in the dataset.', Colors.DIM)}")
                continue

            print_track_list(tracks, title=f"Top {len(tracks)} tracks by {artist_name}", show_album=True)

            # Ask user to select a track (or type a new query!)
            selection = get_user_input(f"Select a track (1-{len(tracks)}) to get recommendations: ").strip()
            if not selection:
                continue
            if selection.lower() in ("quit", "exit", "q"):
                print(f"\n{styled('Thanks for using Music Recommender! 🎵', Colors.CYAN, Colors.BOLD)}\n")
                break
            try:
                sel_idx = int(selection) - 1
                if 0 <= sel_idx < len(tracks):
                    selected = tracks[sel_idx]
                else:
                    print(f"  {styled('Invalid selection index.', Colors.RED)}")
                    continue
            except ValueError:
                # User typed a text string instead of a number — treat as new query!
                pending_query = selection
                continue

        # ─── Song Mode ────────────────────────────────────────────────
        elif query_type == "song":
            song_matches = result

            if len(song_matches) == 1:
                # Auto-select if only one match
                selected = song_matches[0]
                print(f"\n  {styled('✓ Found:', Colors.GREEN)} {styled(selected['name'], Colors.BOLD, Colors.WHITE)} "
                      f"— {styled(selected['artist'], Colors.CYAN)}")
            else:
                print(f"\n  {styled('🔍 Did you mean...', Colors.YELLOW, Colors.BOLD)}")
                print_track_list(song_matches, title=f"Search results for \"{query}\"", show_album=True)

                selection = get_user_input(f"Select a track (1-{len(song_matches)}) to get recommendations: ").strip()
                if not selection:
                    continue
                if selection.lower() in ("quit", "exit", "q"):
                    print(f"\n{styled('Thanks for using Music Recommender! 🎵', Colors.CYAN, Colors.BOLD)}\n")
                    break
                try:
                    sel_idx = int(selection) - 1
                    if 0 <= sel_idx < len(song_matches):
                        selected = song_matches[sel_idx]
                    else:
                        print(f"  {styled('Invalid selection index.', Colors.RED)}")
                        continue
                except ValueError:
                    # User typed a text string instead of a number — treat as new query!
                    pending_query = selection
                    continue

        # ─── Playlist radio and ranking controls ───────────────────────
        seed_tracks = [selected]
        while True:
            additional_seed = choose_playlist_seed(recommender)
            if additional_seed is None:
                break
            if additional_seed["catalog_idx"] in {seed["catalog_idx"] for seed in seed_tracks}:
                print(f"  {styled('That track is already in the playlist.', Colors.YELLOW)}")
            else:
                seed_tracks.append(additional_seed)
                print(f"  {styled('Added:', Colors.GREEN)} {additional_seed['name']} — {additional_seed['artist']}")
        seed_indices = [seed["catalog_idx"] for seed in seed_tracks]

        mode = get_recommendation_settings()
        seed_rows = recommender.catalog.iloc[seed_indices]
        feature_means = seed_rows[["energy", "danceability", "valence"]].mean()
        genre_set = set().union(*seed_rows["genre_set"])
        genre_str = next(iter(genre_set), "pop")
        energy_display = f"{feature_means['energy']:.2f}"
        dance_display = f"{feature_means['danceability']:.2f}"
        valence_display = f"{feature_means['valence']:.2f}"

        print(f"\n  {styled('✨ User Profile taste signature derived from seed:', Colors.WHITE, Colors.BOLD)}")
        print(f"     - Favorite Genre: {styled(genre_str.title(), Colors.YELLOW)}")
        print(f"     - Seed Tracks: {styled(str(len(seed_indices)), Colors.YELLOW)}")
        print(f"     - Target Energy Centroid: {styled(energy_display, Colors.YELLOW)}")
        print(f"     - Target Danceability Centroid: {styled(dance_display, Colors.YELLOW)}")
        print(f"     - Target Valence Centroid: {styled(valence_display, Colors.YELLOW)}")
        print(f"     - Ranking Mode: {styled(mode.title(), Colors.YELLOW)}")

        print(f"\n  {styled('⏳ Computing recommendations...', Colors.DIM)}", flush=True)

        recs = recommender.recommend_from_seeds(
            seed_indices, k=15, max_per_artist=1,
            max_per_other_artist=2,
            weights=ProductionRecommender.SCORING_PRESETS[mode],
            exclude_seed_artists=mode == "popular",
            cap_unknown_artists=mode == "popular",
        )

        if not recs:
            print(f"  {styled('No recommendations could be generated.', Colors.RED)}")
            continue

        print_recommendations(recs, selected["name"], selected["artist"])

        # Ask if user wants to continue
        print(f"  {styled('💡 Tip:', Colors.YELLOW)} Pick any recommended song to chain recommendations!")
        print()


if __name__ == "__main__":
    main()
