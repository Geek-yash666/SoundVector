#!/usr/bin/env python3
"""
SoundVector Configuration & Global Constants
"""

import os
import sys

GPU_USAGE = int(os.environ.get("GPU_USAGE", "1"))
if GPU_USAGE:
    try:
        import spaces
        HAS_SPACES = True
    except ImportError:
        HAS_SPACES = False
else:
    HAS_SPACES = False

N_AUDIO_DIMS = 8

class C:
    B = "\033[1m"
    D = "\033[2m"
    R = "\033[0m"
    CY = "\033[36m"
    GR = "\033[32m"
    YE = "\033[33m"
    RE = "\033[31m"
    WH = "\033[37m"


def s(t: str, *st) -> str:
    return f"{''.join(st)}{t}{C.R}"


SCORING_PRESETS = {
    "similar":  {"embed": 0.30, "audio": 0.25, "genre": 0.25, "artist": 0.05, "popularity": 0.15, "era": 0.00},
    "vibe":     {"embed": 0.45, "audio": 0.35, "genre": 0.20, "artist": 0.00, "popularity": 0.00, "era": 0.00},
    "popular":  {"embed": 0.25, "audio": 0.10, "genre": 0.20, "artist": 0.00, "popularity": 0.45, "era": 0.00},
    "discover": {"embed": 0.25, "audio": 0.05, "genre": 0.30, "artist": 0.00, "popularity": 0.15, "era": 0.25},
}

BASE_GENRE_MAP = {
    'pop': 'pop', 'dance pop': 'pop', 'canadian pop': 'pop', 'viral pop': 'pop',
    'electropop': 'electro', 'art pop': 'pop', 'indie pop': 'pop', 'synth-pop': 'electro',
    'k-pop': 'pop', 'europop': 'pop', 'pop rock': 'pop rock', 'pop rap': 'pop',
    'chamber pop': 'pop', 'dream pop': 'pop', 'power pop': 'pop', 'neo mellow': 'pop',
    'rock': 'rock', 'alternative rock': 'rock', 'indie rock': 'rock', 'classic rock': 'rock',
    'garage rock': 'rock', 'punk rock': 'rock', 'modern rock': 'rock', 'permanent wave': 'rock',
    'new wave': 'rock', 'hip hop': 'hip hop', 'rap': 'hip hop', 'trap': 'hip hop',
    'conscious hip hop': 'hip hop', 'r&b': 'r&b', 'contemporary r&b': 'r&b',
    'urban contemporary': 'r&b', 'edm': 'edm', 'house': 'edm', 'tech house': 'edm',
    'deep house': 'edm', 'tropical house': 'edm', 'electronic': 'edm', 'electro house': 'edm',
    'country': 'country', 'classic country': 'country', 'country rock': 'country',
    'jazz': 'jazz', 'soul': 'soul', 'funk': 'soul', 'metal': 'metal', 'heavy metal': 'metal',
    'latin': 'latin', 'reggaeton': 'latin', 'urbano latino': 'latin', 'musica mexicana': 'latin',
    'norteno': 'latin', 'ranchera': 'latin', 'banda': 'latin', 'trap latino': 'latin',
    'latin pop': 'latin', 'classical': 'classical', 'lo-fi': 'lo-fi', 'lofi': 'lo-fi',
    'filmi': 'filmi', 'bollywood': 'filmi', 'modern bollywood': 'filmi', 'desi pop': 'filmi',
    'punjabi pop': 'filmi', 'indian pop': 'filmi', 'indian classical': 'indian classical',
    'afrobeats': 'afrobeats', 'afropop': 'afrobeats', 'j-pop': 'j-pop', 'anime': 'anime',
}

SYNONYMS = {
    # Activity-based
    "gym": "workout edm dance energy hip hop trap phonk hardstyle",
    "workout": "workout edm dance energy hip hop phonk",
    "running": "workout edm run dance energy",
    "exercise": "workout edm dance energy",
    "jogging": "workout edm run dance",
    "lifting": "workout edm trap hip hop energy hardstyle",
    "yoga": "ambient chill acoustic meditation",
    "meditation": "ambient lo-fi chill acoustic",
    "study": "lo-fi study focus beats ambient chillhop",
    "studying": "lo-fi study focus ambient",
    "focus": "focus beats lo-fi study ambient instrumental",
    "homework": "lo-fi study focus beats",
    "coding": "lo-fi focus beats electronic ambient synthwave",
    "reading": "ambient acoustic lo-fi chill",
    "cooking": "jazz soul funk pop acoustic",
    "cleaning": "pop dance edm energy",
    "commute": "pop rock indie synthwave",
    "roadtrip": "rock pop indie classic rock driving",
    # Sleep/Relax
    "sleep": "sleep ambient lo-fi acoustic chill",
    "sleepy": "sleep ambient acoustic",
    "relax": "chill ambient acoustic lo-fi",
    "relaxing": "chill ambient acoustic",
    "chill": "chill lo-fi chillhop ambient bedroom pop",
    "unwind": "chill ambient acoustic lo-fi",
    "spa": "ambient acoustic chill",
    # Party/Social
    "party": "dance pop edm party trap house",
    "dancing": "dance pop edm house",
    "club": "edm house dance electronic techno",
    "pregame": "hip hop trap edm dance",
    "celebration": "pop dance edm happy",
    "wedding": "pop soul r&b dance romantic",
    # Emotions
    "sad": "sad lo-fi acoustic melancholy heartbreak moody",
    "cry": "sad acoustic melancholy heartbreak",
    "heartbreak": "sad acoustic r&b melancholy breakup",
    "breakup": "sad acoustic r&b pop melancholy",
    "lonely": "sad lo-fi acoustic ambient moody",
    "happy": "happy pop dance upbeat feel-good",
    "upbeat": "happy dance pop energy",
    "energetic": "edm dance workout energy hype",
    "hype": "edm trap hip hop energy dance rage",
    "rage": "trap phonk metal energy hype",
    "angry": "metal rock hard rock aggressive",
    "aggressive": "metal rock trap hard rock",
    "calm": "ambient acoustic chill lo-fi",
    "romantic": "r&b soul love pop romantic acoustic",
    "love": "r&b soul love pop romantic",
    "nostalgic": "classic rock pop soul retro 80s synthwave",
    "dark": "dark trap dark r&b electronic phonk",
    "moody": "dark r&b sad lo-fi ambient",
    "dreamy": "dream pop chillwave ambient shoegaze",
    "euphoric": "edm house dance trance synthwave",
    "melancholy": "sad lo-fi acoustic ambient moody",
    "confident": "hip hop rap pop energy hype",
    "motivation": "hip hop rap pop energy workout gym",
    "inspirational": "pop rock indie acoustic",
    # Weather/Time
    "rainy": "lo-fi acoustic ambient chill sad",
    "rain": "lo-fi ambient acoustic sad",
    "night": "dark lo-fi ambient r&b midnight",
    "midnight": "dark lo-fi r&b ambient",
    "morning": "acoustic happy folk pop sunrise",
    "sunrise": "ambient acoustic chill folk",
    "sunset": "chill lo-fi ambient synthwave",
    "summer": "tropical house dance pop reggaeton",
    "winter": "acoustic ambient lo-fi folk",
    "spring": "indie pop acoustic folk",
    "autumn": "folk acoustic indie lo-fi",
    # Regional / Language — maps to nearest available genres
    "telugu": "filmi desi pop indian pop tollywood telugu pop",
    "hindi": "modern bollywood filmi desi pop ghazal",
    "bollywood": "modern bollywood filmi desi pop",
    "tamil": "filmi indian pop desi pop kollywood",
    "kannada": "filmi indian pop desi pop",
    "malayalam": "filmi indian pop desi pop",
    "punjabi": "punjabi pop bhangra desi pop filmi",
    "desi": "desi pop filmi indian pop",
    "indian": "indian pop filmi desi pop",
    "korean": "k-pop pop dance",
    "kpop": "k-pop pop dance",
    "japanese": "j-pop anime pop",
    "anime": "anime j-pop pop",
    "latin": "latin reggaeton urbano latino",
    "spanish": "latin pop reggaeton urbano latino",
    "african": "afrobeats afropop amapiano",
    "afro": "afrobeats afropop amapiano",
    # Genre shortcuts & subgenres
    "phonk": "phonk trap edm workout energy rage",
    "synthwave": "synthwave electronic retro 80s dark",
    "lofi": "lo-fi chillhop ambient beats study",
    "lo-fi": "lo-fi chillhop ambient beats study",
    "hiphop": "hip hop rap trap",
    "rnb": "r&b contemporary r&b soul",
    "rock": "rock alternative rock indie rock",
    "metal": "metal heavy metal hard rock",
    "jazz": "jazz vocal jazz soul",
    "classical": "classical baroque",
    "country": "country classic country",
    "electronic": "electronic edm house techno",
    "folk": "folk acoustic singer-songwriter",
    "blues": "blues soul jazz",
    "reggae": "reggae dancehall",
    "punk": "punk rock pop punk",
    # Tempo/Style
    "fast": "edm dance electronic energy",
    "slow": "acoustic ambient lo-fi chill",
    "bass": "edm trap electronic bass",
    "beats": "lo-fi hip hop electronic beats",
    "songs": "",
    "music": "",
    "playlist": "",
    "tracks": "",
    "vibes": "chill lo-fi ambient",
    "drive": "synthwave pop rock indie driving",
    "driving": "synthwave rock pop energy",
}

FEATURE_TERMS = {
    "energetic": ("energy", ">=", 0.60), "high-energy": ("energy", ">=", 0.60),
    "driving": ("energy", ">=", 0.60), "intense": ("energy", ">=", 0.60),
    "pumping": ("energy", ">=", 0.60), "explosive": ("energy", ">=", 0.60),
    "mellow": ("energy", "<=", 0.45), "laid-back": ("energy", "<=", 0.45),
    "calm": ("energy", "<=", 0.45), "gentle": ("energy", "<=", 0.45),
    "soft": ("energy", "<=", 0.45), "relaxed": ("energy", "<=", 0.45),
    "happy": ("valence", ">=", 0.55), "upbeat": ("valence", ">=", 0.55),
    "bright": ("valence", ">=", 0.55), "cheerful": ("valence", ">=", 0.55),
    "joyful": ("valence", ">=", 0.55), "uplifting": ("valence", ">=", 0.55),
    "feel-good": ("valence", ">=", 0.55),
    "sad": ("valence", "<=", 0.45), "melancholy": ("valence", "<=", 0.45),
    "melancholic": ("valence", "<=", 0.45), "moody": ("valence", "<=", 0.45),
    "somber": ("valence", "<=", 0.45), "brooding": ("valence", "<=", 0.45),
    "wistful": ("valence", "<=", 0.45), "downbeat": ("valence", "<=", 0.45),
    "danceable": ("danceability", ">=", 0.60), "groovy": ("danceability", ">=", 0.60),
    "acoustic": ("acousticness", ">=", 0.50), "stripped-back": ("acousticness", ">=", 0.50),
    "unplugged": ("acousticness", ">=", 0.50),
    "fast": ("tempo_bpm", ">=", 120), "uptempo": ("tempo_bpm", ">=", 120),
    "slow": ("tempo_bpm", "<=", 100), "downtempo": ("tempo_bpm", "<=", 100),
}

DEFAULT_MOOD_MODEL_PATH = "artifacts/mood_model.pkl"
LONG_TERM_DECAY = 0.9
SHORT_TERM_DECAY = 0.6


def load_env(path: str = ".env"):
    if os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def resolve_artifacts_dir(path: str) -> str:
    resolved = path
    if not (os.path.isabs(path) or os.path.exists(path)):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        candidate = os.path.normpath(os.path.join(script_dir, "..", path))
        resolved = candidate if os.path.exists(candidate) else path

    index_file = os.path.join(resolved, "index.bin")
    if not os.path.exists(index_file):
        hf_dataset = os.environ.get("HF_ARTIFACTS_DATASET")
        if hf_dataset:
            print(f"  📥 Artifacts not found locally. Downloading from HF Dataset '{hf_dataset}'...")
            try:
                from huggingface_hub import snapshot_download
                os.makedirs(resolved, exist_ok=True)
                snapshot_download(repo_id=hf_dataset, repo_type="dataset", local_dir=resolved)
                print("  ✓ Download complete!")
            except Exception as exc:
                print(f"  ⚠️ Could not download artifacts from HF Dataset: {exc}")
    return resolved
