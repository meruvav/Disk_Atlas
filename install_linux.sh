#!/usr/bin/env bash
set -e

echo "=========================================="
echo "    DiskInsight Pro Linux Installer       "
echo "=========================================="

DEFAULT_DIR="$HOME/.local/share/DiskInsightPro"
read -p "Enter installation directory [$DEFAULT_DIR]: " INSTALL_DIR
INSTALL_DIR="${INSTALL_DIR:-$DEFAULT_DIR}"

mkdir -p "$INSTALL_DIR"
cp -r dist/DiskInsightPro/* "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/DiskInsightPro"

# 1. Register in system application menu
DESKTOP_DIR="$HOME/.local/share/applications"
mkdir -p "$DESKTOP_DIR"
cat <<EOF > "$DESKTOP_DIR/diskinsight.desktop"
[Desktop Entry]
Name=DiskInsight Pro
Comment=Interactive Disk Space Visualizer
Exec=$INSTALL_DIR/DiskInsightPro
Type=Application
Terminal=false
Categories=Utility;System;
EOF

# 2. Create Desktop Shortcut
USER_DESKTOP=$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")
if [ -d "$USER_DESKTOP" ]; then
    cp "$DESKTOP_DIR/diskinsight.desktop" "$USER_DESKTOP/"
    chmod +x "$USER_DESKTOP/diskinsight.desktop"
    gio set "$USER_DESKTOP/diskinsight.desktop" metadata::trusted true 2>/dev/null || true
fi

echo "=========================================="
echo "Installation complete!"
echo "Installed to: $INSTALL_DIR"
echo "Desktop shortcut created & registered in app menu."
echo "=========================================="
