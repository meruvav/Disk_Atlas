"""Tests for lazy tree loading (Phase 4.5).

Large drives produce scan trees far too big to ship to the browser in one
JSON payload. The engine therefore serves a depth-limited, breadth-capped
shallow tree plus on-demand paging endpoints. These tests cover the
serializer, the path index, the subtree summarizer, and the HTTP contract.
"""

import urllib.parse

import pytest

import disk_atlas
from disk_atlas import shallow_tree_copy


def _demo_tree():
    """root/
         a.txt            100 B
         sub/             350 B
           b.bin          300 B
           deep/           50 B
             c.log         50 B
         empty/             0 B
    """
    return {
        "name": "root", "path": "/root", "type": "folder", "size": 450,
        "children": [
            {"name": "a.txt", "path": "/root/a.txt", "type": "file",
             "size": 100, "ext": ".txt"},
            {"name": "sub", "path": "/root/sub", "type": "folder", "size": 350,
             "children": [
                 {"name": "b.bin", "path": "/root/sub/b.bin", "type": "file",
                  "size": 300, "ext": ".bin"},
                 {"name": "deep", "path": "/root/sub/deep", "type": "folder",
                  "size": 50, "children": [
                      {"name": "c.log", "path": "/root/sub/deep/c.log",
                       "type": "file", "size": 50, "ext": ".log"},
                  ]},
             ]},
            {"name": "empty", "path": "/root/empty", "type": "folder",
             "size": 0, "children": []},
        ],
    }


class TestShallowTreeCopy:
    def test_depth_zero_drops_children_with_flag(self):
        node = _demo_tree()["children"][1]  # sub
        out = shallow_tree_copy(node, 0)
        assert out["name"] == "sub"
        assert out["size"] == 350               # sizes stay exact
        assert out["children"] == []
        assert out["children_truncated"] is True
        assert out["child_count"] == 2

    def test_depth_two_keeps_children_and_grandchildren(self):
        out = shallow_tree_copy(_demo_tree(), 2)
        names = {c["name"] for c in out["children"]}
        assert names == {"a.txt", "sub", "empty"}
        sub = next(c for c in out["children"] if c["name"] == "sub")
        assert {c["name"] for c in sub["children"]} == {"b.bin", "deep"}
        deep = next(c for c in sub["children"] if c["name"] == "deep")
        assert deep["children"] == []
        assert deep["children_truncated"] is True
        assert deep["child_count"] == 1
        assert deep["size"] == 50

    def test_breadth_cap_pages_children(self):
        root = {"name": "r", "path": "/r", "type": "folder", "size": 0,
                "children": [
                    {"name": f"f{i}", "path": f"/r/f{i}", "type": "file",
                     "size": i, "ext": ".x"}
                    for i in range(10)
                ]}
        out = shallow_tree_copy(root, 1, page_size=4)
        assert len(out["children"]) == 4
        assert out["children_truncated"] is True
        assert out["child_count"] == 10
        full = shallow_tree_copy(root, 1, page_size=50)
        assert "children_truncated" not in full
        assert len(full["children"]) == 10

    def test_file_nodes_gain_no_children_key(self):
        f = _demo_tree()["children"][0]
        out = shallow_tree_copy(f, 2)
        assert out["name"] == "a.txt"
        assert "children" not in out
        assert "child_count" not in out

    def test_empty_folder_is_not_marked_truncated(self):
        out = shallow_tree_copy(_demo_tree(), 2)
        empty = next(c for c in out["children"] if c["name"] == "empty")
        assert empty["children"] == []
        assert "children_truncated" not in empty
        assert empty["child_count"] == 0

    def test_original_tree_is_not_mutated(self):
        tree = _demo_tree()
        shallow_tree_copy(tree, 0, page_size=1)
        assert len(tree["children"]) == 3
        assert len(tree["children"][1]["children"]) == 2


class TestIndexAndSummary:
    def test_index_builds_on_demand_and_rebuilds_on_new_result(self):
        s = disk_atlas.DiskScanner()
        s.last_result = _demo_tree()
        idx = s.tree_index()
        assert idx["/root/sub/deep"]["size"] == 50
        assert s.tree_index() is idx  # cached while result is unchanged
        s.last_result = _demo_tree()  # new object -> index rebuilds
        assert s.tree_index() is not idx

    def test_index_empty_without_result(self):
        s = disk_atlas.DiskScanner()
        assert s.tree_index() == {}

    def test_summarize_subtree_exact_aggregates(self):
        s = disk_atlas.DiskScanner()
        s.last_result = _demo_tree()
        summary = s.summarize_subtree("/root")
        assert summary["file_count"] == 3
        assert summary["folder_count"] == 4  # root + sub + deep + empty
        assert summary["total_bytes"] == 450
        largest = summary["largest_files"]
        assert [f["name"] for f in largest] == ["b.bin", "a.txt", "c.log"]
        assert largest[0]["size"] == 300
        exts = dict(summary["extensions"])
        assert exts == {".bin": 300, ".txt": 100, ".log": 50}

    def test_summarize_nested_node(self):
        s = disk_atlas.DiskScanner()
        s.last_result = _demo_tree()
        summary = s.summarize_subtree("/root/sub")
        assert summary["file_count"] == 2
        assert summary["folder_count"] == 2  # sub + deep
        assert summary["total_bytes"] == 350
        assert summary["largest_files"][0]["name"] == "b.bin"

    def test_summarize_unknown_path_returns_none(self):
        s = disk_atlas.DiskScanner()
        s.last_result = _demo_tree()
        assert s.summarize_subtree("/nope") is None

    def test_summary_cached_per_result(self):
        s = disk_atlas.DiskScanner()
        s.last_result = _demo_tree()
        first = s.summarize_subtree("/root")
        assert s.summarize_subtree("/root") is first
        s.last_result = _demo_tree()
        assert s.summarize_subtree("/root") is not first


@pytest.fixture()
def wide_folder(tmp_path):
    """A folder with 250 files — beyond the default 200-child page."""
    d = tmp_path / "wide"
    d.mkdir()
    for i in range(250):
        (d / f"f{i:03d}.dat").write_bytes(b"x")
    return tmp_path


class TestTreePagingApi:
    def _scan(self, server, path):
        status, _, _ = server.post("/api/scan", {"path": str(path)})
        assert status in (200, 409)
        server.wait_for_state(("done",), timeout=20)

    def test_data_is_shallow_with_counts(self, server, sample_tree):
        self._scan(server, sample_tree)
        status, tree, _ = server.get("/api/data")
        assert status == 200
        assert tree["size"] == 450
        assert tree["file_count"] == 3
        assert tree["folder_count"] == 3  # scanner counts discovered subdirs
        assert {c["name"] for c in tree["children"]} == {"a.txt", "sub", "empty"}
        sub = next(c for c in tree["children"] if c["name"] == "sub")
        deep = next(c for c in sub["children"] if c["name"] == "deep")
        assert deep["children_truncated"] is True
        assert deep["child_count"] == 1
        assert deep["children"] == []

    def test_children_endpoint_pages_from_scan_result(self, server, sample_tree):
        self._scan(server, sample_tree)
        deep_path = str(sample_tree / "sub" / "deep")
        status, page, _ = server.get(
            "/api/tree/children?path=" + urllib.parse.quote(deep_path))
        assert status == 200
        assert page["child_count"] == 1
        assert page["has_more"] is False
        assert [c["name"] for c in page["children"]] == ["c.log"]
        assert page["children"][0]["size"] == 50

    def test_children_pagination_offset_limit(self, server, wide_folder):
        self._scan(server, wide_folder)

        status, tree, _ = server.get("/api/data")
        assert status == 200
        assert tree["child_count"] == 1  # tmp_path holds only the 'wide' dir
        wide = tree["children"][0]
        assert wide["name"] == "wide"
        assert wide["child_count"] == 250
        assert len(wide["children"]) == 200
        assert wide["children_truncated"] is True

        quoted = urllib.parse.quote(str(wide_folder / "wide"))
        status, page, _ = server.get(
            f"/api/tree/children?path={quoted}&offset=200&limit=200")
        assert status == 200
        assert len(page["children"]) == 50
        assert page["has_more"] is False
        assert page["offset"] == 200

        # first page via the endpoint matches the /api/data page
        status, first, _ = server.get(f"/api/tree/children?path={quoted}")
        assert [c["name"] for c in first["children"]] == \
               [c["name"] for c in wide["children"]]

    def test_children_limit_clamped(self, server, sample_tree):
        self._scan(server, sample_tree)
        quoted = urllib.parse.quote(str(sample_tree))
        status, page, _ = server.get(
            f"/api/tree/children?path={quoted}&limit=999999")
        assert status == 200
        assert page["limit"] == disk_atlas.TREE_PAGE_MAX

    def test_children_ships_grandchild_pages(self, server, sample_tree):
        self._scan(server, sample_tree)
        quoted = urllib.parse.quote(str(sample_tree))
        status, page, _ = server.get(f"/api/tree/children?path={quoted}")
        assert status == 200
        sub = next(c for c in page["children"] if c["name"] == "sub")
        assert {c["name"] for c in sub["children"]} == {"b.bin", "deep"}
        deep = next(c for c in sub["children"] if c["name"] == "deep")
        assert deep["children_truncated"] is True

    def test_children_errors(self, server, sample_tree):
        self._scan(server, sample_tree)
        status, _, _ = server.get("/api/tree/children")
        assert status == 400
        status, _, _ = server.get("/api/tree/children?path=/not/in/scan")
        assert status == 404
        # The index is folders-only, so file paths read as "not found"
        file_path = urllib.parse.quote(str(sample_tree / "a.txt"))
        status, _, _ = server.get(f"/api/tree/children?path={file_path}")
        assert status == 404
        status, _, _ = server.get("/api/tree/children?path=x", token=None)
        assert status == 401

    def test_summary_endpoint(self, server, sample_tree):
        self._scan(server, sample_tree)
        quoted = urllib.parse.quote(str(sample_tree))
        status, summary, _ = server.get(f"/api/tree/summary?path={quoted}")
        assert status == 200
        assert summary["file_count"] == 3
        assert summary["total_bytes"] == 450
        assert summary["largest_files"][0]["name"] == "b.bin"
        assert summary["largest_files"][0]["size"] == 300

        status, _, _ = server.get("/api/tree/summary?path=/not/in/scan")
        assert status == 404
        status, _, _ = server.get("/api/tree/summary")
        assert status == 400
        status, _, _ = server.get(f"/api/tree/summary?path={quoted}", token=None)
        assert status == 401

    def test_history_replay_stays_lazy(self, server, sample_tree, tmp_path,
                                       monkeypatch):
        monkeypatch.setattr(disk_atlas, "user_data_dir", lambda: tmp_path)
        self._scan(server, sample_tree)
        _, items, _ = server.get("/api/history")
        assert len(items) == 1

        status, snapshot, _ = server.post("/api/history/load",
                                          {"id": items[0]["id"]})
        assert status == 200
        tree = snapshot["tree"]
        assert tree["file_count"] == 3
        sub = next(c for c in tree["children"] if c["name"] == "sub")
        deep = next(c for c in sub["children"] if c["name"] == "deep")
        assert deep["children_truncated"] is True

        # The replayed snapshot is paged like a live scan.
        deep_path = urllib.parse.quote(str(sample_tree / "sub" / "deep"))
        status, page, _ = server.get(f"/api/tree/children?path={deep_path}")
        assert status == 200
        assert [c["name"] for c in page["children"]] == ["c.log"]
