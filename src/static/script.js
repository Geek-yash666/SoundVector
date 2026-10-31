/* SoundVector 4 — solid violet, warm paper, music before decoration. */
"use strict";
const C = SoundVectorCore;
const $ = (id) => document.getElementById(id);
const svg = (name, body, filled = false) =>
  `<svg data-name="${name}" viewBox="0 0 24 24" fill="${filled ? "currentColor" : "none"}" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${body}</svg>`;
const icons = {
  home: svg(
    "home",
    '<path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1Z"/>',
  ),
  compass: svg(
    "compass",
    '<circle cx="12" cy="12" r="9"/><path d="m16 8-2 6-6 2 2-6Z"/>',
  ),
  library: svg(
    "library",
    '<path d="M4 4v16M9 4v16m5-15 6 14M14 5l3-1 6 14-3 1Z"/>',
  ),
  search: svg(
    "search",
    '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  ),
  thumbsUp: svg(
    "thumbsUp",
    '<path d="M7 10v11H3V10Zm0 0 5-8c2 0 3 2 2 5l-1 3h6a2 2 0 0 1 2 2l-2 7a3 3 0 0 1-3 2H7"/>',
  ),
  thumbsDown: svg(
    "thumbsDown",
    '<path d="M7 14V3H3v11Zm0 0 5 8c2 0 3-2 2-5l-1-3h6a2 2 0 0 0 2-2l-2-7a3 3 0 0 0-3-2H7"/>',
  ),
  heart: svg(
    "heart",
    '<path d="M20.8 4.8a5.5 5.5 0 0 0-7.8 0L12 5.9l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.4a5.5 5.5 0 0 0 0-7.8Z"/>',
  ),
  play: svg("play", '<path d="m8 5 11 7-11 7Z"/>', true),
  pause: svg("pause", '<path d="M7 5h3v14H7zm7 0h3v14h-3Z"/>', true),
  more: svg(
    "more",
    '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
  ),
  next: svg("next", '<path d="m5 5 10 7-10 7Z"/><path d="M19 5v14"/>', true),
  previous: svg(
    "previous",
    '<path d="m19 5-10 7 10 7Z"/><path d="M5 5v14"/>',
    true,
  ),
  volume: svg(
    "volume",
    '<path d="M4 9h4l5-4v14l-5-4H4Z"/><path d="M17 8a6 6 0 0 1 0 8m3-11a10 10 0 0 1 0 14"/>',
  ),
  queue: svg("queue", '<path d="M3 5h18M3 10h12M3 15h8m4-2 6 4-6 4Z"/>'),
  chevronDown: svg("chevronDown", '<path d="m7 10 5 5 5-5"/>'),
  arrow: svg("arrow", '<path d="M5 12h14m-6-6 6 6-6 6"/>'),
  back: svg("back", '<path d="M19 12H5m6-6-6 6 6 6"/>'),
  close: svg("close", '<path d="m6 6 12 12M6 18 18 6"/>'),
  info: svg(
    "info",
    '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v.1"/>',
  ),
  music: svg(
    "music",
    '<path d="M9 17V5l11-2v12M9 9l11-2"/><ellipse cx="6" cy="18" rx="3" ry="2"/><ellipse cx="17" cy="16" rx="3" ry="2"/>',
  ),
  hide: svg("hide", '<circle cx="12" cy="12" r="9"/><path d="m6 18 12-12"/>'),
  external: svg("external", '<path d="M14 3h7v7m0-7-11 11M10 4H4v16h16v-6"/>'),
  moon: svg("moon", '<path d="M21 13A9 9 0 0 1 11 3a9 9 0 1 0 10 10Z"/>'),
  sun: svg(
    "sun",
    '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1 1m12 12 1 1M5 19l1-1M18 6l1-1"/>',
  ),
  bolt: svg("bolt", '<path d="m13 2-9 12h7l-1 8 10-13h-7Z"/>'),
  headphones: svg(
    "headphones",
    '<path d="M4 13v-2a8 8 0 0 1 16 0v2M4 12h3v8H4a2 2 0 0 1-2-2v-4a2 2 0 0 1 2-2Zm16 0h-3v8h3a2 2 0 0 0 2-2v-4a2 2 0 0 0-2-2Z"/>',
  ),
  spark: svg(
    "spark",
    '<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5Z"/>',
  ),
  album: svg(
    "album",
    '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
  ),
  addQueue: svg("addQueue", '<path d="M3 5h14M3 10h14M3 15h8m7-2v8m-4-4h8"/>'),
  loading: svg("loading", '<path d="M21 12a9 9 0 1 1-9-9"/>'),
};
const savedIdentity = localStorage.getItem("soundvector_user");
const anonymousIdentity =
  localStorage.getItem("soundvector_anonymous") ||
  `guest_${crypto.randomUUID()}`;
localStorage.setItem("soundvector_anonymous", anonymousIdentity);
const state = {
  user:
    savedIdentity && savedIdentity !== "Guest"
      ? savedIdentity
      : anonymousIdentity,
  view: "home",
  params: {},
  profile: { history: [], recent: [] },
  home: null,
  editorial: null,
  playlist: null,
  tracks: new Map(),
  registry: new Map(),
  serial: 0,
  results: null,
  searchFilter: "all",
  libraryFilter: "saved",
  recommendation: null,
  recommendationMode: "flow",
  tasteRevision: 0,
  recommendationRevision: -1,
  artist: null,
  album: null,
  mood: null,
  shown: 30,
  homeDirty: true,
  pending: new Set(),
};
const albumGate = C.gate(),
  insightGate = C.gate(),
  pageGate = C.gate(),
  searchGate = C.gate(),
  profileGate = C.gate();
let homeRefreshTimer,
  editorialPending = "",
  menuAnchor,
  suggestionController;
const playlistItems = new Map();
const suggestionCache = new Map();
let searchTimer,
  suggestItems = [],
  suggestionIndex = -1,
  pageController,
  toastTimer,
  dialogFocus;
let audio = null,
  playing = null,
  playQueue = [],
  queueIndex = -1,
  queueRevision = 0,
  radioLoading = false,
  audioGeneration = 0,
  playedSeconds = 0,
  lastAudioTime = 0,
  listenId = "",
  listenUser = "";
const esc = C.escape;
const displayName = () =>
  state.user.startsWith("guest_") ? "Guest" : state.user;
function actionButton(
  action,
  icon,
  label,
  attrs = "",
  className = "icon-button",
) {
  return `<button class="${className}" ${action === "track-menu" ? 'aria-haspopup="menu" aria-controls="trackPopover"' : ""} data-action="${action}" aria-label="${esc(label)}" title="${esc(label)}" ${attrs}>${icons[icon]}</button>`;
}
function register(track) {
  const key = C.key(track);
  const { user, signal, ts, context, ...metadata } = track;
  const merged = { ...(state.tracks.get(key) || {}), ...metadata };
  if (metadata.reason && !metadata.flow_reasons) {
    delete merged.flow_reasons;
    delete merged.flow_evidence;
    delete merged.recommendation_source;
  }
  state.tracks.set(key, merged);
  if (!state.registry.has(key)) state.registry.set(key, String(++state.serial));
  return state.registry.get(key);
}
function find(id) {
  const pair = [...state.registry].find(([, value]) => value === String(id));
  return pair ? state.tracks.get(pair[0]) : null;
}
function art(track, extra = "") {
  const raw = track.deezer_album_art || track.cover_art || "";
  const url = /2a96cbd8b46e442fc41c2b86b821562f|\/star\.png/.test(raw)
    ? ""
    : C.safeUrl(raw, true);
  const title = String(track.name || track.title || track.artist || "Music");
  const initials = title
    .split(/\s+/)
    .slice(0, 2)
    .map((t) => t[0] || "")
    .join("")
    .toUpperCase();
  const fallback = `<span class="art-placeholder" aria-hidden="true"><span>${esc(initials)}</span>${icons.music}</span>`;
  return url
    ? `<img src="${esc(url)}" alt="" loading="lazy" decoding="async" ${extra}>`
    : fallback;
}
function credits(track) {
  const names = (track.artists || []).map((a) => a.name).filter(Boolean);
  return [
    ...new Set(names.length ? names : [track.artist].filter(Boolean)),
  ].join(", ");
}
function rowCredits(track) {
  return `<span>${esc(credits(track))}</span>${track.duration_seconds ? `<time class="inline-duration"> · ${C.time(track.duration_seconds)}</time>` : ""}`;
}
function feedbackButtons(track) {
  const id = register(track),
    liked = isSaved(track),
    disliked = C.signal(state.profile.history, track) === "dislike";
  return `<span class="feedback-pair">${actionButton("save", "thumbsUp", liked ? `Remove ${track.name} from saved songs` : `Save ${track.name}`, `data-track="${id}" aria-pressed="${liked}"`)}${actionButton("dislike", "thumbsDown", disliked ? `Remove dislike for ${track.name}` : `Dislike ${track.name}`, `data-track="${id}" aria-pressed="${disliked}"`)}</span>`;
}
function recommendationParams(track) {
  return {
    id: register(track),
    name: track.name,
    artist: track.artist,
    row: String(track.row ?? -1),
  };
}
function isSaved(track) {
  return C.signal(state.profile.history, track) === "like";
}
function saveButton(track) {
  return feedbackButtons(track);
}
function card(track) {
  const id = register(track);
  track = find(id);
  return `<article class="music-card" data-key="${esc(C.key(track))}"><div class="card-art" data-art="${id}">${art(track)}${actionButton("play", "play", `Play a preview of ${track.name}`, `data-track="${id}"`, "card-play")}</div><button class="card-name" data-action="similar" data-track="${id}" title="${esc(track.name)}">${esc(track.name)}</button><button class="card-artist" data-action="artist" data-artist="${esc(track.artist)}" title="${esc(credits(track))}">${esc(credits(track))}</button><div class="card-foot">${feedbackButtons(track)}${actionButton("track-menu", "more", `More options for ${track.name}`, `data-track="${id}"`)}</div></article>`;
}
function rows(tracks, showReason = false) {
  return `<div class="track-list">${tracks
    .map((track, i) => {
      const id = register(track);
      track = find(id);
      return `<article class="track-row" data-key="${esc(C.key(track))}"><span class="track-number" aria-hidden="true">${state.view === "album" ? track.track_number || i + 1 : i + 1}</span><div class="track-cell"><button class="list-art row-art" data-art="${id}" data-action="play" data-track="${id}" aria-label="Play a preview of ${esc(track.name)}">${art(track)}</button><div class="track-copy"><button class="track-title" data-action="similar" data-track="${id}" title="${esc(track.name)}">${esc(track.name)}${track.explicit ? '<span class="explicit-mark" aria-label="Explicit">E</span>' : ""}</button><button class="track-by" data-action="details" data-track="${id}" title="${esc(credits(track))}">${rowCredits(track)}</button></div>${feedbackButtons(track)}</div>${showReason && track.flow_reasons?.length ? `<button class="track-album flow-reason" data-action="flow-why" data-track="${id}" title="Why this song?">${esc(track.flow_reasons[0])}${icons.info}</button>` : `<button class="track-album" data-action="song-album" data-track="${id}" title="${esc(track.album || "")}">${esc(track.album || "")}</button>`}<time class="track-duration">${track.duration_seconds ? C.time(track.duration_seconds) : "—"}</time>${actionButton("track-menu", "more", `More options for ${track.name}`, `data-track="${id}"`)}</article>`;
    })
    .join("")}</div>`;
}
function empty(title, description, button = "") {
  return `<div class="empty-state">${icons.music}<h2>${esc(title)}</h2><p>${esc(description)}</p>${button}</div>`;
}
function loading(label) {
  return `<p class="loading-label" role="status">${esc(label)}</p><div class="loading-grid" aria-hidden="true">${Array.from({ length: 6 }, () => '<div class="skeleton"></div>').join("")}</div>`;
}
function heading(title, subtitle, eyebrow = "", tools = "") {
  return `<header class="page-head"><div><h1 tabindex="-1">${esc(title)}</h1>${subtitle ? `<p class="page-subtitle">${esc(subtitle)}</p>` : ""}</div>${tools ? `<div class="head-tools">${tools}</div>` : ""}</header>`;
}
function announce(message) {
  $("announcer").textContent = message;
}
function toast(message, undo) {
  clearTimeout(toastTimer);
  $("toast").innerHTML =
    `<span>${esc(message)}</span>${undo ? '<button data-action="undo">Undo</button>' : ""}`;
  $("toast").hidden = false;
  $("toast").undoAction = undo;
  toastTimer = setTimeout(
    () => {
      $("toast").hidden = true;
    },
    undo ? 10000 : 4200,
  );
}
async function api(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  if (!response.ok) {
    let message = "Something went wrong. Please try again.";
    try {
      const data = await response.json();
      if (typeof data.detail === "string") message = data.detail;
    } catch {}
    throw new Error(message);
  }
  return response.json();
}
function closeSuggestions() {
  clearTimeout(searchTimer);
  searchGate.cancel();
  $("searchSuggestions").hidden = true;
  $("searchInput").setAttribute("aria-expanded", "false");
  $("searchInput").removeAttribute("aria-activedescendant");
  suggestItems = [];
  suggestionIndex = -1;
}
function setNav(view) {
  document.querySelectorAll("[data-view]").forEach((el) => {
    const active =
      el.dataset.view ===
      (view === "library" ? "library" : view === "home" ? "home" : "discover");
    if (active) el.setAttribute("aria-current", "page");
    else el.removeAttribute("aria-current");
  });
  $("profileName").textContent = displayName();
  $("profileInitial").textContent = displayName()[0]?.toUpperCase() || "Y";
  $("profileButton").setAttribute(
    "aria-label",
    `Switch listening profile, currently ${displayName()}`,
  );
  $("libraryCount").textContent =
    state.profile.history.filter((t) => t.signal === "like").length || "";
}
async function loadProfile() {
  const token = profileGate.next(),
    user = state.user;
  const profile = await api(`/api/profile?user=${encodeURIComponent(user)}`);
  if (!profileGate.valid(token) || user !== state.user) return;
  state.profile = profile;
  profile.history.forEach(register);
  setNav(state.view);
  updateSaveButtons();
}
function updateSaveButtons() {
  document.querySelectorAll('[data-action="save"]').forEach((button) => {
    const track = find(button.dataset.track);
    if (!track) return;
    const saved = isSaved(track);
    const label = saved
      ? `Remove ${track.name} from saved songs`
      : `Save ${track.name}`;
    button.setAttribute("aria-pressed", saved);
    button.setAttribute("aria-label", label);
    button.title = label;
  });
  document.querySelectorAll('[data-action="dislike"]').forEach((button) => {
    const t = find(button.dataset.track);
    if (!t) return;
    const value = C.signal(state.profile.history, t) === "dislike";
    button.setAttribute("aria-pressed", value);
    button.setAttribute(
      "aria-label",
      value ? `Remove dislike for ${t.name}` : `Dislike ${t.name}`,
    );
  });
  if (playing) {
    $("playerDislike").setAttribute(
      "aria-pressed",
      C.signal(state.profile.history, playing) === "dislike",
    );
    $("playerSave").setAttribute("aria-pressed", isSaved(playing));
    $("playerSave").setAttribute(
      "aria-label",
      isSaved(playing)
        ? "Remove current song from saved songs"
        : "Save current song",
    );
  }
}
async function route(view, params = {}, push = true) {
  albumGate.cancel();
  if ($("appDialog").open) closeDialog();
  closeTrackMenu(false);
  closeSuggestions();
  if (pageController) pageController.abort();
  pageController = new AbortController();
  const restoreScroll = window.scrollY;
  const token = pageGate.next();
  state.view = view;
  state.params = params;
  state.shown = 30;
  setNav(view);
  if (push) {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (typeof value === "string") query.set(key, value);
    }
    history.pushState(
      { view, params },
      "",
      `#/${view}${query.size ? "?" + query : ""}`,
    );
  }
  document.title = `${{ home: "Home", library: "Your library", discover: "Discover", search: "Search", recommend: "Similar songs", artist: params.name, album: params.title, mix: "Your mix" }[view] || "Music"} · SoundVector`;
  $("mainContent").innerHTML = loading("Loading music…");
  try {
    if (view === "home") {
      if (!state.home || state.homeDirty) {
        const data = await api(
          `/api/home?user=${encodeURIComponent(state.user)}`,
          { signal: pageController.signal },
        );
        if (!pageGate.valid(token)) return;
        state.home = data;
        state.homeDirty = false;
      }
      renderHome();
    } else if (view === "library") {
      await loadProfile();
      if (!pageGate.valid(token)) return;
      renderLibrary();
    } else if (view === "discover") {
      renderDiscover();
    } else if (view === "search") {
      $("searchInput").value = params.q || "";
      state.searchFilter = "all";
      const query = params.q || "";
      const local = await api(
        `/api/search?q=${encodeURIComponent(query)}&quick=true&live=false`,
        { signal: pageController.signal },
      );
      if (!pageGate.valid(token)) return;
      state.results = { ...local, pending: true };
      renderSearch();
      enrichVisible();
      updateSearchPage(query, token, pageController.signal);
    } else if (view === "recommend") {
      const track = C.selectedTrack(params, find(params.id));
      if (!track) throw new Error("Choose a song from search or your library.");
      state.recommendationMode = params.mode || "flow";
      const tasteRevision = state.tasteRevision;
      const data = await api("/api/recommend", {
        method: "POST",
        signal: pageController.signal,
        body: JSON.stringify({
          user: state.user,
          query: track.name,
          seed_track: track,
          mode: state.recommendationMode,
          limit: 40,
        }),
      });
      if (!pageGate.valid(token)) return;
      state.recommendation = data;
      state.recommendationRevision = tasteRevision;
      renderRecommendations();
    } else if (view === "artist") {
      const data = await api(
        `/api/artist?name=${encodeURIComponent(params.name || "")}`,
        { signal: pageController.signal },
      );
      if (!pageGate.valid(token)) return;
      state.artist = data;
      renderArtist();
    } else if (view === "album") {
      const data =
        params.local ||
        (await api(
          `/api/album_tracks?title=${encodeURIComponent(params.title || "")}&artist=${encodeURIComponent(params.artist || "")}&id=${encodeURIComponent(params.id || "")}&source=${encodeURIComponent(params.source || "")}`,
          { signal: pageController.signal },
        ));
      if (!pageGate.valid(token)) return;
      state.album = data;
      renderAlbum();
    } else if (view === "playlist") {
      const data = await api(
        `/api/playlist?${new URLSearchParams({id: params.id || "", source: params.source || "deezer", url: params.url || ""})}`,
        { signal: pageController.signal },
      );
      if (!pageGate.valid(token)) return;
      state.album = data;
      renderAlbum();
    } else if (view === "mix") {
      const data = await api("/api/playlist_gen", {
        method: "POST",
        signal: pageController.signal,
        body: JSON.stringify({
          prompt: params.q || "",
          user: state.user,
          count: 30,
        }),
      });
      if (!pageGate.valid(token)) return;
      state.mood = data;
      renderMix();
    } else {
      renderDiscover();
    }
    if (!pageGate.valid(token)) return;
    document.querySelector(".search-clear").hidden = !$("searchInput").value;
    announce(
      `${$("mainContent").querySelector("h1")?.textContent || "Music"} loaded.`,
    );
    enrichVisible();
    const focusTarget =
      view === "recommend" && params.mode && !push
        ? $("mainContent").querySelector(
            `[data-action="recommend-mode"][data-value="${params.mode}"]`,
          )
        : $("mainContent").querySelector("h1");
    focusTarget?.focus({ preventScroll: true });
    window.scrollTo({
      top: view === "recommend" && params.mode && !push ? restoreScroll : 0,
      behavior: "instant",
    });
  } catch (error) {
    if (error.name === "AbortError" || !pageGate.valid(token)) return;
    $("mainContent").innerHTML = empty(
      "Couldn’t load this music",
      error.message,
      '<button class="primary-button" data-action="retry">Try again</button>',
    );
    announce(error.message);
  }
}
function renderHome() {
  const data = state.home,
    sections = data.sections || [],
    rotation = sections[0]?.tracks || [];
  let html = heading(
    "Home",
    "",
    "",
    actionButton("how-home", "info", "How recommendations work"),
  );
  if (rotation.length)
    html += `<section class="section home-rotation"><div class="section-head"><div><h2>For you</h2><p>Across the songs you save and listen to</p></div><button class="text-button" data-action="play-section" data-section="0">${icons.play} Play previews</button></div>${rows(rotation.slice(0, 12))}</section>`;
  html += '<div id="editorialHome"></div>';
  sections.slice(1).forEach((section, index) => {
    if (section.tracks?.length)
      html += `<section class="section"><div class="section-head"><div><h2>Explore more</h2><p>More artists and a wider mix</p></div><button class="text-button" data-action="play-section" data-section="${index + 1}">${icons.play} Play previews</button></div><div class="compact-shelf">${rows(section.tracks.slice(0, 12))}</div></section>`;
  });
  if (!rotation.length)
    html += empty(
      "Start with a song",
      "Search for music you like and save it to shape Home.",
      '<a class="secondary-button" href="#/discover">Discover music</a>',
    );
  $("mainContent").innerHTML = html;
  renderEditorial();
  loadEditorial();
}
async function loadEditorial() {
  const user = state.user;
  if (state.editorial?.user === user || editorialPending === user) return;
  editorialPending = user;
  try {
    const data = await api(`/api/editorial?user=${encodeURIComponent(user)}`);
    if (state.user !== user) return;
    state.editorial = { ...data, user };
    if (state.view === "home") {
      renderEditorial();
      enrichVisible();
    }
  } catch {
  } finally {
    if (editorialPending === user) editorialPending = "";
  }
}
function renderEditorial() {
  const el = $("editorialHome"),
    data = state.editorial;
  if (!el || data?.user !== state.user) return;
  playlistItems.clear();
  let html = "";
  const providers=[...new Set((data.playlists || []).map(item=>providerName(item.source)))].join(" · ");
  if (data.playlists?.length)
    html += `<section class="section"><div class="section-head"><h2>Playlists for you</h2><span class="quiet-label">${esc(providers)}</span></div><div class="playlist-grid">${data.playlists
      .map((item) => {
        playlistItems.set(`${item.source}:${item.id}`, item);
        const summary=[item.creator || providerName(item.source), Number.isFinite(item.track_count) && item.track_count>=0 ? `${item.track_count} ${item.track_count===1?"song":"songs"}` : ""].filter(Boolean).join(" · ");
        return `<button class="playlist-card" data-action="playlist" data-id="${esc(item.id)}" data-source="${esc(item.source)}"><span class="playlist-art">${art(item)}</span><span class="playlist-copy"><strong title="${esc(item.title)}">${esc(item.title)}</strong><small>${esc(summary)}</small></span>${icons.arrow}</button>`;
      })
      .join("")}</div></section>`;
  if (data.trending?.tracks?.length)
    html += `<section class="section"><div class="section-head"><div><h2>Trending now</h2><p>${esc(data.trending.source)} · refreshed ${esc(new Date(data.trending.updated_at).toLocaleDateString())}</p></div><button class="text-button" data-action="play-trending">${icons.play} Play previews</button></div><div class="compact-shelf">${rows(data.trending.tracks.slice(0, 12))}</div></section>`;
  el.innerHTML = html;
}
function tabs(options, selected, action) {
  return `<div class="tabs" role="tablist" aria-label="${action === "library-filter" ? "Library filters" : "Music filters"}">${options.map(([value, label]) => `<button class="tab" role="tab" id="${action}-${value}" aria-controls="musicPanel" aria-selected="${value === selected}" tabindex="${value === selected ? 0 : -1}" data-action="${action}" data-value="${value}">${label}</button>`).join("")}</div><div id="musicPanel" role="tabpanel" aria-labelledby="${action}-${selected}">`;
}
function renderSearch() {
  const data = state.results || {},
    q = state.params.q || "",
    filter = state.searchFilter;
  albums.clear();
  let html = heading(
    `Results for “${q}”`,
    data.correction &&
      C.key({ name: data.correction, artist: "" }) !==
        C.key({ name: q, artist: "" })
      ? `Closest title: ${data.correction}`
      : "",
    "SEARCH",
  );
  html += tabs(
    [
      ["all", "All"],
      ["songs", "Songs"],
      ["artists", "Artists"],
      ["albums", "Albums"],
    ],
    filter,
    "search-filter",
  );
  const normalized = (value) => String(value || "").toLowerCase().replace(/\s*[([][^)\]]*[)\]]/g, "").replace(/[^\p{L}\p{N}]/gu, "");
  const release = (data.albums || []).find((a) => a.track_count >= 4 && normalized(a.title) === normalized(q));
  if (filter === "all" && release) {
    const id = String(++albumSerial);
    albums.set(id, release);
    html += `<button class="search-album-hit" data-action="album" data-album="${id}"><span class="playlist-art">${art(release)}</span><span><small>Album · ${release.track_count} songs</small><strong>${esc(release.title)}</strong><small>${esc(release.artist || "")}</small></span>${icons.arrow}</button>`;
  }
  if ((filter === "all" || filter === "songs") && data.results?.length)
    html += `<section class="section"><div class="section-head"><h2>Songs</h2><span class="quiet-label">${data.results.length} matches</span></div>${rows(data.results)}</section>`;
  if ((filter === "all" || filter === "artists") && data.artists?.length)
    html += `<section class="section"><div class="section-head"><h2>Artists</h2></div><div class="artist-grid">${data.artists.map((a, i) => `<button class="artist-card" data-action="artist" data-artist="${esc(a.artist)}"><span class="artist-portrait" data-artist-image="${esc(a.artist)}">${art({ artist: a.artist })}</span><strong>${esc(a.artist)}</strong><small>Artist</small></button>`).join("")}</div></section>`;
  if ((filter === "all" || filter === "albums") && data.albums?.length)
    html += `<section class="section"><div class="section-head"><h2>Albums & soundtracks</h2></div><div class="music-grid">${data.albums.map(albumCard).join("")}</div></section>`;
  const count =
    (filter === "all"
      ? (data.results?.length || 0) +
        (data.artists?.length || 0) +
        (data.albums?.length || 0)
      : filter === "songs"
        ? data.results?.length
        : filter === "artists"
          ? data.artists?.length
          : data.albums?.length) || 0;
  if (!count && data.pending)
    html +=
      '<p class="loading-label" role="status">Searching music services…</p>';
  if (!count && !data.pending)
    html += empty(
      "No matches here yet",
      "Try a different title or artist. To describe a feeling or activity, head to Discover.",
      '<a class="secondary-button" href="#/discover">Browse moods</a>',
    );
  $("mainContent").innerHTML = html + "</div>";
}
const albums = new Map();
let albumSerial = 0;
function albumCard(album) {
  const id = String(++albumSerial);
  albums.set(id, album);
  return `<button class="music-card album-card" data-action="album" data-album="${id}"><span class="card-art" style="display:block">${art(album)}</span><span class="card-name">${esc(album.title)}</span><small title="${esc(album.artist || "")}">${esc(album.artist || "Album")}</small>${album.track_count ? `<small>${album.track_count} ${album.track_count === 1 ? "song" : "songs"}</small>` : ""}</button>`;
}
function renderLibrary() {
  const history = state.profile.history || [],
    saved = history.filter((t) => t.signal === "like");
  let tracks =
    state.libraryFilter === "saved"
      ? saved
      : state.libraryFilter === "hidden"
        ? history.filter((t) => ["dislike", "skip"].includes(t.signal))
        : C.unique(state.profile.recent || []);
  $("mainContent").innerHTML =
    heading(
      "Library",
      `${saved.length} saved ${saved.length === 1 ? "song" : "songs"}`,
      "YOUR COLLECTION",
      saved.length
        ? `<button class="secondary-button" data-action="play-library" aria-label="Play saved song previews">${icons.play}<span>Play previews</span></button>`
        : "",
    ) +
    tabs(
      [
        ["saved", "Saved songs"],
        ["recent", "Recently played"],
        ["hidden", "Hidden songs"],
      ],
      state.libraryFilter,
      "library-filter",
    ) +
    (tracks.length
      ? rows(tracks.slice(0, state.shown)) +
        (tracks.length > state.shown
          ? '<button class="secondary-button more-button" data-action="show-more">Show more songs</button>'
          : "")
      : empty(
          state.libraryFilter === "saved"
            ? "Your favorites start here."
            : state.libraryFilter === "recent"
              ? "A little quiet here."
              : "Nothing hidden.",
          state.libraryFilter === "saved"
            ? "Like a song to save it. Your home will start finding more music around the songs you love."
            : state.libraryFilter === "recent"
              ? "Play a preview to start your listening history."
              : "Songs you hide stay out of your home recommendations.",
          '<a class="primary-button" href="#/discover">Find some music</a>',
        )) +
    "</div>";
}
function hero(track, eyebrow = "MORE LIKE THIS") {
  const id = register(track);
  return `<div class="content-hero"><div class="hero-art" data-art="${id}">${art(track)}</div><div class="hero-copy"><h1 tabindex="-1">${esc(track.name)}</h1><p><button class="track-by" data-action="artist" data-artist="${esc(track.artist)}">${esc(track.artist)}</button>${track.year ? ` · ${esc(track.year)}` : ""}</p><div class="head-tools"><button class="primary-button" data-action="play" data-track="${id}">${icons.play} Play preview</button>${saveButton(track)}<button class="secondary-button" data-action="insights" data-track="${id}">${icons.spark} Insights</button>${actionButton("track-menu", "more", `More options for ${track.name}`, `data-track="${id}"`)}</div></div></div>`;
}
function renderRecommendations() {
  const data = state.recommendation;
  $("mainContent").innerHTML =
    `<button class="text-button back-button" data-action="back">${icons.back} Back</button>` +
    hero(data.facts) +
    tabs(
      [
        ["flow", "Flow"],
        ["similar", "Similar"],
        ["vibe", "Vibe"],
        ["popular", "Popular"],
        ["related", "Related"],
      ],
      state.recommendationMode,
      "recommend-mode",
    ) +
    `<section class="section recommendation-list"><p class="section-note">${esc(({flow:"SoundVector Flow · Your saved music and listening, starting from this song",similar:"Songs close to this recording",vibe:"Similar mood, energy, and rhythm",popular:"Familiar hits around this song",related:"More from this artist and nearby recordings",radio:"A flowing mix of artists around this song"})[state.recommendationMode] || "Songs around this recording")}</p>${data.recs?.length ? rows(data.recs.filter(t => !["dislike", "skip"].includes(C.signal(state.profile.history, t))), state.recommendationMode === "flow") : empty("No reliable matches yet", "Try the artist or another song.")}</section></div>`;
}
function renderArtist() {
  const data = state.artist;
  const realAlbums = (data.albums || []).filter((a) => a.id && a.source);
  $("mainContent").innerHTML =
    `<button class="text-button back-button" data-action="back">${icons.back} Back</button><div class="content-hero"><div class="hero-art artist" data-artist-image="${esc(data.artist)}">${art({})}</div><div class="hero-copy"><p class="content-type">Artist</p><h1 tabindex="-1">${esc(data.artist)}</h1><p>${data.tracks?.length || 0} songs to explore</p><div class="head-tools"><button class="primary-button" data-action="play-artist">${icons.play} Play previews</button></div></div></div><section class="section"><div class="section-head"><h2>Songs</h2></div>${data.tracks?.length ? rows(data.tracks.slice(0, state.shown)) : empty("No songs available", "Try this artist again in a moment.")}${(data.tracks?.length || 0) > state.shown ? '<button class="secondary-button more-button" data-action="show-more">Show more songs</button>' : ""}</section>${realAlbums.length ? `<section class="section"><div class="section-head"><h2>Releases</h2></div><div class="music-grid">${realAlbums.slice(0, 12).map(albumCard).join("")}</div></section>` : ""}`;
}
function providerName(source) {
  return {apple_music:"Apple Music",deezer:"Deezer"}[source] || "Public catalog";
}
function collectionTime(seconds) {
  const minutes=Math.round(seconds/60);
  return minutes>=60 ? `${Math.floor(minutes/60)} hr ${minutes%60} min` : `${minutes} min`;
}
function renderAlbum() {
  const data = state.album,
    isPlaylist = state.view === "playlist";
  const subtitle = [
    data.artist,
    data.release_date?.slice(0, 4),
    `${data.tracks?.length || 0}${data.track_count && data.track_count !== data.tracks?.length ? " of " + data.track_count : ""} songs`,
    data.duration_seconds ? (isPlaylist?collectionTime(data.duration_seconds):C.time(data.duration_seconds)) + " total" : "",
  ]
    .filter(Boolean)
    .join(" · ");
  $("mainContent").innerHTML =
    `<button class="text-button back-button" data-action="back">${icons.back} Back</button><div class="content-hero release-hero"><div class="hero-art">${art(data)}</div><div class="hero-copy"><p class="content-type">${isPlaylist ? "Playlist" : "Album"}</p><h1 tabindex="-1">${esc(data.title)}</h1><p>${esc(subtitle)}</p>${data.label ? `<p class="quiet-label">${esc(data.label)}</p>` : ""}<div class="head-tools"><button class="primary-button" data-action="play-album">${icons.play} Play previews</button>${C.safeUrl(data.url) ? `<a class="secondary-button" href="${esc(C.safeUrl(data.url))}" target="_blank" rel="noopener noreferrer">${icons.external} ${isPlaylist ? "Open in " + providerName(data.source) : "Open release"}</a>` : ""}</div></div></div>${data.complete === false ? '<p class="release-status" role="status">Some tracks could not be loaded from this provider. <button class="text-button" data-action="retry">Retry</button></p>' : ""}${data.tracks?.length ? rows(data.tracks) : empty("No songs available", "This provider could not return the release.", '<button class="secondary-button" data-action="retry">Try again</button>')}${data.copyright ? `<p class="release-copyright">${esc(data.copyright)}</p>` : ""}`;
}
const moods = [
  [
    "Slow down",
    "Acoustic · Relaxing",
    "chill relaxing acoustic",
    "#e4d9f6",
    "moon",
  ],
  [
    "Turn it up",
    "Dance · Workout",
    "high energy workout dance",
    "#edd7c9",
    "bolt",
  ],
  [
    "Stay in the zone",
    "Instrumental · Focus",
    "focus instrumental lo-fi",
    "#dddce9",
    "headphones",
  ],
  ["Good company", "Soul · Upbeat", "happy upbeat soul", "#ede1bd", "sun"],
  ["After hours", "R&B · Mellow", "late night mellow r&b", "#d9cbe8", "moon"],
  [
    "Take the long way",
    "Indie · Rock",
    "driving indie rock roadtrip",
    "#e4d9d1",
    "compass",
  ],
];
function renderDiscover() {
  $("mainContent").innerHTML =
    heading("Discover", "Search above or choose a mood below.", "DISCOVER") +
    `<form class="mood-form" id="moodForm"><label for="moodPrompt">What do you want to hear?</label><p>Describe a mood or an activity. We’ll find a mix around it.</p><textarea id="moodPrompt" placeholder="Something mellow for a late-night drive…" maxlength="300" required></textarea><div class="form-bottom"><small></small><button class="primary-button" type="submit">${icons.spark} Find my mix</button></div></form><section class="section"><div class="section-head"><h2>Set the mood</h2></div><div class="mood-grid">${moods.map(([title, description, q, color, icon]) => `<button class="mood-card" data-action="mood" data-query="${q}" style="--mood-bg:${color}"><strong>${title}</strong><small>${description}</small>${icons[icon]}</button>`).join("")}</div></section>`;
}
function renderMix() {
  const data = state.mood;
  $("mainContent").innerHTML =
    heading(
      state.params.title || data.playlist_name || "Your mix",
      data.description || "",
      "DISCOVER",
      data.tracks?.length
        ? '<button class="secondary-button" data-action="play-mix" aria-label="Play mix previews">' +
            icons.play +
            "<span>Play previews</span></button>"
        : "",
    ) +
    (data.tracks?.length
      ? rows(data.tracks)
      : empty(
          "No reliable matches yet",
          "We couldn’t find songs with enough metadata for that request. Try a broader mood or a song you know.",
          '<a class="secondary-button" href="#/discover">Try another mood</a>',
        ));
}
function showDialog(title, body) {
  if (!$("appDialog").open) dialogFocus = document.activeElement;
  $("appDialog").classList.remove("insights-dialog", "details-dialog");
  $("dialogTitle").textContent = title;
  $("dialogBody").innerHTML = body;
  if (!$("appDialog").open) $("appDialog").showModal();
  $("dialogTitle").tabIndex = -1;
  $("dialogTitle").focus({ preventScroll: true });
}
function closeDialog() {
  const wasOpen = $("appDialog").open;
  albumGate.cancel();
  insightGate.cancel();
  $("appDialog").close();
  $("appDialog").classList.remove("insights-dialog", "details-dialog");
  if (wasOpen) dialogFocus?.focus?.();
}
function closeTrackMenu(restore = true) {
  const pop = $("trackPopover");
  if (pop.matches(":popover-open")) pop.hidePopover();
  menuAnchor?.setAttribute?.("aria-expanded", "false");
  if (restore && menuAnchor?.isConnected)
    menuAnchor.focus({ preventScroll: true });
}
function showTrackMenu(track, anchor = document.activeElement) {
  const id = register(track),
    link = C.safeUrl(track.deezer_link),
    pop = $("trackPopover");
  menuAnchor = anchor;
  menuAnchor?.setAttribute?.("aria-expanded", "true");
  const item = (action, icon, text, extra = "") =>
    `<button class="menu-action" role="menuitem" data-action="${action}" data-track="${id}" ${extra}>${icons[icon]}<span>${text}</span></button>`;
  pop.innerHTML = `<div class="popover-meta"><span class="list-art">${art(track)}</span><span><strong>${esc(track.name)}</strong><small>${esc(credits(track))}</small></span></div><div role="menu" aria-label="Song options">${item("similar", "compass", "Start Flow")}${track.flow_reasons?.length ? item("flow-why", "info", "Why this song?") : ""}${item("song-album", "album", "Open album")}${item("insights", "spark", "Song insights")}${item("queue-next", "next", "Play next")}${item("queue-add", "addQueue", "Add to queue")}${item("dislike", "thumbsDown", C.signal(state.profile.history, track) === "dislike" ? "Remove dislike" : "Dislike song")}${item("details", "info", "Song details")}${link ? `<a role="menuitem" class="menu-action" href="${esc(link)}" target="_blank" rel="noopener noreferrer">${icons.external}<span>Open in ${link.includes("apple.com") ? "Apple Music" : link.includes("last.fm") ? "Last.fm" : "Deezer"}</span></a>` : ""}<a role="menuitem" class="menu-action" href="https://music.youtube.com/search?q=${encodeURIComponent(track.artist + " " + track.name)}" target="_blank" rel="noopener noreferrer">${icons.external}<span>YouTube Music</span></a></div>`;
  if (!pop.matches(":popover-open")) pop.showPopover();
  const rect = anchor?.getBoundingClientRect?.() || {
    left: innerWidth / 2,
    bottom: innerHeight / 3,
  };
  pop.style.left =
    Math.max(8, Math.min(rect.left, innerWidth - pop.offsetWidth - 12)) + "px";
  pop.style.top =
    Math.max(
      8,
      Math.min(rect.bottom + 5, innerHeight - pop.offsetHeight - 12),
    ) + "px";
  pop.querySelector('[role="menuitem"]')?.focus({ preventScroll: true });
}
async function openSongAlbum(track, target) {
  const currentView = state.view,
    ticket = albumGate.next();
  if (target) {
    target.disabled = true;
    target.innerHTML = `${icons.loading} Finding album…`;
  }
  try {
    const album = await api(
      `/api/song_album?${new URLSearchParams({ track: track.name, artist: track.artist, album_id: String(track.album_id || ""), album_source: track.album_source || "" })}`,
    );
    if (!albumGate.valid(ticket) || state.view !== currentView) return;
    closeDialog();
    route("album", album);
  } catch (error) {
    if (albumGate.valid(ticket)) {
      showTrackMenu(track);
      const message = document.createElement("p");
      message.className = "menu-error";
      message.setAttribute("role", "status");
      message.textContent = error.message;
      $("trackPopover").append(message);
    }
  }
}
async function showInsights(track, refresh = false) {
  const ticket = insightGate.next(),
    id = register(track);
  showDialog(
    "Song insights",
    `<div class="dialog-meta"><div class="list-art">${art(track)}</div><div><strong>${esc(track.name)}</strong><p>${esc(credits(track))}</p></div></div><div id="insightContent" role="status"><p class="loading-label">${icons.loading} Finding a sourced recording story…</p></div>`,
  );
  $("appDialog").classList.add("insights-dialog");
  try {
    const result = await api(
      `/api/track_intel?${new URLSearchParams({ row: track.row ?? -1, track: track.name, artist: track.artist, refresh: String(refresh), album_id: String(track.album_id || ""), album_source: track.album_source || "" })}`,
    );
    if (!insightGate.valid(ticket) || !$("appDialog").open) return;
    const intel = result.intel || {},
      verified = result.backend === "gemini" && intel.fact_verified;
    let body = `<div class="insight-source">${icons.spark}<strong>Gemini</strong></div>`;
    if (verified && intel.insights?.length) {
      body += `<div class="insight-notes">${intel.insights.map((note) => `<p>${esc(note)}</p>`).join("")}</div><h3 class="sources-title">Sources</h3><ul class="source-list">${(intel.sources || []).map((source) => `<li><a href="${esc(source.url)}" target="_blank" rel="noopener noreferrer">${esc(source.title)} ${icons.external}</a></li>`).join("")}</ul>`;
      if (intel.search_html)
        body += `<iframe class="search-attribution" title="Google Search sources" sandbox="allow-popups allow-popups-to-escape-sandbox" srcdoc="${esc(intel.search_html)}"></iframe>`;
    } else {
      const message =
        result.status === "quota_exceeded"
          ? "Gemini’s usage limit has been reached. Song details are still available."
          : result.status === "not_configured"
            ? "Connect Gemini to see sourced recording stories."
            : result.status === "unavailable"
              ? "Gemini is unavailable right now."
              : "A recording-specific fact could not be verified from a source yet.";
      body += `<p class="insight-empty" role="status">${message}</p>`;
    }
    body += `<div class="insight-actions"><button class="secondary-button" data-action="details" data-track="${id}">${icons.info} Song details</button><button class="text-button" data-action="insights" data-refresh="true" data-track="${id}">Try again ${icons.arrow}</button></div>`;
    $("insightContent").innerHTML = body;
  } catch (error) {
    if (insightGate.valid(ticket) && $("appDialog").open)
      $("insightContent").innerHTML =
        `<p>${esc(error.message)}</p><button class="secondary-button" data-action="insights" data-refresh="true" data-track="${id}">Try again</button>`;
  }
}
function queueSong(track, next = false) {
  queueRevision++;
  const position = next ? queueIndex + 1 : playQueue.length;
  playQueue.splice(Math.max(0, position), 0, track);
  closeDialog();
  toast(next ? "Added to play next" : "Added to queue");
  if (!playing) showQueue();
}
function detailMarkup(track, loading = false) {
  const id = register(track);
  const fields = [
    ["Length", track.duration_seconds ? C.time(track.duration_seconds) : null],
    ["Album", track.album],
    ["Release date", track.release_date?.slice(0, 10) || track.year],
    ["Album artist", track.album_artist],
    ["Composition credits", track.composer_name],
    ["Track", track.track_number],
    ["Disc", track.disc_number],
    ["Label", track.label],
    ["ISRC", track.isrc],
    ["UPC", track.upc],
    [
      "Content",
      typeof track.explicit === "boolean"
        ? track.explicit
          ? "Explicit"
          : "Not explicit"
        : null,
    ],
    ["Language", track.language_source ? track.language : null],
    ["Genre", track.recording_genres?.join(", ")],
  ];
  const list = track.artists?.length
    ? track.artists
    : [{ name: track.artist, role: "Artist" }];
  return `<div class="dialog-meta"><div class="list-art">${art(track)}</div><div><strong>${esc(track.name)}</strong><p>${esc(credits(track))}</p></div></div><h3>Credits</h3><div class="credit-list">${list.map((a) => `<button class="credit-person" data-action="artist" data-artist="${esc(a.name)}"><strong>${esc(a.name)}</strong><small>${esc(a.role || "Artist")}</small>${icons.arrow}</button>`).join("")}</div><dl class="song-facts">${fields
    .filter(
      ([, value]) => value !== null && value !== undefined && value !== "",
    )
    .map(
      ([label, value]) =>
        `<div><dt>${label}</dt><dd>${label === "Album" ? `<button class="text-button" data-action="song-album" data-track="${id}">${esc(value)}</button>` : esc(value)}</dd></div>`,
    )
    .join("")}</dl>${
    track.row >= 0
      ? `<details class="audio-facts"><summary>Catalog audio estimates</summary><dl class="song-facts">${[
          ["Energy", track.energy],
          ["Valence", track.valence],
          ["Danceability", track.danceability],
          ["Tempo", track.tempo_bpm ? track.tempo_bpm + " BPM" : null],
        ]
          .filter(([, v]) => v !== undefined && v !== null)
          .map(([k, v]) => `<div><dt>${k}</dt><dd>${esc(v)}</dd></div>`)
          .join("")}</dl></details>`
      : ""
  }${track.copyright ? `<p class="quiet-label">${esc(track.copyright)}</p>` : ""}${C.safeUrl(track.deezer_link) ? `<a class="text-button" href="${esc(C.safeUrl(track.deezer_link))}" target="_blank" rel="noopener noreferrer">Open provider recording ${icons.external}</a>` : ""}${loading ? '<p class="loading-label" role="status">Loading full credits and recording metadata…</p>' : ""}`;
}
async function showDetails(track) {
  const ticket = insightGate.next();
  showDialog("Song details", detailMarkup(track, true));
  $("appDialog").classList.add("details-dialog");
  try {
    const result = await api("/api/track_details", {
      method: "POST",
      body: JSON.stringify({ facts: track }),
    });
    if (!insightGate.valid(ticket) || !$("appDialog").open) return;
    updateTrackMetadata(result);
    $("dialogBody").innerHTML = detailMarkup(result);
  } catch (error) {
    if (insightGate.valid(ticket) && $("appDialog").open)
      $("dialogBody").innerHTML =
        detailMarkup(track) +
        `<p class="quiet-label" role="status">${esc(error.message)}</p>`;
  }
}
function refreshHomeAfterFeedback() {
  clearTimeout(homeRefreshTimer);
  const user = state.user;
  homeRefreshTimer = setTimeout(async () => {
    if (state.view !== "home" || user !== state.user) return;
    const token = pageGate.next();
    try {
      const data = await api(`/api/home?user=${encodeURIComponent(user)}`);
      if (
        !pageGate.valid(token) ||
        state.view !== "home" ||
        user !== state.user
      )
        return;
      const position = window.scrollY;
      state.home = data;
      state.homeDirty = false;
      renderHome();
      enrichVisible();
      window.scrollTo({ top: position, behavior: "instant" });
      announce("Your rotation updated from your saved songs.");
    } catch {
      /* Keep the saved feedback and current music usable while offline. */
    }
  }, 500);
}

async function feedback(track, signal, undo = false) {
  const key = C.key(track),
    user = state.user,
    pending = `${user}:${key}`;
  if (state.pending.has(pending)) return;
  const previous = C.signal(state.profile.history, track);
  state.pending.add(pending);
  document
    .querySelectorAll(`[data-action="save"][data-track="${register(track)}"], [data-action="dislike"][data-track="${register(track)}"]`)
    .forEach((b) => (b.disabled = true));
  try {
    await api("/api/feedback", {
      method: "POST",
      body: JSON.stringify({
        ...track,
        user,
        signal,
        mode: state.recommendationMode,
      }),
    });
    if (user !== state.user) return;
    profileGate.cancel();
    const focusAction = document.activeElement?.dataset.action;
    const focusTrack = document.activeElement?.dataset.track;
    state.profile.history = state.profile.history.filter(
      (t) => C.key(t) !== key,
    );
    if (signal !== "none") state.profile.history.unshift({ ...track, signal });
    state.homeDirty = true;
    state.tasteRevision++;
    setNav(state.view);
    updateSaveButtons();
    if (signal === "dislike") playQueue = playQueue.filter((t, i) => i <= queueIndex || C.key(t) !== key);
    if (state.view === "recommend" && state.recommendation) {
      renderRecommendations();
      enrichVisible();
    }
    if (state.view === "library") renderLibrary();
    if (state.view === "home") {
      if (signal === "dislike")
        state.home.sections.forEach(
          (section) =>
            (section.tracks = section.tracks.filter((t) => C.key(t) !== key)),
        );
      renderHome();
      updateSaveButtons();
      refreshHomeAfterFeedback();
    }
    if (focusAction && focusTrack) {
      const element = document.querySelector(
        `[data-action="${focusAction}"][data-track="${focusTrack}"]`,
      );
      (element || $("mainContent").querySelector("h1"))?.focus({
        preventScroll: true,
      });
    }
    const message =
      signal === "like"
        ? "Saved to your library"
        : signal === "dislike"
          ? "Hidden from recommendations"
          : previous === "dislike" ? "Dislike removed" : "Removed from your library";
    toast(message, undo ? null : () => feedback(track, previous, true));
    announce(message);
  } catch (error) {
    toast(error.message);
  } finally {
    state.pending.delete(pending);
    document
      .querySelectorAll(`[data-action="save"][data-track="${register(track)}"], [data-action="dislike"][data-track="${register(track)}"]`)
      .forEach((b) => (b.disabled = false));
  }
}
function currentTracks() {
  return state.view === "home"
    ? state.home?.sections?.flatMap((s) => s.tracks) || []
    : state.view === "search"
      ? state.results?.results || []
      : state.view === "artist"
        ? state.artist?.tracks || []
        : ["album", "playlist"].includes(state.view)
          ? state.album?.tracks || []
          : state.view === "recommend"
            ? [
                state.recommendation?.facts,
                ...(state.recommendation?.recs || []),
              ].filter(Boolean)
            : state.view === "mix"
              ? state.mood?.tracks || []
              : state.profile.history.filter((t) => t.signal === "like");
}
const enrichmentPending = new Set();
function updateTrackMetadata(track) {
  const id = register(track);
  document.querySelectorAll(`[data-art="${id}"]`).forEach((el) => {
    const button = el.querySelector("button");
    el.innerHTML = art(track);
    if (button) el.appendChild(button);
    const queueItem = el.closest(".queue-list li");
    if (queueItem) queueItem.querySelector("small").textContent = credits(track) + (track.duration_seconds ? " · " + C.time(track.duration_seconds) : "");
    const row = el.closest(".track-row");
    if (!row) return;
    const by = row.querySelector(".track-by");
    by.innerHTML = rowCredits(track);
    by.title = credits(track);
    const album = row.querySelector(".track-album");
    if (album && !album.classList.contains("flow-reason")) {
      album.textContent = track.album || "";
      album.title = track.album || "";
    }
    row.querySelector(".track-duration").textContent = track.duration_seconds ? C.time(track.duration_seconds) : "—";
  });
}
async function enrichTracks(tracks) {
  const batch = C.unique(tracks)
    .filter(
      (t) =>
        t.name &&
        t.artist &&
        (!t.deezer_preview_url || !t.deezer_album_art || !t.duration_seconds) &&
        !enrichmentPending.has(C.key(t)),
    )
    .slice(0, 18);
  if (!batch.length) return;
  batch.forEach((t) => enrichmentPending.add(C.key(t)));
  try {
    const result = await api("/api/batch_enrich", {
      method: "POST",
      body: JSON.stringify({ tracks: batch }),
    });
    (result.tracks || []).forEach(updateTrackMetadata);
  } catch {
  } finally {
    batch.forEach((t) => enrichmentPending.delete(C.key(t)));
  }
}
const artworkObserver = new IntersectionObserver(
  (entries) => {
    const tracks = entries
      .filter((entry) => entry.isIntersecting)
      .map((entry) => {
        artworkObserver.unobserve(entry.target);
        return find(entry.target.dataset.art);
      })
      .filter(Boolean);
    for (let i = 0; i < tracks.length; i += 18)
      enrichTracks(tracks.slice(i, i + 18));
  },
  { rootMargin: "220px" },
);
function enrichVisible() {
  document
    .querySelectorAll("[data-art]")
    .forEach((el) => artworkObserver.observe(el));
  document.querySelectorAll("[data-artist-image]").forEach(async (el) => {
    const name = el.dataset.artistImage;
    try {
      const data = await api(`/api/artist_image?q=${encodeURIComponent(name)}`);
      const url = C.safeUrl(data.image_url, true);
      if (url && el.isConnected)
        el.innerHTML = `<img src="${esc(url)}" alt="" loading="lazy">`;
    } catch {}
  });
}
async function recordListening() {
  if (!playing || playedSeconds < 5 || !listenId) return;
  const track = playing,
    seconds = playedSeconds,
    duration = audio?.duration || 30,
    event_id = listenId,
    user = listenUser;
  try {
    await api("/api/listen", {
      method: "POST",
      body: JSON.stringify({ user, track, seconds, duration, event_id }),
    });
    if (user === state.user) {
      state.homeDirty = true;
      if (seconds / duration >= .7) state.tasteRevision++;
    }
  } catch {}
}
function playerState(isPlaying) {
  $("playerToggle").innerHTML = isPlaying ? icons.pause : icons.play;
  $("playerToggle").setAttribute(
    "aria-label",
    isPlaying ? "Pause preview" : "Play preview",
  );
}
async function playTrack(track, queue = null, selectedIndex = null) {
  if (!track) return;
  if (playing && C.key(playing) === C.key(track) && audio && !queue) {
    togglePlay();
    return;
  }
  await recordListening();
  if (audio) {
    audio.pause();
    audio.src = "";
  }
  audio = null;
  const token = ++audioGeneration;
  if (queue) {
    radioLoading = false;
    playQueue = queue.slice();
    queueIndex =
      selectedIndex ?? playQueue.findIndex((t) => C.key(t) === C.key(track));
  } else {
    playQueue = [track];
    queueIndex = 0;
    populateRadioQueue(track, token, queueRevision);
  }
  playing = { ...(state.tracks.get(C.key(track)) || track) };
  $("player").hidden = false;
  document.body.classList.add("has-player");
  $("playerTitle").textContent = track.name;
  $("playerArtist").textContent = track.artist;
  $("seek").value = 0;
  $("elapsed").textContent = "0:00";
  $("duration").textContent = "—";
  $("playerArt").innerHTML = art(playing);
  $("previewLabel").textContent = "Finding preview…";
  $("playerToggle").innerHTML = icons.loading;
  $("playerToggle").disabled = true;
  updateSaveButtons();
  if (!playing.deezer_preview_url) {
    await enrichTracks([playing]);
    if (token !== audioGeneration) return;
    playing = { ...playing, ...state.tracks.get(C.key(track)) };
  }
  const url = C.safeUrl(playing.deezer_preview_url, true);
  if (!url) {
    $("playerToggle").disabled = false;
    playerState(false);
    $("previewLabel").textContent = "No preview";
    toast(
      "No preview is available for this song. You can open it from the song menu.",
    );
    return;
  }
  audio = new Audio(url);
  audio.volume = Number($("volume").value);
  playedSeconds = 0;
  lastAudioTime = 0;
  listenId = crypto.randomUUID();
  listenUser = state.user;
  $("playerArt").innerHTML = art(playing);
  $("playerToggle").disabled = false;
  $("previewLabel").textContent = "Preview";
  const thisAudio = audio;
  audio.addEventListener("loadedmetadata", () => {
    if (audio !== thisAudio) return;
    $("seek").max = audio.duration || 30;
    $("duration").textContent = C.time(audio.duration || 30);
    $("previewLabel").textContent = Number.isFinite(audio.duration) ? `${Math.round(audio.duration)} sec preview` : "Preview";
  });
  audio.addEventListener("timeupdate", () => {
    if (audio !== thisAudio) return;
    const delta = audio.currentTime - lastAudioTime;
    if (delta > 0 && delta < 2) playedSeconds += delta;
    lastAudioTime = audio.currentTime;
    $("seek").value = audio.currentTime;
    $("elapsed").textContent = C.time(audio.currentTime);
  });
  audio.addEventListener("play", () => {
    if (audio === thisAudio) playerState(true);
  });
  audio.addEventListener("pause", () => {
    if (audio === thisAudio) {
      playerState(false);
      recordListening();
    }
  });
  audio.addEventListener("ended", () => {
    if (audio === thisAudio) {
      recordListening();
      nextTrack(1, true);
    }
  });
  audio.addEventListener("error", () => {
    if (audio === thisAudio) {
      playerState(false);
      $("previewLabel").textContent = "Preview unavailable";
      toast("This preview couldn’t play. Try opening the song from its menu.");
    }
  });
  try {
    await audio.play();
  } catch {
    if (audio === thisAudio) {
      playerState(false);
      toast("Tap play to start this preview.");
    }
  }
}
function togglePlay() {
  if (!audio) return playing ? playTrack(playing, playQueue) : undefined;
  if (audio.paused)
    audio.play().catch(() => toast("This preview couldn’t start. Try again."));
  else audio.pause();
}
function nextTrack(direction, automatic = false) {
  const next = queueIndex + direction;
  if (next < 0 || next >= playQueue.length) {
    if (!automatic) toast("You’ve reached the end of this queue.");
    return;
  }
  queueIndex = next;
  playTrack(playQueue[next], playQueue, next);
}
async function populateRadioQueue(track, token, revision) {
  radioLoading = true;
  try {
    const cached = state.recommendationMode === "flow" && state.recommendationRevision === state.tasteRevision && C.key(state.recommendation?.facts || {}) === C.key(track) ? state.recommendation : null;
    const data = cached || await api("/api/recommend", {
      method: "POST",
      body: JSON.stringify({seed_track: track, user: state.user, mode: "flow", limit: 24}),
    });
    if (token !== audioGeneration || revision !== queueRevision) return;
    playQueue = C.unique([track, ...(data.recs || [])]).filter((t, i) => i === 0 || C.signal(state.profile.history, t) !== "dislike");
    playQueue.forEach(register);
    queueIndex = 0;
  } catch {
    if (token === audioGeneration) announce("Flow is unavailable. You can still add songs to the queue.");
  } finally {
    if (token === audioGeneration) {
      radioLoading = false;
      if ($("appDialog").open && $("dialogTitle").textContent === "Up next") {
        $("dialogBody").innerHTML = queueMarkup();
        enrichVisible();
      }
    }
  }
}
function queueMarkup() {
  return (radioLoading ? '<p class="loading-label" role="status">Building your Flow…</p>' : "") + (playQueue.length
    ? `<ol class="queue-list">${playQueue.map((track, i) => `<li aria-current="${i === queueIndex}"><button data-action="queue-play" data-index="${i}" data-track="${register(track)}"><span class="list-art" data-art="${register(track)}">${art(track)}</span><span><strong>${esc(track.name)}</strong><small>${esc(credits(track))}${track.duration_seconds ? " · " + C.time(track.duration_seconds) : ""}</small></span></button></li>`).join("")}</ol>`
    : '<p class="dialog-description">Play a song to start a queue.</p>');
}
function showQueue() {
  showDialog("Up next", queueMarkup());
  enrichVisible();
}
async function switchUser(name) {
  await recordListening();
  if (audio) {
    audio.pause();
    audio.src = "";
  }
  audio = null;
  playing = null;
  playQueue = [];
  radioLoading = false;
  queueRevision++;
  audioGeneration++;
  $("player").hidden = true;
  document.body.classList.remove("has-player");
  profileGate.cancel();
  pageGate.cancel();
  state.user = name || anonymousIdentity;
  state.profile = { history: [], recent: [] };
  state.home = null;
  state.editorial = null;
  state.homeDirty = true;
  state.pending.clear();
  state.recommendation = null;
  state.tracks.clear();
  state.registry.clear();
  state.serial = 0;
  albums.clear();
  playlistItems.clear();
  localStorage.setItem("soundvector_user", state.user);
  setNav("home");
  closeDialog();
  try {
    await loadProfile();
  } catch (error) {
    toast(error.message);
  }
  route("home");
}
function showProfile() {
  showDialog(
    "Your listening space",
    `<p class="dialog-description">A name keeps your saved songs and listening together on this server.</p><form class="dialog-form" id="profileForm"><label for="profileInput">Listening profile</label><input id="profileInput" value="${esc(state.user.startsWith("guest_") ? "" : state.user)}" placeholder="Your name" autocomplete="nickname" maxlength="80" required><button class="primary-button" type="submit">Continue listening</button></form><p class="quiet-label" style="margin-top:18px">This is a listening profile, not a password-protected account.</p>`,
  );
}
function parseRoute() {
  if (location.hash && !location.hash.startsWith("#/")) {
    if (!$("mainContent").children.length) route("home", {}, false);
    return;
  }
  const [path, query] = location.hash.replace(/^#\/?/, "").split("?");
  const params = Object.fromEntries(new URLSearchParams(query || ""));
  route(
    path || "home",
    history.state?.view === path
      ? { ...history.state.params, ...params }
      : params,
    false,
  );
}
// All controls share semantic, keyboard-operable buttons and one action dispatcher.
document.addEventListener("click", async (event) => {
  if (event.target.closest(".skip-link")) {
    event.preventDefault();
    $("mainContent").focus({ preventScroll: true });
    $("mainContent").scrollIntoView({ block: "start" });
    return;
  }
  const navigation = event.target.closest("a[data-view]");
  if (navigation && navigation.dataset.view === state.view) {
    event.preventDefault();
    if (state.view === "home" && state.homeDirty) route("home", {}, false);
    else window.scrollTo({ top: 0, behavior: "instant" });
    return;
  }
  const target = event.target.closest("[data-action]");
  if (!target) {
    if (!event.target.closest(".search-wrap")) closeSuggestions();
    return;
  }
  const action = target.dataset.action,
    track = find(target.dataset.track);
  if (action !== "track-menu" && $("trackPopover").matches(":popover-open"))
    closeTrackMenu();
  if (
    ["similar", "artist", "album", "mood", "play"].includes(action) &&
    $("appDialog").open
  )
    closeDialog();
  if (action === "save" && track)
    feedback(track, isSaved(track) ? "none" : "like");
  else if (["dislike", "hide-song"].includes(action) && track) {
    closeDialog();
    feedback(
      track,
      C.signal(state.profile.history, track) === "dislike" ? "none" : "dislike",
    );
  } else if (action === "similar" && track)
    route("recommend", recommendationParams(track));
  else if (action === "artist")
    route("artist", { name: target.dataset.artist });
  else if (action === "album") {
    const album = albums.get(target.dataset.album);
    if (album)
      route("album", {
        title: album.title,
        artist: album.artist || "",
        id: String(album.id || ""),
        source: album.source || "",
      });
  } else if (action === "play" && track) playTrack(track);
  else if (action === "track-menu" && track) showTrackMenu(track, target);
  else if (action === "playlist") {
    const item=playlistItems.get(`${target.dataset.source}:${target.dataset.id}`);
    route("playlist", { id: target.dataset.id, source: target.dataset.source, url: item?.url || "" });
  }
  else if (action === "play-trending")
    playTrack(
      state.editorial.trending.tracks[0],
      state.editorial.trending.tracks,
    );
  else if (action === "details" && track) showDetails(track);
  else if (action === "song-album" && track) openSongAlbum(track, target);
  else if (action === "insights" && track)
    showInsights(track, target.dataset.refresh === "true");
  else if (action === "queue-next" && track) queueSong(track, true);
  else if (action === "queue-add" && track) queueSong(track);
  else if (action === "player-dislike" && playing)
    feedback(
      playing,
      C.signal(state.profile.history, playing) === "dislike"
        ? "none"
        : "dislike",
    );
  else if (action === "player-insights" && playing) showInsights(playing);
  else if (action === "player-menu" && playing) showTrackMenu(playing);
  else if (action === "clear-search") {
    $("searchInput").value = "";
    target.hidden = true;
    closeSuggestions();
    $("searchInput").focus();
  } else if (action === "profile") showProfile();
  else if (action === "flow-why") {
    const track=find(target.dataset.track);
    if (track?.flow_reasons?.length) showDialog("Why this song?", `<p class="dialog-description"><strong>${esc(track.name)}</strong> in SoundVector Flow</p><ul class="flow-reasons">${track.flow_reasons.map(reason=>`<li>${esc(reason)}</li>`).join("")}</ul><p class="quiet-label">Saving songs and completing previews helps Flow learn what you enjoy.</p>`);
  }
  else if (action === "close-dialog") closeDialog();
  else if (action === "back") {
    if (history.state) history.back();
    else route("home");
  } else if (action === "retry") route(state.view, state.params, false);
  else if (action === "refresh-home") {
    state.homeDirty = true;
    route("home", {}, false);
  } else if (action === "search-filter") {
    state.searchFilter = target.dataset.value;
    renderSearch();
    enrichVisible();
    $("mainContent")
      .querySelector(`[data-value="${state.searchFilter}"]`)
      ?.focus();
  } else if (action === "library-filter") {
    state.libraryFilter = target.dataset.value;
    renderLibrary();
    enrichVisible();
    $("mainContent")
      .querySelector(`[data-value="${state.libraryFilter}"]`)
      ?.focus();
  } else if (action === "recommend-mode")
    route("recommend", { ...state.params, mode: target.dataset.value }, false);
  else if (action === "show-more") {
    state.shown += 30;
    if (state.view === "artist") renderArtist();
    else renderLibrary();
    enrichVisible();
  } else if (action === "mood")
    route("mix", {
      q: target.dataset.query,
      title: target.querySelector("strong")?.textContent || "",
    });
  else if (action === "play-section") {
    const tracks =
      state.home.sections[Number(target.dataset.section)]?.tracks || [];
    playTrack(tracks[0], tracks);
  } else if (action === "play-library") {
    const tracks = state.profile.history.filter((t) => t.signal === "like");
    playTrack(tracks[0], tracks);
  } else if (action === "play-artist")
    playTrack(state.artist.tracks[0], state.artist.tracks);
  else if (action === "play-album")
    playTrack(state.album.tracks[0], state.album.tracks);
  else if (action === "play-mix")
    playTrack(state.mood.tracks[0], state.mood.tracks);
  else if (action === "toggle-play") togglePlay();
  else if (action === "next") nextTrack(1);
  else if (action === "previous") nextTrack(-1);
  else if (action === "player-save" && playing)
    feedback(playing, isSaved(playing) ? "none" : "like");
  else if (action === "queue") showQueue();
  else if (action === "queue-play" && track) {
    closeDialog();
    playTrack(track, playQueue, Number(target.dataset.index));
  } else if (action === "undo") {
    $("toast").undoAction?.();
    $("toast").hidden = true;
  } else if (action === "how-home")
    showDialog(
      "How recommendations work",
      '<p class="dialog-description">Saved songs are the strongest signal. Completed previews add a lighter signal. Your rotation blends several songs rather than relying on one artist, and songs you hide stay out.</p><p class="quiet-label">A song’s language is only used when recording-level metadata confirms it. An artist’s genre is not a song language.</p>',
    );
  else if (action === "suggestion") {
    chooseSuggestion(Number(target.dataset.index));
  }
});
function chooseSuggestion(index) {
  const item = suggestItems[index];
  if (!item) return;
  closeSuggestions();
  if (item.kind === "song")
    route("recommend", recommendationParams(item.track));
  else route("artist", { name: item.artist });
}
function suggestionData(data) {
  const previous = suggestionIndex >= 0 ? suggestItems[suggestionIndex] : null;
  suggestItems = [
    ...(data.results || [])
      .slice(0, 6)
      .map((track) => ({ kind: "song", track })),
    ...(data.artists || [])
      .slice(0, 2)
      .map((a) => ({ kind: "artist", artist: a.artist })),
  ];
  if (previous)
    suggestionIndex = suggestItems.findIndex(
      (item) =>
        item.kind === previous.kind &&
        (item.kind === "song"
          ? C.key(item.track) === C.key(previous.track)
          : item.artist === previous.artist),
    );
  $("searchSuggestions").innerHTML =
    suggestItems
      .map(
        (item, i) =>
          `<div class="suggestion" role="option" id="suggestion-${i}" aria-selected="${i === suggestionIndex}" data-action="suggestion" data-index="${i}">${item.kind === "song" ? art(item.track) : art({ artist: item.artist })}<span class="suggestion-info"><strong>${esc(item.kind === "song" ? item.track.name : item.artist)}</strong><small>${esc(item.kind === "song" ? credits(item.track) : "Artist")}</small></span><span class="suggestion-type">${item.kind === "song" && item.track.duration_seconds ? C.time(item.track.duration_seconds) : item.kind === "song" ? "Song" : "Artist"}</span></div>`,
      )
      .join("") +
    (data.pending
      ? '<p class="suggestion-status">Searching services…</p>'
      : !suggestItems.length
        ? '<p class="suggestion-status">No matches yet. Try a title or artist.</p>'
        : "");
  $("searchSuggestions").hidden = false;
  $("searchInput").setAttribute("aria-expanded", "true");
}
async function updateSearchPage(query, ticket, signal) {
  for (let i = 0; i < 60; i++) {
    try {
      const data = await api(
        `/api/search?q=${encodeURIComponent(query)}&quick=true`,
        { signal },
      );
      if (!pageGate.valid(ticket) || state.view !== "search") return;
      const focused = document.activeElement?.dataset.value;
      state.results = data;
      renderSearch();
      enrichVisible();
      if (focused)
        document
          .querySelector(
            `[data-action="search-filter"][data-value="${focused}"]`,
          )
          ?.focus({ preventScroll: true });
      if (!data.pending) return;
      await new Promise((resolve) => setTimeout(resolve, 250));
    } catch (error) {
      if (error.name !== "AbortError") announce(error.message);
      return;
    }
  }
}
$("searchInput").addEventListener("input", () => {
  closeSuggestions();
  if (suggestionController) suggestionController.abort();
  suggestionController = new AbortController();
  const signal = suggestionController.signal,
    query = $("searchInput").value.trim();
  if (query.length < 2) return;
  const token = searchGate.next();
  const valid = () =>
    searchGate.valid(token) &&
    $("searchInput").value.trim() === query &&
    !signal.aborted;
  if (suggestionCache.has(query.toLowerCase()))
    suggestionData(suggestionCache.get(query.toLowerCase()));
  searchTimer = setTimeout(async () => {
    try {
      const local = await api(
        `/api/search?q=${encodeURIComponent(query)}&quick=true&live=false`,
        { signal },
      );
      if (!valid()) return;
      suggestionData({ ...local, pending: true });
      await new Promise((resolve) => setTimeout(resolve, 160));
      for (let i = 0; i < 68 && valid(); i++) {
        const data = await api(
          `/api/search?q=${encodeURIComponent(query)}&quick=true`,
          { signal },
        );
        if (!valid()) return;
        suggestionData(data);
        if (!data.pending) {
          suggestionCache.set(query.toLowerCase(), data);
          if (suggestionCache.size > 60)
            suggestionCache.delete(suggestionCache.keys().next().value);
          break;
        }
        await new Promise((resolve) => setTimeout(resolve, 220));
      }
    } catch {}
  }, 70);
});
$("searchInput").addEventListener("keydown", (event) => {
  if (event.isComposing) return;
  if (event.key === "Escape") closeSuggestions();
  else if (
    ["ArrowDown", "ArrowUp"].includes(event.key) &&
    suggestItems.length
  ) {
    event.preventDefault();
    suggestionIndex =
      (suggestionIndex +
        (event.key === "ArrowDown" ? 1 : -1) +
        suggestItems.length) %
      suggestItems.length;
    document
      .querySelectorAll(".suggestion")
      .forEach((el, i) =>
        el.setAttribute("aria-selected", i === suggestionIndex),
      );
    $("searchInput").setAttribute(
      "aria-activedescendant",
      `suggestion-${suggestionIndex}`,
    );
    $(`suggestion-${suggestionIndex}`)?.scrollIntoView({ block: "nearest" });
  } else if (event.key === "Enter" && suggestionIndex >= 0) {
    event.preventDefault();
    chooseSuggestion(suggestionIndex);
  }
});
$("searchForm").addEventListener("submit", (event) => {
  event.preventDefault();
  const q = $("searchInput").value.trim();
  if (q) route("search", { q });
});
document.addEventListener("submit", (event) => {
  if (event.target.id === "profileForm") {
    event.preventDefault();
    const name = $("profileInput").value.trim();
    if (name) switchUser(name);
  }
  if (event.target.id === "moodForm") {
    event.preventDefault();
    const q = $("moodPrompt").value.trim();
    if (q) route("mix", { q });
  }
});
document.addEventListener("keydown", (event) => {
  const tag = document.activeElement?.tagName;
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    $("searchInput").focus();
    $("searchInput").select();
  }
  if (event.key === "Escape") closeSuggestions();
  if (
    event.code === "Space" &&
    !["INPUT", "TEXTAREA", "BUTTON", "A", "SELECT"].includes(tag) &&
    audio &&
    !$("appDialog").open
  ) {
    event.preventDefault();
    togglePlay();
  }
  if (
    event.target.getAttribute("role") === "tab" &&
    ["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)
  ) {
    event.preventDefault();
    const list = [
      ...event.target.parentElement.querySelectorAll('[role="tab"]'),
    ];
    let i = list.indexOf(event.target);
    i =
      event.key === "Home"
        ? 0
        : event.key === "End"
          ? list.length - 1
          : (i + (event.key === "ArrowRight" ? 1 : -1) + list.length) %
            list.length;
    list[i].focus();
    list[i].click();
  }
});
document.addEventListener(
  "error",
  (event) => {
    const image = event.target;
    if (image.tagName === "IMG" && image.parentElement) {
      image.hidden = true;
      if (!image.parentElement.querySelector(".art-placeholder"))
        image.parentElement.insertAdjacentHTML(
          "afterbegin",
          `<span class="art-placeholder" aria-hidden="true">${icons.music}</span>`,
        );
    }
  },
  true,
);
$("trackPopover").addEventListener("toggle", (event) => {
  if (event.newState === "closed") menuAnchor?.setAttribute?.("aria-expanded", "false");
});
$("seek").addEventListener("input", (event) => {
  if (audio) {
    audio.currentTime = Number(event.target.value);
    lastAudioTime = audio.currentTime;
  }
});
$("volume").addEventListener("input", (event) => {
  if (audio) audio.volume = Number(event.target.value);
});
$("appDialog").addEventListener("click", (event) => {
  if (event.target === $("appDialog")) {
    const box = $("appDialog").getBoundingClientRect();
    if (
      event.clientX < box.left ||
      event.clientX > box.right ||
      event.clientY < box.top ||
      event.clientY > box.bottom
    )
      closeDialog();
  }
});
$("appDialog").addEventListener("close", () => {
  if (!$("appDialog").open) dialogFocus?.focus?.();
});
window.addEventListener("popstate", parseRoute);
window.addEventListener("hashchange", () => {
  if (
    !history.state ||
    location.hash !==
      `#/${state.view}${new URLSearchParams(state.params).size ? "?" + new URLSearchParams(state.params) : ""}`
  )
    parseRoute();
});
window.addEventListener("pagehide", () => {
  if (playing && playedSeconds >= 5)
    fetch("/api/listen", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      keepalive: true,
      body: JSON.stringify({
        user: listenUser,
        track: playing,
        seconds: playedSeconds,
        duration: audio?.duration || 30,
        event_id: listenId,
      }),
    }).catch(() => {});
});
for (const el of document.querySelectorAll("[data-icon]"))
  el.innerHTML = icons[el.dataset.icon] || "";
(async function init() {
  setNav("home");
  try {
    await loadProfile();
  } catch {}
  parseRoute();
})();

$("appDialog").addEventListener("close", () => {
  albumGate.cancel();
  insightGate.cancel();
  $("appDialog").classList.remove("insights-dialog", "details-dialog");
});
$("searchInput").addEventListener("input", () => {
  document.querySelector(".search-clear").hidden = !$("searchInput").value;
});

document.addEventListener("keydown", (event) => {
  const pop = $("trackPopover");
  if (!pop.matches(":popover-open")) return;
  const items = [...pop.querySelectorAll('[role="menuitem"]')];
  const index = items.indexOf(document.activeElement);
  if (event.key === "Escape") {
    event.preventDefault();
    closeTrackMenu();
  } else if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
    event.preventDefault();
    const next =
      event.key === "Home"
        ? 0
        : event.key === "End"
          ? items.length - 1
          : (index + (event.key === "ArrowDown" ? 1 : -1) + items.length) %
            items.length;
    items[next]?.focus();
  }
});
document.addEventListener(
  "error",
  (event) => {
    const img = event.target;
    if (img.tagName !== "IMG") return;
    const holder = img.closest("[data-art]");
    const t = holder ? find(holder.dataset.art) : null;
    img.remove();
    if (holder && t) {
      const copy = { ...t, deezer_album_art: "", cover_art: "" };
      holder.insertAdjacentHTML("afterbegin", art(copy));
    }
  },
  true,
);
