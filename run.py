#!/usr/bin/env python3
"""
Disk Atlas — Main Application Launcher
Run this script to launch Disk Atlas in a native desktop window:
    python run.py

For development server mode (opens in a browser tab):
    python src/disk_atlas.py --browser
"""
import sys
from pathlib import Path

# Add src/ to module search path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from desktop import main

if __name__ == "__main__":
    main()
