#!/usr/bin/env python3
"""
Disk Atlas — Main Application Launcher
Run this script to launch Disk Atlas:
    python run.py
"""
import sys
from pathlib import Path

# Add src/ to module search path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from disk_atlas import run_disk_atlas

if __name__ == "__main__":
    run_disk_atlas()
