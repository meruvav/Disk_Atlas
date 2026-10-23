#!/usr/bin/env python3
"""
Disk Atlas — Windows Build Automation Script
Builds the standalone application and the setup wizard executable:
    1. Builds dist/DiskAtlas/ via PyInstaller
    2. Packages dist/DiskAtlas/ into dist/DiskAtlas_Payload.zip
    3. Builds dist/DiskAtlas_Setup.exe (Single-file UAC-enabled installer wizard)
"""

import os
import sys
import shutil
import zipfile
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT_DIR / "dist"
BUILD_DIR = ROOT_DIR / "build"
PACKAGING_DIR = ROOT_DIR / "packaging"

def run_command(cmd, desc):
    print(f"\n[+] {desc}...")
    print(f"    Running: {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=str(ROOT_DIR))
    if res.returncode != 0:
        print(f"[-] Error: {desc} failed with exit code {res.returncode}")
        sys.exit(res.returncode)

def main():
    print("=" * 60)
    print("        Disk Atlas — Windows Automated Build Pipeline")
    print("=" * 60)

    # 1. Build main DiskAtlas application
    spec_app = PACKAGING_DIR / "DiskAtlas.spec"
    run_command([sys.executable, "-m", "PyInstaller", "--noconfirm", str(spec_app)], "Building DiskAtlas Engine")

    # 2. Package into payload zip
    app_dist = DIST_DIR / "DiskAtlas"
    payload_zip = DIST_DIR / "DiskAtlas_Payload.zip"
    print(f"\n[+] Compressing payload: {payload_zip.name}...")
    if not app_dist.exists():
        print(f"[-] Error: {app_dist} does not exist.")
        sys.exit(1)

    with zipfile.ZipFile(payload_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, _, files in os.walk(app_dist):
            for file in files:
                full_path = Path(root) / file
                rel_path = full_path.relative_to(app_dist)
                zf.write(full_path, rel_path)

    print(f"    Payload zip created: {payload_zip.stat().st_size / (1024*1024):.2f} MB")

    # 3. Build setup wizard executable
    spec_setup = PACKAGING_DIR / "DiskAtlas_Setup.spec"
    run_command([sys.executable, "-m", "PyInstaller", "--noconfirm", str(spec_setup)], "Building DiskAtlas_Setup.exe")

    installer_exe = DIST_DIR / "DiskAtlas_Setup.exe"
    print("\n" + "=" * 60)
    print("  BUILD SUCCESSFUL!")
    print(f"  Installer: {installer_exe}")
    if installer_exe.exists():
        print(f"  Size: {installer_exe.stat().st_size / (1024*1024):.2f} MB")
    print("=" * 60)

if __name__ == "__main__":
    main()
