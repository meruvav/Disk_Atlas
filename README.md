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
│   ├── DiskAtlas.spec            # PyInstaller spec for the application
│   ├── installer_windows.iss     # Inno Setup installer script (single Windows installer)
│   ├── signing.py                # Windows Authenticode signing helpers
│   ├── SIGNING.md                # Code-signing certificate setup guide
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
The Windows installer is built with Inno Setup 6 (`packaging/installer_windows.iss`). To produce it:

```bash
# Install build dependencies + Inno Setup 6 (https://jrsoftware.org/isinfo.php)
pip install -r requirements.txt

# Run the 1-click build pipeline (PyInstaller + Inno Setup)
python packaging/build_windows.py

# Or run only one stage:
python packaging/build_windows.py --app-only
python packaging/build_windows.py --installer-only
```

The resulting standalone installer will be located at:
```text
dist/DiskAtlas_Setup_<version>.exe
```

#### Features of `DiskAtlas_Setup_<version>.exe`:
- **Interactive Directory Selection**: Choose where to install (e.g. `C:\Program Files\DiskAtlas` or a custom folder), including an optional per-user install without admin rights.
- **Automatic Administrator Elevation**: Automatically elevates when installing into system-protected directories.
- **Safe Upgrades**: A running Disk Atlas is closed automatically via Restart Manager before files are replaced.
- **Desktop & Start Menu Shortcuts**: Automatically adds shortcuts for quick access.
- **Windows Settings Integration**: Registers cleanly in **Windows Settings > Apps > Installed Apps** with a full uninstaller, version and publisher metadata.
- **Silent Install**: Standard Inno Setup flags (`/SILENT`, `/VERYSILENT`, `/DIR=...`) work out of the box.

### Code Signing (Windows)
The pipeline signs `DiskAtlas.exe` and the setup wizard automatically when a signing certificate is configured (see `packaging/SIGNING.md`):

```bash
export DISK_ATLAS_SIGN_SUBJECT="Meruva LLC"
python packaging/build_windows.py --require-sign
```

Signing supports a PFX file or the Windows certificate store, SHA-256 digests, and an RFC 3161 timestamp server so signatures outlive the certificate. Release builds should use `--require-sign` so an unconfigured machine fails loudly instead of producing an unsigned installer.

---

## 🌟 Visualization Modes
1. **3D Storage City**: Folders and files rendered as interactive city blocks and skyscrapers scaled by size.
2. **Folder Layers**: Tiered vertical hierarchy displaying nested directories with elevation and depth.
3. **Storage Terrain**: Topographic heat-map representation of storage distribution across your disk.

---

## 📄 License
MIT License. Free for personal and commercial use.
