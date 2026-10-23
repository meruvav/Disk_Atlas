# Disk Atlas 🌐💾

> **Interactive 3D Disk Space Visualizer & Analyzer**
> 
> A desktop storage analyzer that transforms your file system into an interactive 3D environment. Explore disk usage through **3D Storage City**, **Folder Layers**, and **Storage Terrain** visualizations.

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Modern Web Browser (Chrome, Edge, Firefox, Brave)

### Run from Source
```bash
# Clone the repository
git clone https://github.com/meruvav/Disk_Atlas.git
cd Disk_Atlas

# Run Disk Atlas
python run.py
```
Or directly from `src/`:
```bash
python src/disk_atlas.py
```

---

## 📁 Project Structure

The project follows a clean, minimal root directory layout:

```text
Disk_Atlas/
├── src/                          # Application source code & assets
│   ├── web/                      # Frontend 3D visualization engine (Three.js & UI)
│   │   ├── index.html            # Main dashboard interface
│   │   ├── style.css             # Glassmorphism dark theme styles
│   │   ├── visualizer.js         # 3D City, Layers & Terrain visualizer
│   │   ├── app.js                # State management, scan APIs & controls
│   │   ├── three.min.js          # Three.js 3D library
│   │   └── OrbitControls.js      # Camera controls
│   ├── disk_atlas.py             # High-performance scanner & local HTTP API
│   └── disk_insight.py           # Compatibility wrapper
│
├── packaging/                    # Multi-platform installers & build tools
│   ├── scripts/                  # OS post-installation scripts
│   ├── build_windows.py          # 1-click Windows automated build pipeline
│   ├── installer.py              # Windows Setup wizard (GUI, shortcuts, registry)
│   ├── DiskAtlas.spec            # PyInstaller spec for main application
│   ├── DiskAtlas_Setup.spec      # PyInstaller spec for Setup wizard
│   ├── installer_windows.iss     # Inno Setup installer script
│   ├── install_linux.sh          # Linux installer script
│   └── build_macos.sh            # macOS packaging script
│
├── run.py                        # Root launcher script (python run.py)
├── requirements.txt              # Build dependencies
├── .gitignore                    # Git ignore configuration
└── README.md                     # Documentation
```

---

## 🛠️ Building Standalone Installers

### Windows Standalone Installer
To build the complete standalone setup wizard (`DiskAtlas_Setup.exe`):

```bash
# Install PyInstaller
pip install -r requirements.txt

# Run the 1-click build pipeline
python packaging/build_windows.py
```

The resulting standalone installer will be located at:
```text
dist/DiskAtlas_Setup.exe
```

#### Features of `DiskAtlas_Setup.exe`:
- **Interactive Directory Selection**: Choose where to install (e.g. `C:\Program Files\DiskAtlas` or a custom drive/folder).
- **Automatic Administrator Elevation**: Automatically elevates when installing into system-protected directories.
- **Desktop & Start Menu Shortcuts**: Automatically adds shortcuts for quick access.
- **Windows Settings Integration**: Registers cleanly in **Windows Settings > Apps > Installed Apps** with a full uninstaller.

---

## 🌟 Visualization Modes
1. **3D Storage City**: Folders and files rendered as interactive city blocks and skyscrapers scaled by size.
2. **Folder Layers**: Tiered vertical hierarchy displaying nested directories with elevation and depth.
3. **Storage Terrain**: Topographic heat-map representation of storage distribution across your disk.

---

## 📄 License
MIT License. Free for personal and commercial use.
