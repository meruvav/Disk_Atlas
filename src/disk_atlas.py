#!/usr/bin/env python3
"""
Disk Atlas — Desktop Engine & Scanner
Merges 3D Storage City, Folder Layers, and Storage Terrain visualizations into a unified application.
"""

import hmac
import os
import secrets
import sys
import json
import time
import shutil
import ctypes
import threading
import subprocess
import webbrowser
import urllib.parse
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
import socketserver

# Determine base directory (handles PyInstaller bundled mode)
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).resolve().parent

if (BASE_DIR / "web").exists():
    WEB_DIR = BASE_DIR / "web"
elif (BASE_DIR / "src" / "web").exists():
    WEB_DIR = BASE_DIR / "src" / "web"
elif (BASE_DIR.parent / "src" / "web").exists():
    WEB_DIR = BASE_DIR.parent / "src" / "web"
elif (BASE_DIR / "_internal" / "web").exists():
    WEB_DIR = BASE_DIR / "_internal" / "web"
elif (Path(sys.executable).parent / "_internal" / "web").exists():
    WEB_DIR = Path(sys.executable).parent / "_internal" / "web"
else:
    WEB_DIR = BASE_DIR / "web"

# --- DRIVE DETECTION UTILITIES ---
# Filesystems that never represent user storage devices.
_PSEUDO_FSTYPES = {
    "proc", "sysfs", "devtmpfs", "devpts", "tmpfs", "cgroup", "cgroup2",
    "overlay", "squashfs", "aufs", "configfs", "debugfs", "tracefs",
    "securityfs", "pstore", "bpf", "efivarfs", "mqueue", "hugetlbfs",
    "rpc_pipefs", "fusectl", "binfmt_misc", "autofs", "nsfs", "ramfs",
    "selinuxfs", "smackfs", "fd", "ptmx",
}
# Network mounts can hang on stat() when the remote end is unreachable,
# so they are never auto-listed (users can still type their path manually).
_NETWORK_FSTYPES = {
    "nfs", "nfs4", "cifs", "smbfs", "smb3", "sshfs", "fuse.sshfs",
    "davfs", "ceph", "glusterfs", "fuse.davfs2",
}


def _unescape_mount_field(value):
    """Decode octal escapes used in /proc/self/mounts (space, tab, newline, backslash)."""
    return (value
            .replace("\\040", " ")
            .replace("\\011", "\t")
            .replace("\\012", "\n")
            .replace("\\134", "\\"))


def _parse_proc_mounts(text):
    """Parse /proc/self/mounts content into [(device, mountpoint, fstype), ...]
    containing only real local block-device mounts."""
    mounts = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        device, mnt, fstype = parts[0], parts[1], parts[2]
        if fstype in _PSEUDO_FSTYPES or fstype in _NETWORK_FSTYPES:
            continue
        if not device.startswith("/dev/"):
            continue
        if device.startswith("/dev/loop"):  # snap/loop images
            continue
        mounts.append((device, _unescape_mount_field(mnt), fstype))
    return mounts


def _mount_label(path):
    """Human-friendly name for a mount point."""
    if path == "/":
        return "System volume"
    name = os.path.basename(path.rstrip(os.sep))
    return name or path


def _home_entry():
    """The user's home folder, offered as the default first scan target."""
    home = str(Path.home())
    try:
        usage = shutil.disk_usage(home)
        total, free, used = usage.total, usage.free, usage.used
    except (PermissionError, OSError):
        total = free = used = 0
    return {
        "path": home,
        "kind": "home",
        "label": "Home folder",
        "total": total,
        "free": free,
        "used": used,
    }


def list_system_drives():
    """List scan targets with capacity info.

    Returns [{path, kind, label, total, free, used}, ...] where kind is
    "home" for the user's home folder (always the first entry, intended
    as the friendly default scan target) or "drive" for storage devices.
    label may be None (Windows), in which case the UI shows the path.
    """
    drives = []
    seen_devices = set()
    seen_paths = set()

    def add_mount(path, device=None):
        if device and device in seen_devices:
            return
        try:
            key = os.path.realpath(path)
        except OSError:
            key = path
        if key in seen_paths:
            # Path already listed (e.g. "/" added explicitly) — still record
            # the device so other mountpoints of the same disk are deduped.
            if device:
                seen_devices.add(device)
            return
        try:
            usage = shutil.disk_usage(path)
        except (PermissionError, OSError):
            return
        seen_paths.add(key)
        if device:
            seen_devices.add(device)
        drives.append({
            "path": path,
            "kind": "drive",
            "label": _mount_label(path) if sys.platform != 'win32' else None,
            "total": usage.total,
            "free": usage.free,
            "used": usage.used,
        })

    if sys.platform == 'win32':
        if hasattr(os, 'listdrives'):
            drive_letters = os.listdrives()
        else:
            bitmask = ctypes.windll.kernel32.GetLogicalDrives()
            drive_letters = [f"{chr(65 + i)}:\\" for i in range(26) if bitmask & (1 << i)]

        for d in drive_letters:
            entry = {"path": d, "kind": "drive", "label": None}
            try:
                usage = shutil.disk_usage(d)
                entry.update({"total": usage.total, "free": usage.free, "used": usage.used})
            except (PermissionError, OSError):
                entry.update({"total": 0, "free": 0, "used": 0})
            drives.append(entry)
        return [_home_entry()] + drives

    # --- POSIX: always include the root filesystem ---
    add_mount("/")

    if sys.platform == 'darwin':
        # macOS: every mounted volume appears under /Volumes
        try:
            for name in sorted(os.listdir("/Volumes")):
                p = os.path.join("/Volumes", name)
                if os.path.isdir(p) and os.path.ismount(p):
                    add_mount(p)
        except OSError:
            pass
        return [_home_entry()] + drives

    # --- Linux/other POSIX ---
    mounts = None
    try:
        with open("/proc/self/mounts", "r", encoding="utf-8", errors="replace") as f:
            mounts = _parse_proc_mounts(f.read())
    except OSError:
        mounts = None

    if mounts is not None:
        for device, mnt, _fstype in mounts:
            add_mount(mnt, device=device)
    else:
        # Fallback when /proc is unavailable (BSD, minimal containers):
        # scan the conventional hotplug mount directories.
        candidates = ["/media", "/mnt", "/run/media"]
        user = os.environ.get("USER", "")
        if user:
            candidates.insert(0, os.path.join("/run/media", user))
            candidates.insert(0, os.path.join("/media", user))
        for base in candidates:
            try:
                for name in sorted(os.listdir(base)):
                    p = os.path.join(base, name)
                    if os.path.isdir(p) and os.path.ismount(p):
                        add_mount(p)
            except OSError:
                continue

    return [_home_entry()] + drives

# --- HIGH-PERFORMANCE ITERATIVE SCANNER ---
class DiskScanner:
    def __init__(self):
        self.state = "idle" # "idle", "scanning", "done", "error"
        self.cancel_event = threading.Event()
        self.current_path = ""
        self.scanned_files = 0
        self.scanned_folders = 0
        self.total_bytes = 0
        self.last_result = None
        self.error_message = ""
        self._last_progress_time = 0

    def cancel(self):
        self.cancel_event.set()
        self.state = "idle"

    def quick_scan(self, target_path):
        """Ultra-fast non-blocking scan of immediate folder contents (Level 1) in < 15ms."""
        target_path = os.path.abspath(target_path)
        if not os.path.isdir(target_path):
            raise FileNotFoundError(f"Path is not a valid directory: {target_path}")

        children = []
        total_size = 0
        file_count = 0
        folder_count = 0

        try:
            with os.scandir(target_path) as it:
                for entry in it:
                    try:
                        if entry.is_symlink():
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            folder_count += 1
                            children.append({
                                "name": entry.name,
                                "path": entry.path,
                                "type": "folder",
                                "size": 0,
                                "children": []
                            })
                        else:
                            file_count += 1
                            st = entry.stat(follow_symlinks=False)
                            f_size = st.st_size
                            total_size += f_size
                            ext = os.path.splitext(entry.name)[1].lower() or "other"
                            children.append({
                                "name": entry.name,
                                "path": entry.path,
                                "type": "file",
                                "size": f_size,
                                "ext": ext
                            })
                    except (PermissionError, FileNotFoundError, OSError):
                        continue
        except (PermissionError, FileNotFoundError, OSError):
            pass

        # Sort folders first, then files by size descending
        children.sort(key=lambda x: (0 if x["type"] == "folder" else 1, -x["size"]))

        result = {
            "name": os.path.basename(target_path) or target_path,
            "path": target_path,
            "type": "folder",
            "size": total_size,
            "children": children,
            "quick_preview": True,
            "file_count": file_count,
            "folder_count": folder_count
        }
        self.last_result = result
        return result

    def scan_path(self, target_path):
        self.state = "scanning"
        self.cancel_event.clear()
        self.scanned_files = 0
        self.scanned_folders = 0
        self.total_bytes = 0
        self.current_path = target_path
        self.error_message = ""

        try:
            tree = self._iterative_scan(target_path)
            if self.cancel_event.is_set():
                self.state = "idle"
            else:
                self.last_result = tree
                self.state = "done"
        except Exception as e:
            self.error_message = str(e)
            self.state = "error"

    def _iterative_scan(self, root_path):
        root_path = os.path.abspath(root_path)
        if not os.path.exists(root_path):
            raise FileNotFoundError(f"Path does not exist: {root_path}")

        # Node map: path -> dict
        nodes = {}
        # Directories to explore: stack for depth-first
        stack = [root_path]

        root_node = {
            "name": os.path.basename(root_path) or root_path,
            "path": root_path,
            "type": "folder",
            "size": 0,
            "children": []
        }
        nodes[root_path] = root_node

        # Post-order list to aggregate folder sizes from bottom up
        post_order_dirs = []
        items_processed = 0

        while stack:
            if self.cancel_event.is_set():
                return root_node

            curr = stack.pop()
            post_order_dirs.append(curr)

            items_processed += 1
            if items_processed & 127 == 0:
                now = time.time()
                if now - self._last_progress_time > 0.08:
                    self._last_progress_time = now
                    self.current_path = curr

            try:
                with os.scandir(curr) as it:
                    for entry in it:
                        items_processed += 1
                        if items_processed & 255 == 0 and self.cancel_event.is_set():
                            return root_node

                        try:
                            if entry.is_symlink():
                                continue

                            if entry.is_dir(follow_symlinks=False):
                                self.scanned_folders += 1
                                child_dir = {
                                    "name": entry.name,
                                    "path": entry.path,
                                    "type": "folder",
                                    "size": 0,
                                    "children": []
                                }
                                nodes[entry.path] = child_dir
                                nodes[curr]["children"].append(child_dir)
                                stack.append(entry.path)
                            else:
                                self.scanned_files += 1
                                st = entry.stat(follow_symlinks=False)
                                f_size = st.st_size
                                self.total_bytes += f_size
                                ext = os.path.splitext(entry.name)[1].lower() or "other"
                                file_node = {
                                    "name": entry.name,
                                    "path": entry.path,
                                    "type": "file",
                                    "size": f_size,
                                    "ext": ext
                                }
                                nodes[curr]["children"].append(file_node)
                        except (PermissionError, FileNotFoundError, OSError):
                            continue
            except (PermissionError, FileNotFoundError, OSError):
                continue

        # Aggregate folder sizes bottom-up
        for dir_path in reversed(post_order_dirs):
            d_node = nodes[dir_path]
            d_size = 0
            for c in d_node["children"]:
                d_size += c["size"]
            d_node["size"] = d_size
            d_node["children"].sort(key=lambda x: (0 if x["type"] == "folder" else 1, -x["size"]))

        return root_node

scanner_instance = DiskScanner()

# --- HTTP HANDLER & REST API ---
class DiskAtlasRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    # --- Per-launch token auth ---
    # Every /api/* request must carry the launch token in X-Disk-Atlas-Token.
    # The token is injected into index.html at serve time, so only pages served
    # by this same server instance know it. Combined with no CORS headers,
    # cross-origin web pages cannot read the token or call the API.
    def _authorized(self):
        expected = getattr(self.server, "auth_token", "")
        provided = self.headers.get("X-Disk-Atlas-Token", "")
        return bool(expected) and hmac.compare_digest(provided, expected)

    def _reject_unauthorized(self):
        self._send_json({"error": "Unauthorized"}, status=401)

    def _serve_index(self):
        index_file = WEB_DIR / "index.html"
        try:
            html = index_file.read_text(encoding="utf-8")
        except OSError:
            self.send_error(404, "index.html not found")
            return
        token = getattr(self.server, "auth_token", "")
        html = html.replace(
            'window.__DA_TOKEN__ = "";',
            f'window.__DA_TOKEN__ = "{token}";',
            1,
        )
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path.startswith("/api/") and not self._authorized():
            self._reject_unauthorized()
            return
        if path in ("/", "/index.html"):
            self._serve_index()
            return
        if path == "/api/drives":
            drives = list_system_drives()
            self._send_json(drives)
        elif self.path == "/api/status":
            self._send_json({
                "state": scanner_instance.state,
                "current_path": scanner_instance.current_path,
                "scanned_files": scanner_instance.scanned_files,
                "scanned_folders": scanner_instance.scanned_folders,
                "total_bytes": scanner_instance.total_bytes,
                "error": scanner_instance.error_message
            })
        elif self.path.startswith("/api/quick-scan"):
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            target = params.get("path", [""])[0]
            if target and os.path.exists(target):
                try:
                    result = scanner_instance.quick_scan(target)
                    self._send_json(result)
                except Exception as e:
                    self._send_json({"error": str(e)}, status=500)
            else:
                self._send_json({"error": "Invalid or missing path parameter"}, status=400)
        elif self.path == "/api/data":
            if scanner_instance.last_result:
                self._send_json(scanner_instance.last_result)
            else:
                self._send_json({"error": "No scan data available"}, status=404)
        else:
            super().do_GET()

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path.startswith("/api/") and not self._authorized():
            self._reject_unauthorized()
            return
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b"{}"
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            payload = {}

        if self.path == "/api/quick-scan":
            target = payload.get("path")
            if target and os.path.exists(target):
                try:
                    result = scanner_instance.quick_scan(target)
                    if payload.get("auto_deep", True):
                        threading.Thread(target=scanner_instance.scan_path, args=(target,), daemon=True).start()
                    self._send_json(result)
                except Exception as e:
                    self._send_json({"error": str(e)}, status=500)
            else:
                self._send_json({"error": "Invalid or missing path parameter"}, status=400)

        elif self.path == "/api/scan":
            target = payload.get("path")
            if target:
                threading.Thread(target=scanner_instance.scan_path, args=(target,), daemon=True).start()
                self._send_json({"status": "started", "path": target})
            else:
                self._send_json({"error": "Missing path parameter"}, status=400)

        elif self.path == "/api/cancel":
            scanner_instance.cancel()
            self._send_json({"status": "cancelled"})

        elif self.path == "/api/browse":
            browse_data = self._open_native_folder_picker()
            self._send_json(browse_data)

        elif self.path == "/api/open-folder":
            p = payload.get("path")
            if p and os.path.exists(p):
                if sys.platform == 'win32':
                    os.startfile(p)
                elif sys.platform == 'darwin':
                    subprocess.Popen(['open', p])
                else:
                    subprocess.Popen(['xdg-open', p])
                self._send_json({"status": "opened"})
            else:
                self._send_json({"error": "Invalid path"}, status=400)

        elif self.path == "/api/export":
            export_path = self._export_standalone_html()
            self._send_json({"status": "exported", "path": export_path})
        else:
            self._send_json({"error": "Not Found"}, status=404)

    def _open_native_folder_picker(self):
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            selected = filedialog.askdirectory(title="Disk Atlas — Select Folder to Scan")
            root.destroy()
            if selected and os.path.exists(selected):
                try:
                    preview = scanner_instance.quick_scan(selected)
                    return {"path": selected, "preview": preview}
                except Exception:
                    return {"path": selected}
            return {"path": selected or ""}
        except Exception:
            return {"path": ""}

    def _export_standalone_html(self):
        data = scanner_instance.last_result or {"name": "No Data", "size": 0, "children": []}
        
        # Read files to inline
        index_html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
        style_css = (WEB_DIR / "style.css").read_text(encoding="utf-8")
        three_js = (WEB_DIR / "three.min.js").read_text(encoding="utf-8")
        orbit_js = (WEB_DIR / "OrbitControls.js").read_text(encoding="utf-8")
        vis_js = (WEB_DIR / "visualizer.js").read_text(encoding="utf-8")
        app_js = (WEB_DIR / "app.js").read_text(encoding="utf-8")

        # Safely escape script closing tag in JSON data
        safe_json_data = json.dumps(data).replace("</", "<\\/")

        # Construct single self-contained HTML
        bundle = index_html.replace(
            '<link rel="stylesheet" href="style.css">',
            f'<style>\n{style_css}\n</style>'
        )
        
        scripts_bundle = f"""
        <script>
        {three_js}
        </script>
        <script>
        {orbit_js}
        </script>
        <script>
        window.EMBEDDED_DISK_DATA = {safe_json_data};
        </script>
        <script>
        {vis_js}
        </script>
        <script>
        {app_js}
        </script>
        """

        bundle = bundle.replace('<script src="three.min.js"></script>', '')
        bundle = bundle.replace('<script src="OrbitControls.js"></script>', '')
        bundle = bundle.replace('<script src="visualizer.js"></script>', '')
        bundle = bundle.replace('<script src="app.js"></script>', scripts_bundle)

        candidates = []
        if "path" in data and os.path.isdir(data["path"]):
            candidates.append(Path(data["path"]))
        candidates.append(BASE_DIR)
        candidates.append(Path.home() / "Desktop")
        candidates.append(Path.home())

        export_file = None
        for cand in candidates:
            try:
                cand.mkdir(parents=True, exist_ok=True)
                test_file = cand / "DiskAtlas_Interactive_Report.html"
                test_file.write_text(bundle, encoding="utf-8")
                export_file = test_file
                break
            except (PermissionError, OSError):
                continue

        if not export_file:
            raise PermissionError("Could not write export file to any candidate directory.")
        return str(export_file)

    def _send_json(self, data, status=200):
        # Note: intentionally no Access-Control-Allow-Origin header. The app is
        # same-origin, and omitting CORS prevents any other website open in the
        # user's browser from reading API responses.
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # Quiet server logs
        pass

# --- SERVER FACTORY & RUNNERS ---
def create_server(port=0):
    """Create the Disk Atlas HTTP server.

    port=0 asks the OS for a free port, which avoids collisions with other
    apps and makes the fixed port unpredictable to local web pages.
    Returns (server, actual_port). The per-launch API token is available as
    server.auth_token.
    """
    class ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
        daemon_threads = True

    server = ThreadedHTTPServer(("127.0.0.1", port), DiskAtlasRequestHandler)
    server.auth_token = secrets.token_urlsafe(32)
    return server, server.server_address[1]


def run_disk_atlas(port=0, open_browser=True):
    """Development/CLI runner: start the engine and (optionally) open a browser.

    The packaged desktop app uses src/desktop.py instead, which embeds the UI
    in a native pywebview window and manages the server lifecycle itself.
    """
    server, actual_port = create_server(port)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    url = f"http://127.0.0.1:{actual_port}"
    print(f"==================================================")
    print(f" Disk Atlas is running at: {url}")
    print(f" Close this terminal window to stop the engine.")
    print(f"==================================================")

    if open_browser:
        webbrowser.open(url)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping Disk Atlas...")
        server.shutdown()

if __name__ == "__main__":
    port = 0
    open_browser = "--browser" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--browser"]
    if args and args[0].isdigit():
        port = int(args[0])
    run_disk_atlas(port, open_browser=open_browser)
