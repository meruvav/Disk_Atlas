# Disk Atlas 🌐💾

> **Interactive 3D Disk Space Visualizer & Analyzer**
> 
> A desktop storage analyzer that transforms your file system into an interactive 3D environment. Explore disk usage through **3D Storage City**, **Folder Layers**, and **Storage Terrain** visualizations.

---

## 📥 Download

Get the latest desktop build for Windows, macOS, or Linux from the **[download page](https://meruvav.github.io/Disk_Atlas/)** or browse all releases on the **[releases page](https://github.com/meruvav/Disk_Atlas/releases)**. The app checks for new versions automatically (About → Check for Updates).

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
│   ├── build_windows.py          # 1-click Windows automated build pipeline
│   ├── DiskAtlas.spec            # PyInstaller spec for the application
│   ├── installer_windows.iss     # Inno Setup installer script (single Windows installer)
│   ├── signing.py                # Windows Authenticode signing helpers
│   ├── SIGNING.md                # Code-signing certificate setup guide
│   ├── install_linux.sh          # Linux installer script
│   ├── build_macos.sh            # macOS sign / DMG / notarize pipeline
│   ├── macos_entitlements.plist  # Hardened-runtime entitlements
│   └── NOTARIZATION.md           # macOS signing & notarization guide
│
├── docs/                         # Public download page (GitHub Pages)
│   ├── index.html                # OS-aware release download page
│   └── assets/                   # Page assets (app icon)
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

### macOS Standalone DMG (signed + notarized)
The macOS pipeline builds the `.app` bundle, signs it with the hardened runtime, packages a DMG with an /Applications drag-target, notarizes it with Apple, and staples the ticket (see `packaging/NOTARIZATION.md`):

```bash
export DISK_ATLAS_MAC_SIGN_IDENTITY="Developer ID Application: Meruva LLC (TEAMID)"
export DISK_ATLAS_MAC_NOTARY_PROFILE="disk-atlas-notary"
./packaging/build_macos.sh --require-sign
```

Without a signing identity it falls back to ad-hoc signing for local dev builds. The guide covers the one-time Apple setup: Developer account, "Developer ID Application" certificate, and notarytool credentials.

---

## 🚀 Releasing a New Version
Releases are fully automated via GitHub Actions (`.github/workflows/release.yml`):

```bash
# 1. Bump src/version.py (the single version source of truth)
# 2. Commit, then tag with the exact same version
git tag v2.0.0
git push origin main v2.0.0
```

The pipeline runs the pytest suite, verifies the tag matches `src/version.py`, builds on Windows/macOS/Linux runners, signs and notarizes when the secrets below are configured, and publishes a GitHub release with the `DiskAtlas_Setup_<version>.exe` installer, `DiskAtlas_macOS_<version>.dmg`, and `DiskAtlas_linux_<version>.tar.gz` attached. Tags containing `alpha`/`beta`/`rc` are published as pre-releases.

Configure these repository secrets once (Settings > Secrets and variables > Actions):

| Secret | Purpose |
|---|---|
| `WINDOWS_CERT_PFX` | base64-encoded OV/EV code-signing certificate |
| `WINDOWS_CERT_PFX_PASSWORD` | certificate password |
| `MACOS_CERT_P12` | base64-encoded Developer ID Application certificate |
| `MACOS_CERT_PASSWORD` | certificate password |
| `MACOS_SIGN_IDENTITY` | e.g. `Developer ID Application: Meruva LLC (TEAMID)` |
| `DISK_ATLAS_NOTARY_KEY_ID` | App Store Connect API key ID |
| `DISK_ATLAS_NOTARY_ISSUER_ID` | API issuer ID |
| `DISK_ATLAS_NOTARY_KEY_P8` | base64-encoded `AuthKey_*.p8` contents |

Until those exist, the same workflow still runs end-to-end and produces unsigned/dev artifacts. Every push to `main` and every pull request runs the test suite via `.github/workflows/ci.yml`.

### Public download page
A static download page lives in `docs/` (`docs/index.html`). To publish it, enable GitHub Pages once: **Settings > Pages > Source: Deploy from a branch > main > /docs**. It goes live at `https://meruvav.github.io/Disk_Atlas/`, detects the visitor's OS, and serves the newest release assets straight from the GitHub releases API — no rebuild needed on releases.

---

## 🌟 Visualization Modes
1. **3D Storage City**: Folders and files rendered as interactive city blocks and skyscrapers scaled by size.
2. **Folder Layers**: Tiered vertical hierarchy displaying nested directories with elevation and depth.
3. **Storage Treemap**: Proportional flat map — the largest block is the largest file; nested borders show folder structure. Double-click any folder to zoom in.
4. **Storage Terrain**: Topographic heat-map representation of storage distribution across your disk.
5. **Storage Explorer**: Tabular list view with search, sorting, and file attributes.

---

## 📄 License
MIT License. Free for personal and commercial use.
