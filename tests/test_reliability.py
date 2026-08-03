"""Reliability metrics as assertions (req.md reliability system).

Computes the same metrics as src/evaluate.py on a small seed set and asserts
each stays within an acceptable band. Also directly checks the RAG groundedness
guardrail catches an injected false claim.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from evaluate import eval_groundedness, eval_nl, eval_retrieval  # noqa: E402
from app import GroundednessChecker, RAGDJ  # noqa: E402

SEEDS = ["Blinding Lights", "Summertime Sadness", "Treat You Better", "Believer", "Circles"]


@pytest.fixture(scope="module")
def retrieval(engine):
    recall, ild, fidelity, latency = eval_retrieval(engine, SEEDS, k=12)
    return {"recall": recall, "ild": ild, "fidelity": fidelity, "latency": latency}


def test_same_artist_recall(retrieval):
    assert retrieval["recall"] >= 0.8


def test_genre_fidelity(retrieval):
    assert retrieval["fidelity"] >= 0.6


def test_intra_list_diversity_band(retrieval):
    # not all identical (>0.15) and not incoherent noise (<0.95)
    assert 0.15 <= retrieval["ild"] <= 0.95


def test_latency_is_fast(retrieval):
    assert retrieval["latency"] < 500


def test_nl_query_accuracy(engine, mood_model):
    acc, _ = eval_nl(engine, mood_model, k=30)
    assert acc >= 0.6  # directional: mood queries land in the right audio region


def test_rag_groundedness_high(engine):
    dj, checker = RAGDJ(), GroundednessChecker()
    ground, _ = eval_groundedness(engine, dj, checker, SEEDS, k=6)
    assert ground >= 0.9


def test_groundedness_catches_false_claim():
    facts = {"name": "After Hours", "artist": "The Weeknd", "genres": ["pop", "r&b"],
             "energy": 0.78, "valence": 0.23, "danceability": 0.66,
             "acousticness": 0.09, "tempo_bpm": 108}
    recs = [{"name": "The Hills", "artist": "The Weeknd", "genres": ["r&b"],
             "energy": 0.6, "valence": 0.14, "danceability": 0.55,
             "acousticness": 0.06, "tempo_bpm": 113}]
    checker = GroundednessChecker()
    clean = "A moody, intense r&b cut. Try \"The Hills\" by The Weeknd."
    lie = clean + " It's a happy acoustic song by Taylor Swift."
    assert checker.check(clean, facts, recs)["groundedness"] == 1.0
    assert checker.check(lie, facts, recs)["groundedness"] < 1.0
