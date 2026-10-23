#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=========================================="
echo "       Disk Atlas Linux Installer         "
echo "=========================================="

DEFAULT_DIR="$HOME/.local/share/DiskAtlas"
read -p "Enter installation directory [$DEFAULT_DIR]: " INSTALL_DIR
INSTALL_DIR="${INSTALL_DIR:-$DEFAULT_DIR}"

mkdir -p "$INSTALL_DIR"
if [ -d "$ROOT_DIR/dist/DiskAtlas" ]; then
    cp -r "$ROOT_DIR/dist/DiskAtlas/"* "$INSTALL_DIR/"
else
    echo "Warning: dist/DiskAtlas not found, copying from current directory."
    cp -r dist/DiskAtlas/* "$INSTALL_DIR/"
fi
chmod +x "$INSTALL_DIR/DiskAtlas"

# 1. Register in system application menu
DESKTOP_DIR="$HOME/.local/share/applications"
mkdir -p "$DESKTOP_DIR"
cat <<EOF > "$DESKTOP_DIR/diskatlas.desktop"
[Desktop Entry]
Name=Disk Atlas
Comment=Interactive 3D Disk Space Visualizer & Analyzer
Exec=$INSTALL_DIR/DiskAtlas
Type=Application
Terminal=false
Categories=Utility;System;
EOF

# 2. Create Desktop Shortcut
USER_DESKTOP=$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")
if [ -d "$USER_DESKTOP" ]; then
    cp "$DESKTOP_DIR/diskatlas.desktop" "$USER_DESKTOP/"
    chmod +x "$USER_DESKTOP/diskatlas.desktop"
    gio set "$USER_DESKTOP/diskatlas.desktop" metadata::trusted true 2>/dev/null || true
fi

echo "=========================================="
echo "Installation complete!"
echo "Installed to: $INSTALL_DIR"
echo "Desktop shortcut created & registered in app menu."
echo "=========================================="
