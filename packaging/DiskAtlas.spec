# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

block_cipher = None

SPEC_PATH = Path(SPECPATH)
ROOT_DIR = SPEC_PATH.parent if SPEC_PATH.name == "packaging" else SPEC_PATH
SRC_DIR = ROOT_DIR / "src"

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
