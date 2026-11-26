#!/usr/bin/env python3
"""
Disk Atlas — Native Desktop Shell

Wraps the Disk Atlas engine in a native pywebview window:
  - Binds an OS-assigned free port (no fixed-port collisions)
  - Secures the local API with a per-launch token (handled by disk_atlas)
  - Shuts the engine down when the window closes
  - Enforces a single running instance via a lock file

Falls back to browser mode if pywebview is not installed.
"""

import os
import sys
import threading
from pathlib import Path

# Support running directly or as a module / frozen bundle
if getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(sys._MEIPASS)))
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from disk_atlas import create_server, run_disk_atlas

APP_NAME = "Disk Atlas"


def user_data_dir():
    """Per-user writable directory for Disk Atlas state (lock file, logs, cache)."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    d = base / "DiskAtlas"
    d.mkdir(parents=True, exist_ok=True)
    return d


def acquire_single_instance_lock():
    """Hold an OS-level lock for the lifetime of this process.

    Returns the open file handle on success (keep it alive), or None if
    another Disk Atlas instance already holds the lock.
    """
    lock_path = user_data_dir() / "disk_atlas.lock"
    try:
        fh = open(lock_path, "a+b")
    except OSError:
        return None

    if sys.platform == "win32":
        import msvcrt
        try:
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            fh.close()
            return None
    else:
        import fcntl
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fh.close()
            return None
    return fh


def notify_already_running():
    msg = f"{APP_NAME} is already running. Check your taskbar or system tray."
    print(msg)
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        messagebox.showinfo(APP_NAME, msg)
        root.destroy()
    except Exception:
        pass


def main():
    # Single-instance guard
    lock_handle = acquire_single_instance_lock()
    if lock_handle is None:
        notify_already_running()
        sys.exit(0)

    # Start the engine on an OS-assigned free port
    server, port = create_server(port=0)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    url = f"http://127.0.0.1:{port}"

    try:
        import webview
    except ImportError:
        # pywebview unavailable (e.g. dev machine without deps): browser mode
        print(f"[Disk Atlas] pywebview not installed; falling back to browser at {url}")
        server.shutdown()
        server.server_close()
        run_disk_atlas(port=0, open_browser=True)
        return

    window = webview.create_window(
        APP_NAME,
        url,
        width=1280,
        height=860,
        min_size=(960, 640),
    )

    def on_closed():
        server.shutdown()
        server.server_close()

    window.events.closed += on_closed

    # Blocks until the window closes
    webview.start()

    # Guarantee process exit even if background threads linger
    os._exit(0)


if __name__ == "__main__":
    main()
