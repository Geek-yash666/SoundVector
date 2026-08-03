#!/usr/bin/env python3
"""
SoundVector reliability & evaluation harness.

Measures the metrics req.md asks for and writes machine- and human-readable
reports to eval/reliability.json and eval/reliability.md:

  same_artist_recall@50   retrieval finds another track by the seed artist
  intra_list_diversity    1 - mean pairwise cosine of the recommended embeddings
  genre_fidelity          fraction of recs sharing >=1 base genre with the seed
  nl_query_accuracy       MoodToVector queries land in the expected audio region
  rag_groundedness        DJ commentary claims verified against retrieved facts
  latency_ms              end-to-end recommend() latency

Run:
    python3 src/evaluate.py
"""

import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import (  # noqa: E402
    RecommendationEngine, BASE_GENRE_MAP, MoodToVector,
    DEFAULT_MOOD_MODEL_PATH as DEFAULT_PATH, RAGDJ, GroundednessChecker
)

SEED_SONGS = ["Blinding Lights", "Summertime Sadness", "Treat You Better", "Believer",
              "Shape of You", "bad guy", "Levitating", "drivers license", "Circles", "Dynamite"]

# NL query -> expected direction on audio features (feature, comparator, threshold)
NL_CASES = [
    ("sad acoustic ballad", [("valence", "<", 0.5), ("acousticness", ">", 0.4)]),
    ("high energy workout", [("energy", ">", 0.6)]),
    ("chill lo-fi study", [("energy", "<", 0.5), ("acousticness", ">", 0.4)]),
    ("happy upbeat dance party", [("valence", ">", 0.5), ("danceability", ">", 0.5)]),
    ("dark moody late night", [("valence", "<", 0.5)]),
]


def base_genres(engine, row):
    return engine._base_genres(engine._genre_ids(row))


def eval_retrieval(engine, seeds, k=15):
    ild, fidelity, recall, latencies = [], [], [], []
    for s in seeds:
        hits = engine.search(s, limit=1)
        if not hits:
            continue
        row = hits[0]["row"]
        t0 = time.time()
        recs = engine.recommend([row], k=k, mode="similar")
        latencies.append((time.time() - t0) * 1000)
        if len(recs) < 2:
            continue
        vecs = np.stack([np.asarray(engine.embeddings[r["row"]], np.float32) for r in recs])
        vecs /= (np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-9)
        sims = vecs @ vecs.T
        iu = np.triu_indices(len(recs), k=1)
        ild.append(1.0 - float(sims[iu].mean()))
        sg = base_genres(engine, row)
        fidelity.append(np.mean([1.0 if (sg & base_genres(engine, r["row"])) else 0.0 for r in recs]))
        # same-artist recall: is another track by the seed artist retrievable in top-50?
        ann = engine.recommend([row], k=50, mode="similar", max_per_artist=50)
        sa = int(engine.artist_gid[row])
        recall.append(1.0 if any(int(engine.artist_gid[r["row"]]) == sa for r in ann) else 0.0)
    return (float(np.mean(recall)), float(np.mean(ild)),
            float(np.mean(fidelity)), float(np.median(latencies)))


def eval_nl(engine, mood_model, k=30):
    rows = []
    for query, checks in NL_CASES:
        t = mood_model.transform(query)
        tg = {BASE_GENRE_MAP.get(tok, tok) for tok in t["matched_tokens"]}
        recs = engine.recommend_by_vector(t["vector"], k=k, target_base_genres=tg,
                                          target_audio=t["audio"])
        feats = {"energy": engine._dfeat["energy"], "valence": engine._dfeat["valence"],
                 "danceability": engine._dfeat["danceability"],
                 "acousticness": engine._dfeat["acousticness"]}
        means = {f: float(np.mean([engine.audio[r["row"], i] for r in recs])) for f, i in feats.items()}
        passed = []
        for feat, cmp, thr in checks:
            v = means[feat]
            passed.append(v < thr if cmp == "<" else v > thr)
        rows.append({"query": query, "means": {k2: round(v, 2) for k2, v in means.items()},
                     "checks": [f"{f}{c}{t2}" for f, c, t2 in checks], "pass": all(passed)})
    acc = float(np.mean([r["pass"] for r in rows]))
    return acc, rows


def eval_groundedness(engine, dj, checker, seeds, k=6):
    rates, details = [], []
    for s in seeds[:6]:
        hits = engine.search(s, limit=1)
        if not hits:
            continue
        row = hits[0]["row"]
        recs = engine.recommend([row], k=k, mode="similar")
        facts = engine.track_card(row)
        cards = [engine.track_card(r["row"]) for r in recs]
        blurb = dj.narrate(f"{facts['name']} — {facts['artist']}", facts, cards)
        g = checker.check(blurb, facts, cards)
        rates.append(g["groundedness"])
        details.append({"seed": f"{facts['name']} — {facts['artist']}",
                        "groundedness": g["groundedness"],
                        "claims": g["total_claims"], "violations": g["violations"]})
    return float(np.mean(rates)) if rates else 1.0, details


def main():
    print("Loading engine + models...", flush=True)
    engine = RecommendationEngine("artifacts_colab")
    mood_model = MoodToVector.load(DEFAULT_PATH)
    dj = RAGDJ()
    checker = GroundednessChecker()

    print("1/3 retrieval metrics...", flush=True)
    recall, ild, fidelity, latency = eval_retrieval(engine, SEED_SONGS)
    print("2/3 NL-query assertions...", flush=True)
    nl_acc, nl_rows = eval_nl(engine, mood_model)
    print("3/3 RAG groundedness...", flush=True)
    ground, ground_rows = eval_groundedness(engine, dj, checker, SEED_SONGS)

    report = {
        "same_artist_recall@50": round(recall, 3),
        "intra_list_diversity": round(ild, 3),
        "genre_fidelity": round(fidelity, 3),
        "nl_query_accuracy": round(nl_acc, 3),
        "rag_groundedness": round(ground, 3),
        "median_latency_ms": round(latency, 2),
        "dj_backend": dj.backend,
        "nl_cases": nl_rows,
        "groundedness_cases": ground_rows,
    }
    os.makedirs("eval", exist_ok=True)
    with open("eval/reliability.json", "w") as f:
        json.dump(report, f, indent=2)

    lines = ["# SoundVector Reliability Report", "",
             f"_DJ backend: `{dj.backend}` · seeds: {len(SEED_SONGS)}_", "",
             "| Metric | Value | Target |", "|---|---|---|",
             f"| same-artist recall@50 | {recall:.3f} | > 0.80 |",
             f"| intra-list diversity | {ild:.3f} | 0.15 - 0.90 |",
             f"| genre fidelity | {fidelity:.3f} | > 0.60 |",
             f"| NL-query accuracy | {nl_acc:.3f} | > 0.80 |",
             f"| RAG groundedness | {ground:.3f} | > 0.90 |",
             f"| median latency | {latency:.1f} ms | < 500 ms |", "",
             "## Natural-language query assertions", "",
             "| Query | Retrieved means | Expected | Pass |", "|---|---|---|---|"]
    for r in nl_rows:
        m = ", ".join(f"{k}={v}" for k, v in r["means"].items())
        lines.append(f"| {r['query']} | {m} | {', '.join(r['checks'])} | {'✅' if r['pass'] else '❌'} |")
    lines += ["", "## RAG groundedness by seed", "", "| Seed | Groundedness | Claims |", "|---|---|---|"]
    for r in ground_rows:
        lines.append(f"| {r['seed']} | {r['groundedness']:.0%} | {r['claims']} |")
    with open("eval/reliability.md", "w") as f:
        f.write("\n".join(lines) + "\n")

    print("\n".join(lines[3:12]))
    print("\nSaved eval/reliability.json + eval/reliability.md")


if __name__ == "__main__":
    main()
