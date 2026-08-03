#!/usr/bin/env python3
"""
SoundVector MoodToVector NLP Model (TF-IDF + Ridge Regression)
"""

import pickle
import numpy as np

try:
    from .config import DEFAULT_MOOD_MODEL_PATH, SYNONYMS
except ImportError:
    from config import DEFAULT_MOOD_MODEL_PATH, SYNONYMS



class MoodToVector:
    def __init__(self, tfidf, ridge_embed, ridge_audio, vocab_tokens):
        self.tfidf = tfidf
        self.ridge_embed = ridge_embed
        self.ridge_audio = ridge_audio
        self.vocab_tokens = vocab_tokens

    @classmethod
    def load(cls, path: str = DEFAULT_MOOD_MODEL_PATH):
        with open(path, "rb") as f:
            d = pickle.load(f)
        return cls(d["tfidf"], d["ridge_embed"], d["ridge_audio"], d["vocab_tokens"])

    def _expand(self, text: str) -> str:
        toks = text.lower().split()
        extra = [SYNONYMS[t] for t in toks if t in SYNONYMS]
        return " ".join(toks + extra)

    def transform(self, text: str) -> dict:
        from scipy.sparse import hstack, csr_matrix
        expanded = self._expand(text)
        X = self.tfidf.transform([expanded])
        Xi = hstack([X, csr_matrix(np.ones((1, 1)))]).tocsr()
        vec = self.ridge_embed.predict(Xi)[0].astype(np.float32)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        audio = np.clip(self.ridge_audio.predict(Xi)[0].astype(np.float32), 0, 1)

        # Smart audio attribute overrides based on explicit query intent
        low_text = text.lower()
        if any(w in low_text for w in ["sad", "cry", "melancholy", "heartbreak", "breakup", "somber"]):
            audio[1] = min(audio[1], 0.35)  # valence
            audio[0] = min(audio[0], 0.45)  # energy
        elif any(w in low_text for w in ["happy", "upbeat", "cheerful", "party", "celebration"]):
            audio[1] = max(audio[1], 0.70)  # valence
            audio[0] = max(audio[0], 0.65)  # energy

        if any(w in low_text for w in ["gym", "workout", "hype", "rage", "phonk", "pumping", "hardstyle"]):
            audio[0] = max(audio[0], 0.80)  # energy
            audio[2] = max(audio[2], 0.65)  # danceability
            audio[7] = max(audio[7], 0.50)  # tempo

        if any(w in low_text for w in ["chill", "relax", "lo-fi", "lofi", "sleep", "meditation", "unwind", "calm"]):
            audio[0] = min(audio[0], 0.38)  # energy
            audio[3] = max(audio[3], 0.55)  # acousticness

        matched = [t for t in expanded.split() if t in self.vocab_tokens]
        return {"vector": vec, "audio": audio, "matched_tokens": matched, "coverage": X.nnz > 0}
