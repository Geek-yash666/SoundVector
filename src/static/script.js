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
        .replace(/"/g, '&quot;');
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
    const modal = document.getElementById('mobileInsightsModal');
    const body = document.getElementById('mobileInsightsBody');
    if (!modal || !body) return;

    document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
    const navIM = document.getElementById('navIntelMobile');
    if (navIM) navIM.classList.add('active');

    const pBox = document.getElementById('profileBox');
    const djPanel = document.getElementById('djIntelPanel');
    const aPanel = document.getElementById('audioVectorPanel');

    body.innerHTML = '';
    
    if (pBox) {
        const pClone = pBox.cloneNode(true);
        pClone.id = pClone.id + '_mobile';
        pClone.style.marginBottom = '16px';
        pClone.classList.remove('hidden');
        body.appendChild(pClone);
    }
    if (djPanel) {
        const djClone = djPanel.cloneNode(true);
        djClone.id = djClone.id + '_mobile';
        djClone.style.marginBottom = '16px';
        djClone.classList.remove('hidden');
        body.appendChild(djClone);
    }
    if (aPanel) {
        const aClone = aPanel.cloneNode(true);
        aClone.id = aClone.id + '_mobile';
        aClone.style.marginBottom = '16px';
        aClone.classList.remove('hidden');
        body.appendChild(aClone);
    }

    modal.classList.remove('hidden');
}

function closeMobileInsights() {
    const modal = document.getElementById('mobileInsightsModal');
    if (modal) modal.classList.add('hidden');
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
    if (q.length < 2) { hideSuggestions(); return; }

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
            <div class="artist-circle-card" onclick="openArtistPage('${a.artist.replace(/'/g, "\\'")}')">
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
            <div class="dropdown-album-card" onclick="openAlbumPage('${alb.title.replace(/'/g, "\\'")}', '${(alb.artist || '').replace(/'/g, "\\'")}', '${alb.id || ''}', '${alb.source || ''}')" style="display:flex;align-items:center;gap:8px;padding:6px 10px;background:rgba(255,255,255,0.04);border-radius:8px;cursor:pointer;min-width:160px;max-width:220px;border:1px solid rgba(255,255,255,0.06);flex-shrink:0;">
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

function selectDropdownItem(name, artist) {
    const query = artist && artist !== 'Unknown Artist' ? `${name} ${artist}` : name;
    searchInput.value = query;
    hideSuggestions();
    switchTab('discover');
    executeSearch(query, 'track');
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
            html += `<button class="quick-chip" onclick="quickGenreSearch('${g.replace(/'/g, "\\'")}')">${g}</button>`;
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
                <div class="home-card-art enrich-art" id="art-hs-${t.row}" data-track-key="${escapeAttr(getTrackKey(t.name, t.artist))}">🎵</div>
                <div class="home-card-name" title="${escapeAttr(t.name)}">${t.name || 'Unknown'}</div>
                <div class="home-card-artist" onclick="event.stopPropagation();openArtistPage('${escapeJs(t.artist)}')" title="${escapeAttr(t.artist)}">${t.artist || 'Unknown'}</div>
                <div class="home-card-meta">
                    ${genres.map(g => `<span class="genre-badge ${getGenreClass(g)}">${g}</span>`).join('')}
                </div>
                <div class="listen-on-row" id="enrich-hs-${t.row}" data-track-key="${escapeAttr(getTrackKey(t.name, t.artist))}"></div>
            </div>`;
        setTimeout(() => loadTrackEnrichment(t.name, t.artist, `enrich-hs-${t.row}`, t.row), idx * 60);
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
            <div class="browse-card" style="background-color: ${cat.color};" onclick="selectBrowseCategory('${cat.id}', '${cat.title.replace(/'/g, "\\'")}')">
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
async function executeSearch(query, forcedType = null, seedTrack = null) {
    const searchType = forcedType || currentSearchType;
    document.getElementById('recList').innerHTML = `
        <div class="loading-state">
            <div class="spinner"></div>
            <div>Searching for "${query}"...</div>
        </div>`;

    try {
        const res = await fetch(`${API_BASE}/api/recommend`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query, mode: currentMode, user: currentUser, search_type: searchType, seed_track: seedTrack })
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
    data.recs.forEach((r, idx) => {
        const sigs = r.signals || {};
        const activeSig = userTrackSignals[r.row] || '';
        html += `
        <div class="track-card" id="card-${r.row}" onclick="selectTrackForInsights(${r.row}, '${escapeJs(r.name)}', '${escapeJs(r.artist)}', this)">
            <div class="track-info-side">
                <div class="cover-art-box enrich-art" id="art-${r.row}" data-track-key="${escapeAttr(getTrackKey(r.name, r.artist))}">🎵</div>
                <div class="track-details">
                    <div class="track-name">${idx + 1}. ${r.name}</div>
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
                    <button class="btn-act skip ${activeSig === 'skip' ? 'active-skip' : ''}" onclick="event.stopPropagation();sendFeedback(${r.row}, 'skip', this)">${SVG_ICONS.skip}</button>
                    <button class="btn-act explore" onclick="event.stopPropagation();selectDropdownItem('${escapeJs(r.name)}', '${escapeJs(r.artist)}')">${SVG_ICONS.explore} Explore</button>
                </div>
            </div>
        </div>`;
        // Lazy-load enrichment for each rec card
        setTimeout(() => loadTrackEnrichment(r.name, r.artist, `enrich-${r.row}`, r.row), idx * 80);
    });

    document.getElementById('recList').innerHTML = html;
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
        if (modal) modal.classList.remove('hidden');
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

    // AI Insight headline
    if (intel.headline || intel.reasoning) {
        html += `
        <div style="padding:14px 0 10px;border-bottom:1px solid var(--border);">
            ${data.backend && data.backend.includes('gemini') ? `<span style="font-size:10px;font-weight:700;color:var(--accent-green);letter-spacing:0.5px;text-transform:uppercase;display:inline-flex;align-items:center;gap:4px;margin-bottom:6px;"><svg viewBox='0 0 24 24' width='10' height='10' fill='currentColor'><path d='M12 2l2.09 6.26L20 10l-5.91 1.74L12 18l-2.09-6.26L4 10l5.91-1.74z'/></svg>AI Insight</span><br>` : ''}
            <div style="font-size:15px;font-weight:700;color:#fff;line-height:1.4;">${intel.headline || ''}</div>
            ${intel.reasoning ? `<div style="font-size:13px;color:var(--text-secondary);margin-top:6px;line-height:1.5;">${intel.reasoning}</div>` : ''}
            ${intel.listen_if ? `<div style="font-size:12px;color:var(--text-dim);margin-top:6px;font-style:italic;">${intel.listen_if}</div>` : ''}
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
}

// ---------------------------------------------------------
// Track Enrichment: Deezer + iTunes Preview + YouTube Music
// ---------------------------------------------------------
const enrichCache = {};

async function loadTrackEnrichment(trackName, artistName, containerId, row) {
    if (!trackName || !artistName) return;
    const cacheKey = getTrackKey(trackName, artistName);
    let data = enrichCache[cacheKey];
    if (!data) {
        try {
            const res = await fetch(`${API_BASE}/api/enrich?track=${encodeURIComponent(trackName)}&artist=${encodeURIComponent(artistName)}`);
            data = await res.json();
            enrichCache[cacheKey] = data;
        } catch (e) { return; }
    }

    let btns = '';
    if (data.deezer_link) {
        btns += `<a class="listen-btn deezer-btn" href="${data.deezer_link}" target="_blank" onclick="event.stopPropagation();" title="Open on Deezer">${SVG_ICONS.deezer} <span>Deezer</span></a>`;
    }
    if (data.youtube_music_url) {
        btns += `<a class="listen-btn yt-btn" href="${data.youtube_music_url}" target="_blank" onclick="event.stopPropagation();" title="Search on YouTube Music">${SVG_ICONS.youtube} <span>YT Music</span></a>`;
    }

    // Update ALL matching cover art elements in DOM with album art + play overlay
    if (data.deezer_album_art) {
        document.querySelectorAll('.enrich-art').forEach(artEl => {
            if (artEl.getAttribute('data-track-key') === cacheKey) {
                let overlayHtml = '';
                if (data.deezer_preview_url) {
                    // Force HTTPS — iOS Safari blocks HTTP audio on HTTPS pages
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

    // Update ALL matching listen rows in DOM
    document.querySelectorAll('.listen-on-row').forEach(listenEl => {
        if (listenEl.getAttribute('data-track-key') === cacheKey) {
            if (btns) {
                listenEl.innerHTML = btns;
                listenEl.style.display = 'flex';
            } else {
                listenEl.style.display = 'none';
            }
        }
    });
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

function togglePreview(url, row, btn, trackName, artistName, coverArt) {
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
            currentAudio.play();
            btn.innerHTML = SVG_ICONS.pause;
            btn.classList.add('playing');
            if (bar) updatePlayerBarState(true);
            return;
        }
    }

    // Stop current audio immediately if playing a NEW song
    if (currentAudio) {
        currentAudio.pause();
        currentAudio = null;
        if (playerInterval) clearInterval(playerInterval);
        document.querySelectorAll('.art-play-overlay.playing').forEach(b => {
            b.innerHTML = SVG_ICONS.play;
            b.classList.remove('playing');
        });
    }

    currentAudio = new Audio();
    currentAudio.preload = 'none';
    currentAudio.crossOrigin = 'anonymous';
    // Force HTTPS for mobile browser compatibility
    currentAudio.src = url.replace(/^http:\/\//i, 'https://');
    currentPlayingUrl = url;
    currentPlayingRow = row;
    currentAudio.volume = 0.8;

    currentAudio.play().then(() => {
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
    }).catch(err => {
        const isNotSupported = err.name === 'NotSupportedError' || err.message.includes('no supported source');
        const isNotAllowed = err.name === 'NotAllowedError';
        if (isNotAllowed) {
            showToast('Tap the play button to start preview', 'info');
        } else if (isNotSupported) {
            showToast('Preview unavailable for this track', 'info');
        } else {
            showToast('Preview could not load', 'info');
        }
        // Reset button state on failure
        btn.innerHTML = SVG_ICONS.play;
        btn.classList.remove('playing');
        currentAudio = null;
        currentPlayingUrl = null;
    });

    btn.innerHTML = SVG_ICONS.pause;
    btn.classList.add('playing');

    currentAudio.onended = () => {
        btn.innerHTML = SVG_ICONS.play;
        btn.classList.remove('playing');
        currentPlayingRow = null;
        currentPlayingUrl = null;
        if (playerInterval) clearInterval(playerInterval);
        if (bar) updatePlayerBarState(false);
    };
    showToast(`▶ 30s preview playing: ${trackName || 'Preview'}`, '🎵');
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
    const titleEl = document.getElementById('playlistTitle');
    const metaEl = document.getElementById('playlistMeta');
    const listEl = document.getElementById('playlistViewTracksList');

    if (titleEl) titleEl.innerText = data.playlist_name || 'Curated Mix';
    if (metaEl) metaEl.innerText = `${data.description || 'Custom Vibe Mix'} · ${(data.tracks || []).length} songs`;

    if (!listEl) return;

    let html = `<div style="display:flex;flex-direction:column;gap:8px;">`;
    (data.tracks || []).forEach((t, i) => {
        const artHtml = t.deezer_album_art ? `<img src="${t.deezer_album_art}" style="width:44px;height:44px;object-fit:cover;border-radius:6px;">` : `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>`;
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
        setTimeout(() => loadTrackEnrichment(t.name, t.artist, `art-plv-${t.row || i}`, t.row || 0), i * 40);
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

async function loadArtistCircleAvatar(artistName, elementId) {
    const el = document.getElementById(elementId);
    if (!el) return;
    try {
        const res = await fetch(`${API_BASE}/api/artist_image?q=${encodeURIComponent(artistName)}`);
        const data = await res.json();
        if (data && data.image_url) {
            el.innerHTML = `<img src="${data.image_url}" alt="${artistName}" style="width:100%;height:100%;object-fit:cover;border-radius:50%;">`;
        }
    } catch (e) { }
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
        const activeSig = userTrackSignals[t.row] || '';
        html += `
        <div class="track-card" id="card-a-${t.row}" onclick="selectTrackForInsights(${t.row}, '${escapeJs(t.name)}', '${escapeJs(t.artist)}', this)">
            <div class="track-info-side">
                <div class="cover-art-box enrich-art" id="art-a-${t.row}" data-track-key="${escapeAttr(getTrackKey(t.name, t.artist))}">🎵</div>
                <div class="track-details">
                    <div class="track-name">${idx + 1}. ${t.name}</div>
                    <div class="track-artist">${t.artist} ${t.year ? `· <span style="color:var(--text-dim);">${t.year}</span>` : ''}</div>
                    <div class="tags-list">
                        ${genres.map(g => `<span class="genre-badge ${getGenreClass(g)}">${g}</span>`).join('')}
                        ${t.popularity_pct ? `<span class="signal-badge">popularity ${t.popularity_pct}%</span>` : ''}
                        ${t.tempo_bpm ? `<span class="signal-badge">${t.tempo_bpm} BPM</span>` : ''}
                    </div>
                    <div class="listen-on-row" id="enrich-a-${t.row}" data-track-key="${escapeAttr(getTrackKey(t.name, t.artist))}"></div>
                </div>
            </div>
            <div class="track-action-side">
                <div class="action-buttons">
                    <button class="btn-act like ${activeSig === 'like' ? 'active-like' : ''}" onclick="event.stopPropagation();sendFeedback(${t.row}, 'like', this)">${SVG_ICONS.like}</button>
                    <button class="btn-act dislike ${activeSig === 'dislike' ? 'active-dislike' : ''}" onclick="event.stopPropagation();sendFeedback(${t.row}, 'dislike', this)">${SVG_ICONS.dislike}</button>
                    <button class="btn-act skip ${activeSig === 'skip' ? 'active-skip' : ''}" onclick="event.stopPropagation();sendFeedback(${t.row}, 'skip', this)">${SVG_ICONS.skip}</button>
                    <button class="btn-act explore" onclick="event.stopPropagation();selectDropdownItem('${escapeJs(t.name)}', '${escapeJs(t.artist)}')">${SVG_ICONS.explore} Explore</button>
                </div>
            </div>
        </div>`;
        setTimeout(() => loadTrackEnrichment(t.name, t.artist, `enrich-a-${t.row}`, t.row), idx * 15);
    });

    document.getElementById('artistTracksList').innerHTML = html;
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
        <div class="album-card" onclick="expandAlbum(${idx})" title="${cleanTitle}">
            <div class="album-card-art enrich-art" id="art-album-${idx}" data-track-key="${escapeAttr(trackKey)}" style="background:${grad}">
                <div class="album-card-icon">💿</div>
            </div>
            <div class="album-card-info">
                <div class="album-card-title">${cleanTitle}</div>
                <div class="album-card-meta">${al.year} · ${al.track_count} ${al.track_count === 1 ? 'track' : 'tracks'}</div>
            </div>
        </div>`;

        if (firstTrack) {
            setTimeout(() => loadTrackEnrichment(firstTrack.name, firstTrack.artist, `art-album-${idx}`, firstTrack.row), idx * 60);
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
        const activeSig = userTrackSignals[t.row] || '';
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
                    <button class="btn-act skip ${activeSig === 'skip' ? 'active-skip' : ''}" onclick="event.stopPropagation();sendFeedback(${t.row}, 'skip', this)">${SVG_ICONS.skip}</button>
                    <button class="btn-act explore" onclick="event.stopPropagation();selectDropdownItem('${escapeJs(t.name)}', '${escapeJs(t.artist)}')">${SVG_ICONS.explore} Explore</button>
                </div>
            </div>
        </div>`;
        setTimeout(() => loadTrackEnrichment(t.name, t.artist, `enrich-ex-${t.row}`, t.row), tidx * 60);
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
        const activeSig = userTrackSignals[t.row] || '';
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
                    <button class="btn-act skip ${activeSig === 'skip' ? 'active-skip' : ''}" onclick="event.stopPropagation();sendFeedback(${t.row}, 'skip', this)">${SVG_ICONS.skip}</button>
                    <button class="btn-act explore" onclick="event.stopPropagation();selectDropdownItem('${t.name.replace(/'/g, "\\'")}', '${t.artist.replace(/'/g, "\\'")}')">${SVG_ICONS.explore} Explore</button>
                </div>
            </div>
        </div>`;
        setTimeout(() => loadTrackEnrichment(t.name, t.artist, `enrich-alb-${idx}`, t.row), idx * 40);
    });

    document.getElementById('albumTracksList').innerHTML = html;
}

// ---------------------------------------------------------
// Feedback
// ---------------------------------------------------------
let userTrackSignals = {};

async function sendFeedback(row, signal, btnElem) {
    userTrackSignals[row] = signal;

    if (btnElem) {
        btnElem.classList.add('anim-pulse');
        setTimeout(() => btnElem.classList.remove('anim-pulse'), 400);

        const parent = btnElem.parentElement;
        if (parent) {
            parent.querySelectorAll('.btn-act').forEach(b => {
                b.classList.remove('active-like', 'active-dislike', 'active-skip');
            });
            if (signal === 'like') btnElem.classList.add('active-like');
            if (signal === 'dislike') btnElem.classList.add('active-dislike');
            if (signal === 'skip') btnElem.classList.add('active-skip');
        }
    }

    try {
        await fetch(`${API_BASE}/api/feedback`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user: currentUser, row, signal, mode: currentMode })
        });
        refreshProfileStats();
    } catch (err) { console.error(err); }
}

// ---------------------------------------------------------
// Profile Stats & My Songs
// ---------------------------------------------------------
async function refreshProfileStats() {
    try {
        const res = await fetch(`${API_BASE}/api/profile?user=${encodeURIComponent(currentUser)}`);
        const data = await res.json();
        profileDataCache = data.history || [];

        document.getElementById('profileCardUser').innerText = currentUser;
        document.getElementById('topGenresList').innerText = data.top_genres.length ? data.top_genres.map(g => g[0]).join(', ') : 'None yet';
        document.getElementById('topArtistsList').innerText = data.top_artists.length ? data.top_artists.map(a => a[0]).join(', ') : 'None yet';
    } catch (err) { console.error(err); }
}

async function loadMySongs() {
    await refreshProfileStats();
    filterMySongs('all');
}

function filterMySongs(filterType, btnElem) {
    if (btnElem) {
        document.querySelectorAll('#viewMySongs .filter-btn').forEach(b => b.classList.remove('active'));
        btnElem.classList.add('active');
    }

    let filtered = profileDataCache;
    if (filterType === 'like') filtered = profileDataCache.filter(t => t.signal === 'like');
    if (filterType === 'dislike') filtered = profileDataCache.filter(t => t.signal === 'dislike');
    if (filterType === 'skip') filtered = profileDataCache.filter(t => t.signal === 'skip');

    const container = document.getElementById('mySongsList');
    if (!container) return;

    if (filtered.length === 0) {
        container.innerHTML = `<div class="loading-state" style="padding: 60px;">No tracks found in '${filterType}' history for profile '${currentUser}'.</div>`;
        return;
    }

    let html = '<div class="my-songs-grid">';
    filtered.forEach((t, idx) => {
        const signalLabel = t.signal === 'like' ? 'Liked' : t.signal === 'dislike' ? 'Disliked' : 'Skipped';
        const signalClass = t.signal === 'like' ? 'signal-like' : t.signal === 'dislike' ? 'signal-dislike' : 'signal-skip';
        const signalIcon = t.signal === 'like' ? SVG_ICONS.like : t.signal === 'dislike' ? SVG_ICONS.dislike : SVG_ICONS.skip;

        html += `
        <div class="track-card my-song-card" id="card-h-${t.row}" onclick="selectTrackForInsights(${t.row}, '${escapeJs(t.name)}', '${escapeJs(t.artist)}', this)">
            <div class="track-info-side">
                <div class="cover-art-box enrich-art" id="art-h-${t.row}" data-track-key="${escapeAttr(getTrackKey(t.name, t.artist))}">🎵</div>
                <div class="track-details">
                    <div class="track-name">${t.name}</div>
                    <div class="track-artist" onclick="event.stopPropagation();openArtistPage('${escapeJs(t.artist)}')">${t.artist} ${t.year ? `· <span style="color:var(--text-dim);">${t.year}</span>` : ''}</div>
                    <div class="tags-list">
                        <span class="signal-badge ${signalClass}">${signalIcon} ${signalLabel}</span>
                    </div>
                    <div class="listen-on-row" id="enrich-h-${t.row}" data-track-key="${escapeAttr(getTrackKey(t.name, t.artist))}"></div>
                </div>
            </div>
            <div class="track-action-side">
                <button class="btn-act explore" onclick="event.stopPropagation();selectDropdownItem('${t.name.replace(/'/g, "\\'")}', '${t.artist.replace(/'/g, "\\'")}')">${SVG_ICONS.explore} Explore</button>
            </div>
        </div>`;
        setTimeout(() => loadTrackEnrichment(t.name, t.artist, `enrich-h-${t.row}`, t.row), idx * 60);
    });
    html += '</div>';
    container.innerHTML = html;
}

// ---------------------------------------------------------
// Application Init
// ---------------------------------------------------------
window.onload = () => {
    loadUsers();
    refreshProfileStats();
    loadHomePage(); // Start at personalized home instead of Starboy search
};