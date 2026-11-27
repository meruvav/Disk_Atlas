"""HTTP API tests: auth, scan lifecycle, concurrency, and data endpoints.

Every test boots a real engine on an OS-assigned port via the `server`
fixture (see conftest.py).
"""
import time


# ---------------------------------------------------------------- authentication

class TestAuth:
    def test_api_rejects_missing_token(self, server):
        status, body, _ = server.get("/api/drives", token=None)
        assert status == 401
        assert body["error"] == "Unauthorized"

    def test_api_rejects_wrong_token(self, server):
        status, _, _ = server.get("/api/drives", token="wrong-token")
        assert status == 401

    def test_post_rejects_missing_token(self, server):
        status, _, _ = server.post("/api/scan", {"path": "/"}, token=None)
        assert status == 401

    def test_no_cors_header(self, server):
        status, _, headers = server.get("/api/drives")
        assert status == 200
        assert "Access-Control-Allow-Origin" not in headers

    def test_static_assets_served_without_auth(self, server):
        status, body, _ = server.get("/app.js", token=None)
        assert status == 200
        assert len(body["raw"]) > 1000  # real JS, not an error page


# ---------------------------------------------------------------- index & drives

class TestIndexAndDrives:
    def test_index_has_token_injected(self, server):
        import urllib.request
        with urllib.request.urlopen(server.base + "/", timeout=10) as r:
            html = r.read().decode()
        assert f'window.__DA_TOKEN__ = "{server.token}";' in html

    def test_drives_shape_and_home_first(self, server):
        status, drives, _ = server.get("/api/drives")
        assert status == 200
        assert isinstance(drives, list) and len(drives) >= 1
        assert all(set(d) == {"path", "kind", "label", "total", "free", "used"}
                   for d in drives)
        assert drives[0]["kind"] == "home"
        assert any(d["kind"] == "drive" for d in drives)

    def test_version_endpoint(self, server):
        status, data, _ = server.get("/api/version")
        assert status == 200
        assert data["app"] == "Disk Atlas"
        # From src/version.py — the release pipeline's single source of truth
        from version import __version__
        assert data["version"] == __version__

    def test_version_endpoint_requires_auth(self, server):
        status, _, _ = server.get("/api/version", token=None)
        assert status == 401

    def test_exclusions_endpoint(self, server):
        status, rules, _ = server.get("/api/exclusions")
        assert status == 200
        assert "node_modules" in rules["defaults"]
        assert ".git" in rules["defaults"]
        assert ".trash-" in rules["prefixes"]


# ---------------------------------------------------------------- quick scan

class TestQuickScanApi:
    def test_quick_scan_post(self, server, sample_tree):
        status, body, _ = server.post("/api/quick-scan",
                                      {"path": str(sample_tree), "auto_deep": False})
        assert status == 200
        names = {c["name"] for c in body["children"]}
        assert names == {"a.txt", "sub", "empty"}
        assert body["quick_preview"] is True

    def test_quick_scan_starts_deep_scan_by_default(self, server, sample_tree):
        status, body, _ = server.post("/api/quick-scan",
                                      {"path": str(sample_tree)})
        assert status == 200
        assert body["deep_scan"] == "started"
        final = server.wait_for_state(("done",))
        assert final["state"] == "done"

    def test_quick_scan_invalid_path(self, server):
        status, body, _ = server.post("/api/quick-scan",
                                      {"path": "/definitely/not/here"})
        assert status == 400


# ---------------------------------------------------------------- deep scan lifecycle

class TestScanLifecycle:
    def test_full_scan_flow(self, server, sample_tree):
        status, body, _ = server.post("/api/scan", {"path": str(sample_tree)})
        assert status == 200 and body["status"] == "started"

        final = server.wait_for_state(("done", "error"))
        assert final["state"] == "done"
        assert final["scanned_files"] == 3
        assert final["total_bytes"] == 450
        assert final["excluded"] == 2

        status, tree, _ = server.get("/api/data")
        assert status == 200
        assert tree["size"] == 450
        names = {c["name"] for c in tree["children"]}
        assert names == {"a.txt", "sub", "empty"}

    def test_scan_missing_path_param(self, server):
        status, body, _ = server.post("/api/scan", {})
        assert status == 400

    def test_scan_nonexistent_path(self, server):
        status, body, _ = server.post("/api/scan", {"path": "/no/such/place"})
        assert status == 400
        assert "does not exist" in body["error"]

    def test_scan_409_then_force_restart(self, server, big_tree, sample_tree):
        status, _, _ = server.post("/api/scan", {"path": str(big_tree)})
        assert status == 200

        # A concurrent scan must be refused with 409; retry briefly because
        # the first scan can complete unusually fast on small CI disks.
        body = None
        for _ in range(50):
            status, body, _ = server.post("/api/scan", {"path": str(sample_tree)})
            if status == 409:
                break
            time.sleep(0.02)
        assert status == 409, "never observed 409 for a concurrent scan request"
        assert body["state"] == "scanning"
        assert "force" in body["hint"]

        status, body, _ = server.post("/api/scan",
                                      {"path": str(sample_tree), "force": True})
        assert status == 200 and body["status"] == "started"

        final = server.wait_for_state(("done", "error"), timeout=60)
        assert final["state"] == "done"

        # The surviving scan must be the forced one, not the superseded big scan
        status, tree, _ = server.get("/api/data")
        assert tree["name"] == sample_tree.name

    def test_cancel(self, server, big_tree):
        server.post("/api/scan", {"path": str(big_tree)})
        time.sleep(0.05)  # let it get in flight
        status, body, _ = server.post("/api/cancel")
        assert status == 200 and body["status"] == "cancelled"
        final = server.wait_for_state(("idle", "done"), timeout=30)
        assert final["state"] in ("idle", "done")

    def test_custom_exclude_via_api(self, server, sample_tree):
        status, _, _ = server.post("/api/scan",
                                   {"path": str(sample_tree), "exclude": ["sub"]})
        assert status == 200
        final = server.wait_for_state(("done",))
        assert final["excluded"] == 3  # node_modules + .git + sub
        status, tree, _ = server.get("/api/data")
        names = {c["name"] for c in tree["children"]}
        assert names == {"a.txt", "empty"}

    def test_data_404_before_any_scan(self, server):
        import disk_atlas
        disk_atlas.scanner_instance.last_result = None
        status, _, _ = server.get("/api/data")
        assert status == 404


# ---------------------------------------------------------------- export

class TestExport:
    def test_export_writes_standalone_report(self, server, sample_tree):
        server.post("/api/scan", {"path": str(sample_tree)})
        server.wait_for_state(("done",))

        status, body, _ = server.post("/api/export")
        assert status == 200
        report = sample_tree / "DiskAtlas_Interactive_Report.html"
        assert body["path"] == str(report)
        html = report.read_text(encoding="utf-8")
        assert "EMBEDDED_DISK_DATA" in html
        assert sample_tree.name in html
        report.unlink()
