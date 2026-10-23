#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Building macOS .app bundle for Disk Atlas..."
pyinstaller --windowed --name "DiskAtlas" \
            --add-data "$ROOT_DIR/src/web:web" \
            --distpath "$ROOT_DIR/dist" \
            --workpath "$ROOT_DIR/build" \
            "$ROOT_DIR/src/disk_atlas.py"

echo "Creating macOS Package with destination selection..."
chmod +x "$SCRIPT_DIR/scripts/postinstall"
pkgbuild --root "$ROOT_DIR/dist/DiskAtlas.app" \
         --install-location /Applications/DiskAtlas.app \
         --scripts "$SCRIPT_DIR/scripts" \
         --identifier com.meruva.diskatlas \
         --version 2.0 \
         "$ROOT_DIR/dist/DiskAtlas_macOS_Setup.pkg"

echo "Built DiskAtlas_macOS_Setup.pkg successfully!"
