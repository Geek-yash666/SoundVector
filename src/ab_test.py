#!/usr/bin/env python3
"""
Blind A/B taste test: old recommender (src/old) vs new two-stage engine.

For each seed song both systems produce 5 recommendations, shown as unlabeled
List 1 / List 2 (random order per round). You vote in the terminal; at the end
the mapping is revealed, the tally printed, and results saved to
eval/ab_results.json + a markdown table (human-eval evidence for the README).

Usage:
    python3 src/ab_test.py                       # default seed set
    python3 src/ab_test.py "starboy" "believer"  # custom seeds
"""

import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import RecommendationEngine, SCORING_PRESETS  # noqa: E402

DEFAULT_SEEDS = [
    "Treat You Better", "Summertime Sadness", "After Hours", "Starboy",
    "Shape of You", "Believer", "Levitating", "drivers license",
]


def new_recs(engine, query, k=5):
    hits = engine.search(query, limit=1)
    if not hits:
        return None, []
    seed = hits[0]
    recs = engine.recommend([seed["row"]], k=k, mode="similar")
    return f"{seed['name']} — {seed['artist']}", [f"{r['name']} — {r['artist']}" for r in recs]


def old_recs(old, query, k=5):
    matches = old.fuzzy_search_songs(query, limit=5)
    if not matches:
        return None, []
    seed = matches[0]
    recs = old.recommend_from_seeds(
        [seed["catalog_idx"]], k=k, max_per_artist=1, max_per_other_artist=2,
        weights=type(old).SCORING_PRESETS["similar"])
    return f"{seed['name']} — {seed['artist']}", [f"{r['name']} — {r['artist']}" for r in recs]


def main():
    seeds = sys.argv[1:] or DEFAULT_SEEDS
    print("Loading NEW engine...", flush=True)
    engine = RecommendationEngine("artifacts_colab")
    print("Loading OLD engine (parses full parquet, ~1-2 min)...", flush=True)
    from old.recommender import ProductionRecommender
    old = ProductionRecommender()
    print("Ready.\n")

    rounds, votes = [], {"new": 0, "old": 0, "tie": 0}
    for seed_q in seeds:
        seed_new, list_new = new_recs(engine, seed_q)
        seed_old, list_old = old_recs(old, seed_q)
        if not list_new or not list_old:
            print(f"  (skipping '{seed_q}' — not found in both systems)")
            continue

        flip = random.random() < 0.5
        l1, l2 = (list_old, list_new) if flip else (list_new, list_old)
        print("=" * 62)
        print(f"SEED: {seed_new}")
        print("=" * 62)
        print("List 1:")
        for i, t in enumerate(l1, 1):
            print(f"   {i}. {t}")
        print("List 2:")
        for i, t in enumerate(l2, 1):
            print(f"   {i}. {t}")

        while True:
            v = input("Your pick [1/2/t=tie/s=skip/q=quit]: ").strip().lower()
            if v in ("1", "2", "t", "s", "q"):
                break
        if v == "q":
            break
        if v == "s":
            continue
        winner = "tie" if v == "t" else (
            ("old" if v == "1" else "new") if flip else ("new" if v == "1" else "old"))
        votes[winner] += 1
        rounds.append({"seed": seed_new, "vote": winner,
                       "new_list": list_new, "old_list": list_old})
        print(f"  -> recorded ({'revealed at end'})\n")

    print("\n" + "=" * 62)
    print(f"RESULT: new {votes['new']} · old {votes['old']} · ties {votes['tie']}")
    print("=" * 62)
    print("| Seed | Winner |")
    print("|---|---|")
    for r in rounds:
        print(f"| {r['seed']} | {r['vote']} |")

    os.makedirs("eval", exist_ok=True)
    out = {"ts": time.time(), "votes": votes, "rounds": rounds}
    with open("eval/ab_results.json", "w") as f:
        json.dump(out, f, indent=2)
    print("\nSaved eval/ab_results.json")


if __name__ == "__main__":
    main()
