---
title: SoundVector
emoji: 👀
colorFrom: blue
colorTo: yellow
sdk: gradio
sdk_version: 5.29.0
python_version: '3.12'
app_file: app.py
pinned: false
license: mit
---
# SoundVector

**An explainable, two-stage music recommendation engine over 899K tracks — featuring learned contrastive embeddings, natural-language mood search with Gemini-augmented fallback, live external API enrichment (Deezer & iTunes), Movie Soundtrack & Album Page views, Last.fm discography integration, an AI Playlist Generator, and a sleek Web Dashboard.**

SoundVector recommends music the way production systems do architecturally: a fast **retrieval** stage narrows ~900K tracks to a candidate pool via approximate nearest-neighbor search over learned embeddings, followed by a **ranking** stage that scores and diversifies that pool. On top of that, it features a personalized home page, natural-language mood queries with regional language support, artist & movie album discography exploration, 30s audio previews with a floating player UI, and a Gemini-powered AI Intel panel that provides real factual song & artist insights.

---

## 📸 Interface Preview

![SoundVector Web Dashboard](assets/dashboard_ui.png)

![Song UI](assets/song.png)

---

## 🌟 Key Features

### ⚡ 1. Two-Stage ANN Recommendation Engine

- **899K Track Vector Search**: High-speed Approximate Nearest Neighbor (ANN) retrieval over 899,224 tracks using 256-D contrastive embeddings and HNSW indexing.
- **Multi-Factor Ranking & Diversification**: Re-ranks candidate pools using embedding similarity, audio feature proximity, genre overlap, era decay, and adaptive same-artist caps.
- **4 Distinct Recommendation Modes**:
  - **`Similar`**: Maximum semantic & embedding fidelity.
  - **`Vibe Match`**: Balanced audio feature & genre alignment.
  - **`Popular`**: Weighted towards popular catalog hits.
  - **`Discover`**: High-novelty exploration mode uncovering hidden gems.

### 🎧 2. High-Res Cover Art & 30s Audio Previews

- **Instant Audio Streaming**: Real 30-second audio preview streams powered by Deezer & iTunes integration.
- **Floating Bottom Audio Player**: Persistent, slick media bar at the bottom with play/pause, time scrubber, track details, and cover art thumbnails.
- **1-Click Instant Switching**: Seamlessly click any song preview while another is playing to immediately switch tracks without double clicks.
- **Streaming Micro-Pills**: Compact direct links to open tracks on **Deezer** and **YouTube Music**.

### 💿 3. Movie Soundtrack & Album Discography Views

- **Albums & Soundtracks Search**: Dedicated search dropdown section for movie titles and album releases (*Saaho*, *Animal*, *Starboy*, *Aashiqui 2*, *RRR*, *Kabir Singh*, *Justice*).
- **Standalone Album View Page (`openAlbumPage`)**: Displays official 140px square album poster artwork, movie title, composer info, and **all songs included in that soundtrack** with audio previews.

### 📊 4. Last.fm Global Artist Integration & Full Discographies

- **CORS-Free Backend Photo Proxy (`/api/artist_image`)**: Proxying artist photos through Python backend guarantees HD artist profile photos in search suggestions, hero headers, and similar artist circles.
- **Last.fm Listener & Playcount Stats**: Live global listener counts, total play counts, full bio, top tags, and similar artists.
- **Automatic Discography Expansion**: Seamlessly complements dataset tracks for regional or niche artists (*Thaman S, Anirudh, A.R. Rahman, Pritam*) with 25+ live top hit tracks.

### 🔮 5. Intelligent NLP Vibe & Mood Search

- **Out-of-Vocabulary Resilience**: Eliminates "no results" errors for regional or compound queries like `"telugu gym songs"` or `"sad rainy night"`.
- **100+ Built-in Synonym Mappings**: Built-in coverage for regional languages (*Telugu, Hindi, Tamil, Kannada, Punjabi, Malayalam, K-Pop, J-Pop, Latin*), activities (*gym, coding, roadtrip, yoga*), and emotions.
- **Gemini Intent Projection**: Automatically translates zero-coverage queries into target 8-D audio attributes (*energy, valence, tempo, acousticness*) and matching catalog genres.

### 🪄 6. AI Playlist Generator (`/api/playlist_gen`)

- **Regional & Language Token Awareness**: Automatically detects regional keywords in prompts (*telugu, hindi, punjabi, kpop, spanish, latin*).
- **Authentic Track Blending**: Queries live APIs & local vectors specifically for authentic regional tracks (e.g. *telugu sleep songs recent* returns real Telugu sleep songs).
- **Curated Titles & Emojis**: Dynamically crafts creative playlist names, single-sentence descriptions, and matching emojis (🌙 for sleep, ⚡ for workout, 🎉 for party).

### 🧠 7. AI Track Insights (Gemini-Powered)

- **Artist Trivia**: Replaces generic AI commentary with Gemini-generated factual insights covering production context, chart milestones, musical influences, and sound profile descriptions.
- **Fact-Grounded Verification**: `GroundednessChecker` validates generated statements against 8-D catalog audio metadata to prevent hallucinations.
- **Data-Derived Fallback**: Generates catalog popularity percentiles, tempo classification, genre rarity, and era context directly from dataset metadata when offline.

---

## 📐 Architecture Overview

```
User Query (Track / Artist / Movie Album / Natural-Language Vibe)
         │
         ├─ Track / Artist ─► Fuzzy Catalog Search & ANN Seed ──► 256-D Seed Embedding
         ├─ Album / Movie ──► Live Album Search & Lookup ──────► Album Tracks Page
         └─ Mood Text ──────► MoodToVector (TF-IDF + Ridge) ────► 256-D Query Vector
                               └── (Fallback: Gemini NLP interpreter if 0 coverage)
         │
    1. RETRIEVAL  ── HNSW ANN over 899K × 256 embeddings ──► ~2,000 candidates (adaptive)
         │
    2. RANKING    ── embed + audio + genre + artist + popularity + era
                     ──► Canonical Dedup ──► Artist Caps ──► Redundancy Gate ──► Top-K
         │
    3. ENRICHMENT ── Deezer + iTunes + Last.fm Live Proxy
                     ──► High-Res Cover Art ──► 30s Audio Stream ──► Streaming Links
         │
    4. AI INTEL   ── Seed Track + Top Candidates ──► Gemini AI Insights / Factual Claims
                     ──► GroundednessChecker verifies factual claims
         │
    Output: Personalized Home / Search Recs + Floating Player + Album Page + AI Intel Panel
```

---

## 🚀 Getting Started

### Prerequisites & Installation

```bash
pip install -r requirements.txt
```

### Running the Web Dashboard (Recommended)

Launch the self-contained Web UI server:

```bash
python3 backend/app.py --web
```

Open your browser at **`http://localhost:8000`** to experience SoundVector!

### Running in Terminal Mode

You can also run SoundVector directly in your terminal:

```bash
python3 backend/app.py                        # Interactive Terminal CLI mode
python3 backend/app.py "telugu gym songs"     # One-shot natural language query
python3 backend/app.py --user Yash            # Load CLI with taste profile 'Yash'
```

---

## 🔑 Environment Setup (Optional)

Configure your API keys and dataset/backend references in `.env`:

```env
GEMINI_API_KEY=your_gemini_api_key_here
LASTFM_API_KEY=your_lastfm_api_key_here
SOUNDVECTOR_API_BASE=backend_url_here(if deployed)
HF_ARTIFACTS_DATASET=artifacts_url(optional)
```

*Note: If no API key is provided, SoundVector automatically uses data-derived catalog insights, public Last.fm integration, and built-in synonym expansion at zero API cost.*

---

## 🧪 Testing & Verification

Run automated test suites and reliability evaluations:

```bash
python3 -m pytest tests/ -q              # Run pytest suite (16 tests pass)
python3 src/evaluate.py                  # Generate reliability report
```

### Reliability Summary (10 Seed Songs)

| Metric                               | Measured         | Target       |
| :----------------------------------- | :--------------- | :----------- |
| **Same-Artist Recall@50**      | **1.000**  | > 0.80       |
| **Intra-List Diversity (ILD)** | **0.548**  | 0.15 – 0.90 |
| **Genre Fidelity**             | **0.940**  | > 0.60       |
| **NL Query Accuracy**          | **0.800**  | > 0.80       |
| **RAG Groundedness**           | **1.000**  | > 0.90       |
| **Median Latency**             | **4.6 ms** | < 500 ms     |

---

## 📁 Repository Structure

```text
backend/
  app.py                         Self-contained backend app (Engine, NLP, AI Intel, Live API Proxy, FastAPI)
src/
  soundvector_train_emb.ipynb   Full training notebook (PyTorch contrastive training, HNSW index builder)
  ab_test.py                     Blind A/B taste test evaluator
  evaluate.py                   Reliability metrics evaluator
  api/                           Vercel serverless proxy functions
  static/                        Web dashboard frontend assets
    index.html                  Glassmorphic HTML layout with floating player & album view
    style.css                   Vanilla CSS styling with dark mode, animations & genre badges
    script.js                   Interactive frontend logic, audio player, album views & API integrations
  vercel.json                    Vercel deployment & routing configuration
profiles/                        User taste profiles & interaction history
artifacts/                       Pre-trained embeddings (899K × 256), HNSW index & MoodToVector models
tests/                           Pytest unit test suite (16 test cases)
```

---

## 🚢 Deployment & Cache Management

SoundVector uses a **multi-layer cache-busting system** to ensure every user gets the correct UI after a new build is pushed, with zero manual browser cache clearing required.

### How It Works

| Layer | Mechanism | Effect |
|---|---|---|
| **HTML** | `Cache-Control: no-store` on `index.html` | Browser always fetches a fresh HTML shell |
| **JS / CSS** | Version query string (`?v=2.0`) in `<script>` and `<link>` tags | Browser fetches new assets when version changes |
| **localStorage** | `BUILD_VERSION` constant checked on every page load | Stale session state cleared automatically |
| **sessionStorage** | Cleared entirely on version mismatch | No stale enrichment or search state persists |

### Pushing a New Build

When you update `script.js`, `style.css`, or any backend logic and need to force a full refresh for all users:

**Step 1 — Bump the build version in `script.js`:**
```js
// src/static/script.js, line 6
const BUILD_VERSION = '2.1';  // ← increment this
```

**Step 2 — Bump the asset version strings in `index.html`:**
```html
<!-- src/static/index.html -->
<link rel="stylesheet" href="style.css?v=2.1">   <!-- ← match BUILD_VERSION -->
<script src="script.js?v=2.1"></script>            <!-- ← match BUILD_VERSION -->
```

**Step 3 — Restart the server:**
```bash
python3 backend/app.py --web
```

### What Gets Cleared vs. Preserved on Upgrade

| Data | Cleared? | Reason |
|---|---|---|
| Stale enrichment / search cache in browser | ✅ Yes | sessionStorage cleared |
| Old UI state, cached panels | ✅ Yes | sessionStorage cleared |
| All `soundvector_*` localStorage keys | ✅ Yes | Version mismatch wipe |
| **User login** (`soundvector_user`) | ❌ Preserved | Re-persisted after wipe |

> [!NOTE]
> The version check is an **IIFE** that runs synchronously before any app code, so there is zero risk of stale state leaking into any module or component.

---

## 📄 License & Credits

Built as part of the **AI 110 Module 3 Music Recommender Project**. Developed by **Yash & Roop**.

