# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

block_cipher = None

SPEC_PATH = Path(SPECPATH)
ROOT_DIR = SPEC_PATH.parent if SPEC_PATH.name == "packaging" else SPEC_PATH
PACKAGING_DIR = ROOT_DIR / "packaging"

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
)
