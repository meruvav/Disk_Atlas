"""Tests for scan-history persistence (Phase 6.2).

Covers the pure persistence helpers with an isolated user-data dir plus
the live HTTP endpoints against a real engine.
"""

import json
import threading
import time

import pytest

import disk_atlas


@pytest.fixture()
def isolated_history(tmp_path, monkeypatch):
    """Point user_data_dir() at a temp dir so tests never touch real state."""
    monkeypatch.setattr(disk_atlas, "user_data_dir", lambda: tmp_path)
    return tmp_path


def _tiny_tree():
    return {
        "name": "demo",
        "path": "/tmp/demo",
        "type": "folder",
        "size": 1500,
        "children": [
            {"name": "big.bin", "path": "/tmp/demo/big.bin", "type": "file", "size": 1000, "ext": ".bin"},
            {"name": "sub", "path": "/tmp/demo/sub", "type": "folder", "size": 500,
             "children": [
                 {"name": "small.txt", "path": "/tmp/demo/sub/small.txt", "type": "file", "size": 500, "ext": ".txt"},
             ]},
        ],
    }


class TestPersistenceHelpers:
    def test_save_and_roundtrip(self, isolated_history):
        hid = disk_atlas.save_scan_history("/tmp/demo", _tiny_tree(), 0.5, 3)
        assert hid
        snapshot = disk_atlas.load_scan_history(hid)
        assert snapshot["root_path"] == "/tmp/demo"
        assert snapshot["file_count"] == 2
        assert snapshot["folder_count"] == 2
        assert snapshot["total_bytes"] == 1500
        assert snapshot["excluded"] == 3
        assert snapshot["tree"]["children"][0]["name"] == "big.bin"

    def test_list_returns_metadata_newest_first(self, isolated_history):
        h1 = disk_atlas.save_scan_history("/tmp/a", _tiny_tree(), 0.1, 0)
        time.sleep(1.1)  # ids are second-resolution timestamps
        h2 = disk_atlas.save_scan_history("/tmp/b", _tiny_tree(), 0.2, 1)
        items = disk_atlas.list_scan_history()
        assert [i["id"] for i in items] == [h2, h1]
        assert "tree" not in items[0]

    def test_atomic_write_leaves_no_tmp(self, isolated_history):
        disk_atlas.save_scan_history("/tmp/demo", _tiny_tree(), 0.1, 0)
        leftovers = list(isolated_history.rglob("*.tmp"))
        assert leftovers == []

    def test_load_rejects_bad_ids(self, isolated_history):
        disk_atlas.save_scan_history("/tmp/demo", _tiny_tree(), 0.1, 0)
        assert disk_atlas.load_scan_history("../etc/passwd") is None
        assert disk_atlas.load_scan_history("") is None
        assert disk_atlas.load_scan_history("nope") is None

    def test_delete(self, isolated_history):
        hid = disk_atlas.save_scan_history("/tmp/demo", _tiny_tree(), 0.1, 0)
        assert disk_atlas.delete_scan_history(hid) is True
        assert disk_atlas.load_scan_history(hid) is None
        assert disk_atlas.delete_scan_history(hid) is False

    def test_corrupt_files_are_skipped(self, isolated_history):
        hid = disk_atlas.save_scan_history("/tmp/demo", _tiny_tree(), 0.1, 0)
        (isolated_history / "history" / "garbage.json").write_text("{not json")
        items = disk_atlas.list_scan_history()
        assert [i["id"] for i in items] == [hid]

    def test_save_failure_returns_none(self, isolated_history, monkeypatch):
        monkeypatch.setattr(
            disk_atlas, "history_dir",
            lambda: (_ for _ in ()).throw(OSError("read-only fs")))
        assert disk_atlas.save_scan_history("/tmp/demo", _tiny_tree(), 0.1, 0) is None


class TestHistoryApi:
    def test_full_cycle_over_http(self, server, sample_tree, isolated_history):
        # scan → auto-saved → listed → loadable → deletable
        status, _, _ = server.post("/api/scan", {"path": str(sample_tree)})
        assert status in (200, 409)
        server.wait_for_state(("done",), timeout=20)

        status, items, _ = server.get("/api/history")
        assert status == 200
        assert len(items) == 1
        entry = items[0]
        assert entry["root_path"] == str(sample_tree)
        assert entry["file_count"] > 0
        assert "tree" not in entry

        status, snapshot, _ = server.post("/api/history/load", {"id": entry["id"]})
        assert status == 200
        assert snapshot["tree"]["name"] == sample_tree.name

        # replayed into the live scanner: /api/data now serves the snapshot
        status, data, _ = server.get("/api/data")
        assert status == 200
        assert data["name"] == sample_tree.name

        status, out, _ = server.post("/api/history/delete", {"id": entry["id"]})
        assert status == 200
        status, items, _ = server.get("/api/history")
        assert items == []

    def test_history_requires_auth(self, server):
        status, _, _ = server.get("/api/history", token=None)
        assert status == 401
        status, _, _ = server.post("/api/history/load", {"id": "x"}, token=None)
        assert status == 401

    def test_load_unknown_id_404(self, server, isolated_history):
        status, body, _ = server.post("/api/history/load", {"id": "does-not-exist"})
        assert status == 404

    def test_delete_missing_id_400(self, server, isolated_history):
        status, _, _ = server.post("/api/history/delete", {})
        assert status == 400

    def test_quick_scan_does_not_write_history(self, server, sample_tree, isolated_history):
        status, _, _ = server.post("/api/quick-scan",
                                   {"path": str(sample_tree), "auto_deep": False})
        assert status == 200
        _, items, _ = server.get("/api/history")
        assert items == []

    def test_duplicate_deep_scan_deduplicated(self, server, sample_tree, isolated_history):
        # The UI legitimately fires quick-scan(auto_deep) + explicit deep
        # scan for the same target; history must record it only once.
        status, _, _ = server.post("/api/quick-scan",
                                   {"path": str(sample_tree), "auto_deep": True})
        assert status == 200
        # Back-to-back second deep scan of the same path
        server.post("/api/scan", {"path": str(sample_tree), "force": True})
        server.wait_for_state(("done",), timeout=20)
        # Small margin for a trailing duplicate completion
        import time as _t; _t.sleep(0.3)
        _, items, _ = server.get("/api/history")
        same_path = [i for i in items if i["root_path"] == str(sample_tree)]
        assert len(same_path) == 1
