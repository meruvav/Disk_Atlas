#!/bin/bash
set -e
echo "Building macOS .app bundle..."
pyinstaller --windowed --name "DiskInsightPro" disk_insight.py

echo "Creating macOS Package with destination selection..."
chmod +x scripts/postinstall
pkgbuild --root dist/DiskInsightPro.app \
         --install-location /Applications/DiskInsightPro.app \
         --scripts scripts \
         --identifier com.meruva.diskinsight \
         --version 1.0 \
         DiskInsightPro_macOS_Setup.pkg

echo "Built DiskInsightPro_macOS_Setup.pkg successfully!"
