// =============================================================
// BUILD VERSION — increment this on every deploy.
// Changing this value forces all users to reload fresh assets
// and clears any stale localStorage state from the old build.
// =============================================================
const BUILD_VERSION = '2.7';

(function _clearStaleBuildCache() {
    const STORE_KEY = 'soundvector_build_version';
    const stored = localStorage.getItem(STORE_KEY);
    if (stored !== BUILD_VERSION) {
        // New build detected — wipe all SoundVector cache keys EXCEPT the user login
        const savedUser = localStorage.getItem('soundvector_user');
        // Clear everything in localStorage that belongs to SoundVector
        Object.keys(localStorage).forEach(k => {
            if (k.startsWith('soundvector_')) localStorage.removeItem(k);
        });
        // Re-persist login so user isn't logged out on upgrade
        if (savedUser) localStorage.setItem('soundvector_user', savedUser);
        // Mark the new version so we don't clear again until next deploy
        localStorage.setItem(STORE_KEY, BUILD_VERSION);
        // Also clear sessionStorage entirely for a clean slate
        sessionStorage.clear();
    }
})();

let API_BASE = "";


let currentMode = 'similar';
let currentSearchType = 'track';
let currentUser = 'Guest';
let searchTimeout = null;
let profileDataCache = [];
let currentRecData = null;
let currentArtistName = null;
let currentView = 'home';
let currentSeedFacts = null;  // seed track facts for why-rec

// Audio player state
let currentAudio = null;
let currentPlayingRow = null;

// Playlist generator state
let playlistGenerating = false;

let suggestions = [];
let artistSuggestions = [];
let activeSuggestionIdx = -1;

// SVG Icon Templates
const SVG_ICONS = {
    like: `<svg class="btn-svg-icon" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"></path></svg>`,
    dislike: `<svg class="btn-svg-icon" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h3a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-3"></path></svg>`,
    skip: `<svg class="btn-svg-icon" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 4 15 12 5 20 5 4"></polygon><line x1="19" y1="5" x2="19" y2="19"></line></svg>`,
    explore: `<svg class="btn-svg-icon" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"></polygon></svg>`,
    sparkle: `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2l2.09 6.26L20 10l-5.91 1.74L12 18l-2.09-6.26L4 10l5.91-1.74z"/></svg>`,
    play: `<svg class="btn-svg-icon" viewBox="0 0 24 24" width="11" height="11" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>`,
    pause: `<svg class="btn-svg-icon" viewBox="0 0 24 24" width="11" height="11" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>`,
    deezer: `<svg class="btn-svg-icon" viewBox="0 0 24 24" width="12" height="12" fill="currentColor"><rect x="18" y="6" width="3" height="12" rx="1"/><rect x="13" y="10" width="3" height="8" rx="1"/><rect x="8" y="13" width="3" height="5" rx="1"/><rect x="3" y="8" width="3" height="10" rx="1"/></svg>`,
    youtube: `<svg class="btn-svg-icon" viewBox="0 0 24 24" width="12" height="12" fill="currentColor"><path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/></svg>`,
    lastfm: `<svg class="btn-svg-icon" viewBox="0 0 24 24" width="12" height="12" fill="currentColor"><path d="M10.9 16.9l-.8-2.2s-1.3 1.5-3.2 1.5c-1.7 0-2.9-1.5-2.9-3.8 0-3 1.5-4.1 3-4.1 2.1 0 2.8 1.4 3.4 3.2l.8 2.4c.8 2.4 2.2 4.3 6.4 4.3 3 0 5-1 5-3.5 0-2-1.1-3.1-3.2-3.6l-1.6-.4c-1.1-.3-1.4-.7-1.4-1.5 0-.9.7-1.4 1.8-1.4 1.2 0 1.9.5 2 1.7l2.6-.3c-.2-2.4-1.9-3.4-4.5-3.4-2.3 0-4.5 1-4.5 3.7 0 1.7.8 2.9 2.8 3.4l1.7.4c1.3.3 1.7.9 1.7 1.6 0 1-.9 1.5-2.3 1.5-2.2 0-3.2-1.2-3.7-2.8l-.8-2.4C11.1 8.5 9.6 6.5 6 6.5 2.2 6.5 0 9.1 0 12.4c0 3.2 1.7 5.7 5.7 5.7 2.3 0 3.9-.8 4.8-1.7.4.5.7.9 1.5 1.5l1.6-1.6c-.7-.4-1.2-.8-1.7-1.3"/></svg>`,
    playlist: `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>`,
    trash: `<svg class="btn-svg-icon" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>`,
};

// Genre color mapping
const GENRE_COLORS = {
    'pop': 'pop', 'rock': 'rock', 'hip hop': 'hip-hop', 'hip-hop': 'hip-hop', 'rap': 'hip-hop',
    'edm': 'edm', 'electronic': 'edm', 'r&b': 'rnb', 'rnb': 'rnb', 'soul': 'soul',
    'latin': 'latin', 'country': 'country', 'jazz': 'jazz', 'classical': 'classical',
    'metal': 'metal', 'filmi': 'filmi', 'bollywood': 'filmi', 'lo-fi': 'lo-fi', 'lofi': 'lo-fi',
};

function getGenreClass(genre) {
    const lower = genre.toLowerCase();
    for (const [key, cls] of Object.entries(GENRE_COLORS)) {
        if (lower.includes(key)) return cls;
    }
    return 'default';
}

function escapeAttr(str) {
    if (!str) return '';
    return String(str).replace(/&/g, '&amp;').replace(/"/g, '&quot;');
}

function escapeJs(str) {
    if (!str) return '';
    return String(str)
        .replace(/\\/g, '\\\\')
        .replace(/'/g, "\\'")
        .replace(/"/g, '&quot;')
        .replace(/\n/g, '\\n')
        .replace(/\r/g, '\\r');
}

function getTrackKey(name, artist) {
    if (!name || !artist) return '';
    return `${name.toLowerCase().trim()}||${artist.toLowerCase().trim()}`;
}


// ---------------------------------------------------------
// Search Mode Toggle
// ---------------------------------------------------------
function setSearchType(type) {
    currentSearchType = type;
    document.getElementById('typeTrackBtn').classList.toggle('active', type === 'track');
    document.getElementById('typeNlpBtn').classList.toggle('active', type === 'nlp');

    const input = document.getElementById('searchInput');
    if (type === 'nlp') {
        input.placeholder = "Describe your mood (e.g. telugu gym songs, sad rainy night)...";
        hideSuggestions();
    } else {
        input.placeholder = "Search songs, artists, or describe a mood...";
    }
}

// ---------------------------------------------------------
// Navigation
// ---------------------------------------------------------
function goHome() {
    currentView = 'home';
    closeMobileInsights();
    document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.view-panel').forEach(v => v.classList.add('hidden'));
    const navH = document.getElementById('navHome');
    if (navH) navH.classList.add('active');
    const navHM = document.getElementById('navHomeMobile');
    if (navHM) navHM.classList.add('active');
    document.getElementById('viewHome').classList.remove('hidden');
    loadHomePage();
}

function switchTab(tabId) {
    currentView = tabId;
    closeMobileInsights();
    document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.view-panel').forEach(v => v.classList.add('hidden'));

    if (tabId === 'discover') {
        const navD = document.getElementById('navDiscover');
        if (navD) navD.classList.add('active');
        const navDM = document.getElementById('navDiscoverMobile');
        if (navDM) navDM.classList.add('active');
        document.getElementById('viewDiscover').classList.remove('hidden');
        if (currentRecData && currentRecData.recs && currentRecData.recs.length > 0) {
            renderMainData(currentRecData);
            renderIntelPanel(currentRecData.intel, currentRecData.backend, currentRecData.facts);
        } else {
            if (searchInput) searchInput.value = '';
            loadBrowseAllGrid();
        }
    } else if (tabId === 'artist') {
        document.getElementById('viewArtist').classList.remove('hidden');
    } else if (tabId === 'album') {
        document.getElementById('viewAlbum').classList.remove('hidden');
    } else if (tabId === 'playlist') {
        document.getElementById('viewPlaylist').classList.remove('hidden');
    } else if (tabId === 'home') {
        goHome();
        return;
    } else {
        const navM = document.getElementById('navMySongs');
        if (navM) navM.classList.add('active');
        const navMM = document.getElementById('navMySongsMobile');
        if (navMM) navMM.classList.add('active');
        document.getElementById('viewMySongs').classList.remove('hidden');
        loadMySongs();
    }
}

// ---------------------------------------------------------
// Sidebar Collapse / Expand
// ---------------------------------------------------------
function toggleLeftSidebar() {
    const sidebar = document.querySelector('.sidebar');
    const mainBody = document.querySelector('.main-body');
    if (!sidebar || !mainBody) return;
    sidebar.classList.toggle('collapsed');
    mainBody.classList.toggle('left-collapsed');
}

function toggleRightSidebar() {
    const djSidebar = document.querySelector('.dj-sidebar');
    const mainBody = document.querySelector('.main-body');
    const reopenTab = document.getElementById('insightsReopenTab');
    if (!djSidebar || !mainBody) return;

    const isCollapsed = djSidebar.classList.toggle('collapsed');
    mainBody.classList.toggle('right-collapsed', isCollapsed);
    if (reopenTab) reopenTab.style.display = isCollapsed ? 'flex' : 'none';
}

function openMobileInsights() {
    const trackNameEl = document.getElementById('playerTrackName');
    const artistNameEl = document.getElementById('playerArtistName');
    
    if (currentPlayingRow !== null && trackNameEl && trackNameEl.innerText && trackNameEl.innerText !== 'Audio Preview') {
        selectTrackForInsights(currentPlayingRow, trackNameEl.innerText, artistNameEl ? artistNameEl.innerText : '', null);
        return;
    }

    const modal = document.getElementById('mobileInsightsModal');
    const body = document.getElementById('mobileInsightsBody');
    if (!modal || !body) return;
    const sheetTitle = modal.querySelector('.sheet-header h3');
    if (sheetTitle) sheetTitle.textContent = 'Track Insights & Taste';

    document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
    const navIM = document.getElementById('navIntelMobile');
    if (navIM) navIM.classList.add('active');

    const pBox = document.querySelector('.profile-box');
    const djSidebar = document.querySelector('.dj-sidebar');

    body.innerHTML = '';
    
    if (pBox) {
        const pClone = pBox.cloneNode(true);
        pClone.id = (pClone.id || 'profileBox') + '_mobile';
        pClone.style.marginBottom = '16px';
        pClone.classList.remove('hidden');
        body.appendChild(pClone);
    }
    
    if (djSidebar) {
        const panels = djSidebar.querySelectorAll('.panel-box');
        panels.forEach((p, idx) => {
            const pClone = p.cloneNode(true);
            pClone.id = p.id ? p.id + '_mobile' : 'dj_panel_mobile_' + idx;
            pClone.style.marginBottom = '16px';
            pClone.classList.remove('hidden');
            body.appendChild(pClone);
        });
    }

    modal.classList.remove('hidden');
    modal.classList.add('open');
}

function closeMobileInsights() {
    const modal = document.getElementById('mobileInsightsModal');
    if (modal) {
        modal.classList.add('hidden');
        modal.classList.remove('open');
    }
}

function closeMobileInsightsOnBackdrop(e) {
    if (e.target && e.target.id === 'mobileInsightsModal') {
        closeMobileInsights();
    }
}

// ---------------------------------------------------------
// User Profile
// ---------------------------------------------------------
const currentUserDisplay = document.getElementById('currentUserDisplay');
const profilePillBtn = document.getElementById('profilePillBtn');
const profilePillWrap = document.getElementById('profilePillWrap');
const profileDropdown = document.getElementById('profileDropdown');
const logoutBtn = document.getElementById('logoutBtn');
const deleteUserBtn = document.getElementById('deleteUserBtn');
const loginModal = document.getElementById('loginModal');
const loginForm = document.getElementById('loginForm');
const loginInput = document.getElementById('loginInput');

// Profile dropdown menu toggle
if (profilePillBtn && profileDropdown) {
    profilePillBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        const isOpen = !profileDropdown.classList.contains('hidden');
        if (isOpen) {
            profileDropdown.classList.add('hidden');
            if (profilePillWrap) profilePillWrap.classList.remove('open');
        } else {
            profileDropdown.classList.remove('hidden');
            if (profilePillWrap) profilePillWrap.classList.add('open');
        }
    });

    document.addEventListener('click', (e) => {
        if (profilePillWrap && !profilePillWrap.contains(e.target)) {
            profileDropdown.classList.add('hidden');
            profilePillWrap.classList.remove('open');
        }
    });
}

function checkAuth() {
    const storedUser = localStorage.getItem('soundvector_user');
    if (!storedUser) {
        currentUser = 'Guest';
        if (currentUserDisplay) currentUserDisplay.innerText = currentUser;
        const profileCardUser = document.getElementById('profileCardUser');
        if (profileCardUser) profileCardUser.innerText = currentUser;
        if (loginModal) loginModal.classList.add('open');
        setTimeout(() => { if (loginInput) loginInput.focus(); }, 100);
    } else {
        currentUser = storedUser;
        if (loginModal) loginModal.classList.remove('open');
        onUserChanged();
    }
}

async function loadUsers() {
    checkAuth();
}

if (loginForm) {
    loginForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const name = loginInput.value.trim();
        if (!name) return;
        localStorage.setItem('soundvector_user', name);
        if (loginModal) loginModal.classList.remove('open');
        checkAuth();
    });
}

if (logoutBtn) {
    logoutBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        if (profileDropdown) profileDropdown.classList.add('hidden');
        if (profilePillWrap) profilePillWrap.classList.remove('open');
        localStorage.removeItem('soundvector_user');
        if (loginInput) loginInput.value = '';
        showToast("Logged out successfully.");
        checkAuth();
    });
}

if (deleteUserBtn) {
    deleteUserBtn.addEventListener('click', async (e) => {
        e.stopPropagation();
        if (profileDropdown) profileDropdown.classList.add('hidden');
        if (profilePillWrap) profilePillWrap.classList.remove('open');

        if (!currentUser || currentUser === 'Guest') {
            showToast("No active profile to delete.", "error");
            return;
        }

        if (!confirm(`Are you sure you want to completely delete the profile for '${currentUser}'? This cannot be undone.`)) {
            return;
        }
        try {
            const res = await fetch(`${API_BASE}/api/users/${encodeURIComponent(currentUser)}`, { method: 'DELETE' });
            if (res.ok) {
                showToast(`Profile '${currentUser}' deleted successfully.`);
                localStorage.removeItem('soundvector_user');
                setTimeout(() => {
                    checkAuth();
                }, 1000);
            } else {
                const data = await res.json();
                showToast(data.detail || "Failed to delete profile.", "error");
            }
        } catch (err) {
            console.error(err);
            showToast("Network error deleting profile.", "error");
        }
    });
}

function onUserChanged() {
    if (currentUserDisplay) currentUserDisplay.innerText = currentUser;
    const profileCardUser = document.getElementById('profileCardUser');
    if (profileCardUser) profileCardUser.innerText = currentUser;

    refreshProfileStats();
    if (currentView === 'home') loadHomePage();
    if (currentView === 'mysongs') loadMySongs();
}

function setMode(mode, btn) {
    currentMode = mode;
    document.querySelectorAll('.mode-chip').forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');

    let currentQuery = searchInput ? searchInput.value.trim() : '';
    if (!currentQuery && currentSeedFacts && currentSeedFacts.name) {
        currentQuery = `${currentSeedFacts.name} ${currentSeedFacts.artist || ''}`.trim();
    }

    if (currentQuery) {
        executeSearch(currentQuery, currentSearchType, currentSeedFacts);
    }
}

// ---------------------------------------------------------
// Live Search & Autocomplete
// ---------------------------------------------------------
const searchInput = document.getElementById('searchInput');
const dropdown = document.getElementById('searchDropdown');

let albumSuggestions = [];

searchInput.addEventListener('input', (e) => {
    if (currentSearchType === 'nlp') return;
    const q = e.target.value.trim();
    clearTimeout(searchTimeout);
    if (q.length < 3) { hideSuggestions(); return; }

    searchTimeout = setTimeout(async () => {

        try {
            const res = await fetch(`${API_BASE}/api/search?q=${encodeURIComponent(q)}`);
            if (!res.ok) return hideSuggestions();
            const data = await res.json();
            suggestions = data.results || [];
            artistSuggestions = data.artists || [];
            albumSuggestions = data.albums || [];
            activeSuggestionIdx = -1;
            renderSuggestions();
        } catch (err) { hideSuggestions(); }
    }, 400);
});

function hideSuggestions() {
    dropdown.classList.add('hidden');
    dropdown.innerHTML = '';
    suggestions = [];
    artistSuggestions = [];
    albumSuggestions = [];
    activeSuggestionIdx = -1;
}

let currentSuggestionObjects = [];

function renderSuggestions() {
    if (!suggestions.length && !artistSuggestions.length && !albumSuggestions.length) { hideSuggestions(); return; }
    currentSuggestionObjects = suggestions;
    let html = '';

    if (artistSuggestions.length > 0) {
        html += `<div class="dropdown-section-title">Artists</div>`;
        html += `<div class="artist-circles-row">`;
        artistSuggestions.forEach((a, idx) => {
            const avatarId = `art-drop-${a.artist.replace(/[^a-zA-Z0-9]/g, '_')}`;
            setTimeout(() => loadArtistCircleAvatar(a.artist, avatarId), idx * 40);
            html += `
            <div class="artist-circle-card" onclick="openArtistPage('${escapeJs(a.artist)}')">
                <div class="artist-avatar" id="${avatarId}">${a.artist.substring(0, 1).toUpperCase()}</div>
                <div class="artist-circle-name">${a.artist}</div>
            </div>`;
        });
        html += `</div>`;
    }

    if (albumSuggestions && albumSuggestions.length > 0) {
        html += `<div class="dropdown-section-title">Albums & Soundtracks</div>`;
        html += `<div class="album-circles-row" style="display:flex;gap:10px;overflow-x:auto;padding-bottom:8px;margin-bottom:8px;scrollbar-width:none;">`;
        albumSuggestions.forEach(alb => {
            const artHtml = alb.cover_art ? `<img src="${alb.cover_art}" style="width:38px;height:38px;object-fit:cover;border-radius:6px;">` : '💿';
            html += `
            <div class="dropdown-album-card" onclick="openAlbumPage('${escapeJs(alb.title)}', '${escapeJs(alb.artist || '')}', '${escapeJs(alb.id || '')}', '${escapeJs(alb.source || '')}')" style="display:flex;align-items:center;gap:8px;padding:6px 10px;background:rgba(255,255,255,0.04);border-radius:8px;cursor:pointer;min-width:160px;max-width:220px;border:1px solid rgba(255,255,255,0.06);flex-shrink:0;">
                <div style="width:38px;height:38px;border-radius:6px;overflow:hidden;flex-shrink:0;background:#222;display:flex;align-items:center;justify-content:center;font-size:16px;">${artHtml}</div>
                <div style="overflow:hidden;display:flex;flex-direction:column;align-items:flex-start;text-align:left;">
                    <span style="font-size:12px;font-weight:700;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:140px;">${alb.title}</span>
                    <span style="font-size:10px;color:#a7a7a7;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:140px;">${alb.artist || 'Album'}</span>
                </div>
            </div>`;
        });
        html += `</div>`;
    }

    if (suggestions.length > 0) {
        html += `<div class="dropdown-section-title">Tracks</div>`;
        html += suggestions.map((s, idx) => {
            const artHtml = s.deezer_album_art ? `<img src="${s.deezer_album_art}" style="width:34px;height:34px;object-fit:cover;border-radius:4px;">` : `<span style="font-size:16px;">🎵</span>`;
            return `
            <div class="dropdown-item ${idx === activeSuggestionIdx ? 'active' : ''}" onclick="selectDropdownItemByIdx(${idx})">
                <div class="s-thumb enrich-art" data-track-key="${escapeAttr(getTrackKey(s.name, s.artist))}" style="width:34px;height:34px;border-radius:4px;background:#222;display:flex;align-items:center;justify-content:center;margin-right:12px;flex-shrink:0;overflow:hidden;">${artHtml}</div>
                <div class="s-details" style="display:flex;flex-direction:column;align-items:flex-start;text-align:left;flex:1;min-width:0;">
                    <span class="s-name" style="font-size:13px;font-weight:600;color:#fff;text-align:left;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;width:100%;">${s.name}</span>
                    <span class="s-artist" style="font-size:11px;color:#a7a7a7;text-align:left;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;width:100%;">${s.artist}</span>
                </div>
                ${s.year ? `<div class="s-meta-right" style="margin-left:auto;"><span class="s-year">${s.year}</span></div>` : ''}
            </div>
            `;
        }).join('');
    }

    dropdown.innerHTML = html;
    dropdown.classList.remove('hidden');
}

function selectDropdownItemByIdx(idx) {
    const item = currentSuggestionObjects[idx];
    if (item) {
        const query = item.artist && item.artist !== 'Unknown Artist' ? `${item.name} ${item.artist}` : item.name;
        searchInput.value = query;
        hideSuggestions();
        switchTab('discover');
        executeSearch(query, 'track', item);
    }
}

function selectDropdownItem(name, artist, itemObj = null) {
    const query = artist && artist !== 'Unknown Artist' ? `${name} ${artist}` : name;
    searchInput.value = query;
    hideSuggestions();
    switchTab('discover');
    const seedTrack = itemObj || { name, artist, row: -1 };
    executeSearch(query, 'track', seedTrack);
}

searchInput.addEventListener('keydown', (e) => {
    if (dropdown.classList.contains('hidden')) {
        if (e.key === 'Enter') {
            e.preventDefault();
            switchTab('discover');
            executeSearch(searchInput.value);
        }
        return;
    }

    if (e.key === 'ArrowDown') {
        e.preventDefault();
        activeSuggestionIdx = Math.min(suggestions.length - 1, activeSuggestionIdx + 1);
        renderSuggestions();
    } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        activeSuggestionIdx = Math.max(0, activeSuggestionIdx - 1);
        renderSuggestions();
    } else if (e.key === 'Enter') {
        e.preventDefault();
        if (activeSuggestionIdx >= 0 && activeSuggestionIdx < suggestions.length) {
            const s = suggestions[activeSuggestionIdx];
            selectDropdownItem(s.name, s.artist);
        } else {
            hideSuggestions();
            switchTab('discover');
            executeSearch(searchInput.value);
        }
    } else if (e.key === 'Escape') {
        hideSuggestions();
    }
});

document.addEventListener('click', (e) => {
    if (!e.target.closest('.search-container')) hideSuggestions();
});

document.addEventListener('keydown', (e) => {
    if (e.key === '/' && document.activeElement.tagName !== 'INPUT') {
        e.preventDefault();
        searchInput.focus();
    }
});

// ---------------------------------------------------------
// Toast Manager
// ---------------------------------------------------------
function showToast(msg) {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.innerText = msg;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(12px)';
        setTimeout(() => toast.remove(), 300);
    }, 2200);
}

async function loadHomePage() {
    const audioPanel = document.getElementById('audioVectorPanel');
    if (audioPanel) audioPanel.classList.add('hidden');

    renderIntelPanel({
        headline: "Explore Your Vibe",
        insights: [
            "Personalized recommendations based on your taste profile.",
            "Search any song, artist, or mood (e.g., 'telugu gym songs').",
            "Like and skip tracks to train your real-time vector profile."
        ]
    }, "Gemini");

    const homeContent = document.getElementById('homeContent');
    // Show skeleton while loading
    homeContent.innerHTML = `
        <div class="home-skeleton">
            <div class="skeleton-greeting skeleton-pulse"></div>
            <div class="skeleton-chips">
                <div class="skeleton-chip skeleton-pulse"></div>
                <div class="skeleton-chip skeleton-pulse"></div>
                <div class="skeleton-chip skeleton-pulse"></div>
                <div class="skeleton-chip skeleton-pulse"></div>
            </div>
            <div class="skeleton-section">
                <div class="skeleton-section-title skeleton-pulse"></div>
                <div class="skeleton-cards-row">
                    <div class="skeleton-card skeleton-pulse"></div>
                    <div class="skeleton-card skeleton-pulse"></div>
                    <div class="skeleton-card skeleton-pulse"></div>
                    <div class="skeleton-card skeleton-pulse"></div>
                    <div class="skeleton-card skeleton-pulse"></div>
                </div>
            </div>
            <div class="skeleton-section">
                <div class="skeleton-section-title skeleton-pulse"></div>
                <div class="skeleton-cards-row">
                    <div class="skeleton-card skeleton-pulse"></div>
                    <div class="skeleton-card skeleton-pulse"></div>
                    <div class="skeleton-card skeleton-pulse"></div>
                    <div class="skeleton-card skeleton-pulse"></div>
                    <div class="skeleton-card skeleton-pulse"></div>
                </div>
            </div>
        </div>`;

    try {
        const res = await fetch(`${API_BASE}/api/home?user=${encodeURIComponent(currentUser)}`);
        const data = await res.json();
        renderHomePage(data);
    } catch (err) {
        homeContent.innerHTML = `<div class="loading-state">Could not load home page.</div>`;
    }
}

function renderHomePage(data) {
    const homeContent = document.getElementById('homeContent');
    let html = '';

    // Greeting
    html += `
        <div class="home-greeting">
            <h1>${data.greeting}, ${data.user}</h1>
            <p>${data.has_history ? 'Personalized picks based on your taste' : 'Discover music tailored to you — start liking tracks!'}</p>
        </div>`;

    // Quick Genre Chips
    if (data.quick_genres && data.quick_genres.length > 0) {
        html += `<div class="quick-chips">`;
        data.quick_genres.forEach(g => {
            html += `<button class="quick-chip" onclick="quickGenreSearch('${escapeJs(g)}')">${g}</button>`;
        });
        // Add some extra mood chips
        const moodChips = ['chill', 'workout', 'focus', 'party', 'sad'];
        moodChips.forEach(m => {
            if (!data.quick_genres.includes(m)) {
                html += `<button class="quick-chip" onclick="quickMoodSearch('${m}')">${m}</button>`;
            }
        });
        html += `</div>`;
    }

    // Recommendation Sections
    if (data.sections && data.sections.length > 0) {
        data.sections.forEach(section => {
            if (section.tracks) section.tracks.forEach(seedEnrichCache);
            html += renderHomeSection(section);
        });
    }

    homeContent.innerHTML = html;
}

function onHomeCardClick(row, name, artist) {
    const item = { row, name, artist };
    const query = artist && artist !== 'Unknown Artist' ? `${name} ${artist}` : name;
    if (searchInput) searchInput.value = query;
    hideSuggestions();
    switchTab('discover');
    executeSearch(query, 'track', item);
}

function renderHomeSection(section) {
    const secId = section.id || ('sec_' + Math.random().toString(36).substring(2, 7));
    let html = `
        <div class="home-section">
            <div class="section-header">
                <div>
                    <div class="section-title">${section.title}</div>
                    <div class="section-subtitle">${section.subtitle || ''}</div>
                </div>
                <div class="scroll-controls">
                    <button class="scroll-arrow-btn" onclick="scrollSectionRow('${secId}', -400)" title="Scroll Left">‹</button>
                    <button class="scroll-arrow-btn" onclick="scrollSectionRow('${secId}', 400)" title="Scroll Right">›</button>
                </div>
            </div>
            <div class="cards-scroll-row" id="scroll-row-${secId}">`;

    (section.tracks || []).forEach((t, idx) => {
        const genres = (t.base_genres || t.genres || []).slice(0, 2);

        html += `
            <div class="home-track-card" id="card-hs-${t.row}" onclick="onHomeCardClick(${t.row}, '${escapeJs(t.name)}', '${escapeJs(t.artist)}')">
                <div class="home-card-art enrich-art" id="art-hs-${t.row}" data-track-key="${escapeAttr(getTrackKey(t.name, t.artist))}">${getInitialArtHtml(t)}</div>
                <div class="home-card-name" title="${escapeAttr(t.name)}">${t.name || 'Unknown'}</div>
                <div class="home-card-artist" onclick="event.stopPropagation();openArtistPage('${escapeJs(t.artist)}')" title="${escapeAttr(t.artist)}">${t.artist || 'Unknown'}</div>
                <div class="home-card-meta">
                    ${genres.map(g => `<span class="genre-badge ${getGenreClass(g)}">${g}</span>`).join('')}
                </div>
                <div class="listen-on-row" id="enrich-hs-${t.row}" data-track-key="${escapeAttr(getTrackKey(t.name, t.artist))}" style="${t.deezer_link || t.youtube_music_url ? 'display:flex;' : ''}">${getInitialListenRowHtml(t)}</div>
            </div>`;
        queueTrackEnrichment(t.name, t.artist, t.row, t);
    });

    html += `</div></div>`;
    return html;
}

function scrollSectionRow(secId, distance) {
    const row = document.getElementById(`scroll-row-${secId}`);
    if (row) {
        row.scrollBy({ left: distance, behavior: 'smooth' });
    }
}

function quickGenreSearch(genre) {
    searchInput.value = genre;
    setSearchType('nlp');
    switchTab('discover');
    executeSearch(genre, 'nlp');
}

function quickMoodSearch(mood) {
    searchInput.value = mood;
    setSearchType('nlp');
    switchTab('discover');
    executeSearch(mood, 'nlp');
}

// ---------------------------------------------------------
//  BROWSE ALL GRID
// ---------------------------------------------------------
const BROWSE_CATEGORIES = [
    { id: 'pop', title: 'Pop', color: '#dc148c', icon: '🎤' },
    { id: 'hip-hop', title: 'Hip-Hop', color: '#bc5900', icon: '🎧' },
    { id: 'filmi', title: 'Bollywood', color: '#e8115b', icon: '🎬' },
    { id: 'edm', title: 'EDM & Dance', color: '#1e3264', icon: '⚡' },
    { id: 'rock', title: 'Rock', color: '#e91429', icon: '🎸' },
    { id: 'lo-fi', title: 'Lo-Fi & Study', color: '#27856a', icon: '☕' },
    { id: 'workout', title: 'Workout & Gym', color: '#777777', icon: '🏋️' },
    { id: 'chill', title: 'Chill Vibes', color: '#509bf5', icon: '🌙' },
    { id: 'rnb', title: 'R&B & Soul', color: '#d84000', icon: '🎷' },
    { id: 'indie', title: 'Indie & Alt', color: '#608108', icon: '🌿' },
    { id: 'party', title: 'Party & Hype', color: '#8d67ab', icon: '🎉' },
    { id: 'sad', title: 'Sad & Melancholy', color: '#477d95', icon: '🌧️' },
    { id: 'latin', title: 'Latin', color: '#e1118c', icon: '💃' },
    { id: 'country', title: 'Country', color: '#d84000', icon: '🤠' },
    { id: 'classical', title: 'Classical', color: '#7d4b00', icon: '🎻' },
    { id: 'synthwave', title: 'Synthwave & Drive', color: '#8c1932', icon: '🚘' },
];

function loadBrowseAllGrid() {
    const recList = document.getElementById('recList');
    if (!recList) return;

    let html = `
        <div class="browse-container">
            <h1 class="browse-title">Browse all</h1>
            <div class="browse-grid">`;

    BROWSE_CATEGORIES.forEach(cat => {
        html += `
            <div class="browse-card" style="background-color: ${cat.color};" onclick="selectBrowseCategory('${cat.id}', '${escapeJs(cat.title)}')">
                <span class="browse-card-title">${cat.title}</span>
                <div class="browse-card-deco">${cat.icon}</div>
            </div>`;
    });

    html += `</div></div>`;
    recList.innerHTML = html;
}

function selectBrowseCategory(catId, catTitle) {
    const query = catTitle || catId;
    searchInput.value = query;
    setSearchType('nlp');
    executeSearch(query, 'nlp');
}

// ---------------------------------------------------------
// Core Recommendation Execution
// ---------------------------------------------------------
let currentOffset = 0;
const currentLimit = 15;
let isFetchingMore = false;
let lastSearchParams = null;

async function executeSearch(query, forcedType = null, seedTrack = null) {
    const searchType = forcedType || currentSearchType;
    document.getElementById('recList').innerHTML = `
        <div class="loading-state">
            <div class="spinner"></div>
            <div>Searching for "${query}"...</div>
        </div>`;

    lastSearchParams = { query, searchType, seedTrack };
    currentOffset = 0;
    
    try {
        const res = await fetch(`${API_BASE}/api/recommend`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query, mode: currentMode, user: currentUser, search_type: searchType, seed_track: seedTrack, limit: currentLimit, offset: currentOffset })
        });
        const data = await res.json();
        currentRecData = data;
        currentSeedFacts = data.facts || null;
        renderMainData(data);
        renderIntelPanel(data.intel, data.backend, data.facts);
    } catch (err) {
        document.getElementById('recList').innerHTML = `<div class="loading-state">Error fetching recommendations.</div>`;
    }
}

function renderMainData(data) {
    if (data && data.recs) {
        data.recs.forEach(seedEnrichCache);
    }
    const audioPanel = document.getElementById('audioVectorPanel');

    if (audioPanel) audioPanel.classList.remove('hidden');

    // Audio Feature Meters (animated)
    const f = data.facts || {};
    animateMeter('mEnergy', 'fEnergy', f.energy || 0.5);
    animateMeter('mValence', 'fValence', f.valence || 0.5);
    animateMeter('mDance', 'fDance', f.danceability || 0.5);

    document.getElementById('mTempo').innerText = `${f.tempo_bpm || 120} BPM`;
    document.getElementById('fTempo').style.width = `${Math.min(100, (f.tempo_bpm || 120) / 200 * 100)}%`;

    let html = '';

    // AI Fallback Banner
    if (f.ai_interpreted) {
        html += `
            <div class="ai-fallback-banner">
                ${SVG_ICONS.sparkle}
                <span><strong>AI-interpreted:</strong> ${f.ai_interpreted}</span>
            </div>`;
    }

    // Target Seed Track Logic
    if (f.name && f.artist && f.artist !== "your vibe") {
        html += `<h2 style="font-size: 18px; font-weight: 800; margin-bottom: 14px; color: #fff;">Recommendations based on "${f.name}"</h2>`;

        // Ensure the seed track is included at the top of the recommendations list
        // so that it gets all the like/dislike/skip action buttons
        const seedInRecs = data.recs.some(r => r.row === f.row || (r.name === f.name && r.artist === f.artist));
        if (!seedInRecs) {
            data.recs.unshift({
                row: f.row || -1,
                name: f.name,
                artist: f.artist,
                year: f.year,
                score: 1.0,
                signals: { embed: 1.0, audio: 1.0, genre: 1.0 }
            });
        }
    } else {
        html += `<h2 style="font-size: 18px; font-weight: 800; margin-bottom: 14px; color: #fff;">Recommendations for "${f.name || data.header}"</h2>`;
    }

    // Track Cards
    html += `<div id="trackCardsContainer">`;
    data.recs.forEach((r, idx) => {
        const sigs = r.signals || {};
        const activeSig = (r.row >= 0 ? userTrackSignals[r.row] : null) || userTrackSignals[getTrackKey(r.name, r.artist)] || '';
        html += `
        <div class="track-card" id="card-${r.row}" onclick="selectTrackForInsights(${r.row}, '${escapeJs(r.name)}', '${escapeJs(r.artist)}', this)">
            <div class="track-info-side">
                <div class="cover-art-box enrich-art" id="art-${r.row}" data-track-key="${escapeAttr(getTrackKey(r.name, r.artist))}" data-track-name="${escapeAttr(r.name)}" data-artist-name="${escapeAttr(r.artist)}" data-row="${r.row}">${getInitialArtHtml(r)}</div>
                <div class="track-details">
                    <div class="track-name">${idx + 1}. ${r.name}</div>
                    <div class="track-artist" onclick="event.stopPropagation();openArtistPage('${escapeJs(r.artist)}')">${r.artist} ${r.year ? `· <span style="color:var(--text-dim);">${r.year}</span>` : ''}</div>
                    <div class="tags-list">
                        ${sigs.embed ? `<span class="signal-badge">embed ${sigs.embed.toFixed(2)}</span>` : ''}
                        ${sigs.audio ? `<span class="signal-badge">audio ${sigs.audio.toFixed(2)}</span>` : ''}
                        ${sigs.genre ? `<span class="signal-badge">genre ${sigs.genre.toFixed(2)}</span>` : ''}
                    </div>
                    <div class="listen-on-row" id="enrich-${r.row}" data-track-key="${escapeAttr(getTrackKey(r.name, r.artist))}" style="${r.deezer_link || r.youtube_music_url ? 'display:flex;' : ''}">${getInitialListenRowHtml(r)}</div>
                </div>
            </div>
            <div class="track-action-side">
                <div class="score-badge">${(r.score * 100).toFixed(1)}%</div>
                <div class="action-buttons">
                    <button class="btn-act like ${activeSig === 'like' ? 'active-like' : ''}" onclick="event.stopPropagation();sendFeedback(${r.row}, 'like', this)">${SVG_ICONS.like}</button>
                    <button class="btn-act dislike ${activeSig === 'dislike' ? 'active-dislike' : ''}" onclick="event.stopPropagation();sendFeedback(${r.row}, 'dislike', this)">${SVG_ICONS.dislike}</button>
                    <button class="btn-act explore" onclick="event.stopPropagation();selectDropdownItem('${escapeJs(r.name)}', '${escapeJs(r.artist)}')">${SVG_ICONS.explore} Explore</button>
                </div>
            </div>
        </div>`;
        if (r) seedEnrichCache(r);
    });
    html += `</div>`;
    
    html += `<button id="btn-show-more" class="btn-primary" style="margin-top:20px;width:100%" onclick="loadMoreRecommendations()">Show More Tracks</button>`;

    const recListEl = document.getElementById('recList');
    recListEl.innerHTML = html;
    observeEnrichElements(recListEl);
}

async function loadMoreRecommendations() {
    if (isFetchingMore || !lastSearchParams) return;
    isFetchingMore = true;
    
    const btn = document.getElementById('btn-show-more');
    if (btn) btn.innerText = 'Loading...';
    
    currentOffset += currentLimit;
    
    try {
        const res = await fetch(`${API_BASE}/api/recommend`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                query: lastSearchParams.query, 
                mode: currentMode, 
                user: currentUser, 
                search_type: lastSearchParams.searchType, 
                seed_track: lastSearchParams.seedTrack,
                limit: currentLimit,
                offset: currentOffset
            })
        });
        const data = await res.json();
        
        const container = document.getElementById('trackCardsContainer');
        if (container && data.recs && data.recs.length > 0) {
            let appendHtml = '';
            data.recs.forEach((r, idx) => {
                const globalIdx = currentOffset + idx;
                const sigs = r.signals || {};
                const activeSig = (r.row >= 0 ? userTrackSignals[r.row] : null) || userTrackSignals[getTrackKey(r.name, r.artist)] || '';
                appendHtml += `
                <div class="track-card" id="card-${r.row}" onclick="selectTrackForInsights(${r.row}, '${escapeJs(r.name)}', '${escapeJs(r.artist)}', this)">
                    <div class="track-info-side">
                        <div class="cover-art-box enrich-art" id="art-${r.row}" data-track-key="${escapeAttr(getTrackKey(r.name, r.artist))}">🎵</div>
                        <div class="track-details">
                            <div class="track-name">${globalIdx + 1}. ${r.name}</div>
                            <div class="track-artist" onclick="event.stopPropagation();openArtistPage('${escapeJs(r.artist)}')">${r.artist} ${r.year ? `· <span style="color:var(--text-dim);">${r.year}</span>` : ''}</div>
                            <div class="tags-list">
                                ${sigs.embed ? `<span class="signal-badge">embed ${sigs.embed.toFixed(2)}</span>` : ''}
                                ${sigs.audio ? `<span class="signal-badge">audio ${sigs.audio.toFixed(2)}</span>` : ''}
                                ${sigs.genre ? `<span class="signal-badge">genre ${sigs.genre.toFixed(2)}</span>` : ''}
                            </div>
                            <div class="listen-on-row" id="enrich-${r.row}" data-track-key="${escapeAttr(getTrackKey(r.name, r.artist))}"></div>
                        </div>
                    </div>
                    <div class="track-action-side">
                        <div class="score-badge">${(r.score * 100).toFixed(1)}%</div>
                        <div class="action-buttons">
                            <button class="btn-act like ${activeSig === 'like' ? 'active-like' : ''}" onclick="event.stopPropagation();sendFeedback(${r.row}, 'like', this)">${SVG_ICONS.like}</button>
                            <button class="btn-act dislike ${activeSig === 'dislike' ? 'active-dislike' : ''}" onclick="event.stopPropagation();sendFeedback(${r.row}, 'dislike', this)">${SVG_ICONS.dislike}</button>
                            <button class="btn-act explore" onclick="event.stopPropagation();selectDropdownItem('${escapeJs(r.name)}', '${escapeJs(r.artist)}')">${SVG_ICONS.explore} Explore</button>
                        </div>
                    </div>
                </div>`;
                queueTrackEnrichment(r.name, r.artist, r.row, r);
            });
            container.insertAdjacentHTML('beforeend', appendHtml);
        }
        
        if (currentRecData && currentRecData.recs && data.recs) {
            currentRecData.recs.push(...data.recs);
        }
        
        if (btn) {
            if (!data.recs || data.recs.length === 0) {
                btn.style.display = 'none';
            } else {
                btn.innerText = 'Show More Tracks';
            }
        }
    } catch (err) {
        console.error("Failed to load more recommendations", err);
        if (btn) btn.innerText = 'Show More Tracks';
    }
    
    isFetchingMore = false;
}

function animateMeter(labelId, fillId, value) {
    document.getElementById(labelId).innerText = value.toFixed(2);
    document.getElementById(fillId).style.width = `${value * 100}%`;
}

// ---------------------------------------------------------
// AI Intel Panel
// ---------------------------------------------------------
function renderIntelPanel(intel, backend, facts) {
    if (!intel) return;

    let html = '';

    // AI badge if Gemini powered
    if (backend && backend.includes('gemini')) {
        html += `<div class="intel-ai-badge">${SVG_ICONS.sparkle} Powered by Gemini</div>`;
    }

    // Headline
    html += `<div class="intel-headline">${intel.headline || 'Analyzing...'}</div>`;

    // Insights list
    if (intel.insights && intel.insights.length > 0) {
        html += `<ul class="intel-insights-list">`;
        intel.insights.forEach(insight => {
            html += `<li class="intel-insight-item"><span class="intel-insight-icon">✦</span><span>${insight}</span></li>`;
        });
        html += `</ul>`;
    }

    // Sound profile
    if (intel.sound_profile) {
        html += `<div class="intel-sound-profile">${intel.sound_profile}</div>`;
    }

    // Mood tags (filter out generic slop)
    const genericSlop = ['personalized', 'ai-powered', 'vector-retrieval'];
    const validTags = (intel.mood_tags || []).filter(tag => !genericSlop.includes(tag.toLowerCase()));
    if (validTags.length > 0) {
        html += `<div class="intel-mood-tags">`;
        validTags.forEach(tag => {
            html += `<span class="intel-mood-tag">${tag}</span>`;
        });
        html += `</div>`;
    }

    // Listen-if
    if (intel.listen_if) {
        html += `<div class="intel-listen-if">${intel.listen_if}</div>`;
    }

    const desktopIntel = document.getElementById('intelPanel');
    if (desktopIntel) desktopIntel.innerHTML = html;
}

// ---------------------------------------------------------
// ---------------------------------------------------------
// Select Track for Insights (Clicking ANY song updates sidebar)
// ---------------------------------------------------------
async function selectTrackForInsights(row, trackName, artistName, cardElem) {
    document.querySelectorAll('.track-card.active-selected').forEach(c => c.classList.remove('active-selected'));
    if (cardElem) cardElem.classList.add('active-selected');

    const isMobile = window.innerWidth <= 992;

    if (isMobile) {
        // On mobile, open the bottom sheet immediately with a loading state
        const modal = document.getElementById('mobileInsightsModal');
        const body = document.getElementById('mobileInsightsBody');
        const sheetTitle = modal ? modal.querySelector('.sheet-header h3') : null;
        if (sheetTitle) sheetTitle.textContent = `${trackName}`;
        if (body) body.innerHTML = `
            <div class="loading-state" style="padding:32px 0;">
                <div class="spinner"></div>
                <div style="font-size:12px;color:var(--text-secondary);margin-top:8px;">Loading insights...</div>
            </div>`;
        if (modal) {
            modal.classList.remove('hidden');
            modal.classList.add('open');
        }
    } else {
        const intelPanel = document.getElementById('intelPanel');
        if (intelPanel) {
            intelPanel.innerHTML = `
                <div class="loading-state" style="padding: 24px 12px;">
                    <div class="spinner" style="width:22px;height:22px;"></div>
                    <div style="font-size:12px;color:var(--text-secondary);">Generating insights for "${trackName}"...</div>
                </div>`;
        }
    }

    try {
        const res = await fetch(`${API_BASE}/api/track_intel?row=${row}&track=${encodeURIComponent(trackName)}&artist=${encodeURIComponent(artistName)}`);
        const data = await res.json();

        const f = data.facts || {};

        if (isMobile) {
            openMobileTrackInsights(trackName, artistName, data, row);
        } else {
            const audioPanel = document.getElementById('audioVectorPanel');
            if (audioPanel) audioPanel.classList.remove('hidden');
            animateMeter('mEnergy', 'fEnergy', f.energy || 0.5);
            animateMeter('mValence', 'fValence', f.valence || 0.5);
            animateMeter('mDance', 'fDance', f.danceability || 0.5);
            document.getElementById('mTempo').innerText = `${f.tempo_bpm || 120} BPM`;
            document.getElementById('fTempo').style.width = `${Math.min(100, (f.tempo_bpm || 120) / 200 * 100)}%`;
            renderIntelPanel(data.intel, data.backend, data.facts);
        }
    } catch (e) {
        console.error(e);
    }
}

function openMobileTrackInsights(trackName, artistName, data, row) {
    const modal = document.getElementById('mobileInsightsModal');
    const body = document.getElementById('mobileInsightsBody');
    const sheetTitle = modal ? modal.querySelector('.sheet-header h3') : null;
    if (!modal || !body) return;

    if (sheetTitle) sheetTitle.textContent = trackName;
    const intel = data.intel || {};
    const f = data.facts || {};

    const meterBar = (val) => `
        <div style="height:4px;background:rgba(255,255,255,0.08);border-radius:2px;overflow:hidden;margin-top:4px;">
            <div style="height:100%;width:${Math.round((val || 0) * 100)}%;background:var(--accent-green);border-radius:2px;transition:width 0.5s ease;"></div>
        </div>`;

    let html = '';

    // AI Insight headline & deep analysis
    if (intel.headline || intel.reasoning || (intel.insights && intel.insights.length)) {
        html += `
        <div style="padding:14px 0 10px;border-bottom:1px solid var(--border);">
            ${data.backend && data.backend.includes('gemini') ? `<span style="font-size:10px;font-weight:700;color:var(--accent-green);letter-spacing:0.5px;text-transform:uppercase;display:inline-flex;align-items:center;gap:4px;margin-bottom:6px;"><svg viewBox='0 0 24 24' width='10' height='10' fill='currentColor'><path d='M12 2l2.09 6.26L20 10l-5.91 1.74L12 18l-2.09-6.26L4 10l5.91-1.74z'/></svg>AI Insight</span><br>` : ''}
            <div style="font-size:15px;font-weight:700;color:#fff;line-height:1.4;">${intel.headline || ''}</div>
            ${intel.reasoning ? `<div style="font-size:13px;color:var(--text-secondary);margin-top:6px;line-height:1.5;">${intel.reasoning}</div>` : ''}
            ${intel.insights && intel.insights.length > 0 ? `
                <div style="margin-top:8px;display:flex;flex-direction:column;gap:6px;">
                    ${intel.insights.map(ins => `<div style="font-size:12.5px;color:#d0d0d0;display:flex;gap:6px;align-items:flex-start;line-height:1.4;"><span style="color:var(--accent-green);flex-shrink:0;margin-top:1px;">✦</span><span>${ins}</span></div>`).join('')}
                </div>
            ` : ''}
            ${intel.sound_profile ? `<div style="font-size:12px;color:var(--text-secondary);margin-top:10px;padding:8px 10px;background:rgba(255,255,255,0.03);border-radius:6px;border-left:2px solid var(--accent-green);line-height:1.4;">${intel.sound_profile}</div>` : ''}
            ${intel.listen_if ? `<div style="font-size:12px;color:var(--text-dim);margin-top:8px;font-style:italic;">${intel.listen_if}</div>` : ''}
        </div>`;
    }

    // Audio meters
    if (f.energy !== undefined) {
        html += `<div style="padding:12px 0;border-bottom:1px solid var(--border);">
            <div style="font-size:11px;font-weight:700;color:var(--text-dim);letter-spacing:0.5px;text-transform:uppercase;margin-bottom:10px;">Audio Attributes</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
                <div><div style="font-size:12px;color:var(--text-secondary);display:flex;justify-content:space-between;"><span>Energy</span><span style="color:#fff;font-weight:600;">${(f.energy || 0).toFixed(2)}</span></div>${meterBar(f.energy)}</div>
                <div><div style="font-size:12px;color:var(--text-secondary);display:flex;justify-content:space-between;"><span>Mood</span><span style="color:#fff;font-weight:600;">${(f.valence || 0).toFixed(2)}</span></div>${meterBar(f.valence)}</div>
                <div><div style="font-size:12px;color:var(--text-secondary);display:flex;justify-content:space-between;"><span>Dance</span><span style="color:#fff;font-weight:600;">${(f.danceability || 0).toFixed(2)}</span></div>${meterBar(f.danceability)}</div>
                <div><div style="font-size:12px;color:var(--text-secondary);display:flex;justify-content:space-between;"><span>Tempo</span><span style="color:#fff;font-weight:600;">${f.tempo_bpm || 120} BPM</span></div>${meterBar(Math.min(1, (f.tempo_bpm || 120) / 200))}</div>
            </div>
        </div>`;
    }

    // Mood tags
    if (intel.mood_tags && intel.mood_tags.length) {
        html += `<div style="padding:10px 0;border-bottom:1px solid var(--border);">
            <div style="display:flex;flex-wrap:wrap;gap:6px;">${intel.mood_tags.map(t => `<span class="genre-badge">${t}</span>`).join('')}</div>
        </div>`;
    }

    // Quick actions
    html += `<div style="padding:12px 0;display:flex;gap:8px;">
        <button class="btn-primary" onclick="closeMobileInsights();selectDropdownItem('${escapeJs(trackName)}','${escapeJs(artistName)}')" style="flex:1;padding:10px;font-size:13px;border-radius:8px;cursor:pointer;font-weight:700;">Explore Similar</button>
        <button onclick="closeMobileInsights();openArtistPage('${escapeJs(artistName)}')" style="flex:1;padding:10px;font-size:13px;border-radius:8px;cursor:pointer;background:rgba(255,255,255,0.06);border:1px solid var(--border);color:#fff;font-weight:600;">Artist Page</button>
    </div>`;

    body.innerHTML = html;
    modal.classList.remove('hidden');
    modal.classList.add('open');
}

// ---------------------------------------------------------
// Track Enrichment: Deezer + iTunes Preview + YouTube Music
// Batch system: collects enrichment needs and fires ONE /api/batch_enrich
// instead of one /api/enrich per card (eliminates the request waterfall).
// ---------------------------------------------------------
const enrichCache = {};
const _pendingEnrich = new Set(); // tracks keys currently in-flight
let _enrichQueue = [];            // batch queue
let _enrichFlushTimer = null;     // debounce timer for flushing

function seedEnrichCache(track) {
    if (!track || !track.name || !track.artist) return;
    if (track.deezer_album_art || track.deezer_preview_url || track.deezer_link || track.youtube_music_url) {
        const cacheKey = getTrackKey(track.name, track.artist);
        if (!enrichCache[cacheKey]) {
            enrichCache[cacheKey] = {
                deezer_album_art: track.deezer_album_art || "",
                deezer_preview_url: track.deezer_preview_url || "",
                deezer_link: track.deezer_link || "",
                deezer_album_name: track.deezer_album_name || "",
                youtube_music_url: track.youtube_music_url || `https://music.youtube.com/search?q=${encodeURIComponent(track.artist + ' ' + track.name)}`,
                youtube_url: track.youtube_url || `https://www.youtube.com/results?search_query=${encodeURIComponent(track.artist + ' ' + track.name)}`
            };
        }
    }
}

function getInitialArtHtml(t) {
    if (!t) return '🎵';
    const key = getTrackKey(t.name, t.artist);
    const data = t.deezer_album_art ? t : (enrichCache[key] || {});
    if (data.deezer_album_art) {
        let overlayHtml = '';
        if (data.deezer_preview_url) {
            const httpsUrl = data.deezer_preview_url.replace(/^http:\/\//i, 'https://');
            const safeUrl = httpsUrl.replace(/"/g, '&quot;');
            const safeName = (t.name || '').replace(/"/g, '&quot;');
            const safeArtist = (t.artist || '').replace(/"/g, '&quot;');
            const safeArt = (data.deezer_album_art || '').replace(/"/g, '&quot;');
            overlayHtml = `<button class="art-play-overlay" data-preview-url="${safeUrl}" data-row="${t.row}" data-track-name="${safeName}" data-artist-name="${safeArtist}" data-album-art="${safeArt}" onclick="event.stopPropagation();handlePreviewClick(this)" title="Play 30s preview">${SVG_ICONS.play}</button>`;
        }
        return `<img src="${data.deezer_album_art}" alt="album art" style="width:100%;height:100%;object-fit:cover;border-radius:8px;">${overlayHtml}`;
    }
    return '🎵';
}

function getInitialListenRowHtml(t) {
    if (!t) return '';
    const key = getTrackKey(t.name, t.artist);
    const data = t.deezer_link ? t : (enrichCache[key] || t);
    const btns = [];
    if (data.deezer_link) {
        btns.push(`<a class="listen-btn deezer-btn" href="${data.deezer_link}" target="_blank" onclick="event.stopPropagation();" title="Open on Deezer">${SVG_ICONS.deezer} <span>Deezer</span></a>`);
    }
    const ytUrl = data.youtube_music_url || (t.artist && t.name ? `https://music.youtube.com/search?q=${encodeURIComponent(t.artist + ' ' + t.name)}` : '');
    if (ytUrl) {
        btns.push(`<a class="listen-btn yt-btn" href="${ytUrl}" target="_blank" onclick="event.stopPropagation();" title="Search on YouTube Music">${SVG_ICONS.youtube} <span>YT Music</span></a>`);
    }
    return btns.join('');
}

/**
 * Apply enrichment data to all matching DOM elements (art boxes + listen rows).
 */
function _applyEnrichmentToDOM(cacheKey, data, trackName, artistName, row) {
    const btns = [];
    if (data.deezer_link) {
        btns.push(`<a class="listen-btn deezer-btn" href="${data.deezer_link}" target="_blank" onclick="event.stopPropagation();" title="Open on Deezer">${SVG_ICONS.deezer} <span>Deezer</span></a>`);
    }
    if (data.youtube_music_url) {
        btns.push(`<a class="listen-btn yt-btn" href="${data.youtube_music_url}" target="_blank" onclick="event.stopPropagation();" title="Search on YouTube Music">${SVG_ICONS.youtube} <span>YT Music</span></a>`);
    }
    const btnsHtml = btns.join('');

    if (data.deezer_album_art) {
        document.querySelectorAll('.enrich-art').forEach(artEl => {
            if (artEl.getAttribute('data-track-key') === cacheKey) {
                let overlayHtml = '';
                if (data.deezer_preview_url) {
                    const httpsUrl = data.deezer_preview_url.replace(/^http:\/\//i, 'https://');
                    const safeUrl = httpsUrl.replace(/"/g, '&quot;');
                    const safeName = (trackName || '').replace(/"/g, '&quot;');
                    const safeArtist = (artistName || '').replace(/"/g, '&quot;');
                    const safeArt = (data.deezer_album_art || '').replace(/"/g, '&quot;');
                    overlayHtml = `<button class="art-play-overlay" data-preview-url="${safeUrl}" data-row="${row}" data-track-name="${safeName}" data-artist-name="${safeArtist}" data-album-art="${safeArt}" onclick="event.stopPropagation();handlePreviewClick(this)" title="Play 30s preview">${SVG_ICONS.play}</button>`;
                }
                artEl.innerHTML = `<img src="${data.deezer_album_art}" alt="album art" style="width:100%;height:100%;object-fit:cover;border-radius:8px;">${overlayHtml}`;
            }
        });
    }

    document.querySelectorAll('.listen-on-row').forEach(listenEl => {
        if (listenEl.getAttribute('data-track-key') === cacheKey) {
            if (btnsHtml) {
                listenEl.innerHTML = btnsHtml;
                listenEl.style.display = 'flex';
            } else {
                listenEl.style.display = 'none';
            }
        }
    });
}

/**
 * Flush the enrichment queue: fire ONE /api/batch_enrich for all queued tracks.
 * This replaces the old per-card setTimeout + /api/enrich waterfall.
 */
async function _flushEnrichQueue() {
    if (_enrichQueue.length === 0) return;
    const batch = _enrichQueue.splice(0, _enrichQueue.length); // drain queue atomically

    // Filter to only tracks not already cached or in-flight
    const toFetch = [];
    const localData = [];
    for (const item of batch) {
        const key = getTrackKey(item.name, item.artist);
        const cached = enrichCache[key];
        if (cached && cached.deezer_album_art && cached.deezer_preview_url) {
            localData.push({ ...item, _cached: cached });
        } else if (!_pendingEnrich.has(key)) {
            _pendingEnrich.add(key);
            toFetch.push(item);
        }
    }

    // Apply already-cached items immediately
    for (const item of localData) {
        _applyEnrichmentToDOM(getTrackKey(item.name, item.artist), item._cached, item.name, item.artist, item.row);
    }

    if (toFetch.length === 0) return;

    try {
        const res = await fetch(`${API_BASE}/api/batch_enrich`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tracks: toFetch.map(t => ({ name: t.name, artist: t.artist, row: t.row })) })
        });
        const data = await res.json();
        const enriched = data.tracks || [];
        for (const track of enriched) {
            if (!track || !track.name || !track.artist) continue;
            const key = getTrackKey(track.name, track.artist);
            const cached = {
                deezer_album_art: track.deezer_album_art || '',
                deezer_preview_url: track.deezer_preview_url || '',
                deezer_link: track.deezer_link || '',
                deezer_album_name: track.deezer_album_name || '',
                youtube_music_url: track.youtube_music_url || `https://music.youtube.com/search?q=${encodeURIComponent(track.artist + ' ' + track.name)}`,
                youtube_url: track.youtube_url || ''
            };
            enrichCache[key] = cached;
            _pendingEnrich.delete(key);
            // Find original row from our toFetch list
            const orig = toFetch.find(t => getTrackKey(t.name, t.artist) === key);
            _applyEnrichmentToDOM(key, cached, track.name, track.artist, orig ? orig.row : -1);
        }
    } catch (e) {
        // On failure, remove from pending so they can be retried
        for (const item of toFetch) {
            _pendingEnrich.delete(getTrackKey(item.name, item.artist));
        }
    }
}

/**
 * Queue a track for enrichment (debounced batch flush).
 * This is the replacement for the old loadTrackEnrichment()+setTimeout waterfall.
 */
function queueTrackEnrichment(trackName, artistName, row, trackObj) {
    if (!trackName || !artistName) return;
    if (trackObj) seedEnrichCache(trackObj);
    const key = getTrackKey(trackName, artistName);
    const cached = enrichCache[key];
    if (cached && cached.deezer_album_art && cached.deezer_preview_url) {
        // Already fully cached — apply on next tick after DOM elements are inserted into document
        setTimeout(() => _applyEnrichmentToDOM(key, cached, trackName, artistName, row), 0);
        return;
    }
    if (_pendingEnrich.has(key)) return; // already in-flight
    _enrichQueue.push({ name: trackName, artist: artistName, row: row || -1 });
    // Debounce: collect for 30ms then flush as one batch
    clearTimeout(_enrichFlushTimer);
    _enrichFlushTimer = setTimeout(_flushEnrichQueue, 30);
}

const _lazyEnrichObserver = new IntersectionObserver((entries, observer) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            const el = entry.target;
            const name = el.getAttribute('data-track-name');
            const artist = el.getAttribute('data-artist-name');
            const row = parseInt(el.getAttribute('data-row') || '-1', 10);
            if (name && artist) {
                queueTrackEnrichment(name, artist, row);
            }
            observer.unobserve(el);
        }
    });
}, { rootMargin: '250px 0px' });

function observeEnrichElements(container) {
    const parent = container || document;
    parent.querySelectorAll('.enrich-art[data-track-name]:not([data-lazy-observed="true"])').forEach(el => {
        el.setAttribute('data-lazy-observed', 'true');
        _lazyEnrichObserver.observe(el);
    });
}

/**
 * Legacy compatibility shim — redirect to queue system.
 * @deprecated Use queueTrackEnrichment() for new code.
 */
async function loadTrackEnrichment(trackName, artistName, containerId, row, trackObj) {
    queueTrackEnrichment(trackName, artistName, row, trackObj);
}

function handlePreviewClick(btn) {
    const url = btn.getAttribute('data-preview-url');
    const row = btn.getAttribute('data-row');

    let trackName = btn.getAttribute('data-track-name') || '';
    let artistName = btn.getAttribute('data-artist-name') || '';
    let coverArt = btn.getAttribute('data-album-art') || '';

    if (!trackName || !artistName) {
        const card = btn.closest('.home-track-card, .track-card');
        if (card) {
            const nameEl = card.querySelector('.home-card-name, .track-name');
            const artistEl = card.querySelector('.home-card-artist, .track-artist');
            const imgEl = card.querySelector('.enrich-art img');
            if (nameEl && !trackName) trackName = nameEl.innerText.replace(/^\d+\.\s*/, '');
            if (artistEl && !artistName) artistName = artistEl.innerText.split('·')[0].trim();
            if (imgEl && !coverArt) coverArt = imgEl.src;
        }
    }

    if (url) {
        togglePreview(url, row, btn, trackName, artistName, coverArt);
    } else {
        showToast('Preview unavailable', '⚠️');
    }
}

let playerInterval = null;
let currentPlayingUrl = null;

async function togglePreview(url, row, btn, trackName, artistName, coverArt) {
    const bar = document.getElementById('globalPlayerBar');

    // If clicking the EXACT SAME song URL currently playing, toggle pause/play
    if (currentPlayingUrl === url && currentAudio) {
        if (!currentAudio.paused) {
            currentAudio.pause();
            btn.innerHTML = SVG_ICONS.play;
            btn.classList.remove('playing');
            if (bar) updatePlayerBarState(false);
            return;
        } else {
            currentAudio.play().catch(e => console.warn("Resume play failed:", e));
            btn.innerHTML = SVG_ICONS.pause;
            btn.classList.add('playing');
            if (bar) updatePlayerBarState(true);
            return;
        }
    }

    // Stop current audio immediately if playing a NEW song
    if (currentAudio) {
        currentAudio.onerror = null;
        currentAudio.onended = null;
        currentAudio.pause();
        currentAudio = null;
        if (playerInterval) clearInterval(playerInterval);
        document.querySelectorAll('.art-play-overlay.playing').forEach(b => {
            b.innerHTML = SVG_ICONS.play;
            b.classList.remove('playing');
        });
    }

    const audio = new Audio();
    audio.preload = 'none';
    // NOTE: DO NOT set crossOrigin = 'anonymous' because third-party MP3 CDNs (Deezer, iTunes)
    // do not return CORS headers for direct media requests, causing browser CORS / 403 blocks.
    currentAudio = audio;
    currentPlayingUrl = url;
    currentPlayingRow = row;
    audio.volume = 0.8;

    const startPlayback = (audioObj, srcUrl) => {
        audioObj.src = srcUrl;

        audioObj.onended = () => {
            btn.innerHTML = SVG_ICONS.play;
            btn.classList.remove('playing');
            currentPlayingRow = null;
            currentPlayingUrl = null;
            if (playerInterval) clearInterval(playerInterval);
            if (bar) updatePlayerBarState(false);
        };

        return audioObj.play().then(() => {
            btn.innerHTML = SVG_ICONS.pause;
            btn.classList.add('playing');
            if (bar) {
                bar.classList.remove('hidden');
                document.body.classList.add('has-player-bar');
                const nameEl = document.getElementById('playerTrackName');
                const artistEl = document.getElementById('playerArtistName');
                const thumbEl = document.getElementById('playerThumb');
                if (nameEl) nameEl.innerText = trackName || 'Audio Preview';
                if (artistEl) artistEl.innerText = artistName || 'SoundVector';
                if (thumbEl) thumbEl.innerHTML = coverArt ? `<img src="${coverArt}">` : '🎵';

                updatePlayerBarState(true);

                if (playerInterval) clearInterval(playerInterval);
                playerInterval = setInterval(() => {
                    if (currentAudio && !currentAudio.paused) {
                        const cur = currentAudio.currentTime || 0;
                        const dur = currentAudio.duration || 30;
                        const pct = Math.min(100, (cur / dur) * 100);
                        const fill = document.getElementById('playerProgressFill');
                        const txt = document.getElementById('playerCurrentTime');
                        if (fill) fill.style.width = `${pct}%`;
                        if (txt) {
                            const sec = Math.floor(cur % 60);
                            txt.innerText = `0:${sec < 10 ? '0' : ''}${sec}`;
                        }
                    }
                }, 250);
            }
            showToast(`▶ 30s preview playing: ${trackName || 'Preview'}`, '🎵');
            return true;
        });
    };

    const initialSrc = url.replace(/^http:\/\//i, 'https://');

    try {
        await startPlayback(audio, initialSrc);
    } catch (primaryErr) {
        console.warn("Primary audio preview failed (403/expired/blocked). Attempting live iTunes fallback...", primaryErr);
        if (currentAudio !== audio) return;

        let freshUrl = null;
        try {
            let cleanTrack = (trackName || '').replace(/\s*[\(\[\{].*?[\)\]\}]/g, '').replace(/ - .*$/, '').trim();
            let cleanArtist = (artistName || '').split(/[,&/]|feat\.?|ft\.?/i)[0].trim();
            let q = `${cleanTrack} ${cleanArtist}`.trim();
            if (!q) q = (trackName || '').trim();

            if (q) {
                const fRes = await fetch(`https://itunes.apple.com/search?term=${encodeURIComponent(q)}&entity=song&limit=3`);
                const fData = await fRes.json();
                if (fData.results && fData.results.length > 0) {
                    const match = fData.results.find(item => item.previewUrl);
                    if (match) freshUrl = match.previewUrl;
                }
            }
        } catch (e) {
            console.error("iTunes fallback fetch error:", e);
        }

        if (freshUrl && currentAudio === audio) {
            try {
                const freshHttpsUrl = freshUrl.replace(/^http:\/\//i, 'https://');
                await startPlayback(audio, freshHttpsUrl);
                return;
            } catch (fallbackErr) {
                console.error("Fallback iTunes audio playback failed:", fallbackErr);
            }
        }

        if (currentAudio === audio) {
            btn.innerHTML = SVG_ICONS.play;
            btn.classList.remove('playing');
            currentAudio = null;
            currentPlayingUrl = null;
            const isNotAllowed = primaryErr && primaryErr.name === 'NotAllowedError';
            if (isNotAllowed) {
                showToast('Tap play again to start audio', 'info');
            } else {
                showToast('Preview unavailable for this track', 'info');
            }
        }
    }
}

function updatePlayerBarState(isPlaying) {
    const playBtn = document.getElementById('playerPlayBtn');
    if (playBtn) {
        playBtn.innerHTML = isPlaying
            ? `<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>`
            : `<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>`;
    }
}

function togglePlayerBarPlay() {
    if (!currentAudio) return;
    if (currentAudio.paused) {
        currentAudio.play();
        updatePlayerBarState(true);
    } else {
        currentAudio.pause();
        updatePlayerBarState(false);
    }
}

function closePlayerBar() {
    if (currentAudio) {
        currentAudio.pause();
        currentAudio = null;
    }
    if (playerInterval) clearInterval(playerInterval);
    currentPlayingRow = null;
    document.querySelectorAll('.art-play-overlay.playing').forEach(b => {
        b.innerHTML = SVG_ICONS.play;
        b.classList.remove('playing');
    });
    const bar = document.getElementById('globalPlayerBar');
    if (bar) bar.classList.add('hidden');
    document.body.classList.remove('has-player-bar');
}

// ---------------------------------------------------------
// Playlist Generator Modal
// ---------------------------------------------------------
function openPlaylistModal() {
    let widget = document.getElementById('playlistModal');
    if (!widget) {
        widget = document.createElement('div');
        widget.id = 'playlistModal';
        widget.className = 'ai-playlist-widget hidden';
        widget.innerHTML = `
            <div class="playlist-panel-header">
                <div class="playlist-panel-title-group">
                    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="var(--accent-green)" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                        <line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/>
                        <line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>
                    </svg>
                    <div>
                        <div class="playlist-panel-name">AI Playlist Curator</div>
                        <div class="playlist-panel-sub">Describe a vibe, artist style, or mood</div>
                    </div>
                </div>
                <button class="playlist-panel-close" onclick="closePlaylistModal()">&times;</button>
            </div>

            <div class="playlist-panel-body">
                <div class="prompt-examples-row">
                    <span class="prompt-chip" onclick="setPlaylistPrompt('songs like believer')">songs like believer</span>
                    <span class="prompt-chip" onclick="setPlaylistPrompt('bollywood energy hype')">bollywood energy hype</span>
                    <span class="prompt-chip" onclick="setPlaylistPrompt('chill acoustic lo-fi focus')">chill acoustic focus</span>
                    <span class="prompt-chip" onclick="setPlaylistPrompt('late night drive')">late night drive</span>
                </div>

                <div class="playlist-input-container">
                    <textarea id="playlistPromptInput" class="playlist-textarea" placeholder="Describe a vibe (e.g., songs like believer, upbeat workout)..." rows="2"></textarea>
                    <div class="playlist-controls-row">
                        <div class="count-select-wrap">
                            <label>Tracks: 
                                <select id="playlistCountInput" class="count-select">
                                    <option value="10">10 tracks</option>
                                    <option value="15" selected>15 tracks</option>
                                    <option value="20">20 tracks</option>
                                    <option value="25">25 tracks</option>
                                </select>
                            </label>
                        </div>
                        <button class="btn-gen-playlist" id="genPlaylistBtn" onclick="generatePlaylist()">
                            <span>Generate Playlist</span>
                        </button>
                    </div>
                </div>

                <div id="playlistResult" class="playlist-result hidden"></div>
            </div>`;
        document.body.appendChild(widget);
    }

    widget.classList.remove('hidden');
    setTimeout(() => widget.classList.add('open'), 10);
}

function setPlaylistPrompt(text) {
    const inp = document.getElementById('playlistPromptInput');
    if (inp) { inp.value = text; inp.focus(); }
}

function closePlaylistModal() {
    const widget = document.getElementById('playlistModal');
    if (widget) {
        widget.classList.remove('open');
        setTimeout(() => widget.classList.add('hidden'), 200);
    }
}

function renderPlaylistView(data) {
    if (data && data.tracks) {
        data.tracks.forEach(seedEnrichCache);
    }
    const titleEl = document.getElementById('playlistTitle');
    const metaEl = document.getElementById('playlistMeta');
    const listEl = document.getElementById('playlistViewTracksList');

    if (titleEl) titleEl.innerText = data.playlist_name || 'Curated Mix';
    if (metaEl) metaEl.innerText = `${data.description || 'Custom Vibe Mix'} · ${(data.tracks || []).length} songs`;

    if (!listEl) return;

    let html = `<div style="display:flex;flex-direction:column;gap:8px;">`;
    (data.tracks || []).forEach((t, i) => {
        const artHtml = t.deezer_album_art ? `<img src="${t.deezer_album_art}" style="width:60px;height:60px;object-fit:cover;border-radius:8px;">` : `<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>`;
        const trackKey = getTrackKey(t.name, t.artist);
        html += `
        <div class="artist-track-card" style="display:flex;align-items:center;gap:14px;padding:10px 14px;background:var(--bg-surface);border:1px solid var(--border);border-radius:10px;cursor:pointer;" onclick="selectDropdownItem('${escapeJs(t.name)}', '${escapeJs(t.artist)}')">
            <span style="font-size:13px;font-weight:700;color:var(--text-dim);width:24px;text-align:center;">${i + 1}</span>
            <div class="cover-art-box enrich-art" id="art-plv-${t.row || i}" data-track-key="${escapeAttr(trackKey)}">${artHtml}</div>
            <div style="display:flex;flex-direction:column;align-items:flex-start;text-align:left;flex:1;min-width:0;">
                <span style="font-size:14px;font-weight:700;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;width:100%;">${t.name}</span>
                <span onclick="event.stopPropagation();openArtistPage('${escapeJs(t.artist)}')" style="font-size:12px;color:var(--text-secondary);cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;width:100%;margin-top:2px;">${t.artist}</span>
            </div>
            <button class="btn-secondary" onclick="event.stopPropagation();selectDropdownItem('${escapeJs(t.name)}', '${escapeJs(t.artist)}')" style="padding:6px 14px;font-size:12px;border-radius:500px;">Explore</button>
        </div>`;
        queueTrackEnrichment(t.name, t.artist, t.row || 0, t);
    });
    html += `</div>`;
    listEl.innerHTML = html;
}

async function generatePlaylist() {
    const prompt = (document.getElementById('playlistPromptInput') || {}).value || '';
    const count = parseInt((document.getElementById('playlistCountInput') || {}).value || 15);
    if (!prompt.trim()) { showToast('Please enter a description or vibe first', 'info'); return; }
    if (playlistGenerating) return;
    playlistGenerating = true;

    const btn = document.getElementById('genPlaylistBtn');
    if (btn) btn.innerHTML = `<div class="spinner" style="width:14px;height:14px;border-width:2px;"></div> Curating...`;

    const result = document.getElementById('playlistResult');
    if (result) {
        result.classList.remove('hidden');
        result.innerHTML = `<div class="loading-state" style="padding:16px 0;"><div class="spinner"></div><div>Generating playlist...</div></div>`;
    }

    try {
        const res = await fetch(`${API_BASE}/api/playlist_gen`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt, user: currentUser, count })
        });
        const data = await res.json();
        renderPlaylistView(data);

        if (result) {
            result.innerHTML = `
                <div style="display:flex;flex-direction:column;gap:10px;padding:12px;background:rgba(255,255,255,0.03);border-radius:10px;border:1px solid var(--border);margin-top:10px;">
                    <div style="font-size:14px;font-weight:700;color:#fff;">${data.playlist_name || 'Curated Mix'}</div>
                    <div style="font-size:12px;color:var(--text-secondary);">${(data.tracks || []).length} songs curated for "${prompt}"</div>
                    <button class="btn-primary" onclick="closePlaylistModal();switchTab('playlist');" style="padding:10px;font-size:13px;border-radius:8px;cursor:pointer;width:100%;font-weight:700;">View Playlist &rarr;</button>
                </div>`;
        }

        switchTab('playlist');
    } catch (e) {
        if (result) result.innerHTML = `<div style="color:var(--accent-red);padding:12px 0;">Failed to generate playlist. Please try again.</div>`;
    } finally {
        playlistGenerating = false;
        if (btn) btn.innerHTML = `<span>Generate Playlist</span>`;
    }
}

// ---------------------------------------------------------
// Artist Discography — Horizontal Card Grid + Accordion
// ---------------------------------------------------------
let currentArtistAlbums = [];
let currentArtistTracks = [];
let expandedAlbumIdx = -1;

async function openArtistPage(artistName, sortBy = 'popularity') {
    currentArtistName = artistName;
    hideSuggestions();
    switchTab('artist');

    document.getElementById('artistHeroName').innerText = artistName;
    document.getElementById('artistAvatarCircle').innerText = artistName.substring(0, 1).toUpperCase();
    loadArtistHeaderPhoto(artistName);

    document.getElementById('artistTracksList').innerHTML = `<div class="loading-state"><div class="spinner"></div><div>Loading ${artistName}'s catalog...</div></div>`;

    try {
        const res = await fetch(`${API_BASE}/api/artist?name=${encodeURIComponent(artistName)}&sort=${sortBy}`);
        const data = await res.json();
        currentArtistAlbums = data.albums || [];
        currentArtistTracks = data.tracks || [];
        expandedAlbumIdx = -1;
        document.getElementById('artistHeroMeta').innerText = `${currentArtistTracks.length} tracks across ${currentArtistAlbums.length} album releases`;

        renderLastfmArtistInfo(data.lastfm || {}, artistName);
        renderArtistTracks(currentArtistTracks);
    } catch (err) {
        document.getElementById('artistTracksList').innerHTML = `<div class="loading-state">Could not load artist tracks.</div>`;
    }
}

async function loadArtistHeaderPhoto(artistName) {
    const avatarEl = document.getElementById('artistAvatarCircle');
    if (!avatarEl) return;
    try {
        const res = await fetch(`${API_BASE}/api/artist_image?q=${encodeURIComponent(artistName)}`);
        const data = await res.json();
        if (data && data.image_url) {
            avatarEl.innerHTML = `<img src="${data.image_url}" alt="${artistName}" style="width:100%;height:100%;object-fit:cover;border-radius:50%;">`;
        }
    } catch (e) { }
}

const artistImageCache = {};

async function loadArtistCircleAvatar(artistName, elementId) {
    const el = document.getElementById(elementId);
    if (!el || !artistName) return;
    const key = artistName.toLowerCase().trim();
    if (artistImageCache[key] !== undefined) {
        if (artistImageCache[key]) {
            el.innerHTML = `<img src="${artistImageCache[key]}" alt="${artistName}" style="width:100%;height:100%;object-fit:cover;border-radius:50%;">`;
        }
        return;
    }
    try {
        const res = await fetch(`${API_BASE}/api/artist_image?q=${encodeURIComponent(artistName)}`);
        const data = await res.json();
        artistImageCache[key] = (data && data.image_url) ? data.image_url : "";
        if (artistImageCache[key]) {
            el.innerHTML = `<img src="${artistImageCache[key]}" alt="${artistName}" style="width:100%;height:100%;object-fit:cover;border-radius:50%;">`;
        }
    } catch (e) { artistImageCache[key] = ""; }
}


function renderLastfmArtistInfo(lfm, artistName) {
    let existing = document.getElementById('lastfmArtistPanel');
    if (existing) existing.remove();
    if (!lfm || typeof lfm !== 'object' || !Object.keys(lfm).length) return;

    const listeners = lfm.listeners ? `${(lfm.listeners / 1000).toFixed(0)}K listeners` : '';
    const bio = lfm.bio ? lfm.bio.split('Read more')[0].trim() : '';
    const tags = (lfm.tags || []).map(t => `<span class="genre-badge">${t}</span>`).join('');

    const simList = lfm.similar_artists || lfm.similar || [];
    const similarHtml = simList.slice(0, 6).map((s, idx) => {
        const sName = typeof s === 'string' ? s : (s.name || '');
        const idStr = `sim-art-${sName.replace(/[^a-zA-Z0-9]/g, '_')}`;
        setTimeout(() => loadArtistCircleAvatar(sName, idStr), idx * 40);
        return `
        <div class="artist-circle-card" onclick="openArtistPage('${escapeJs(sName)}')">
            <div class="artist-avatar" id="${idStr}">${sName.substring(0, 1).toUpperCase()}</div>
            <div class="artist-circle-name">${sName}</div>
        </div>`;
    }).join('');

    const panel = document.createElement('div');
    panel.id = 'lastfmArtistPanel';
    panel.className = 'lastfm-artist-panel';
    panel.innerHTML = `
        ${listeners ? `<div class="lastfm-listeners">🎧 ${listeners} on Last.fm</div>` : ''}
        ${tags ? `<div class="lastfm-tags">${tags}</div>` : ''}
        ${bio ? `<div class="lastfm-bio">${bio}</div>` : ''}
        ${similarHtml ? `
        <div class="similar-artists-container" style="margin-top:14px;border-top:1px solid rgba(255,255,255,0.06);padding-top:12px;">
            <div style="font-size:11px;font-weight:700;color:var(--text-dim);margin-bottom:8px;text-transform:uppercase;letter-spacing:0.5px;">Similar Artists</div>
            <div class="artist-circles-row">${similarHtml}</div>
        </div>` : ''}
    `;
    const artistView = document.getElementById('viewArtist');
    const filterBar = artistView.querySelector('.artist-filter-bar');
    if (filterBar) artistView.insertBefore(panel, filterBar);
}

function sortArtistTracks(sortBy, btnElem) {
    if (btnElem) {
        document.querySelectorAll('.artist-filter-bar .filter-btn').forEach(b => b.classList.remove('active'));
        btnElem.classList.add('active');
    }
    expandedAlbumIdx = -1;

    if (!currentArtistTracks || currentArtistTracks.length === 0) return;

    let sorted = [...currentArtistTracks];
    if (sortBy === 'popularity') {
        sorted.sort((a, b) => (b.popularity_pct || 0) - (a.popularity_pct || 0));
    } else if (sortBy === 'newest') {
        sorted.sort((a, b) => (parseInt(b.year) || 0) - (parseInt(a.year) || 0));
    } else if (sortBy === 'oldest') {
        sorted.sort((a, b) => (parseInt(a.year) || 0) - (parseInt(b.year) || 0));
    } else if (sortBy === 'title') {
        sorted.sort((a, b) => (a.name || '').localeCompare(b.name || ''));
    }

    renderArtistTracks(sorted);
}

function toggleArtistAlbumsView(btnElem) {
    if (btnElem) {
        document.querySelectorAll('.artist-filter-bar .filter-btn').forEach(b => b.classList.remove('active'));
        btnElem.classList.add('active');
    }
    expandedAlbumIdx = -1;
    renderArtistAlbums(currentArtistAlbums);
}

function renderArtistTracks(tracks) {
    if (!tracks || tracks.length === 0) {
        document.getElementById('artistTracksList').innerHTML = `<div class="loading-state">No tracks found.</div>`;
        return;
    }

    let html = '';
    tracks.forEach((t, idx) => {
        const genres = (t.base_genres || t.genres || []).slice(0, 2);
        const activeSig = (t.row >= 0 ? userTrackSignals[t.row] : null) || userTrackSignals[getTrackKey(t.name, t.artist)] || '';
        html += `
        <div class="track-card" id="card-a-${t.row}" onclick="selectTrackForInsights(${t.row}, '${escapeJs(t.name)}', '${escapeJs(t.artist)}', this)">
            <div class="track-info-side">
                <div class="cover-art-box enrich-art" id="art-a-${t.row}" data-track-key="${escapeAttr(getTrackKey(t.name, t.artist))}" data-track-name="${escapeAttr(t.name)}" data-artist-name="${escapeAttr(t.artist)}" data-row="${t.row}">${getInitialArtHtml(t)}</div>
                <div class="track-details">
                    <div class="track-name">${idx + 1}. ${t.name}</div>
                    <div class="track-artist">${t.artist} ${t.year ? `· <span style="color:var(--text-dim);">${t.year}</span>` : ''}</div>
                    <div class="tags-list">
                        ${genres.map(g => `<span class="genre-badge ${getGenreClass(g)}">${g}</span>`).join('')}
                        ${t.popularity_pct ? `<span class="signal-badge">popularity ${t.popularity_pct}%</span>` : ''}
                        ${t.tempo_bpm ? `<span class="signal-badge">${t.tempo_bpm} BPM</span>` : ''}
                    </div>
                    <div class="listen-on-row" id="enrich-a-${t.row}" data-track-key="${escapeAttr(getTrackKey(t.name, t.artist))}" style="${t.deezer_link || t.youtube_music_url ? 'display:flex;' : ''}">${getInitialListenRowHtml(t)}</div>
                </div>
            </div>
            <div class="track-action-side">
                <div class="action-buttons">
                    <button class="btn-act like ${activeSig === 'like' ? 'active-like' : ''}" onclick="event.stopPropagation();sendFeedback(${t.row}, 'like', this)">${SVG_ICONS.like}</button>
                    <button class="btn-act dislike ${activeSig === 'dislike' ? 'active-dislike' : ''}" onclick="event.stopPropagation();sendFeedback(${t.row}, 'dislike', this)">${SVG_ICONS.dislike}</button>
                    <button class="btn-act explore" onclick="event.stopPropagation();selectDropdownItem('${escapeJs(t.name)}', '${escapeJs(t.artist)}')">${SVG_ICONS.explore} Explore</button>
                </div>
            </div>
        </div>`;
        if (t) seedEnrichCache(t);
    });

    const artistListEl = document.getElementById('artistTracksList');
    artistListEl.innerHTML = html;
    observeEnrichElements(artistListEl);
}

// ---- Album view: horizontal cards + accordion expand ----

function renderArtistAlbums(albums) {
    if (!albums || albums.length === 0) {
        document.getElementById('artistTracksList').innerHTML = `<div class="loading-state">No albums found.</div>`;
        return;
    }

    if (expandedAlbumIdx >= 0 && expandedAlbumIdx < albums.length) {
        renderExpandedAlbum(albums, expandedAlbumIdx);
        return;
    }

    const albumGradients = [
        'linear-gradient(135deg,#1a1a2e,#16213e)', 'linear-gradient(135deg,#0d0d0d,#1e3a1e)',
        'linear-gradient(135deg,#1a0a0a,#3a1010)', 'linear-gradient(135deg,#0a0a1a,#1a1040)',
    ];
    let html = `<div class="album-card-grid">`;
    albums.forEach((al, idx) => {
        const grad = albumGradients[idx % albumGradients.length];
        const cleanTitle = al.title.replace(' & Album Tracks', '').replace(' (Single/Release)', '');
        const firstTrack = (al.tracks && al.tracks.length) ? al.tracks[0] : null;
        const trackKey = firstTrack ? getTrackKey(firstTrack.name, firstTrack.artist) : '';

        html += `
        <div class="album-card" onclick="expandAlbum(${idx})" title="${escapeAttr(cleanTitle)}">
            <div class="album-card-art enrich-art" id="art-album-${idx}" data-track-key="${escapeAttr(trackKey)}" style="background:${grad}">
                <div class="album-card-icon">💿</div>
            </div>
            <div class="album-card-info">
                <div class="album-card-title">${cleanTitle}</div>
                <div class="album-card-meta">${al.year} · ${al.track_count} ${al.track_count === 1 ? 'track' : 'tracks'}</div>
            </div>
        </div>`;

        if (firstTrack) {
            queueTrackEnrichment(firstTrack.name, firstTrack.artist, firstTrack.row, firstTrack);
        }
    });
    html += `</div>`;
    document.getElementById('artistTracksList').innerHTML = html;
}

function expandAlbum(idx) {
    expandedAlbumIdx = idx;
    renderExpandedAlbum(currentArtistAlbums, idx);
}

function renderExpandedAlbum(albums, idx) {
    const album = albums[idx];
    if (!album) return;
    const total = albums.length;
    const hasPrev = idx > 0;
    const hasNext = idx < total - 1;
    const cleanTitle = album.title.replace(' & Album Tracks', '').replace(' (Single/Release)', '');

    let html = `
    <div class="album-expanded-header">
        <button class="album-back-btn" onclick="collapseAlbum()">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="15 18 9 12 15 6"/></svg>
            All Albums
        </button>
        <div class="album-nav-wrap">
            <button class="album-nav-btn" ${hasPrev ? '' : 'disabled'} onclick="expandAlbum(${idx - 1})">
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="15 18 9 12 15 6"/></svg>
            </button>
            <span class="album-nav-label">${idx + 1} / ${total}</span>
            <button class="album-nav-btn" ${hasNext ? '' : 'disabled'} onclick="expandAlbum(${idx + 1})">
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"/></svg>
            </button>
        </div>
    </div>
    <div class="album-expanded-info">
        <div class="album-expanded-art">💿</div>
        <div>
            <div class="album-expanded-title">${cleanTitle}</div>
            <div class="album-expanded-meta">${album.year} · ${album.track_count} ${album.track_count === 1 ? 'track' : 'tracks'}</div>
        </div>
    </div>
    <div class="album-tracks-list">`;

    album.tracks.forEach((t, tidx) => {
        const trackKey = getTrackKey(t.name, t.artist);
        const genres = (t.base_genres || t.genres || []).slice(0, 2);
        const activeSig = (t.row >= 0 ? userTrackSignals[t.row] : null) || userTrackSignals[getTrackKey(t.name, t.artist)] || '';
        html += `
        <div class="track-card" id="card-ex-${t.row}" onclick="selectTrackForInsights(${t.row}, '${escapeJs(t.name)}', '${escapeJs(t.artist)}', this)">
            <div class="track-info-side">
                <div class="cover-art-box enrich-art" id="art-ex-${t.row}" data-track-key="${escapeAttr(trackKey)}">🎵</div>
                <div class="track-details">
                    <div class="track-name">${tidx + 1}. ${t.name}</div>
                    <div class="track-artist">${t.artist} ${t.year ? `· <span style="color:var(--text-dim);">${t.year}</span>` : ''}</div>
                    <div class="tags-list">
                        ${genres.map(g => `<span class="genre-badge ${getGenreClass(g)}">${g}</span>`).join('')}
                        ${t.popularity_pct ? `<span class="signal-badge">popularity ${t.popularity_pct}%</span>` : ''}
                    </div>
                    <div class="listen-on-row" id="enrich-ex-${t.row}" data-track-key="${escapeAttr(trackKey)}"></div>
                </div>
            </div>
            <div class="track-action-side">
                <div class="action-buttons">
                    <button class="btn-act like ${activeSig === 'like' ? 'active-like' : ''}" onclick="event.stopPropagation();sendFeedback(${t.row}, 'like', this)">${SVG_ICONS.like}</button>
                    <button class="btn-act dislike ${activeSig === 'dislike' ? 'active-dislike' : ''}" onclick="event.stopPropagation();sendFeedback(${t.row}, 'dislike', this)">${SVG_ICONS.dislike}</button>
                    <button class="btn-act explore" onclick="event.stopPropagation();selectDropdownItem('${escapeJs(t.name)}', '${escapeJs(t.artist)}')">${SVG_ICONS.explore} Explore</button>
                </div>
            </div>
        </div>`;
        queueTrackEnrichment(t.name, t.artist, t.row, t);
    });
    html += `</div>`;
    document.getElementById('artistTracksList').innerHTML = html;
}

function collapseAlbum() {
    expandedAlbumIdx = -1;
    renderArtistAlbums(currentArtistAlbums);
}



// ---------------------------------------------------------
// Standalone Album & Movie Soundtrack Page View
// ---------------------------------------------------------
async function openAlbumPage(albumTitle, artistName = '', albumId = '', source = '') {
    currentArtistName = artistName;
    hideSuggestions();
    switchTab('album');

    document.getElementById('albumTitle').innerText = albumTitle;
    document.getElementById('albumMeta').innerText = `${artistName || 'Various Artists'} · Movie / Soundtrack Album`;
    document.getElementById('albumArtBox').innerHTML = '💿';
    document.getElementById('albumTracksList').innerHTML = `<div class="loading-state"><div class="spinner"></div><div>Loading tracks for "${albumTitle}"...</div></div>`;

    try {
        const res = await fetch(`${API_BASE}/api/album_tracks?title=${encodeURIComponent(albumTitle)}&artist=${encodeURIComponent(artistName)}&id=${encodeURIComponent(albumId)}&source=${encodeURIComponent(source)}`);
        const data = await res.json();

        document.getElementById('albumTitle').innerText = data.title || albumTitle;
        document.getElementById('albumMeta').innerText = `${data.artist || artistName || 'Soundtrack'} · ${data.tracks.length} songs`;

        if (data.cover_art) {
            document.getElementById('albumArtBox').innerHTML = `<img src="${data.cover_art}" alt="${albumTitle}" style="width:100%;height:100%;object-fit:cover;border-radius:12px;">`;
        } else if (data.tracks.length > 0 && data.tracks[0].deezer_album_art) {
            document.getElementById('albumArtBox').innerHTML = `<img src="${data.tracks[0].deezer_album_art}" alt="${albumTitle}" style="width:100%;height:100%;object-fit:cover;border-radius:12px;">`;
        }

        if (data.tracks) {
            data.tracks.forEach(seedEnrichCache);
        }

        renderAlbumTrackList(data.tracks, albumTitle);
    } catch (err) {
        document.getElementById('albumTracksList').innerHTML = `<div class="loading-state">Could not load album tracks.</div>`;
    }
}

function renderAlbumTrackList(tracks, albumTitle) {
    if (!tracks || tracks.length === 0) {
        document.getElementById('albumTracksList').innerHTML = `<div class="loading-state">No songs found in this album.</div>`;
        return;
    }

    let html = '';
    tracks.forEach((t, idx) => {
        const trackKey = getTrackKey(t.name, t.artist);
        const genres = (t.base_genres || t.genres || []).slice(0, 2);
        const activeSig = (t.row >= 0 ? userTrackSignals[t.row] : null) || userTrackSignals[getTrackKey(t.name, t.artist)] || '';
        const artHtml = t.deezer_album_art ? `<img src="${t.deezer_album_art}" style="width:100%;height:100%;object-fit:cover;border-radius:8px;">` : '🎵';

        html += `
        <div class="track-card" id="card-alb-${idx}" onclick="selectTrackForInsights(${t.row}, '${escapeJs(t.name)}', '${escapeJs(t.artist)}', this)">
            <div class="track-info-side">
                <div class="cover-art-box enrich-art" id="art-alb-${idx}" data-track-key="${escapeAttr(trackKey)}">${artHtml}</div>
                <div class="track-details">
                    <div class="track-name">${idx + 1}. ${t.name}</div>
                    <div class="track-artist">${t.artist} ${t.year ? `· <span style="color:var(--text-dim);">${t.year}</span>` : ''}</div>
                    <div class="tags-list">
                        ${genres.map(g => `<span class="genre-badge ${getGenreClass(g)}">${g}</span>`).join('')}
                        ${t.popularity_pct ? `<span class="signal-badge">popularity ${t.popularity_pct}%</span>` : ''}
                        ${t.tempo_bpm ? `<span class="signal-badge">${t.tempo_bpm} BPM</span>` : ''}
                    </div>
                    <div class="listen-on-row" id="enrich-alb-${idx}" data-track-key="${escapeAttr(trackKey)}"></div>
                </div>
            </div>
            <div class="track-action-side">
                <div class="action-buttons">
                    <button class="btn-act like ${activeSig === 'like' ? 'active-like' : ''}" onclick="event.stopPropagation();sendFeedback(${t.row}, 'like', this)">${SVG_ICONS.like}</button>
                    <button class="btn-act dislike ${activeSig === 'dislike' ? 'active-dislike' : ''}" onclick="event.stopPropagation();sendFeedback(${t.row}, 'dislike', this)">${SVG_ICONS.dislike}</button>
                    <button class="btn-act explore" onclick="event.stopPropagation();selectDropdownItem('${escapeJs(t.name)}', '${escapeJs(t.artist)}')">${SVG_ICONS.explore} Explore</button>
                </div>
            </div>
        </div>`;
        queueTrackEnrichment(t.name, t.artist, t.row, t);
    });

    document.getElementById('albumTracksList').innerHTML = html;
}

// ---------------------------------------------------------
// Feedback
// ---------------------------------------------------------
let userTrackSignals = {};

async function sendFeedback(row, signal, btnElem, extraName, extraArtist) {
    let name = extraName || "";
    let artist = extraArtist || "";
    let deezer_album_art = "";
    let deezer_preview_url = "";

    if (btnElem) {
        const card = btnElem.closest('.track-card') || btnElem.closest('.home-track-card');
        if (card) {
            const nameEl = card.querySelector('.track-name') || card.querySelector('.home-card-name');
            const artistEl = card.querySelector('.track-artist') || card.querySelector('.home-card-artist');
            const imgEl = card.querySelector('.cover-art-box img') || card.querySelector('.home-card-art img');
            if (nameEl && !name) name = nameEl.innerText.replace(/^\d+\.\s*/, '').trim();
            if (artistEl && !artist) artist = artistEl.innerText.split('·')[0].trim();
            if (imgEl) deezer_album_art = imgEl.src || "";
        }
    }

    const trackKey = (name && artist) ? getTrackKey(name, artist) : "";
    const rKey = (row !== undefined && row !== null && row >= 0) ? row : (trackKey || `ext_${name}_${artist}`);

    // YouTube-style toggle logic: clicking an active button toggles it OFF ('none')
    let activeSignal = signal;
    if (userTrackSignals[rKey] === signal || (trackKey && userTrackSignals[trackKey] === signal)) {
        activeSignal = "none";
    }

    userTrackSignals[rKey] = activeSignal;
    if (trackKey) userTrackSignals[trackKey] = activeSignal;

    if (btnElem) {
        btnElem.classList.add('anim-pulse');
        setTimeout(() => btnElem.classList.remove('anim-pulse'), 400);

        const parent = btnElem.parentElement;
        if (parent) {
            parent.querySelectorAll('.btn-act').forEach(b => {
                b.classList.remove('active-like', 'active-dislike');
            });
            if (activeSignal === 'like') btnElem.classList.add('active-like');
            if (activeSignal === 'dislike') btnElem.classList.add('active-dislike');
        }
    }

    if (name && artist) {
        const cacheKey = getTrackKey(name, artist);
        const cached = enrichCache[cacheKey];
        if (cached) {
            if (cached.deezer_album_art) deezer_album_art = cached.deezer_album_art;
            if (cached.deezer_preview_url) deezer_preview_url = cached.deezer_preview_url;
        }
    }

    if (activeSignal === 'none') {
        showToast(signal === 'like' ? 'Removed from Liked Songs' : 'Dislike removed');
    } else if (activeSignal === 'like') {
        showToast(`Added "${name || 'song'}" to Liked Songs`, 'success');
    } else if (activeSignal === 'dislike') {
        showToast(`Marked "${name || 'song'}" as Disliked`, 'info');
    }

    try {
        await fetch(`${API_BASE}/api/feedback`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user: currentUser,
                row: (row !== undefined && row !== null) ? row : -1,
                signal: activeSignal,
                mode: currentMode,
                name: name || undefined,
                artist: artist || undefined,
                deezer_album_art: deezer_album_art || undefined,
                deezer_preview_url: deezer_preview_url || undefined
            })
        });
        refreshProfileStats();
    } catch (err) { console.error(err); }
}

// ---------------------------------------------------------
// Profile Stats & My Songs
// ---------------------------------------------------------
// Debounce: at most one profile refresh per 3 seconds
let _profileRefreshTimer = null;
let _profileRefreshPending = false;

async function _doRefreshProfileStats() {
    _profileRefreshPending = false;
    try {
        const res = await fetch(`${API_BASE}/api/profile?user=${encodeURIComponent(currentUser)}`);
        const data = await res.json();
        profileDataCache = data.history || [];

        // Pre-fill userTrackSignals map from profile active history
        (data.history || []).forEach(ev => {
            if (ev.signal) {
                if (ev.row !== undefined && ev.row !== null && ev.row >= 0) {
                    userTrackSignals[ev.row] = ev.signal;
                }
                if (ev.name && ev.artist) {
                    const tk = getTrackKey(ev.name, ev.artist);
                    userTrackSignals[tk] = ev.signal;
                }
            }
        });

        document.getElementById('profileCardUser').innerText = currentUser;
        document.getElementById('topGenresList').innerText = data.top_genres.length ? data.top_genres.map(g => g[0]).join(', ') : 'None yet';
        document.getElementById('topArtistsList').innerText = data.top_artists.length ? data.top_artists.map(a => a[0]).join(', ') : 'None yet';
    } catch (err) { console.error(err); }
}

async function refreshProfileStats() {
    // Debounce: coalesce rapid calls (e.g. multiple likes in quick succession)
    // into at most one network request per 3 seconds.
    if (_profileRefreshPending) return;
    _profileRefreshPending = true;
    clearTimeout(_profileRefreshTimer);
    _profileRefreshTimer = setTimeout(_doRefreshProfileStats, 3000);
}

async function loadMySongs() {
    await refreshProfileStats();
    filterMySongs('all');
}

async function removeMySong(row, name, artist, cardElem) {
    if (cardElem) {
        cardElem.style.transition = 'all 0.3s ease';
        cardElem.style.opacity = '0';
        cardElem.style.transform = 'scale(0.95)';
        setTimeout(() => {
            cardElem.remove();
            const container = document.getElementById('mySongsList');
            if (container && container.querySelectorAll('.my-song-card').length === 0) {
                container.innerHTML = `<div class="loading-state" style="padding: 60px;">No tracks found in history for profile '${currentUser}'.</div>`;
            }
        }, 300);
    }

    const trackKey = (name && artist) ? getTrackKey(name, artist) : "";
    const rKey = (row !== undefined && row !== null && row >= 0) ? row : (trackKey || `ext_${name}_${artist}`);

    userTrackSignals[rKey] = 'none';
    if (trackKey) userTrackSignals[trackKey] = 'none';

    profileDataCache = profileDataCache.filter(item => {
        const itemKey = getTrackKey(item.name, item.artist);
        if (trackKey && itemKey === trackKey) return false;
        if (row >= 0 && item.row === row) return false;
        return true;
    });

    showToast(`Removed "${name || 'song'}" from My Songs`, 'info');

    try {
        await fetch(`${API_BASE}/api/feedback`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user: currentUser,
                row: (row !== undefined && row !== null) ? row : -1,
                signal: 'none',
                mode: currentMode,
                name: name || undefined,
                artist: artist || undefined
            })
        });
        refreshProfileStats();
    } catch (err) { console.error(err); }
}

async function handleMySongSignal(row, signal, btnElem, name, artist) {
    const card = btnElem.closest('.my-song-card');
    const tk = getTrackKey(name, artist);
    const rKey = (row !== undefined && row !== null && row >= 0) ? row : (tk || `ext_${name}_${artist}`);
    const cardSig = card ? card.getAttribute('data-signal') : '';
    const currentSignal = userTrackSignals[rKey] || userTrackSignals[tk] || cardSig || '';

    if (currentSignal === signal) {
        // Clicking active icon again removes the song from My Songs
        await removeMySong(row, name, artist, card);
    } else {
        await sendFeedback(row, signal, btnElem, name, artist);
        const item = profileDataCache.find(i => (row >= 0 && i.row === row) || (getTrackKey(i.name, i.artist) === tk));
        if (item) item.signal = signal;

        if (card) {
            card.setAttribute('data-signal', signal);
            const badgeBox = card.querySelector('.tags-list');
            if (badgeBox) {
                const signalLabel = signal === 'like' ? 'Liked' : 'Disliked';
                const signalClass = signal === 'like' ? 'signal-like' : 'signal-dislike';
                const signalIcon = signal === 'like' ? SVG_ICONS.like : SVG_ICONS.dislike;
                badgeBox.innerHTML = `<span class="signal-badge ${signalClass}">${signalIcon} ${signalLabel}</span>`;
            }
            const likeBtn = card.querySelector('.btn-act.like');
            const dislikeBtn = card.querySelector('.btn-act.dislike');
            if (likeBtn) likeBtn.classList.toggle('active-like', signal === 'like');
            if (dislikeBtn) dislikeBtn.classList.toggle('active-dislike', signal === 'dislike');
        }
    }
}

function filterMySongs(filterType, btnElem) {
    if (btnElem) {
        document.querySelectorAll('#viewMySongs .filter-btn').forEach(b => b.classList.remove('active'));
        btnElem.classList.add('active');
    }

    let filtered = profileDataCache;
    if (filterType === 'like') filtered = profileDataCache.filter(t => t.signal === 'like');
    if (filterType === 'dislike') filtered = profileDataCache.filter(t => t.signal === 'dislike');

    const container = document.getElementById('mySongsList');
    if (!container) return;

    if (filtered.length === 0) {
        container.innerHTML = `<div class="loading-state" style="padding: 60px;">No tracks found in '${filterType}' history for profile '${currentUser}'.</div>`;
        return;
    }

    let html = '<div class="my-songs-grid">';
    filtered.forEach((t, idx) => {
        const signalLabel = t.signal === 'like' ? 'Liked' : 'Disliked';
        const signalClass = t.signal === 'like' ? 'signal-like' : 'signal-dislike';
        const signalIcon = t.signal === 'like' ? SVG_ICONS.like : SVG_ICONS.dislike;

        const artHtml = t.deezer_album_art ? `<img src="${t.deezer_album_art}" style="width:100%;height:100%;object-fit:cover;border-radius:8px;">` : '🎵';

        const tk = getTrackKey(t.name, t.artist);
        const rKey = (t.row !== undefined && t.row !== null && t.row >= 0) ? t.row : (tk || `ext_${t.name}_${t.artist}`);
        const activeSig = userTrackSignals[rKey] || userTrackSignals[tk] || t.signal || '';

        html += `
        <div class="track-card my-song-card" id="card-h-${t.row}" data-signal="${activeSig}" onclick="selectTrackForInsights(${t.row}, '${escapeJs(t.name)}', '${escapeJs(t.artist)}', this)">
            <div class="track-info-side">
                <div class="cover-art-box enrich-art" id="art-h-${t.row}" data-track-key="${escapeAttr(getTrackKey(t.name, t.artist))}">${artHtml}</div>
                <div class="track-details">
                    <div class="track-name">${t.name}</div>
                    <div class="track-artist" onclick="event.stopPropagation();openArtistPage('${escapeJs(t.artist)}')">${t.artist} ${t.year ? `· <span style="color:var(--text-dim);">${t.year}</span>` : ''}</div>
                    <div class="tags-list">
                        <span class="signal-badge ${signalClass}">${signalIcon} ${signalLabel}</span>
                    </div>
                    <div class="listen-on-row" id="enrich-h-${t.row}" data-track-key="${escapeAttr(getTrackKey(t.name, t.artist))}"></div>
                </div>
            </div>
            <div class="track-action-side" style="display:flex;align-items:center;gap:6px;">
                <button class="btn-act like ${activeSig === 'like' ? 'active-like' : ''}" title="${activeSig === 'like' ? 'Remove from My Songs' : 'Like'}" onclick="event.stopPropagation();handleMySongSignal(${t.row}, 'like', this, '${escapeJs(t.name)}', '${escapeJs(t.artist)}')">${SVG_ICONS.like}</button>
                <button class="btn-act dislike ${activeSig === 'dislike' ? 'active-dislike' : ''}" title="${activeSig === 'dislike' ? 'Remove from My Songs' : 'Dislike'}" onclick="event.stopPropagation();handleMySongSignal(${t.row}, 'dislike', this, '${escapeJs(t.name)}', '${escapeJs(t.artist)}')">${SVG_ICONS.dislike}</button>
                <button class="btn-act explore" onclick="event.stopPropagation();selectDropdownItem('${escapeJs(t.name)}', '${escapeJs(t.artist)}', {name: '${escapeJs(t.name)}', artist: '${escapeJs(t.artist)}', row: ${t.row !== undefined && t.row !== null ? t.row : -1}, deezer_album_art: '${escapeJs(t.deezer_album_art || '')}'})">${SVG_ICONS.explore} Explore</button>
            </div>
        </div>`;
        queueTrackEnrichment(t.name, t.artist, t.row, t);
    });
    html += '</div>';
    container.innerHTML = html;
}

// ---------------------------------------------------------
// Horizontal Drag-to-Scroll & Mouse Wheel Support for Desktop
// ---------------------------------------------------------
function makeHorizontalScrollable(el) {
    if (!el || el.dataset.scrollAttached) return;
    el.dataset.scrollAttached = 'true';

    let isDown = false;
    let startX, scrollLeft;

    el.addEventListener('mousedown', (e) => {
        isDown = true;
        startX = e.pageX - el.offsetLeft;
        scrollLeft = el.scrollLeft;
        el.style.cursor = 'grabbing';
    });

    el.addEventListener('mouseleave', () => {
        isDown = false;
        el.style.cursor = '';
    });

    el.addEventListener('mouseup', () => {
        isDown = false;
        el.style.cursor = '';
    });

    el.addEventListener('mousemove', (e) => {
        if (!isDown) return;
        e.preventDefault();
        const x = e.pageX - el.offsetLeft;
        const walk = (x - startX) * 1.6;
        el.scrollLeft = scrollLeft - walk;
    });

    el.addEventListener('wheel', (e) => {
        if (e.deltaY !== 0 && el.scrollWidth > el.clientWidth) {
            e.preventDefault();
            el.scrollLeft += e.deltaY;
        }
    }, { passive: false });
}

function enableAllHorizontalScrolls() {
    document.querySelectorAll('.album-circles-row, .artist-circles-row, .cards-scroll-row, .search-albums-row').forEach(makeHorizontalScrollable);
}

// ---------------------------------------------------------
// Application Init
// ---------------------------------------------------------
window.onload = () => {
    loadUsers();
    refreshProfileStats();
    loadHomePage();

    // Use MutationObserver instead of setInterval polling to bind scroll handlers.
    // This fires only when DOM actually changes, saving ~500ms CPU cycles/second.
    const _scrollObserver = new MutationObserver(() => {
        enableAllHorizontalScrolls();
    });
    const _mainContent = document.querySelector('.main-content') || document.body;
    _scrollObserver.observe(_mainContent, { childList: true, subtree: true });
    // Run once on load in case elements already exist
    enableAllHorizontalScrolls();
};