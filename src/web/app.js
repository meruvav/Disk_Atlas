/**
 * Disk Atlas - Main Frontend Application Controller
 * Handles UI interactions, API calls, Inspector Sidebar, Breadcrumbs, and Theme switching.
 * 
 * Optimized for ultra-fast folder selection, instant contents preview, and memoized stats.
 */

class DiskAtlasApp {
  constructor() {
    this.currentData = null;
    this.currentNode = null;
    this.selectedNode = null;
    this.breadcrumbTrail = [];
    this.theme = 'dark';
    this.activeScope = 'folder'; // 'folder', 'drive' ('all' is not implemented yet)
    this.viewMode = 'city'; // 'city', 'layers', 'treemap', 'terrain', 'list'
    this.activeTab = 'contents'; // 'contents', 'hierarchy', 'largest', 'insights'
    this.isScanning = false;
    this.scanPollTimer = null;
    this.nodePathMap = new Map();
    this.appVersion = null;

    this.initVisualizer();
    this.bindEvents();
    this.checkEmbeddedData();
    this.fetchDrives();
    this.initVersionAndUpdates();
  }

  initVisualizer() {
    this.vis = new DiskAtlasVisualizer('canvas-container', {
      theme: this.theme,
      onSelect: (node) => this.selectNode(node),
      onDrillDown: (node) => this.drillDown(node),
    });
  }

  bindEvents() {
    // Theme Toggle
    const themeBtn = document.getElementById('theme-toggle-btn');
    if (themeBtn) {
      themeBtn.addEventListener('click', () => this.toggleTheme());
    }

    // View Mode Tabs
    document.querySelectorAll('.view-tab-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const mode = e.currentTarget.dataset.mode;
        this.setViewMode(mode);
      });
    });

    // Inspector Tabs
    document.querySelectorAll('.tab-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const tab = e.currentTarget.dataset.tab;
        this.setInspectorTab(tab);
      });
    });

    // Scope Pills
    document.querySelectorAll('.scope-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        document.querySelectorAll('.scope-btn').forEach(b => b.classList.remove('active'));
        e.currentTarget.classList.add('active');
        const scope = e.currentTarget.dataset.scope;
        this.onScopeChange(scope);
      });
    });

    // Scan Button
    const scanBtn = document.getElementById('scan-btn');
    if (scanBtn) {
      scanBtn.addEventListener('click', () => {
        if (this.isScanning) {
          this.cancelScan();
        } else {
          const pathInput = document.getElementById('path-input');
          const path = pathInput ? pathInput.value.trim() : '';
          if (path) this.loadFolderQuickly(path, true);
        }
      });
    }

    // Browse Button -> Instant Folder Load
    const browseBtn = document.getElementById('browse-btn');
    if (browseBtn) {
      browseBtn.addEventListener('click', () => this.browseDirectory());
    }

    // Drive Select -> Instant Folder Load
    const driveSelect = document.getElementById('drive-select');
    if (driveSelect) {
      driveSelect.addEventListener('change', (e) => {
        this.loadFolderQuickly(e.target.value, true);
      });
    }

    // Path Input Enter Key -> Instant Folder Load
    const pathInput = document.getElementById('path-input');
    if (pathInput) {
      pathInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          this.loadFolderQuickly(pathInput.value, true);
        }
      });
    }

    // Export HTML Button
    const exportBtn = document.getElementById('export-btn');
    if (exportBtn) {
      exportBtn.addEventListener('click', () => this.exportHtml());
    }

    // Layers View: Explode / Collapse buttons
    const explodeBtn = document.getElementById('btn-explode');
    const collapseBtn = document.getElementById('btn-collapse');
    if (explodeBtn) {
      explodeBtn.addEventListener('click', () => {
        explodeBtn.classList.add('active');
        if (collapseBtn) collapseBtn.classList.remove('active');
        this.vis.toggleExplode(true);
      });
    }
    if (collapseBtn) {
      collapseBtn.addEventListener('click', () => {
        collapseBtn.classList.add('active');
        if (explodeBtn) explodeBtn.classList.remove('active');
        this.vis.toggleExplode(false);
      });
    }

    // Terrain View: Depth buttons
    document.querySelectorAll('.depth-num').forEach(btn => {
      btn.addEventListener('click', (e) => {
        document.querySelectorAll('.depth-num').forEach(b => b.classList.remove('active'));
        e.currentTarget.classList.add('active');
        const depth = parseInt(e.currentTarget.dataset.depth, 10);
        this.vis.setTerrainDepth(depth);
      });
    });

    // Camera HUD controls
    document.getElementById('hud-reset')?.addEventListener('click', () => this.vis.resetCameraPosition());
    document.getElementById('hud-iso')?.addEventListener('click', () => this.vis.setCameraView('iso'));
    document.getElementById('hud-top')?.addEventListener('click', () => this.vis.setCameraView('top'));
    document.getElementById('hud-front')?.addEventListener('click', () => this.vis.setCameraView('front'));

    // Open in Explorer
    document.getElementById('btn-open-explorer')?.addEventListener('click', () => {
      if (this.selectedNode && this.selectedNode.path) {
        this.openInExplorer(this.selectedNode.path);
      }
    });

    // Modal Cancel Scan
    document.getElementById('modal-cancel-btn')?.addEventListener('click', () => this.cancelScan());

    // About / Update modal
    const aboutModal = document.getElementById('about-modal');
    document.getElementById('about-btn')?.addEventListener('click', () => {
      aboutModal?.classList.add('open');
    });
    document.getElementById('about-close-btn')?.addEventListener('click', () => {
      aboutModal?.classList.remove('open');
    });
    aboutModal?.addEventListener('click', (e) => {
      if (e.target === aboutModal) aboutModal.classList.remove('open');
    });
    document.getElementById('check-updates-btn')?.addEventListener('click', () => this.checkForUpdates(true));
    document.getElementById('update-banner-dismiss')?.addEventListener('click', () => {
      document.getElementById('update-banner')?.setAttribute('hidden', '');
    });

    // Scan History panel
    document.getElementById('history-btn')?.addEventListener('click', () => this.toggleHistoryPanel());
    document.getElementById('history-close')?.addEventListener('click', () => {
      document.getElementById('history-panel')?.setAttribute('hidden', '');
    });
  }

  // --- VERSION + UPDATE CHECK ---
  // Reported by the local engine (/api/version). Updates are discovered via
  // the public GitHub releases API directly from the renderer — the local
  // server stays hermetic and never makes outbound calls.
  static UPDATE_REPO = 'meruvav/Disk_Atlas';

  async initVersionAndUpdates() {
    // Skip in exported standalone reports (no token, no engine).
    if (!window.__DA_TOKEN__) return;
    try {
      const res = await this.apiFetch('/api/version');
      if (!res.ok) return;
      const data = await res.json();
      this.appVersion = data.version;
      const versionEl = document.getElementById('about-app-version');
      if (versionEl) versionEl.textContent = `v${data.version}`;
      this.checkForUpdates(false); // silent background check on startup
    } catch (_) {
      // Static/exported mode or engine unavailable — nothing to do.
    }
  }

  static compareVersions(a, b) {
    // Returns 1 when a > b, -1 when a < b, 0 when equal. "v" prefixes ignored.
    const parse = (v) => String(v || '').replace(/^v/i, '').split(/[.-]/)
      .map((p) => (p.match(/^\d+$/) ? parseInt(p, 10) : -1));
    const va = parse(a), vb = parse(b);
    const len = Math.max(va.length, vb.length);
    for (let i = 0; i < len; i++) {
      const x = i < va.length ? va[i] : 0;
      const y = i < vb.length ? vb[i] : 0;
      // A suffixed tag (rc/beta, parsed as -1) sorts before the plain version
      if (x !== y) return x > y ? 1 : -1;
    }
    return 0;
  }

  async checkForUpdates(manual) {
    const statusEl = document.getElementById('update-status');
    const setStatus = (msg, cls = '') => {
      if (statusEl) {
        statusEl.textContent = msg;
        statusEl.className = `update-status ${cls}`;
      }
    };

    if (!this.appVersion) {
      if (manual) setStatus('Version unknown — update check unavailable.');
      return;
    }

    if (manual) setStatus('Checking for updates...');
    try {
      const res = await fetch(
        `https://api.github.com/repos/${DiskAtlasApp.UPDATE_REPO}/releases/latest`,
        { headers: { Accept: 'application/vnd.github+json' } }
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const latest = (data.tag_name || '').replace(/^v/i, '');

      if (DiskAtlasApp.compareVersions(latest, this.appVersion) > 0) {
        setStatus(`v${latest} is available — you're on v${this.appVersion}.`, 'update-new');
        this.showUpdateBanner(latest, data.html_url);
      } else if (manual) {
        setStatus(`Up to date (v${this.appVersion}).`, 'update-ok');
      }
    } catch (_) {
      if (manual) setStatus('Update check failed — offline or GitHub unreachable.');
    }
  }

  showUpdateBanner(latest, url) {
    const banner = document.getElementById('update-banner');
    const text = document.getElementById('update-banner-text');
    const link = document.getElementById('update-download-link');
    if (!banner || !url) return;
    if (text) text.textContent = `Disk Atlas v${latest} is available (you have v${this.appVersion}).`;
    if (link) link.href = url;
    banner.removeAttribute('hidden');
  }

  // --- SCAN HISTORY PANEL ---
  // Every completed deep scan is persisted by the engine; the panel lists
  // them newest-first and can reopen or delete any snapshot.
  async toggleHistoryPanel() {
    const panel = document.getElementById('history-panel');
    if (!panel) return;
    if (panel.hasAttribute('hidden')) {
      panel.removeAttribute('hidden');
      await this.renderHistoryList();
    } else {
      panel.setAttribute('hidden', '');
    }
  }

  async renderHistoryList() {
    const container = document.getElementById('history-list');
    if (!container) return;
    container.innerHTML = '<div class="history-empty">Loading…</div>';
    try {
      const res = await this.apiFetch('/api/history');
      const items = res.ok ? await res.json() : [];
      if (!items.length) {
        container.innerHTML = '<div class="history-empty">No saved scans yet. Completed scans appear here automatically.</div>';
        return;
      }
      container.innerHTML = '';
      for (const item of items) {
        container.appendChild(this._buildHistoryItem(item));
      }
    } catch (_) {
      container.innerHTML = '<div class="history-empty">History unavailable — engine offline.</div>';
    }
  }

  _buildHistoryItem(item) {
    const el = document.createElement('div');
    el.className = 'history-item';

    const when = item.timestamp
      ? new Date(item.timestamp).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
      : '—';
    const sizeStr = this.formatBytes(item.total_bytes || 0);
    const files = item.file_count?.toLocaleString?.() || '0';
    const folders = item.folder_count?.toLocaleString?.() || '0';

    el.innerHTML = `
      <div class="history-item-title" title="${this.escapeHtml(item.root_path || '')}">📁 ${this.escapeHtml(item.name || 'Scan')}</div>
      <div class="history-item-meta">
        <span>${when}</span>
        <span>${sizeStr}</span>
        <span>${files} files · ${folders} folders</span>
      </div>
      <div class="history-item-actions">
        <button class="history-open">Open</button>
        <button class="history-rescan">Re-scan</button>
        <button class="history-delete" title="Delete this saved scan">🗑</button>
      </div>`;

    el.querySelector('.history-open').addEventListener('click', () => this.openHistoryScan(item.id));
    el.querySelector('.history-rescan').addEventListener('click', () => {
      document.getElementById('history-panel')?.setAttribute('hidden', '');
      this.loadFolderQuickly(item.root_path, true);
    });
    el.querySelector('.history-delete').addEventListener('click', () => this.deleteHistoryScan(item.id, el));
    return el;
  }

  async openHistoryScan(id) {
    try {
      const res = await this.apiFetch('/api/history/load', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id })
      });
      if (!res.ok) {
        this.showScanStatusPill('⚠ That saved scan could not be loaded.');
        return;
      }
      const snapshot = await res.json();
      this.setData(snapshot.tree);
      const pathInput = document.getElementById('path-input');
      if (pathInput) pathInput.value = snapshot.root_path || '';
      document.getElementById('history-panel')?.setAttribute('hidden', '');
      this.showScanStatusPill(`🕘 Restored scan of ${snapshot.root_path} (${this.formatBytes(snapshot.total_bytes)}).`);
    } catch (_) {
      this.showScanStatusPill('⚠ History load failed — engine offline.');
    }
  }

  async deleteHistoryScan(id, rowEl) {
    try {
      const res = await this.apiFetch('/api/history/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id })
      });
      if (res.ok && rowEl) rowEl.remove();
    } catch (_) {
      // engine offline — leave the row in place
    }
  }

  // --- CENTRALIZED API HELPER ---
  // Attaches the per-launch auth token (injected into index.html by the
  // backend) to every request. In exported standalone reports the token is
  // empty and all API calls simply fail gracefully into static mode.
  apiFetch(path, opts = {}) {
    const headers = Object.assign({}, opts.headers || {});
    if (window.__DA_TOKEN__) {
      headers['X-Disk-Atlas-Token'] = window.__DA_TOKEN__;
    }
    return fetch(path, Object.assign({}, opts, { headers }));
  }

  // --- FAST FOLDER LOADER (< 15ms Preview + Progressive Deep Scan) ---
  async loadFolderQuickly(targetPath, triggerDeep = true) {
    if (!targetPath) return;
    targetPath = targetPath.trim();

    const pathInput = document.getElementById('path-input');
    if (pathInput) pathInput.value = targetPath;

    this.showScanStatusPill(`⚡ Opening ${targetPath}...`);

    try {
      const res = await this.apiFetch('/api/quick-scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: targetPath, auto_deep: triggerDeep })
      });

      if (res.ok) {
        const data = await res.json();
        // Immediately render the folder contents in milliseconds!
        this.setData(data);

        if (triggerDeep) {
          this.isScanning = true;
          this.updateScanButtonUI(true);
          if (data.deep_scan === 'already_running') {
            this.showScanStatusPill(`🔍 Another scan is already running — showing its progress...`);
          } else {
            this.showScanStatusPill(`🔍 Calculating deep sizes...`);
          }
          if (this.scanPollTimer) clearInterval(this.scanPollTimer);
          this.scanPollTimer = setInterval(() => this.pollScanStatus(), 400);
        } else {
          this.hideScanStatusPill();
        }
        return;
      }
    } catch (e) {
      console.warn("Fast scan fallback:", e);
    }

    // Fallback if backend does not support quick-scan
    this.startScan();
  }

  showScanStatusPill(msg) {
    let pill = document.getElementById('fast-scan-indicator');
    if (!pill) {
      const ribbonLeft = document.querySelector('.stats-left');
      if (ribbonLeft) {
        pill = document.createElement('div');
        pill.id = 'fast-scan-indicator';
        pill.className = 'stat-chip';
        pill.style.color = 'var(--accent-cyan)';
        pill.style.fontWeight = 'bold';
        ribbonLeft.appendChild(pill);
      }
    }
    if (pill) {
      pill.style.display = 'flex';
      pill.innerText = msg;
    }
  }

  hideScanStatusPill() {
    const pill = document.getElementById('fast-scan-indicator');
    if (pill) pill.style.display = 'none';
  }

  // --- EMBEDDED DATA CHECK ---
  checkEmbeddedData() {
    if (window.EMBEDDED_DISK_DATA && window.EMBEDDED_DISK_DATA.name) {
      this.setData(window.EMBEDDED_DISK_DATA);
    } else {
      this.fetchCurrentData();
    }
  }

  // --- THEME ENGINE ---
  toggleTheme() {
    this.theme = this.theme === 'dark' ? 'light' : 'dark';
    if (this.theme === 'light') {
      document.body.classList.add('theme-light');
      document.getElementById('theme-toggle-btn').innerHTML = '☀️ Light';
    } else {
      document.body.classList.remove('theme-light');
      document.getElementById('theme-toggle-btn').innerHTML = '🌙 Dark';
    }
    this.vis.setTheme(this.theme);
  }

  // --- VIEW MODE MANAGEMENT ---
  setViewMode(mode) {
    this.viewMode = mode;
    document.querySelectorAll('.view-tab-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.mode === mode);
    });

    const modeTitle = document.getElementById('current-mode-title');
    const modeSubtitle = document.getElementById('current-mode-subtitle');
    const subControlsLayers = document.getElementById('sub-controls-layers');
    const depthHud = document.getElementById('depth-hud');
    const canvasContainer = document.getElementById('canvas-container');
    const listViewContainer = document.getElementById('list-view-container');

    if (mode === 'city') {
      modeTitle.innerText = "A / Storage City";
      modeSubtitle.innerText = "Folders are districts. Files are buildings. Size is shown by both area and height.";
      subControlsLayers.style.display = 'none';
      depthHud.style.display = 'none';
      canvasContainer.style.display = 'block';
      listViewContainer.style.display = 'none';
      this.vis.setMode('city');
    } else if (mode === 'layers') {
      modeTitle.innerText = "B / Folder Layers";
      modeSubtitle.innerText = "Stacked translucent glass floor plates. Explode layers to reveal inner hierarchy.";
      subControlsLayers.style.display = 'flex';
      depthHud.style.display = 'none';
      canvasContainer.style.display = 'block';
      listViewContainer.style.display = 'none';
      this.vis.setMode('layers');
    } else if (mode === 'treemap') {
      modeTitle.innerText = "E / Storage Treemap";
      modeSubtitle.innerText = "Proportional map of the folder — the largest block is the largest file. Double-click a folder to zoom in.";
      subControlsLayers.style.display = 'none';
      depthHud.style.display = 'none';
      canvasContainer.style.display = 'block';
      listViewContainer.style.display = 'none';
      this.vis.setMode('treemap');
      this.vis.setCameraView('top');
    } else if (mode === 'terrain') {
      modeTitle.innerText = "D / Storage Terrain";
      modeSubtitle.innerText = "Voxel topographical landscape. Mountain peaks represent high-density storage.";
      subControlsLayers.style.display = 'none';
      depthHud.style.display = 'flex';
      canvasContainer.style.display = 'block';
      listViewContainer.style.display = 'none';
      this.vis.setMode('terrain');
    } else if (mode === 'list') {
      modeTitle.innerText = "C / Storage Explorer";
      modeSubtitle.innerText = "Tabular view with search, sorting, and file attributes.";
      subControlsLayers.style.display = 'none';
      depthHud.style.display = 'none';
      canvasContainer.style.display = 'none';
      listViewContainer.style.display = 'block';
      this.renderListView();
    }
  }

  // --- INSPECTOR TABS ---
  setInspectorTab(tab) {
    this.activeTab = tab;
    document.querySelectorAll('.tab-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.tab === tab);
    });

    document.querySelectorAll('.tab-pane').forEach(pane => {
      pane.style.display = pane.id === `tab-${tab}` ? 'block' : 'none';
    });

    if (tab === 'hierarchy') this.renderHierarchyTree();
    else if (tab === 'contents') this.renderContentsTable();
    else if (tab === 'largest') this.renderLargestFiles();
    else if (tab === 'insights') this.renderInsights();
  }

  // --- FAST DATA SET & O(1) INDEXING ---
  setData(data) {
    this.currentData = data;
    this.currentNode = data;
    this.selectedNode = data;
    this.breadcrumbTrail = [data];

    // Build O(1) path lookup index
    this.nodePathMap.clear();
    const indexTree = (node, parent = null) => {
      if (!node) return;
      if (node.path) this.nodePathMap.set(node.path, node);
      node._parent = parent;
      // A folder arriving with children already holds page 1 of them
      // (server pages are deterministic), so drilling skips a refetch.
      if (node.type === 'folder' && node.children && node.children.length > 0) {
        node._childrenLoaded = true;
      }
      if (node.children) {
        for (let i = 0; i < node.children.length; i++) {
          indexTree(node.children[i], node);
        }
      }
    };
    indexTree(data);

    this.updateStatsRibbon();
    this.updateBreadcrumbs();
    this.updateSelectedCard();
    this.setInspectorTab(this.activeTab);

    this.vis.setData(data);
    if (this.viewMode === 'list') {
      this.renderListView();
    }
  }

  // --- LAZY TREE LOADING (Phase 4.5) ---
  // Deep-scan trees arrive depth-limited and breadth-capped; folders beyond
  // that horizon carry children_truncated + child_count with exact sizes.
  // Children are paged in from the engine's in-memory result on demand.
  async ensureChildrenLoaded(node) {
    if (!node || node.type !== 'folder') return;

    // Deep-scan tree: page this folder's children in from the scan result.
    if (node.children_truncated && !node._childrenLoaded) {
      try {
        const res = await this.apiFetch(`/api/tree/children?path=${encodeURIComponent(node.path)}`);
        if (res.ok) {
          const data = await res.json();
          this._adoptChildren(node, data.children || [], data);
        }
      } catch (e) {}
      return;
    }

    // Quick-preview tree (deep scan still running): instant live re-scan,
    // the original < 15ms behavior for the shallow preview level.
    if ((!node.children || node.children.length === 0) &&
        this.currentData && this.currentData.quick_preview) {
      try {
        const res = await this.apiFetch(`/api/quick-scan?path=${encodeURIComponent(node.path)}`);
        if (res.ok) {
          const subData = await res.json();
          node.children = subData.children || [];
          if (!node.size || node.size === 0) node.size = subData.size || 0;
          (node.children || []).forEach(c => {
            if (c.path) this.nodePathMap.set(c.path, c);
            c._parent = node;
          });
        }
      } catch (e) {}
    }
  }

  _adoptChildren(node, children, pageInfo = {}) {
    node.children = children;
    node.child_count = pageInfo.child_count ?? children.length;
    node._childrenLoaded = true;
    node.children_truncated = pageInfo.has_more === true;
    // Newly loaded descendants invalidate memoized Largest/Insights caches
    // on this node and every ancestor up to the root.
    let p = node;
    while (p) {
      delete p._cachedLargest;
      delete p._cachedExt;
      p = p._parent;
    }
    children.forEach(c => {
      if (c.path) this.nodePathMap.set(c.path, c);
      c._parent = node;
      // Folder children arrive holding their own first page (depth-1 copies)
      if (c.type === 'folder' && c.children && c.children.length > 0) {
        c._childrenLoaded = true;
      }
    });
  }

  // Fetch the next page of children for a folder that has more on the
  // engine than the UI has loaded so far ("Load more" in the tables).
  async loadMoreChildren(node) {
    if (!node || !node.children_truncated) return;
    const offset = (node.children || []).length;
    try {
      const res = await this.apiFetch(
        `/api/tree/children?path=${encodeURIComponent(node.path)}&offset=${offset}`);
      if (res.ok) {
        const data = await res.json();
        const merged = (node.children || []).concat(data.children || []);
        this._adoptChildren(node, merged, data);
        this.setInspectorTab(this.activeTab);
        if (this.viewMode === 'list') this.renderListView();
      }
    } catch (e) {}
  }

  // True when any descendant of `node` is known to exist on the engine but
  // not loaded in the browser yet (client-side aggregates would be partial).
  treeHasTruncated(root) {
    const stack = [root];
    while (stack.length) {
      const n = stack.pop();
      if (n.children_truncated) return true;
      const ch = n.children;
      if (ch) for (let i = 0; i < ch.length; i++) stack.push(ch[i]);
    }
    return false;
  }

  async drillDown(node) {
    if (!node || node.type !== 'folder') return;

    await this.ensureChildrenLoaded(node);

    this.currentNode = node;
    this.selectedNode = node;
    this.breadcrumbTrail.push(node);

    this.updateBreadcrumbs();
    this.updateSelectedCard();
    this.setInspectorTab(this.activeTab);

    this.vis.setNode(node);
    if (this.viewMode === 'list') {
      this.renderListView();
    }
  }

  selectNode(node) {
    this.selectedNode = node;
    this.updateSelectedCard();
  }

  // --- BREADCRUMBS ---
  updateBreadcrumbs() {
    const container = document.getElementById('breadcrumb-bar');
    if (!container) return;
    container.innerHTML = '';

    this.breadcrumbTrail.forEach((node, idx) => {
      const item = document.createElement('span');
      item.className = `breadcrumb-item ${idx === this.breadcrumbTrail.length - 1 ? 'active' : ''}`;
      item.innerText = idx === 0 ? `📁 ${node.name || 'Root'}` : node.name;
      item.onclick = () => {
        this.breadcrumbTrail = this.breadcrumbTrail.slice(0, idx + 1);
        this.currentNode = node;
        this.selectedNode = node;
        this.updateBreadcrumbs();
        this.updateSelectedCard();
        this.vis.setNode(node);
        this.setInspectorTab(this.activeTab);
        if (this.viewMode === 'list') this.renderListView();
      };

      container.appendChild(item);
      if (idx < this.breadcrumbTrail.length - 1) {
        const sep = document.createElement('span');
        sep.innerText = ' › ';
        sep.style.color = 'var(--text-dim)';
        container.appendChild(sep);
      }
    });
  }

  // --- STATS RIBBON ---
  updateStatsRibbon() {
    if (!this.currentData) return;
    document.getElementById('ribbon-path').innerText = this.currentData.path || this.currentData.name;
    document.getElementById('stat-total-size').innerText = this.formatBytes(this.currentData.size);

    let fileCount = this.currentData.file_count || 0;
    let folderCount = this.currentData.folder_count || 0;

    if (!fileCount && !folderCount) {
      const countItems = (n) => {
        if (n.type === 'file') fileCount++;
        else if (n.type === 'folder') {
          folderCount++;
          (n.children || []).forEach(countItems);
        }
      };
      countItems(this.currentData);
    }

    document.getElementById('stat-file-count').innerText = `${fileCount.toLocaleString()} files`;
    document.getElementById('stat-folder-count').innerText = `${folderCount.toLocaleString()} folders`;
    document.getElementById('stat-scan-time').innerText = `Scanned: Just now`;
  }

  // --- SELECTED ITEM CARD ---
  updateSelectedCard() {
    const node = this.selectedNode || this.currentNode;
    if (!node) return;

    document.getElementById('summary-icon').innerText = node.type === 'folder' ? '📁' : '📄';
    document.getElementById('summary-name').innerText = node.name;
    document.getElementById('summary-size').innerText = this.formatBytes(node.size);

    const total = (this.currentData ? this.currentData.size : node.size) || 1;
    const pct = ((node.size / total) * 100).toFixed(1);
    document.getElementById('summary-percent').innerText = `${pct}% of total`;
    document.getElementById('size-bar-fill').style.width = `${Math.min(100, Math.max(2, pct))}%`;

    let subFiles = 0;
    let subFolders = 0;
    if (node.children) {
      for (let i = 0; i < node.children.length; i++) {
        if (node.children[i].type === 'file') subFiles++;
        else subFolders++;
      }
    }
    const isFolder = node.type === 'folder';
    // With lazy loading the browser may hold only the first page of a big
    // folder; child_count is the exact on-disk direct-child total.
    const folderSummary = (isFolder && node.children_truncated && node.child_count != null)
      ? `${node.child_count.toLocaleString()} items (${(subFiles + subFolders).toLocaleString()} loaded)`
      : `${subFiles} files, ${subFolders} folders`;

    document.getElementById('summary-items-count').innerText = isFolder
      ? folderSummary
      : `File (${node.ext || 'other'})`;

    // Footer details
    document.getElementById('detail-type').innerText = isFolder ? 'File folder' : `${(node.ext || '').toUpperCase()} File`;
    document.getElementById('detail-path').innerText = node.path || node.name;
    document.getElementById('detail-bytes').innerText = `${this.formatBytes(node.size)} (${(node.size || 0).toLocaleString()} bytes)`;
    document.getElementById('detail-contains').innerText = isFolder ? folderSummary : '—';
  }

  // --- TAB: CONTENTS TABLE (Image 1 & Image 2) ---
  renderContentsTable() {
    const pane = document.getElementById('tab-contents');
    if (!pane) return;
    const node = this.currentNode;
    const children = (node.children || []).slice(0, 150); // Capped for fast DOM reflow

    let html = `
      <table class="items-table">
        <thead>
          <tr>
            <th>Name</th>
            <th style="text-align: right;">Size</th>
            <th style="text-align: right;">Type</th>
          </tr>
        </thead>
        <tbody>
    `;

    children.forEach(c => {
      html += `
        <tr onclick="app.selectNodeByPath('${this.escapeAttr(c.path)}')">
          <td style="display:flex; align-items:center; gap:6px;">
            <span>${c.type === 'folder' ? '📁' : '📄'}</span>
            <span style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width: 170px;">${this.escapeHtml(c.name)}</span>
          </td>
          <td style="text-align: right; font-weight:600; color:var(--text-main);">${this.formatBytes(c.size)}</td>
          <td style="text-align: right; color:var(--text-dim);">${c.type === 'folder' ? 'Folder' : (c.ext || 'File')}</td>
        </tr>
      `;
    });

    html += `</tbody></table>`;
    const loadedCount = (node.children || []).length;
    const totalCount = node.child_count ?? loadedCount;
    if (loadedCount > 150) {
      html += `<div style="text-align:center; padding:8px; font-size:0.72rem; color:var(--text-dim);">Showing top 150 of ${loadedCount.toLocaleString()} loaded items</div>`;
    }
    if (node.children_truncated) {
      const remaining = totalCount - loadedCount;
      html += `
        <div style="text-align:center; padding:8px; font-size:0.72rem; color:var(--text-dim);">
          ${remaining.toLocaleString()} more item${remaining === 1 ? '' : 's'} on disk —
          <button class="load-more-btn" onclick="app.loadMoreChildren(app.currentNode)">Load more</button>
        </div>`;
    }
    pane.innerHTML = html;
  }

  // --- TAB: HIERARCHY TREE (Image 3) ---
  renderHierarchyTree() {
    const pane = document.getElementById('tab-hierarchy');
    if (!pane) return;
    pane.innerHTML = '';

    const buildTreeDOM = (node, container, depth = 0) => {
      if (depth > 3 || !node.children) return;

      const items = (node.children || []).slice(0, 60);
      items.forEach(child => {
        const row = document.createElement('div');
        row.className = `tree-node ${this.selectedNode === child ? 'selected' : ''}`;
        row.style.paddingLeft = `${depth * 14 + 6}px`;

        row.innerHTML = `
          <div class="node-left">
            <span>${child.type === 'folder' ? '📁' : '📄'}</span>
            <span>${this.escapeHtml(child.name)}</span>
          </div>
          ${child.children_truncated ? `<span class="node-badge" title="Not loaded yet — double-click to open" style="background:rgba(255,255,255,0.12); color:var(--text-dim);">+${(child.child_count ?? 0).toLocaleString()}</span>` : ''}
          <span class="node-badge" style="background:${this.getBadgeColor(child.size)}; color:#fff;">
            ${this.formatBytes(child.size)}
          </span>
        `;

        row.onclick = () => {
          this.selectNode(child);
          this.renderHierarchyTree();
        };

        if (child.type === 'folder') {
          row.ondblclick = () => this.drillDown(child);
        }

        container.appendChild(row);
        if (child.type === 'folder') {
          buildTreeDOM(child, container, depth + 1);
        }
      });
    };

    buildTreeDOM(this.currentNode, pane);
  }

  // Exact whole-subtree aggregates from the engine (computed over the full
  // in-memory scan, even parts the browser hasn't loaded). Returns null in
  // standalone/exported mode or when the engine is unreachable.
  async fetchTreeSummary(node) {
    if (!window.__DA_TOKEN__ || !node || !node.path) return null;
    try {
      const res = await this.apiFetch(`/api/tree/summary?path=${encodeURIComponent(node.path)}`);
      if (res.ok) return await res.json();
    } catch (_) {}
    return null;
  }

  // --- TAB: LARGEST FILES ---
  // Engine summary keeps this tab exact on lazily-loaded trees; the
  // client-side harvest remains as the standalone-report fallback.
  async renderLargestFiles() {
    const pane = document.getElementById('tab-largest');
    if (!pane) return;
    const node = this.currentNode;
    if (!node) return;

    const summary = await this.fetchTreeSummary(node);
    if (this.currentNode !== node) return; // user moved on while fetching

    let topFiles;
    let partial = false;
    if (summary) {
      topFiles = summary.largest_files || [];
    } else {
      if (!node._cachedLargest) {
        const files = [];
        const harvestFiles = (n) => {
          if (n.type === 'file') files.push(n);
          if (n.children && n.children.length > 0) {
            for (let i = 0; i < n.children.length; i++) {
              harvestFiles(n.children[i]);
            }
          }
        };
        harvestFiles(node);
        files.sort((a, b) => (b.size || 0) - (a.size || 0));
        node._cachedLargest = files.slice(0, 15);
      }
      topFiles = node._cachedLargest;
      partial = this.treeHasTruncated(node);
    }

    let html = `<div style="display:flex; flex-direction:column; gap:6px;">`;
    topFiles.forEach(f => {
      html += `
        <div class="tree-node" onclick="app.selectNodeByPath('${this.escapeAttr(f.path)}')" style="justify-content:space-between;">
          <div class="node-left" style="max-width:210px;">
            <span>📄</span>
            <span title="${this.escapeAttr(f.path)}">${this.escapeHtml(f.name)}</span>
          </div>
          <span style="font-weight:700; color:var(--accent-cyan);">${this.formatBytes(f.size)}</span>
        </div>
      `;
    });
    if (topFiles.length === 0) {
      html += `<div style="color:var(--text-dim); font-size:0.8rem; padding:8px 4px;">No files in this branch.</div>`;
    }
    html += `</div>`;
    if (partial) {
      html += `<div style="text-align:center; padding:8px; font-size:0.72rem; color:var(--text-dim);">Based on items loaded so far — drill into folders to refine.</div>`;
    }
    pane.innerHTML = html;
  }

  // --- TAB: INSIGHTS & FILE TYPES ---
  async renderInsights() {
    const pane = document.getElementById('tab-insights');
    if (!pane) return;
    const node = this.currentNode;
    if (!node) return;

    const summary = await this.fetchTreeSummary(node);
    if (this.currentNode !== node) return; // user moved on while fetching

    let sorted;
    let total;
    let partial = false;
    if (summary) {
      sorted = summary.extensions || [];
      total = summary.total_bytes || 1;
    } else {
      if (!node._cachedExt) {
        const extMap = {};
        const harvestExt = (n) => {
          if (n.type === 'file') {
            const ext = n.ext || 'other';
            extMap[ext] = (extMap[ext] || 0) + (n.size || 0);
          }
          if (n.children && n.children.length > 0) {
            for (let i = 0; i < n.children.length; i++) {
              harvestExt(n.children[i]);
            }
          }
        };
        harvestExt(node);
        node._cachedExt = Object.entries(extMap).sort((a, b) => b[1] - a[1]);
      }
      sorted = node._cachedExt;
      total = node.size || 1;
      partial = this.treeHasTruncated(node);
    }

    let html = `<div style="font-size:0.8rem; margin-bottom:12px; font-weight:600; color:var(--text-muted);">EXTENSIONS BREAKDOWN</div>`;
    sorted.slice(0, 7).forEach(([ext, sz]) => {
      const pct = ((sz / total) * 100).toFixed(1);
      html += `
        <div style="margin-bottom:10px;">
          <div style="display:flex; justify-content:space-between; font-size:0.75rem; margin-bottom:4px;">
            <span>${ext.toUpperCase()}</span>
            <span><strong>${this.formatBytes(sz)}</strong> (${pct}%)</span>
          </div>
          <div class="size-progress-bg">
            <div class="size-progress-fill" style="width: ${pct}%;"></div>
          </div>
        </div>
      `;
    });
    if (sorted.length === 0) {
      html += `<div style="color:var(--text-dim); font-size:0.8rem; padding:8px 4px;">No files in this branch.</div>`;
    }
    if (partial) {
      html += `<div style="text-align:center; padding:8px; font-size:0.72rem; color:var(--text-dim);">Based on items loaded so far — drill into folders to refine.</div>`;
    }

    pane.innerHTML = html;
  }

  // --- TABULAR LIST VIEW (Full Viewport) ---
  renderListView() {
    const container = document.getElementById('list-view-container');
    if (!container) return;

    const node = this.currentNode;
    const children = (node.children || []).slice(0, 200);
    const loadedCount = (node.children || []).length;
    const totalCount = node.child_count ?? loadedCount;
    let html = `
      <div style="margin-bottom:14px; display:flex; justify-content:space-between; align-items:center;">
        <h3 style="font-size:1.1rem;">Contents of ${this.escapeHtml(node.name)}</h3>
        <span style="color:var(--text-muted); font-size:0.8rem;">${loadedCount.toLocaleString()}${node.children_truncated ? ` of ${totalCount.toLocaleString()}` : ''} items</span>
      </div>
      <table class="items-table" style="background:var(--bg-card); border-radius:8px; overflow:hidden;">
        <thead>
          <tr>
            <th>Name</th>
            <th>Type</th>
            <th style="text-align: right;">Size</th>
            <th>Path</th>
          </tr>
        </thead>
        <tbody>
    `;

    children.forEach(c => {
      html += `
        <tr onclick="app.selectNodeByPath('${this.escapeAttr(c.path)}')" ondblclick="app.drillDownByPath('${this.escapeAttr(c.path)}')">
          <td style="font-weight:600; display:flex; align-items:center; gap:8px;">
            <span>${c.type === 'folder' ? '📁' : '📄'}</span>
            <span>${this.escapeHtml(c.name)}</span>
          </td>
          <td style="color:var(--text-dim);">${c.type === 'folder' ? 'Folder' : (c.ext || 'File')}</td>
          <td style="text-align: right; font-weight:700; color:var(--accent-cyan);">${this.formatBytes(c.size)}</td>
          <td style="color:var(--text-dim); font-size:0.72rem; user-select:text;">${this.escapeHtml(c.path)}</td>
        </tr>
      `;
    });

    html += `</tbody></table>`;
    if (loadedCount > 200) {
      html += `<div style="text-align:center; padding:8px; font-size:0.72rem; color:var(--text-dim);">Showing first 200 of ${loadedCount.toLocaleString()} loaded items</div>`;
    }
    if (node.children_truncated) {
      const remaining = totalCount - loadedCount;
      html += `
        <div style="text-align:center; padding:8px; font-size:0.72rem; color:var(--text-dim);">
          ${remaining.toLocaleString()} more item${remaining === 1 ? '' : 's'} on disk —
          <button class="load-more-btn" onclick="app.loadMoreChildren(app.currentNode)">Load more</button>
        </div>`;
    }
    container.innerHTML = html;
  }

  // --- O(1) LOOKUP HELPERS ---
  selectNodeByPath(path) {
    const node = this.nodePathMap.get(path);
    if (node) this.selectNode(node);
  }

  drillDownByPath(path) {
    const node = this.nodePathMap.get(path);
    if (node && node.type === 'folder') this.drillDown(node);
  }

  // --- API BACKEND INTEGRATION ---
  driveOptionText(d) {
    const name = d.label || d.path;
    if (d.kind === 'home') return `${name} — ${d.path}`;
    if (d.total > 0) {
      return `${name} — ${this.formatBytes(d.free)} free of ${this.formatBytes(d.total)}`;
    }
    return `${name} (unavailable)`;
  }

  async fetchDrives() {
    try {
      const res = await this.apiFetch('/api/drives');
      if (res.ok) {
        const drives = await res.json();
        const select = document.getElementById('drive-select');
        if (select && drives.length > 0) {
          select.innerHTML = '';
          drives.forEach(d => {
            const opt = document.createElement('option');
            opt.value = d.path;
            opt.innerText = this.driveOptionText(d);
            if (d.kind !== 'home' && !(d.total > 0)) opt.disabled = true;
            select.appendChild(opt);
          });

          // Default scan target: home folder if offered, else first drive.
          // Never auto-scan: the user confirms with the Scan button.
          const preferred = drives.find(d => d.kind === 'home') || drives[0];
          select.value = preferred.path;
          const pathInput = document.getElementById('path-input');
          if (pathInput && !pathInput.value) pathInput.value = preferred.path;

          // First-run hint: make the next step obvious
          if (!this.currentData) {
            this.showScanStatusPill(`Ready — press Scan to analyze ${preferred.path}`);
          }
        }
      }
    } catch (e) {}
  }

  // --- SCOPE PILLS (Folder / Drive / All drives) ---
  onScopeChange(scope) {
    const driveSelect = document.getElementById('drive-select');
    const pathInput = document.getElementById('path-input');

    if (scope === 'all') {
      // Multi-drive scans are not supported by the engine yet; be honest
      // about it instead of silently scanning nothing useful.
      this.showScanStatusPill('Scanning all drives at once is not supported yet — pick a single drive.');
      const prev = document.querySelector(`.scope-btn[data-scope="${this.activeScope || 'folder'}"]`);
      document.querySelectorAll('.scope-btn').forEach(b => b.classList.remove('active'));
      if (prev) prev.classList.add('active');
      return;
    }

    this.activeScope = scope;

    if (scope === 'drive') {
      // Drive mode: the picker drives the path input
      if (driveSelect && driveSelect.value) {
        if (pathInput) pathInput.value = driveSelect.value;
        driveSelect.focus();
      }
    } else if (scope === 'folder') {
      if (pathInput) pathInput.focus();
    }
  }

  async browseDirectory() {
    try {
      const res = await this.apiFetch('/api/browse', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        if (data.preview) {
          const pathInput = document.getElementById('path-input');
          if (pathInput) pathInput.value = data.path;
          this.setData(data.preview);
          this.loadFolderQuickly(data.path, true);
        } else if (data.path) {
          this.loadFolderQuickly(data.path, true);
        }
      }
    } catch (e) {
      console.warn("Browse dialog unavailable in static mode");
    }
  }

  async startScan() {
    const pathInput = document.getElementById('path-input');
    const path = pathInput ? pathInput.value.trim() : '';
    if (!path) return;

    this.isScanning = true;
    this.updateScanButtonUI(true);
    this.showScanStatusPill(`🔍 Scanning ${path}...`);

    try {
      const res = await this.apiFetch('/api/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: path })
      });

      if (res.status === 409) {
        // A scan is already running on the engine: attach to its progress
        this.showScanStatusPill(`🔍 A scan is already running — showing its progress...`);
      } else if (res.status === 400) {
        const err = await res.json().catch(() => ({}));
        this.showScanStatusPill(`⚠️ ${err.error || 'Invalid path'}`);
        this.isScanning = false;
        this.updateScanButtonUI(false);
        return;
      }

      if (this.scanPollTimer) clearInterval(this.scanPollTimer);
      this.scanPollTimer = setInterval(() => this.pollScanStatus(), 400);
    } catch (e) {
      this.cancelScan();
    }
  }

  async pollScanStatus() {
    try {
      const res = await this.apiFetch('/api/status');
      if (res.ok) {
        const status = await res.json();

        if (status.state === 'done') {
          clearInterval(this.scanPollTimer);
          this.isScanning = false;
          this.updateScanButtonUI(false);
          this.hideScanStatusPill();
          this.fetchCurrentData();
        } else if (status.state === 'error' || status.state === 'idle') {
          this.cancelScan();
        }
      }
    } catch (e) {
      this.cancelScan();
    }
  }

  async cancelScan() {
    this.isScanning = false;
    clearInterval(this.scanPollTimer);
    this.updateScanButtonUI(false);
    this.hideScanStatusPill();
    try {
      await this.apiFetch('/api/cancel', { method: 'POST' });
    } catch (e) {}
  }

  updateScanButtonUI(scanning) {
    const btn = document.getElementById('scan-btn');
    if (btn) {
      if (scanning) {
        btn.classList.add('btn-danger');
        btn.innerHTML = '🛑 Stop';
      } else {
        btn.classList.remove('btn-danger');
        btn.innerHTML = '🔍 Scan';
      }
    }
  }

  async fetchCurrentData() {
    try {
      const res = await this.apiFetch('/api/data');
      if (res.ok) {
        const data = await res.json();
        this.setData(data);
        return;
      }
    } catch (e) {}

    // No scan data on the server: show the empty state and wait for
    // the user to pick a drive/folder and press Scan.
    this.showEmptyState();
  }

  // --- EMPTY STATE (no scan data yet) ---
  showEmptyState() {
    this.currentData = null;
    this.currentNode = null;
    this.selectedNode = null;
    this.breadcrumbTrail = [];
    this.nodePathMap.clear();

    // Stats ribbon
    document.getElementById('ribbon-path').innerText = '—';
    document.getElementById('stat-total-size').innerText = '—';
    document.getElementById('stat-file-count').innerText = '—';
    document.getElementById('stat-folder-count').innerText = '—';
    document.getElementById('stat-scan-time').innerText = 'Not scanned yet';

    // Summary card + details footer
    document.getElementById('summary-icon').innerText = '📁';
    document.getElementById('summary-name').innerText = 'Nothing selected';
    document.getElementById('summary-size').innerText = '—';
    document.getElementById('summary-percent').innerText = '—';
    document.getElementById('summary-items-count').innerText = '—';
    document.getElementById('size-bar-fill').style.width = '0%';
    document.getElementById('detail-type').innerText = '—';
    document.getElementById('detail-path').innerText = '—';
    document.getElementById('detail-bytes').innerText = '—';
    document.getElementById('detail-contains').innerText = '—';

    this.updateBreadcrumbs();

    // Inspector panes: friendly prompt instead of demo rows
    const emptyMsg = `
      <div style="padding: 28px 16px; text-align:center; color: var(--text-dim); font-size: 0.85rem; line-height: 1.6;">
        <div style="font-size: 1.6rem; margin-bottom: 8px;">🗂️</div>
        No scan data yet.<br>
        Pick a drive or folder above, then press <strong>Scan</strong>.
      </div>`;
    ['tab-contents', 'tab-hierarchy', 'tab-largest', 'tab-insights'].forEach(id => {
      const pane = document.getElementById(id);
      if (pane) pane.innerHTML = emptyMsg;
    });

    // Clear the 3D scene
    this.vis.setData(null);
  }

  async openInExplorer(path) {
    try {
      await this.apiFetch('/api/open-folder', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: path })
      });
    } catch (e) {}
  }

  async exportHtml() {
    try {
      const res = await this.apiFetch('/api/export', { method: 'POST' });
      if (res.ok) {
        const result = await res.json();
        alert(`Standalone HTML report exported successfully!\nSaved to: ${result.path}`);
      }
    } catch (e) {
      alert("Exporting HTML is supported through the Python backend launcher.");
    }
  }

  // --- UTILS ---
  formatBytes(bytes) {
    if (!bytes || bytes <= 0) return "0 B";
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }

  getBadgeColor(bytes) {
    if (bytes >= 1e9) return 'var(--accent-coral)';
    if (bytes >= 1e8) return 'var(--accent-amber)';
    return 'var(--accent-cyan)';
  }

  escapeHtml(str) {
    if (!str) return '';
    return str.replace(/[&<>"']/g, m => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[m]);
  }

  escapeAttr(str) {
    if (!str) return '';
    return str.replace(/'/g, "\\'").replace(/"/g, '&quot;');
  }
}

// Global initialization
let app = null;
window.addEventListener('DOMContentLoaded', () => {
  app = new DiskAtlasApp();
});
