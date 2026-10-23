/**
 * Disk Atlas - 3D Visualizer Engine
 * Seamlessly merges:
 *   - Concept A: "Storage City" (3D Districts & Skyscrapers with neon glow)
 *   - Concept B: "Folder Layers" (Frosted Glass Stacked Layers with Explode/Collapse)
 *   - Concept D: "Storage Terrain" (3D Voxel Topography with Peak Pins & Depth filter)
 * 
 * Optimized for lightning-fast folder switching and high-performance rendering.
 */

class DiskAtlasVisualizer {
  constructor(containerId, options = {}) {
    this.container = document.getElementById(containerId);
    this.options = Object.assign({
      theme: 'dark',
      onSelect: null,
      onDrillDown: null,
    }, options);

    this.currentMode = 'city'; // 'city', 'layers', 'terrain'
    this.currentData = null;
    this.currentNode = null;
    this.terrainDepth = 3;
    this.isExploded = false;
    this.explodedFactor = 0; // 0 = collapsed, 1 = fully exploded
    this.targetExplodedFactor = 0;
    
    this.interactiveObjects = [];
    this.hoveredObject = null;
    this.selectedObject = null;
    this.peakPins = [];

    this.initThree();
    this.initMaterials();
    this.initEvents();
    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  initThree() {
    const width = this.container.clientWidth || window.innerWidth;
    const height = this.container.clientHeight || window.innerHeight;

    // 1. Scene
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(this.options.theme === 'light' ? 0xedf1f7 : 0x0a0d14);

    // 2. Camera (Isometric Perspective)
    this.camera = new THREE.PerspectiveCamera(40, width / height, 0.5, 1000);
    this.resetCameraPosition();

    // 3. Renderer
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'high-performance' });
    this.renderer.setSize(width, height);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.1;
    this.container.appendChild(this.renderer.domElement);

    // 4. OrbitControls
    if (typeof THREE.OrbitControls !== 'undefined') {
      this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
      this.controls.enableDamping = true;
      this.controls.dampingFactor = 0.05;
      this.controls.maxPolarAngle = Math.PI / 2 - 0.02; // prevent going below ground
      this.controls.minDistance = 20;
      this.controls.maxDistance = 350;
      this.controls.target.set(0, 0, 0);
    }

    // 5. Lights
    this.ambientLight = new THREE.AmbientLight(
      this.options.theme === 'light' ? 0xffffff : 0x4a5d78, 
      this.options.theme === 'light' ? 0.9 : 0.8
    );
    this.scene.add(this.ambientLight);

    this.dirLight1 = new THREE.DirectionalLight(0xffffff, this.options.theme === 'light' ? 1.0 : 0.9);
    this.dirLight1.position.set(50, 80, 40);
    this.scene.add(this.dirLight1);

    this.dirLight2 = new THREE.DirectionalLight(0x00f0ff, this.options.theme === 'light' ? 0.2 : 0.4);
    this.dirLight2.position.set(-60, 40, -40);
    this.scene.add(this.dirLight2);

    // 6. Ground Grid
    this.gridHelper = new THREE.GridHelper(
      180, 36, 
      this.options.theme === 'light' ? 0xcad3df : 0x1f293d, 
      this.options.theme === 'light' ? 0xe2e8f0 : 0x131a29
    );
    this.gridHelper.position.y = -0.2;
    this.scene.add(this.gridHelper);

    // 7. Raycaster for Interaction
    this.raycaster = new THREE.Raycaster();
    this.mouse = new THREE.Vector2();

    // 8. Visual Root Group
    this.visualGroup = new THREE.Group();
    this.scene.add(this.visualGroup);
  }

  initMaterials() {
    // Shared reusable materials to prevent GC stutters and maximize FPS
    this.materials = {
      dark: {
        plinth: new THREE.MeshStandardMaterial({ color: 0x111624, roughness: 0.6, metalness: 0.2 }),
        edge: new THREE.LineBasicMaterial({ color: 0x00e5ff, linewidth: 2 }),
        cyan: new THREE.MeshStandardMaterial({ color: 0x00f0ff, roughness: 0.3, metalness: 0.4, transparent: true, opacity: 0.85 }),
        amber: new THREE.MeshStandardMaterial({ color: 0xf59e0b, roughness: 0.3, metalness: 0.4, transparent: true, opacity: 0.85 }),
        coral: new THREE.MeshStandardMaterial({ color: 0xef4444, roughness: 0.3, metalness: 0.4, transparent: true, opacity: 0.88 }),
        folder: new THREE.MeshStandardMaterial({ color: 0x3b82f6, roughness: 0.3, metalness: 0.3, transparent: true, opacity: 0.92 }),
        antenna: new THREE.MeshBasicMaterial({ color: 0xef4444 })
      },
      light: {
        plinth: new THREE.MeshStandardMaterial({ color: 0xdfe6ef, roughness: 0.6, metalness: 0.2 }),
        edge: new THREE.LineBasicMaterial({ color: 0x3b82f6, linewidth: 2 }),
        cyan: new THREE.MeshStandardMaterial({ color: 0x0284c7, roughness: 0.3, metalness: 0.4, transparent: true, opacity: 0.85 }),
        amber: new THREE.MeshStandardMaterial({ color: 0xd97706, roughness: 0.3, metalness: 0.4, transparent: true, opacity: 0.85 }),
        coral: new THREE.MeshStandardMaterial({ color: 0xdc2626, roughness: 0.3, metalness: 0.4, transparent: true, opacity: 0.88 }),
        folder: new THREE.MeshStandardMaterial({ color: 0x2563eb, roughness: 0.3, metalness: 0.3, transparent: true, opacity: 0.92 }),
        antenna: new THREE.MeshBasicMaterial({ color: 0xdc2626 })
      }
    };
  }

  getMat(type) {
    const themeKey = this.options.theme === 'light' ? 'light' : 'dark';
    return this.materials[themeKey][type] || this.materials[themeKey].cyan;
  }

  setTheme(theme) {
    this.options.theme = theme;
    const isLight = theme === 'light';
    this.scene.background.setHex(isLight ? 0xedf1f7 : 0x0a0d14);
    this.ambientLight.color.setHex(isLight ? 0xffffff : 0x4a5d78);
    this.ambientLight.intensity = isLight ? 0.9 : 0.8;
    this.dirLight1.intensity = isLight ? 1.0 : 0.9;
    this.dirLight2.intensity = isLight ? 0.2 : 0.4;
    this.gridHelper.material.color.setHex(isLight ? 0xcad3df : 0x1f293d);

    if (this.currentNode) {
      this.renderCurrentView();
    }
  }

  resetCameraPosition() {
    this.camera.position.set(70, 65, 80);
    if (this.controls) {
      this.controls.target.set(0, 5, 0);
      this.controls.update();
    }
  }

  setCameraView(preset) {
    if (!this.controls) return;
    if (preset === 'iso') {
      this.camera.position.set(70, 65, 80);
      this.controls.target.set(0, 5, 0);
    } else if (preset === 'top') {
      this.camera.position.set(0, 110, 0.1);
      this.controls.target.set(0, 0, 0);
    } else if (preset === 'front') {
      this.camera.position.set(0, 20, 110);
      this.controls.target.set(0, 10, 0);
    }
    this.controls.update();
  }

  initEvents() {
    window.addEventListener('resize', () => {
      const w = this.container.clientWidth;
      const h = this.container.clientHeight;
      if (w > 0 && h > 0) {
        this.camera.aspect = w / h;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(w, h);
      }
    });

    const dom = this.renderer.domElement;
    dom.addEventListener('mousemove', (e) => this.onMouseMove(e));
    dom.addEventListener('click', (e) => this.onClick(e));
    dom.addEventListener('dblclick', (e) => this.onDoubleClick(e));
  }

  onMouseMove(e) {
    const rect = this.renderer.domElement.getBoundingClientRect();
    this.mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    this.mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

    this.raycaster.setFromCamera(this.mouse, this.camera);
    const intersects = this.raycaster.intersectObjects(this.interactiveObjects, true);

    const tooltip = document.getElementById('floating-tooltip');

    if (intersects.length > 0) {
      let hit = intersects[0].object;
      while (hit && !hit.userData.node && hit.parent) {
        hit = hit.parent;
      }

      if (hit && hit.userData.node) {
        if (this.hoveredObject !== hit) {
          if (this.hoveredObject && this.hoveredObject !== this.selectedObject) {
            this.setObjectHighlight(this.hoveredObject, false);
          }
          this.hoveredObject = hit;
          this.setObjectHighlight(hit, true);
        }

        const node = hit.userData.node;
        if (tooltip) {
          tooltip.style.display = 'block';
          tooltip.style.left = `${e.clientX}px`;
          tooltip.style.top = `${e.clientY}px`;
          tooltip.innerHTML = `
            <div class="tooltip-title">${node.type === 'folder' ? '📁' : '📄'} ${this.escapeHtml(node.name)}</div>
            <div class="tooltip-meta">${this.formatBytes(node.size)} ${node.type === 'folder' ? `• ${(node.children || []).length} items` : ''}</div>
          `;
        }
        return;
      }
    }

    if (this.hoveredObject && this.hoveredObject !== this.selectedObject) {
      this.setObjectHighlight(this.hoveredObject, false);
      this.hoveredObject = null;
    }
    if (tooltip) {
      tooltip.style.display = 'none';
    }
  }

  onClick(e) {
    this.raycaster.setFromCamera(this.mouse, this.camera);
    const intersects = this.raycaster.intersectObjects(this.interactiveObjects, true);

    if (intersects.length > 0) {
      let hit = intersects[0].object;
      while (hit && !hit.userData.node && hit.parent) {
        hit = hit.parent;
      }

      if (hit && hit.userData.node) {
        if (this.selectedObject && this.selectedObject !== hit) {
          this.setObjectHighlight(this.selectedObject, false);
        }
        this.selectedObject = hit;
        this.setObjectHighlight(hit, true);

        if (this.options.onSelect) {
          this.options.onSelect(hit.userData.node);
        }
      }
    }
  }

  onDoubleClick(e) {
    this.raycaster.setFromCamera(this.mouse, this.camera);
    const intersects = this.raycaster.intersectObjects(this.interactiveObjects, true);

    if (intersects.length > 0) {
      let hit = intersects[0].object;
      while (hit && !hit.userData.node && hit.parent) {
        hit = hit.parent;
      }

      if (hit && hit.userData.node && hit.userData.node.type === 'folder') {
        if (this.options.onDrillDown) {
          this.options.onDrillDown(hit.userData.node);
        }
      }
    }
  }

  setObjectHighlight(obj, active) {
    if (!obj || !obj.material) return;
    if (Array.isArray(obj.material)) {
      obj.material.forEach(m => {
        if (m.emissive) m.emissive.setHex(active ? 0x2563eb : (m.userData.origEmissive || 0x000000));
      });
    } else if (obj.material.emissive) {
      if (active) {
        if (!obj.material.userData.origEmissive) obj.material.userData.origEmissive = obj.material.emissive.getHex();
        obj.material.emissive.setHex(0x3b82f6);
      } else {
        obj.material.emissive.setHex(obj.material.userData.origEmissive || 0x000000);
      }
    }
  }

  // --- DATA LOADING & VIEW SWITCHING ---
  setData(rootNode) {
    this.currentData = rootNode;
    this.currentNode = rootNode;
    this.renderCurrentView();
  }

  setNode(node) {
    this.currentNode = node;
    this.renderCurrentView();
  }

  setMode(mode) {
    this.currentMode = mode;
    this.renderCurrentView();
  }

  setTerrainDepth(depth) {
    this.terrainDepth = depth;
    if (this.currentMode === 'terrain') {
      this.renderCurrentView();
    }
  }

  toggleExplode(explode) {
    this.isExploded = explode;
    this.targetExplodedFactor = explode ? 1 : 0;
  }

  clearScene() {
    this.interactiveObjects = [];
    this.hoveredObject = null;
    this.selectedObject = null;
    this.peakPins = [];

    // Clear visual meshes safely without disposing shared palette materials
    while (this.visualGroup.children.length > 0) {
      const obj = this.visualGroup.children[0];
      this.visualGroup.remove(obj);
      if (obj.geometry) obj.geometry.dispose();
    }
  }

  renderCurrentView() {
    this.clearScene();
    if (!this.currentNode) return;

    if (this.currentMode === 'city') {
      this.renderStorageCity(this.currentNode);
    } else if (this.currentMode === 'layers') {
      this.renderFolderLayers(this.currentNode);
    } else if (this.currentMode === 'terrain') {
      this.renderStorageTerrain(this.currentNode);
    }
  }

  // ==========================================
  // CONCEPT A: STORAGE CITY (Image 2)
  // Folders are districts. Files are skyscrapers.
  // ==========================================
  renderStorageCity(root) {
    const isLight = this.options.theme === 'light';
    const children = (root.children || []);
    if (children.length === 0) return;

    const districts = children.filter(c => c.type === 'folder');
    const directFiles = children.filter(c => c.type === 'file');

    const allDistricts = [...districts];
    if (directFiles.length > 0) {
      allDistricts.push({
        name: "Root Files",
        path: root.path,
        size: directFiles.reduce((acc, f) => acc + (f.size || 0), 0),
        type: "folder",
        children: directFiles
      });
    }

    const citySize = 90;
    const districtBoxes = this.layoutTreemap(allDistricts, -citySize/2, -citySize/2, citySize, citySize);

    districtBoxes.forEach(dist => {
      const node = dist.node;
      const w = Math.max(8, dist.w - 3);
      const d = Math.max(8, dist.h - 3);
      const cx = dist.x + dist.w / 2;
      const cz = dist.y + dist.h / 2;

      // 1. Elevated District Plinth
      const plinthGeo = new THREE.BoxGeometry(w, 2.5, d);
      const plinth = new THREE.Mesh(plinthGeo, this.getMat('plinth'));
      plinth.position.set(cx, 1.25, cz);
      plinth.userData = { node: node };
      this.visualGroup.add(plinth);
      this.interactiveObjects.push(plinth);

      // Glowing Canal / Border Outline
      const edges = new THREE.EdgesGeometry(plinthGeo);
      const border = new THREE.LineSegments(edges, this.getMat('edge'));
      plinth.add(border);

      // 2. Skyscrapers (Subfolders and Files inside district, capped at top 24 for ultra-smooth 60fps)
      const subItems = (node.children || []).slice(0, 24);
      if (subItems.length > 0) {
        const subBoxes = this.layoutTreemap(subItems, -w/2 + 0.8, -d/2 + 0.8, w - 1.6, d - 1.6);
        subBoxes.forEach(s => {
          const itemNode = s.node;
          const bw = Math.max(1.2, s.w - 0.4);
          const bd = Math.max(1.2, s.h - 0.4);
          const sz = itemNode.size || 0;
          const bh = Math.min(38, Math.max(1.5, Math.log10(Math.max(1024, sz)) * 3.5));
          
          const buildingGeo = new THREE.BoxGeometry(bw, bh, bd);
          const matType = itemNode.type === 'folder' ? 'folder' : (sz >= 1e9 ? 'coral' : (sz >= 1e8 ? 'amber' : 'cyan'));
          const building = new THREE.Mesh(buildingGeo, this.getMat(matType));
          building.position.set(cx + s.x + s.w/2, 2.5 + bh/2, cz + s.y + s.h/2);
          building.userData = { node: itemNode };
          this.visualGroup.add(building);
          this.interactiveObjects.push(building);

          // Skyscraper roof highlight / antenna if tall
          if (bh > 18) {
            const antGeo = new THREE.CylinderGeometry(0.1, 0.1, 3);
            const ant = new THREE.Mesh(antGeo, this.getMat('antenna'));
            ant.position.set(0, bh/2 + 1.5, 0);
            building.add(ant);
          }
        });
      }
    });
  }

  // ==========================================
  // CONCEPT B: FOLDER LAYERS (Image 1)
  // Stacked Frosted Glass Plates with Explode Animation
  // ==========================================
  renderFolderLayers(root) {
    const isLight = this.options.theme === 'light';
    const children = (root.children || []);
    if (children.length === 0) return;

    this.layersList = [];

    // Base Chamfered Metal Plinth
    const baseW = 85;
    const baseD = 65;
    const baseGeo = new THREE.BoxGeometry(baseW, 3, baseD);
    const baseMat = new THREE.MeshStandardMaterial({
      color: isLight ? 0xe2e8f0 : 0x151b2a,
      roughness: 0.4,
      metalness: 0.6
    });
    const baseMesh = new THREE.Mesh(baseGeo, baseMat);
    baseMesh.position.set(0, 1.5, 0);
    this.visualGroup.add(baseMesh);

    // Sibling base blocks on Layer 0
    const topFolders = children.slice(0, 6);
    const layer0Boxes = this.layoutTreemap(topFolders, -baseW/2 + 3, -baseD/2 + 3, baseW - 6, baseD - 6);

    let stackTarget = topFolders[0]; // Active branch to stack upwards

    layer0Boxes.forEach((b, idx) => {
      const node = b.node;
      const bw = Math.max(6, b.w - 3);
      const bd = Math.max(6, b.h - 3);
      const bh = 5;

      const glassMat = new THREE.MeshPhysicalMaterial({
        color: this.getSizeColor(node.size || 0, isLight),
        transparent: true,
        opacity: 0.65,
        roughness: 0.1,
        metalness: 0.1,
        transmission: 0.4,
        ior: 1.4
      });

      const blockGeo = new THREE.BoxGeometry(bw, bh, bd);
      const blockMesh = new THREE.Mesh(blockGeo, glassMat);
      const bx = b.x + b.w/2;
      const bz = b.y + b.h/2;
      blockMesh.position.set(bx, 3 + bh/2, bz);
      blockMesh.userData = { node: node };
      this.visualGroup.add(blockMesh);
      this.interactiveObjects.push(blockMesh);

      if (idx === 0) {
        stackTarget = node;
      }
    });

    // Create Stacked Floating Glass Levels for stackTarget
    if (stackTarget && stackTarget.children && stackTarget.children.length > 0) {
      const subItems = stackTarget.children.slice(0, 8);

      const l1Group = new THREE.Group();
      l1Group.userData = { baseOffset: 8, explodeOffset: 16 };

      const plate1Geo = new THREE.BoxGeometry(45, 1.2, 38);
      const plate1Mat = new THREE.MeshPhysicalMaterial({
        color: isLight ? 0xffffff : 0x223049,
        transparent: true,
        opacity: 0.75,
        transmission: 0.6,
        roughness: 0.1
      });
      const plate1 = new THREE.Mesh(plate1Geo, plate1Mat);
      l1Group.add(plate1);

      // Sub-blocks on Layer 1
      const l1Boxes = this.layoutTreemap(subItems, -21, -17, 42, 34);
      l1Boxes.forEach(sb => {
        const snode = sb.node;
        const sw = Math.max(3, sb.w - 1.5);
        const sd = Math.max(3, sb.h - 1.5);
        const sh = Math.min(10, Math.max(2, Math.log10(Math.max(1024, snode.size || 0)) * 2));

        const subMat = new THREE.MeshStandardMaterial({
          color: this.getSizeColor(snode.size || 0, isLight),
          roughness: 0.2,
          metalness: 0.3,
          transparent: true,
          opacity: 0.85
        });
        const subMesh = new THREE.Mesh(new THREE.BoxGeometry(sw, sh, sd), subMat);
        subMesh.position.set(sb.x + sb.w/2, 0.6 + sh/2, sb.y + sb.h/2);
        subMesh.userData = { node: snode };
        l1Group.add(subMesh);
        this.interactiveObjects.push(subMesh);
      });

      l1Group.position.set(0, 14, 0);
      this.visualGroup.add(l1Group);
      this.layersList.push(l1Group);

      // Dashed vertical guide pillars
      const guidePoints = [
        new THREE.Vector3(-22, 3, -18), new THREE.Vector3(-22, 28, -18),
        new THREE.Vector3(22, 3, -18), new THREE.Vector3(22, 28, -18),
        new THREE.Vector3(-22, 3, 18), new THREE.Vector3(-22, 28, 18),
        new THREE.Vector3(22, 3, 18), new THREE.Vector3(22, 28, 18),
      ];
      for (let i = 0; i < guidePoints.length; i += 2) {
        const lineGeo = new THREE.BufferGeometry().setFromPoints([guidePoints[i], guidePoints[i+1]]);
        const line = new THREE.Line(lineGeo, new THREE.LineDashedMaterial({
          color: isLight ? 0x94a3b8 : 0x3b82f6,
          dashSize: 1.5,
          gapSize: 1.2
        }));
        line.computeLineDistances();
        this.visualGroup.add(line);
      }
    }
  }

  // ==========================================
  // CONCEPT D: STORAGE TERRAIN (Image 3)
  // 3D Voxel Topography with Peaks, Pins & Depth
  // ==========================================
  renderStorageTerrain(root) {
    const isLight = this.options.theme === 'light';
    const children = (root.children || []);
    if (children.length === 0) return;

    const trayW = 94;
    const trayD = 58;
    const trayH = 2.5;

    // Compartment Tray Frame
    const frameGeo = new THREE.BoxGeometry(trayW + 2, trayH, trayD + 2);
    const frameMat = new THREE.MeshStandardMaterial({
      color: isLight ? 0xd1d5db : 0x111622,
      roughness: 0.5,
      metalness: 0.3
    });
    const frame = new THREE.Mesh(frameGeo, frameMat);
    frame.position.set(0, trayH/2, 0);
    this.visualGroup.add(frame);

    // Compartment partitions based on top directories
    const topFolders = children.slice(0, 5);
    const bins = this.layoutTreemap(topFolders, -trayW/2 + 1, -trayD/2 + 1, trayW - 2, trayD - 2);

    const largestFilesAcrossAll = [];

    bins.forEach(bin => {
      const node = bin.node;
      const bw = bin.w - 1.5;
      const bd = bin.h - 1.5;
      const bx = bin.x + bin.w/2;
      const bz = bin.y + bin.h/2;

      // Inner divider line
      const divGeo = new THREE.EdgesGeometry(new THREE.BoxGeometry(bw, trayH, bd));
      const divider = new THREE.LineSegments(divGeo, new THREE.LineBasicMaterial({
        color: isLight ? 0x9ca3af : 0x1e293b
      }));
      divider.position.set(bx, trayH/2 + 0.1, bz);
      this.visualGroup.add(divider);

      // Collect flat items up to selected hierarchy depth
      const harvested = [];
      this.harvestToDepth(node, harvested, 1, this.terrainDepth);

      // Generate Voxel Columns Grid
      const cols = Math.max(3, Math.min(10, Math.floor(bw / 3.0)));
      const rows = Math.max(3, Math.min(10, Math.floor(bd / 3.0)));
      const cellW = bw / cols;
      const cellD = bd / rows;

      harvested.sort((a, b) => (b.size || 0) - (a.size || 0));
      if (harvested.length > 0 && harvested[0].type === 'file') {
        largestFilesAcrossAll.push(harvested[0]);
      }

      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          const idx = (r * cols + c) % (harvested.length || 1);
          const item = harvested[idx] || node;

          const sz = item.size || 0;
          const sizeNorm = Math.min(1, Math.log10(Math.max(1024, sz) + 1) / 10);
          const vh = Math.max(1.2, sizeNorm * 26 * (1 + 0.25 * Math.sin(c + r)));

          const vColor = this.getTerrainColor(vh / 26, isLight);

          const voxelGeo = new THREE.BoxGeometry(cellW - 0.25, vh, cellD - 0.25);
          const voxelMat = new THREE.MeshStandardMaterial({
            color: vColor,
            roughness: 0.35,
            metalness: 0.25
          });

          const voxel = new THREE.Mesh(voxelGeo, voxelMat);
          const vx = (bin.x + 0.75) + c * cellW + cellW/2;
          const vz = (bin.y + 0.75) + r * cellD + cellD/2;
          voxel.position.set(vx, trayH + vh/2, vz);
          voxel.userData = { node: item, peakHeight: trayH + vh };
          this.visualGroup.add(voxel);
          this.interactiveObjects.push(voxel);
        }
      }
    });

    // 3D Peak Pins for top 2 largest files
    largestFilesAcrossAll.slice(0, 2).forEach((fileNode) => {
      const targetVoxel = this.interactiveObjects.find(o => o.userData.node === fileNode);
      if (targetVoxel) {
        const topY = targetVoxel.userData.peakHeight;
        const px = targetVoxel.position.x;
        const pz = targetVoxel.position.z;

        // Glowing Beacon Head
        const pinHeadGeo = new THREE.SphereGeometry(0.8, 16, 16);
        const pinHeadMat = new THREE.MeshBasicMaterial({ color: 0xffffff });
        const pinHead = new THREE.Mesh(pinHeadGeo, pinHeadMat);
        pinHead.position.set(px, topY + 4, pz);
        this.visualGroup.add(pinHead);

        // Leader Line
        const lineGeo = new THREE.BufferGeometry().setFromPoints([
          new THREE.Vector3(px, topY, pz),
          new THREE.Vector3(px, topY + 4, pz)
        ]);
        const leader = new THREE.Line(lineGeo, new THREE.LineBasicMaterial({ color: 0xffffff }));
        this.visualGroup.add(leader);
      }
    });
  }

  harvestToDepth(node, outList, currentDepth, maxDepth) {
    if (currentDepth >= maxDepth || !node.children || node.children.length === 0) {
      outList.push(node);
      return;
    }
    for (let i = 0; i < node.children.length; i++) {
      this.harvestToDepth(node.children[i], outList, currentDepth + 1, maxDepth);
    }
  }

  // --- SQUARIFIED TREEMAP 2D PACKING HELPER ---
  layoutTreemap(items, x, y, w, h) {
    if (!items || items.length === 0) return [];
    const total = items.reduce((s, it) => s + Math.max(1024, it.size || 0), 0);
    const results = [];
    let curX = x;
    let curY = y;
    let remW = w;
    let remH = h;

    items.forEach((item) => {
      const frac = Math.max(1024, item.size || 0) / total;
      if (remW > remH) {
        const itemW = Math.max(1, frac * w);
        results.push({ node: item, x: curX, y: curY, w: itemW, h: remH });
        curX += itemW;
      } else {
        const itemH = Math.max(1, frac * h);
        results.push({ node: item, x: curX, y: curY, w: remW, h: itemH });
        curY += itemH;
      }
    });

    return results;
  }

  // --- COLOR UTILITIES ---
  getSizeColor(bytes, isLight) {
    if (bytes >= 1e9) { // > 1 GB
      return isLight ? 0xdc2626 : 0xef4444; // Coral / Red
    } else if (bytes >= 1e8) { // 100 MB - 1 GB
      return isLight ? 0xd97706 : 0xf59e0b; // Amber / Orange
    } else { // < 100 MB
      return isLight ? 0x0284c7 : 0x00f0ff; // Cyan / Blue
    }
  }

  getTerrainColor(t, isLight) {
    if (t > 0.65) {
      return isLight ? 0xdc2626 : 0xef4444; // Coral / Red Peak
    } else if (t > 0.3) {
      return isLight ? 0xd97706 : 0xf59e0b; // Amber Slope
    } else {
      return isLight ? 0x059669 : 0x00f0ff; // Cyan/Green Valley
    }
  }

  formatBytes(bytes) {
    if (!bytes || bytes <= 0) return "0 B";
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }

  escapeHtml(str) {
    if (!str) return '';
    return str.replace(/[&<>"']/g, m => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[m]);
  }

  // --- ANIMATION LOOP ---
  animate() {
    requestAnimationFrame(this.animate);

    if (this.controls) {
      this.controls.update();
    }

    // Smooth Explode / Collapse lerp in Layers mode
    if (this.currentMode === 'layers' && this.layersList && this.layersList.length > 0) {
      this.explodedFactor += (this.targetExplodedFactor - this.explodedFactor) * 0.08;
      this.layersList.forEach((layer, idx) => {
        const targetY = 10 + (idx + 1) * (6 + this.explodedFactor * 16);
        layer.position.y += (targetY - layer.position.y) * 0.1;
      });
    }

    this.renderer.render(this.scene, this.camera);
  }
}
