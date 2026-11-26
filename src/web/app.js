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
    this.viewMode = 'city'; // 'city', 'layers', 'terrain', 'list'
    this.activeTab = 'contents'; // 'contents', 'hierarchy', 'largest', 'insights'
    this.isScanning = false;
    this.scanPollTimer = null;
    this.nodePathMap = new Map();

    this.initVisualizer();
    this.bindEvents();
    this.checkEmbeddedData();
    this.fetchDrives();
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
          this.showScanStatusPill(`🔍 Calculating deep sizes...`);
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

  async drillDown(node) {
    if (!node || node.type !== 'folder') return;

    // If folder children are not loaded yet (shallow preview), fetch instantly in < 15ms
    if (!node.children || node.children.length === 0) {
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

    document.getElementById('summary-items-count').innerText = node.type === 'folder' 
      ? `${subFiles} files, ${subFolders} folders` 
      : `File (${node.ext || 'other'})`;

    // Footer details
    document.getElementById('detail-type').innerText = node.type === 'folder' ? 'File folder' : `${(node.ext || '').toUpperCase()} File`;
    document.getElementById('detail-path').innerText = node.path || node.name;
    document.getElementById('detail-bytes').innerText = `${this.formatBytes(node.size)} (${(node.size || 0).toLocaleString()} bytes)`;
    document.getElementById('detail-contains').innerText = node.type === 'folder' ? `${subFiles} files, ${subFolders} folders` : '—';
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
    if ((node.children || []).length > 150) {
      html += `<div style="text-align:center; padding:8px; font-size:0.72rem; color:var(--text-dim);">Showing top 150 of ${node.children.length} items</div>`;
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

  // --- TAB: LARGEST FILES (Memoized O(1) Access) ---
  renderLargestFiles() {
    const pane = document.getElementById('tab-largest');
    if (!pane) return;

    if (!this.currentNode._cachedLargest) {
      const files = [];
      const harvestFiles = (n) => {
        if (n.type === 'file') files.push(n);
        if (n.children && n.children.length > 0) {
          for (let i = 0; i < n.children.length; i++) {
            harvestFiles(n.children[i]);
          }
        }
      };
      harvestFiles(this.currentNode);
      files.sort((a, b) => (b.size || 0) - (a.size || 0));
      this.currentNode._cachedLargest = files.slice(0, 15);
    }

    const topFiles = this.currentNode._cachedLargest;

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
    html += `</div>`;
    pane.innerHTML = html;
  }

  // --- TAB: INSIGHTS & FILE TYPES (Memoized O(1) Access) ---
  renderInsights() {
    const pane = document.getElementById('tab-insights');
    if (!pane) return;

    if (!this.currentNode._cachedExt) {
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
      harvestExt(this.currentNode);
      this.currentNode._cachedExt = Object.entries(extMap).sort((a, b) => b[1] - a[1]);
    }

    const sorted = this.currentNode._cachedExt;
    const total = this.currentNode.size || 1;

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

    pane.innerHTML = html;
  }

  // --- TABULAR LIST VIEW (Full Viewport) ---
  renderListView() {
    const container = document.getElementById('list-view-container');
    if (!container) return;

    const children = (this.currentNode.children || []).slice(0, 200);
    let html = `
      <div style="margin-bottom:14px; display:flex; justify-content:space-between; align-items:center;">
        <h3 style="font-size:1.1rem;">Contents of ${this.escapeHtml(this.currentNode.name)}</h3>
        <span style="color:var(--text-muted); font-size:0.8rem;">${(this.currentNode.children || []).length} items</span>
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
            opt.innerText = `${d.path} (${this.formatBytes(d.total)})`;
            select.appendChild(opt);
          });
          const pathInput = document.getElementById('path-input');
          if (pathInput && !pathInput.value) pathInput.value = drives[0].path;
        }
      }
    } catch (e) {}
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
      await this.apiFetch('/api/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: path })
      });

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

    // Fallback Mock Data if opening directly without server
    this.loadSampleData();
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

  // --- SAMPLE DATA GENERATOR (MATCHING IMAGES) ---
  loadSampleData() {
    const mock = {
      name: "Archive",
      path: "D:\\Archive",
      type: "folder",
      size: 240 * 1024 * 1024 * 1024,
      children: [
        {
          name: "Videos",
          path: "D:\\Archive\\Videos",
          type: "folder",
          size: 120 * 1024 * 1024 * 1024,
          children: [
            {
              name: "Recordings",
              path: "D:\\Archive\\Videos\\Recordings",
              type: "folder",
              size: 72 * 1024 * 1024 * 1024,
              children: [
                { name: "Vacation 2023", path: "D:\\Archive\\Videos\\Recordings\\Vacation 2023", size: 28.4 * 1024 * 1024 * 1024, type: "folder" },
                { name: "Family", path: "D:\\Archive\\Videos\\Recordings\\Family", size: 18.1 * 1024 * 1024 * 1024, type: "folder" },
                { name: "Screen Recordings", path: "D:\\Archive\\Videos\\Recordings\\Screen Recordings", size: 11.6 * 1024 * 1024 * 1024, type: "folder" },
                { name: "Drone Footage", path: "D:\\Archive\\Videos\\Recordings\\Drone Footage", size: 7.9 * 1024 * 1024 * 1024, type: "folder" },
                { name: "Documentary_4K.mkv", path: "D:\\Archive\\Videos\\Recordings\\Documentary_4K.mkv", size: 8.4 * 1024 * 1024 * 1024, type: "file", ext: ".mkv" },
                { name: "rec_2023_07_14.mp4", path: "D:\\Archive\\Videos\\Recordings\\rec_2023_07_14.mp4", size: 4.8 * 1024 * 1024 * 1024, type: "file", ext: ".mp4" },
                { name: "rec_2023_06_02.mp4", path: "D:\\Archive\\Videos\\Recordings\\rec_2023_06_02.mp4", size: 3.9 * 1024 * 1024 * 1024, type: "file", ext: ".mp4" }
              ]
            },
            {
              name: "Movies",
              path: "D:\\Archive\\Videos\\Movies",
              type: "folder",
              size: 36 * 1024 * 1024 * 1024,
              children: [
                { name: "Series", path: "D:\\Archive\\Videos\\Movies\\Series", size: 28 * 1024 * 1024 * 1024, type: "folder" },
                { name: "Clips", path: "D:\\Archive\\Videos\\Movies\\Clips", size: 8 * 1024 * 1024 * 1024, type: "folder" }
              ]
            },
            {
              name: "Clips",
              path: "D:\\Archive\\Videos\\Clips",
              type: "folder",
              size: 12 * 1024 * 1024 * 1024,
              children: [
                { name: "interview_final.mov", path: "D:\\Archive\\Videos\\Clips\\interview_final.mov", size: 2.6 * 1024 * 1024 * 1024, type: "file", ext: ".mov" },
                { name: "drone_mountain.mp4", path: "D:\\Archive\\Videos\\Clips\\drone_mountain.mp4", size: 2.4 * 1024 * 1024 * 1024, type: "file", ext: ".mp4" },
                { name: "meeting_capture.mkv", path: "D:\\Archive\\Videos\\Clips\\meeting_capture.mkv", size: 980 * 1024 * 1024, type: "file", ext: ".mkv" }
              ]
            }
          ]
        },
        {
          name: "Projects",
          path: "D:\\Archive\\Projects",
          type: "folder",
          size: 64 * 1024 * 1024 * 1024,
          children: [
            { name: "Project_Final.zip", path: "D:\\Archive\\Projects\\Project_Final.zip", size: 6.1 * 1024 * 1024 * 1024, type: "file", ext: ".zip" },
            { name: "Build_Assets", path: "D:\\Archive\\Projects\\Build_Assets", size: 14.2 * 1024 * 1024 * 1024, type: "folder" },
            { name: "Source_Code", path: "D:\\Archive\\Projects\\Source_Code", size: 8.5 * 1024 * 1024 * 1024, type: "folder" }
          ]
        },
        {
          name: "Photos",
          path: "D:\\Archive\\Photos",
          type: "folder",
          size: 40 * 1024 * 1024 * 1024,
          children: [
            { name: "RAW_2024", path: "D:\\Archive\\Photos\\RAW_2024", size: 28 * 1024 * 1024 * 1024, type: "folder" },
            { name: "Exported_JPEG", path: "D:\\Archive\\Photos\\Exported_JPEG", size: 12 * 1024 * 1024 * 1024, type: "folder" }
          ]
        },
        {
          name: "Documents",
          path: "D:\\Archive\\Documents",
          type: "folder",
          size: 12 * 1024 * 1024 * 1024,
          children: [
            { name: "Financials.xlsx", path: "D:\\Archive\\Documents\\Financials.xlsx", size: 150 * 1024 * 1024, type: "file", ext: ".xlsx" },
            { name: "Architecture_Specs.pdf", path: "D:\\Archive\\Documents\\Architecture_Specs.pdf", size: 450 * 1024 * 1024, type: "file", ext: ".pdf" }
          ]
        },
        {
          name: "Other",
          path: "D:\\Archive\\Other",
          type: "folder",
          size: 4 * 1024 * 1024 * 1024,
          children: [
            { name: "Cache.tmp", path: "D:\\Archive\\Other\\Cache.tmp", size: 2.1 * 1024 * 1024 * 1024, type: "file", ext: ".tmp" }
          ]
        }
      ]
    };

    this.setData(mock);
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
