# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Disk Atlas desktop app.

App identity (version, name, bundle id) is read from src/version.py —
bump it there, not here.
"""
import sys
from pathlib import Path

SPEC_PATH = Path(SPECPATH)
ROOT_DIR = SPEC_PATH.parent if SPEC_PATH.name == "packaging" else SPEC_PATH
SRC_DIR = ROOT_DIR / "src"
ASSETS_DIR = ROOT_DIR / "packaging" / "assets"

# --- App identity from src/version.py ---
_ns = {}
exec((SRC_DIR / "version.py").read_text(encoding="utf-8"), _ns)
APP_VERSION = _ns["__version__"]
APP_NAME = _ns["APP_NAME"]
COMPANY_NAME = _ns["COMPANY_NAME"]
BUNDLE_ID = _ns["BUNDLE_ID"]
_ver = tuple(int(p) for p in APP_VERSION.split("."))
VERSION_4 = _ver + (0,) * (4 - len(_ver))

added_files = [
    (str(SRC_DIR / "web"), "web"),
]

hidden_imports = ["webview"]
try:
    # pywebview ships JS/assets that must be bundled for the native window
    from PyInstaller.utils.hooks import collect_data_files
    added_files += collect_data_files("webview")
except Exception:
    pass

# --- Windows version resource (Properties dialog metadata) ---
version_info = None
exe_icon = None
if sys.platform == "win32":
    from PyInstaller.utils.win32 import versioninfo as vi
    version_info = vi.VSVersionInfo(
        ffi=vi.FixedFileInfo(
            filevers=VERSION_4, prodvers=VERSION_4,
            mask=0x3F, flags=0x0, OS=0x40004, fileType=0x1,
            subtype=0x0, date=(0, 0),
        ),
        kids=[
            vi.StringFileInfo([vi.StringTable("040904B0", [
                vi.StringStruct("CompanyName", COMPANY_NAME),
                vi.StringStruct("FileDescription",
                                f"{APP_NAME} — Interactive 3D Disk Space Visualizer"),
                vi.StringStruct("FileVersion", ".".join(str(v) for v in VERSION_4)),
                vi.StringStruct("InternalName", "DiskAtlas"),
                vi.StringStruct("LegalCopyright", "MIT License"),
                vi.StringStruct("OriginalFilename", "DiskAtlas.exe"),
                vi.StringStruct("ProductName", APP_NAME),
                vi.StringStruct("ProductVersion", ".".join(str(v) for v in VERSION_4)),
            ])]),
            vi.VarFileInfo([vi.VarStruct("Translation", [1033, 1200])]),
        ],
    )
    exe_icon = str(ASSETS_DIR / "diskatlas.ico")

a = Analysis(
    [str(SRC_DIR / "desktop.py")],
    pathex=[str(SRC_DIR)],
    binaries=[],
    datas=added_files,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DiskAtlas",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=version_info,
    icon=exe_icon,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="DiskAtlas",
)

# --- macOS .app bundle with full metadata ---
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="DiskAtlas.app",
        icon=str(ASSETS_DIR / "diskatlas.icns"),
        bundle_identifier=BUNDLE_ID,
        version=APP_VERSION,
        info_plist={
            "CFBundleName": APP_NAME,
            "CFBundleDisplayName": APP_NAME,
            "CFBundleShortVersionString": APP_VERSION,
            "CFBundleVersion": APP_VERSION,
            "CFBundleExecutable": "DiskAtlas",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "10.13",
            "NSHumanReadableCopyright": "MIT License",
        },
    )
