# SoundVector

Music discovery that learns from the songs you save and listen to. SoundVector combines the supplied trained recommendation model with catalog search, personalized Home recommendations, Apple Music playlists, artist and album browsing, a saved library, mood mixes, and optional Gemini song insights.

## Run locally

The existing checkout is at `/Users/roop/Downloads/SoundVector`. Run commands from the project root so the app can find `.env` and the trained artifacts.

### 1. Install dependencies

Python 3.13 is verified with this checkout. Use a virtual environment for a fresh installation:

```bash
cd /path/to/SoundVector
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

On Windows, activate with `.venv\Scripts\activate` instead. Node.js is needed only for the client tests; the web app has no npm install or frontend build step. GPU hardware is not required to serve the supplied model.

### 2. Configure optional services

Create a local configuration file only if one does not already exist:

```bash
if [ ! -f .env ]; then cp .env.example .env; fi
```

Edit `.env` using the settings below. The core local recommendation model does **not** require an API key. It does require the trained files in `artifacts/`. Live catalog results, artwork, playlists, and previews need an internet connection.

### 3. Start the app

```bash
python backend/app.py --web --port 8000
```

Wait for the engine initialization and the server's startup message. Open **[http://localhost:8000/#/home](http://localhost:8000/#/home)**. The same Python server serves both the UI and API; no second frontend server is needed.

API documentation is available at [http://localhost:8000/docs](http://localhost:8000/docs). Keep the terminal running while testing. Press **Ctrl+C** to stop it. Restart the command after changing Python files or `.env`; reload the browser after changing UI files.

To use another port:

```bash
python backend/app.py --web --port 8001
```

`PORT`, if set in the process environment or `.env`, overrides `--port`. The current launcher binds to `0.0.0.0`, so it can also listen on other network interfaces; the URL above uses your own computer.

## API keys and configuration

| Setting | Required? | What it enables |
| --- | --- | --- |
| `GEMINI_API_KEY` | Optional | Gemini song insights with searched sources. Without it, the UI reports that AI insights are not configured and can show available catalog notes. |
| `LASTFM_API_KEY` | Optional | Last.fm similar-track/artist evidence and metadata enrichment. Without it, recommendations still use the local model and available catalog evidence. |
| `APPLE_MUSIC_STOREFRONT` | Optional; defaults to `us` | Two-letter Apple catalog storefront, for example `us` or `in`. It selects catalog availability; it does not set or infer your listening language. |
| `HF_ARTIFACTS_DATASET` | Only for downloading missing artifacts | Hugging Face dataset ID such as `owner/soundvector-artifacts`. If `artifacts/index.bin` is absent, startup attempts to download this dataset into `artifacts/`. |
| `HF_TOKEN` | Only if the artifact dataset requires access | A Hugging Face token with read access to that dataset. It is used by `huggingface_hub`; it is unnecessary when the artifacts are already local. |
| `SOUNDVECTOR_CACHE_DIR` | Optional | Directory for the persistent catalog metadata cache. Defaults to the project's `.cache/` directory. |
| `PORT` | Optional | Server port; defaults to `8000`. Overrides the CLI `--port` value. |

Get a Gemini key from [Google AI Studio](https://aistudio.google.com/apikey); see [Google's API key documentation](https://ai.google.dev/gemini-api/docs/api-key). The configured model is `gemini-3.1-flash-lite` in `backend/rag_dj.py`. Valid credentials, model access, and available quota are needed for live insights. An HTTP 429 response means the provider has rejected the request for quota or rate limits; the app reports this instead of presenting catalog notes as Gemini facts.

For Last.fm, sign in and [create an API account](https://www.last.fm/api/account/create). This app uses the **API key**, not the shared secret or a user session token.

For restricted Hugging Face artifacts, see [user access tokens](https://huggingface.co/docs/hub/security-tokens). The dataset must contain the matching runtime files listed below at its root. Setting a dataset ID does not create or train those files.

**No Spotify key, Deezer key, Apple Music developer token, or Apple Music subscription is required by the current integration.** Apple playlists are read from anonymous public Apple Music pages; public iTunes lookup supplies available song previews. Deezer supplies public catalog data, fallback playlists, and the current chart. This does not synchronize a private Apple library or provide full-song streaming. Apple's public page format can change; unavailable Apple playlist searches fall back to Deezer with the correct provider label.

`HF_BUCKET_URL`, if present in an older `.env`, is not read by the current Python app. Do not put API keys in `src/static/` or commit `.env`. The supplied `.env.example` contains placeholders only. The app's simple `.env` loader accepts `KEY=value` lines and full-line comments; use separate comment lines and restart the server after edits. Already exported environment variables take precedence over `.env`.

## Trained model files

The supplied `artifacts/` folder is required for the local engine. It is ignored by Git, so a fresh source clone may not include it. Copy the existing folder or configure `HF_ARTIFACTS_DATASET` before launching.

Runtime files read by the app:

```text
artifacts/
  embeddings.npy
  features_dense.npy
  meta.parquet
  prep_meta.json
  genre_indices.npy
  genre_offsets.npy
  index.bin
  index_meta.json
  mood_model.pkl
```

Keep these files from the same trained export: metadata rows, embeddings, features, genre indices, and the HNSW index must agree. `encoder.pt`, training logs, and the training notebook are useful for training work but are not needed to serve the existing model. Running the app does not retrain it. If a Git LFS download contains text pointers instead of binary files, download the actual artifacts first.

## How to test the product

1. Open Home and use the profile menu to select your listening profile. Saving songs and completing previews shape future recommendations automatically; there is no manual artist/language setup form.
2. Search for a song, artist, album, or a slightly misspelled title. Typing shows suggestions; Enter submits the search unless a suggestion is selected. Arrow keys navigate suggestions. Selecting a song opens its recommendations.
3. Save or dislike a few songs, then revisit Home. Saves, weaker listening signals, representative recordings, artist affinity, and available recording-language evidence contribute to the feed. Removing a save updates the active taste profile.
4. Open a Home playlist or an album. Check its provider, song count, artwork, track durations, and the loaded track list. A partial provider response is labelled as incomplete.
5. Open a song's three-dot menu for album navigation, details, insights, queue actions, and provider links. Use the adjacent thumbs-up/down controls for feedback. **Flow** is SoundVector’s personal continuation: the selected song sets the context, while active saves and completed previews help choose familiar music and nearby discoveries. **Similar** focuses on recording similarity, **Vibe** emphasizes measured audio character, **Popular** favors familiar hits, and **Related** explores the selected artist. Flow also builds the player’s Up next queue.
6. Play a preview and browse another page. Check pause, seek, volume, previous/next, and the queue. Previews are provider samples, often around 30 seconds; a displayed song duration is the full recording's length.

Keyboard shortcuts: **Cmd+K / Ctrl+K** focuses search; **Escape** dismisses suggestions and dialogs; **Space** toggles playback outside input controls. Feedback has an Undo action.

Profile names select local listening data; they are not password-protected accounts. Saves, dislikes, and listening history live in `profiles/` locally. On a host with a writable `/data` directory, the app instead uses `/data/profiles/`. The browser remembers the selected profile. Back up profile files separately from the model. Catalog metadata is cached in `.cache/`; changing `SOUNDVECTOR_CACHE_DIR` does not move profiles or model artifacts.

## How Flow learns

Flow runs locally without Gemini. It retrieves from the trained embedding index, acoustically compatible catalog songs, and the artists represented in your active saves and completed previews. Its own ranker balances session context, familiarity, popularity, and limited provider listening evidence. It spaces recurring artists and albums, reduces immediate replays, and excludes disliked or skipped recordings. Removing a like removes its explicit influence; a separately completed preview remains a weaker listening signal.

Use **Why this song?** from the three-dot menu (or the explanation in a wide-screen Flow row) to see the actual signals used. Provider-only recordings cannot claim measured sound similarity. Artist genre tags are not treated as song languages. Model files are unchanged.

Personalization uses the selected **SoundVector** profile; it cannot see a private YouTube Music listening history. Accounts with different saves will therefore get different queues. Public provider metadata supplies artwork, credits, releases, and listening-neighbor candidates; providers do not determine Flow’s final order. Without internet or optional Last.fm credentials, catalog recordings can still use the local model. New recordings outside the trained catalog have less evidence and may produce a shorter queue.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| `ModuleNotFoundError` | Activate the virtual environment and install the root `requirements.txt` using that environment's `python -m pip`. |
| `hnswlib` fails to build during installation | It needs a working C++ compiler when a compatible wheel is unavailable. On macOS, install Xcode Command Line Tools; then retry the installation. |
| Missing `index.bin`, NumPy, Parquet, or pickle files | Check the runtime artifact list above, the dataset layout, and your working directory. The automatic download is triggered by a missing `index.bin`; it does not repair a partially mixed export. |
| Port already in use | Stop the existing server with Ctrl+C, or choose another port and check that `PORT` is not overriding it. |
| Gemini is unconfigured or quota-limited | Check `GEMINI_API_KEY`, access and quota in AI Studio, and restart after changing the key. A configured key alone does not prove a successful Gemini request. |
| Missing artwork, previews, or live results | Check network and provider availability. Provider catalogs vary by storefront; some recordings do not have public previews. |
| Changes are not visible | Restart for backend/configuration changes, then reload the browser at the port you actually started. |

For a quick server check:

```bash
curl --fail --silent --output /dev/null --write-out 'HTTP %{http_code}\n' http://localhost:8000/script.js
curl 'http://localhost:8000/api/search?q=After%20Hours&quick=true&live=false'
```

## Automated checks

From the project root:

```bash
python -m pytest tests/ -q
node --test tests/test_frontend.cjs
node --check src/static/script.js
```

The Python tests include model checks that require the trained artifacts and fixture-based checks for recording identity, feedback, personalization, metadata, provider behavior, and API flows. Browser testing is still needed for layout, keyboard interaction, and audio playback. The tests do not certify subjective recommendation quality or full accessibility compliance.

## Code map

| Location | Purpose |
| --- | --- |
| `backend/app.py`, `backend/routes.py` | CLI launcher, UI delivery, and FastAPI endpoints. |
| `backend/flow.py` | Personal continuation retrieval, ranking, and sequence spacing. |
| `backend/engine.py`, `backend/mood.py` | Trained embeddings, HNSW retrieval, ranking, and mood projection. |
| `backend/discovery.py`, `backend/home.py`, `backend/neighbors.py` | Product recommendation composition and optional Last.fm neighbors. |
| `backend/profiles.py` | Persistent saves, dislikes, listening events, and taste profiles. |
| `backend/search.py`, `backend/metadata.py`, `backend/catalog_cache.py` | Catalog search, recording identity, metadata provenance, and caching. |
| `backend/apple_music.py`, `backend/curation.py`, `backend/albums.py` | Public playlists, charts, and complete release lookup. |
| `backend/rag_dj.py`, `backend/insights.py` | Gemini prompting, source-backed insights, and insight caching. |
| `src/static/` | Browser interface and preview player. |
| `DESIGN_SYSTEM.md` | UI tokens, components, and interaction guidelines. |
| `src/soundvector_train_emb.ipynb` | Training notebook; not part of local startup. |
