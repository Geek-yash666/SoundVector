import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

ARTIFACTS = os.path.join(os.path.dirname(__file__), "..", "artifacts")
MOOD_PATH = os.path.join(ARTIFACTS, "mood_model.pkl")

_missing = not os.path.exists(os.path.join(ARTIFACTS, "embeddings.npy"))
pytestmark = pytest.mark.skipif(_missing, reason="artifacts not present")


@pytest.fixture(scope="session")
def engine():
    from app import RecommendationEngine
    return RecommendationEngine(ARTIFACTS)


@pytest.fixture(scope="session")
def mood_model():
    from app import MoodToVector
    if not os.path.exists(MOOD_PATH):
        pytest.skip("mood_model.pkl not fitted")
    return MoodToVector.load(MOOD_PATH)
