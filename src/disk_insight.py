#!/usr/bin/env python3
"""
DiskInsight Pro -> Disk Atlas Compatibility Wrapper
Runs the modern Disk Atlas 3D visualization engine.
"""
import sys
from pathlib import Path

# Support running directly or as a module
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from disk_atlas import run_disk_atlas
except ImportError:
    from src.disk_atlas import run_disk_atlas

if __name__ == "__main__":
    run_disk_atlas()
