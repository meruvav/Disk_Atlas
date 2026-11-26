#!/usr/bin/env python3
"""
Disk Atlas — Windows Build Pipeline

Two stages:
    1. Build dist/DiskAtlas/ with PyInstaller (packaging/DiskAtlas.spec)
    2. Compile dist/DiskAtlas_Setup_<version>.exe with Inno Setup 6
       (packaging/installer_windows.iss)

Usage:
    python packaging/build_windows.py                # full pipeline
    python packaging/build_windows.py --app-only     # PyInstaller stage only
    python packaging/build_windows.py --installer-only  # Inno stage only
                                                      # (needs an existing
                                                      #  dist/DiskAtlas/)

The Inno compiler is located via, in order:
    1. ISCC_PATH environment variable (full path to ISCC.exe)
    2. PATH (iscc or ISCC.exe)
    3. Default Inno Setup 6 install locations
Install Inno Setup 6 from https://jrsoftware.org/isinfo.php

Build artifacts stay under dist/. Releases are published via CI
(GitHub Actions), not by copying files into repo folders.
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT_DIR / "dist"
BUILD_DIR = ROOT_DIR / "build"
PACKAGING_DIR = ROOT_DIR / "packaging"
SRC_DIR = ROOT_DIR / "src"

ISS_FILE = PACKAGING_DIR / "installer_windows.iss"
SPEC_FILE = PACKAGING_DIR / "DiskAtlas.spec"


def read_version() -> str:
    """Single source of truth: src/version.py"""
    namespace: dict = {}
    exec((SRC_DIR / "version.py").read_text(encoding="utf-8"), namespace)
    return namespace["__version__"]


def run_command(cmd: list, desc: str) -> None:
    print(f"\n[+] {desc}...")
    print(f"    Running: {' '.join(str(c) for c in cmd)}")
    res = subprocess.run([str(c) for c in cmd], cwd=str(ROOT_DIR))
    if res.returncode != 0:
        print(f"[-] Error: {desc} failed with exit code {res.returncode}")
        sys.exit(res.returncode)


def find_iscc() -> str:
    """Locate the Inno Setup 6 command-line compiler (ISCC)."""
    env_path = os.environ.get("ISCC_PATH")
    if env_path and Path(env_path).is_file():
        return env_path

    for name in ("ISCC.exe", "iscc"):
        on_path = shutil.which(name)
        if on_path:
            return on_path

    if sys.platform == "win32":
        for root in (
            os.environ.get("ProgramFiles(x86)", ""),
            os.environ.get("ProgramFiles", ""),
            os.environ.get("LOCALAPPDATA", ""),
        ):
            if not root:
                continue
            candidate = Path(root) / "Inno Setup 6" / "ISCC.exe"
            if candidate.is_file():
                return str(candidate)

    print("[-] Error: Inno Setup 6 compiler (ISCC.exe) not found.")
    print("    Install it from https://jrsoftware.org/isinfo.php or set the")
    print("    ISCC_PATH environment variable to the compiler's full path.")
    sys.exit(2)


def build_app() -> None:
    run_command(
        [
            sys.executable, "-m", "PyInstaller",
            "--noconfirm",
            "--distpath", str(DIST_DIR),
            "--workpath", str(BUILD_DIR),
            str(SPEC_FILE),
        ],
        "Building DiskAtlas application",
    )
    if not (DIST_DIR / "DiskAtlas" / "DiskAtlas.exe").exists() and sys.platform == "win32":
        print("[-] Error: dist/DiskAtlas/DiskAtlas.exe was not produced.")
        sys.exit(1)


def build_installer(version: str) -> Path:
    if not (DIST_DIR / "DiskAtlas").is_dir():
        print("[-] Error: dist/DiskAtlas/ not found — run without --installer-only first.")
        sys.exit(1)

    iscc = find_iscc()
    run_command(
        [iscc, f"/DMyAppVersion={version}", str(ISS_FILE)],
        "Compiling DiskAtlas Setup with Inno Setup",
    )
    return DIST_DIR / f"DiskAtlas_Setup_{version}.exe"


def main() -> None:
    parser = argparse.ArgumentParser(description="Disk Atlas Windows build pipeline")
    parser.add_argument("--app-only", action="store_true",
                        help="build dist/DiskAtlas/ only, skip the installer")
    parser.add_argument("--installer-only", action="store_true",
                        help="compile the Inno Setup installer from an existing dist/DiskAtlas/")
    args = parser.parse_args()
    if args.app_only and args.installer_only:
        parser.error("--app-only and --installer-only are mutually exclusive")

    version = read_version()

    print("=" * 60)
    print("        Disk Atlas - Windows Automated Build Pipeline")
    print("=" * 60)
    print(f"  Version: {version}")

    DIST_DIR.mkdir(parents=True, exist_ok=True)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    installer_exe = None
    if not args.installer_only:
        build_app()
    if not args.app_only:
        installer_exe = build_installer(version)

    print("\n" + "=" * 60)
    print("  BUILD SUCCESSFUL!")
    print(f"  App folder: {DIST_DIR / 'DiskAtlas'}")
    if installer_exe:
        if installer_exe.exists():
            size_mb = installer_exe.stat().st_size / (1024 * 1024)
            print(f"  Installer:  {installer_exe}")
            print(f"  Size:       {size_mb:.2f} MB")
        else:
            print(f"  Installer expected at: {installer_exe}")
            print("  (Inno reported success but the output file is missing — check its log.)")
    print("  Next step before public release: code-sign the installer (Phase 5.3).")
    print("=" * 60)


if __name__ == "__main__":
    main()
