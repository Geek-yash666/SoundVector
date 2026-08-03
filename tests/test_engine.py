"""Unit tests for search + two-stage recommendation behavior."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from app import _norm_title  # noqa: E402


def test_search_exact_title_ranks_famous_first(engine):
    hits = engine.search("blinding lights", limit=5)
    assert hits, "expected results for a well-known title"
    assert hits[0]["name"].lower() == "blinding lights"
    assert hits[0]["artist"] == "The Weeknd"


def test_search_common_word_finds_the_hit(engine):
    # 'baby' must surface Justin Bieber's "Baby" near the top, not bury it
    hits = engine.search("baby", limit=8)
    titles = [(h["name"].lower(), h["artist"]) for h in hits]
    assert any(n == "baby" and a == "Justin Bieber" for n, a in titles)


def test_artist_typo_resolves(engine):
    matches = engine.match_artist("justin beiber")
    assert matches and matches[0]["artist"] == "Justin Bieber"


def test_no_results_is_graceful(engine):
    assert engine.search("zzzxq wqpltk vvv", limit=5) == []


def test_recommend_returns_k(engine):
    seed = engine.search("Blinding Lights", limit=1)[0]
    recs = engine.recommend([seed["row"]], k=10, mode="similar")
    assert len(recs) == 10


def test_no_duplicate_songs(engine):
    seed = engine.search("Summertime Sadness", limit=1)[0]
    recs = engine.recommend([seed["row"]], k=12, mode="similar")
    keys = [f"{_norm_title(r['name'])}||{engine.artist_gid[r['row']]}" for r in recs]
    assert len(keys) == len(set(keys)), "recommendations contain a duplicate version"


def test_artist_cap_for_short_lists(engine):
    # short lists should not repeat a *named* artist (adaptive cap = 1 for k <= 8);
    # "Unknown Artist" is a data placeholder, not a real artist, so it may recur.
    seed = engine.search("Blinding Lights", limit=1)[0]
    recs = engine.recommend([seed["row"]], k=5, mode="similar")
    named = [r["artist"] for r in recs if r["artist"] != "Unknown Artist"]
    assert len(named) == len(set(named)), "short list repeats a named artist"


def test_seed_excluded_from_results(engine):
    seed = engine.search("Blinding Lights", limit=1)[0]
    recs = engine.recommend([seed["row"]], k=10, mode="similar")
    assert all(r["name"].lower() != "blinding lights" for r in recs)


def test_mood_vector_retrieval_runs(engine, mood_model):
    t = mood_model.transform("sad acoustic ballad")
    recs = engine.recommend_by_vector(t["vector"], k=8, target_audio=t["audio"])
    assert len(recs) == 8


def test_artist_albums_returns_albums(engine):
    albums = engine.artist_albums("Justin Bieber")
    assert len(albums) > 0, "expected albums for Justin Bieber"
    assert albums[0]["track_count"] >= 18
