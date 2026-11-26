"""Shared fixtures for the Disk Atlas test suite.

Run from the repo root:
    python -m pytest tests/ -v
"""
import json
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

# Make src/ importable without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import disk_atlas  # noqa: E402


@pytest.fixture()
def sample_tree(tmp_path):
    """A small tree with known sizes.

    Layout:
        a.txt                 100 B
        sub/b.bin             300 B
        sub/deep/c.log         50 B
        node_modules/junk.js 5000 B   (excluded by default rules)
        .git/HEAD              200 B  (excluded by default rules)
        empty/                          (empty directory)

    Expected scanned total: 450 B, excluded entries: 2.
    """
    (tmp_path / "a.txt").write_bytes(b"x" * 100)
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.bin").write_bytes(b"x" * 300)
    (tmp_path / "sub" / "deep").mkdir()
    (tmp_path / "sub" / "deep" / "c.log").write_bytes(b"x" * 50)
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "junk.js").write_bytes(b"x" * 5000)
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_bytes(b"x" * 200)
    (tmp_path / "empty").mkdir()
    return tmp_path


@pytest.fixture(scope="module")
def big_tree(tmp_path_factory):
    """A tree large enough to stay mid-scan while a test acts on it."""
    root = tmp_path_factory.mktemp("big_tree")
    for d in range(60):
        sub = root / f"dir_{d:03d}"
        sub.mkdir()
        for f in range(50):
            (sub / f"file_{f:03d}.bin").write_bytes(b"z" * 64)
    return root  # 3000 files in 60 dirs


class ApiClient:
    """Minimal authenticated HTTP client for the test server."""

    def __init__(self, base_url, token):
        self.base = base_url
        self.token = token

    def _request(self, method, path, payload=None, token="__default__"):
        headers = {"Content-Type": "application/json"}
        if token == "__default__":
            token = self.token
        if token is not None:
            headers["X-Disk-Atlas-Token"] = token
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(self.base + path, data=data,
                                     headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                body = r.read()
                try:
                    parsed = json.loads(body) if body else {}
                except (ValueError, UnicodeDecodeError):
                    parsed = {"raw": body.decode("utf-8", "replace")}
                return r.status, parsed, dict(r.headers)
        except urllib.error.HTTPError as e:
            body = e.read()
            try:
                parsed = json.loads(body)
            except (ValueError, UnicodeDecodeError):
                parsed = {"raw": body.decode("utf-8", "replace")}
            return e.code, parsed, dict(e.headers)

    def get(self, path, **kw):
        return self._request("GET", path, **kw)

    def post(self, path, payload=None, **kw):
        return self._request("POST", path, payload=payload or {}, **kw)

    def wait_for_state(self, target_states=("done", "error"), timeout=30):
        import time
        deadline = time.time() + timeout
        while time.time() < deadline:
            _, status, _ = self.get("/api/status")
            if status["state"] in target_states:
                return status
            time.sleep(0.05)
        raise TimeoutError(f"scanner never reached {target_states}")


@pytest.fixture()
def server():
    """A live Disk Atlas engine on an OS-assigned port, torn down per test."""
    disk_atlas.scanner_instance.cancel()
    srv, port = disk_atlas.create_server(0)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    client = ApiClient(f"http://127.0.0.1:{port}", srv.auth_token)
    yield client
    disk_atlas.scanner_instance.cancel()
    srv.shutdown()
    srv.server_close()
