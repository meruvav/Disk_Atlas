# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

block_cipher = None

SPEC_PATH = Path(SPECPATH)
ROOT_DIR = SPEC_PATH.parent if SPEC_PATH.name == "packaging" else SPEC_PATH
PACKAGING_DIR = ROOT_DIR / "packaging"
SRC_DIR = ROOT_DIR / "src"
ASSETS_DIR = PACKAGING_DIR / "assets"

# --- App identity from src/version.py ---
_ns = {}
exec((SRC_DIR / "version.py").read_text(encoding="utf-8"), _ns)
APP_VERSION = _ns["__version__"]
APP_NAME = _ns["APP_NAME"]
COMPANY_NAME = _ns["COMPANY_NAME"]
_ver = tuple(int(p) for p in APP_VERSION.split("."))
VERSION_4 = _ver + (0,) * (4 - len(_ver))

# --- Windows version resource + icon for the setup wizard ---
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
                vi.StringStruct("FileDescription", f"{APP_NAME} Setup Wizard"),
                vi.StringStruct("FileVersion", ".".join(str(v) for v in VERSION_4)),
                vi.StringStruct("InternalName", "DiskAtlas_Setup"),
                vi.StringStruct("LegalCopyright", "MIT License"),
                vi.StringStruct("OriginalFilename", "DiskAtlas_Setup.exe"),
                vi.StringStruct("ProductName", f"{APP_NAME} Setup"),
                vi.StringStruct("ProductVersion", ".".join(str(v) for v in VERSION_4)),
            ])]),
            vi.VarFileInfo([vi.VarStruct("Translation", [1033, 1200])]),
        ],
    )
    exe_icon = str(ASSETS_DIR / "diskatlas.ico")

payload_zip = ROOT_DIR / "dist" / "DiskAtlas_Payload.zip"
if not payload_zip.exists():
    payload_zip = ROOT_DIR / "DiskAtlas_Payload.zip"

a = Analysis(
    [str(PACKAGING_DIR / "installer.py")],
    pathex=[str(PACKAGING_DIR)],
    binaries=[],
    datas=[
        (str(payload_zip), "."),
    ],
    hiddenimports=[],
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
    a.binaries,
    a.datas,
    [],
    name="DiskAtlas_Setup",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=True,
    version=version_info,
    icon=exe_icon,
)
