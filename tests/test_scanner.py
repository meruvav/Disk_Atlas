"""Unit and integration tests for DiskScanner and the exclusion rules."""
import os
import sys
import threading
import time

import pytest

from disk_atlas import (
    DEFAULT_EXCLUSIONS,
    DiskScanner,
    is_excluded_name,
    normalize_exclusions,
)


# ---------------------------------------------------------------- exclusion rules

class TestExclusionRules:
    @pytest.mark.parametrize("name", [
        "node_modules", "NODE_Modules", "Node_Modules",
        ".git", ".GIT", ".svn", ".hg",
        "$Recycle.Bin", "$RECYCLE.BIN",
        "System Volume Information", "system volume information",
        ".Trashes", ".Spotlight-V100", ".fseventsd", ".DocumentRevisions-V100",
        "lost+found", ".Trash", ".Trash-1000", ".Trash-501",
    ])
    def test_defaults_excluded(self, name):
        assert is_excluded_name(name)

    @pytest.mark.parametrize("name", [
        "src", "package.json", ".gitignore", ".gitattributes",
        "node_modules_backup", "my.node_modules", "Trash", "photos",
        "System Volume", "volume information",
    ])
    def test_normal_names_kept(self, name):
        assert not is_excluded_name(name)

    def test_custom_exclusion(self):
        assert is_excluded_name("build", extra={"build"})
        assert is_excluded_name("BUILD", extra={"build"})
        assert not is_excluded_name("builder", extra={"build"})

    def test_normalize_none_and_empty(self):
        assert normalize_exclusions(None) == frozenset()
        assert normalize_exclusions([]) == frozenset()

    def test_normalize_string_is_not_char_iterated(self):
        # A bare string must not be treated as an iterable of characters
        assert normalize_exclusions("node_modules") == frozenset()

    def test_normalize_lowercases_and_coerces(self):
        result = normalize_exclusions(["Cache", 42])
        assert result == frozenset({"cache", "42"})

    def test_default_set_is_lowercase(self):
        assert all(n == n.lower() for n in DEFAULT_EXCLUSIONS)


# ---------------------------------------------------------------- quick scan

class TestQuickScan:
    def test_lists_immediate_children_only(self, sample_tree):
        s = DiskScanner()
        result = s.quick_scan(str(sample_tree))
        names = {c["name"] for c in result["children"]}
        assert names == {"a.txt", "sub", "empty"}

    def test_folders_have_zero_size_and_empty_children(self, sample_tree):
        s = DiskScanner()
        result = s.quick_scan(str(sample_tree))
        sub = next(c for c in result["children"] if c["name"] == "sub")
        assert sub["type"] == "folder"
        assert sub["size"] == 0
        assert sub["children"] == []

    def test_counts_and_sorting(self, sample_tree):
        s = DiskScanner()
        result = s.quick_scan(str(sample_tree))
        assert result["file_count"] == 1
        assert result["folder_count"] == 2
        types = [c["type"] for c in result["children"]]
        assert types == sorted(types, key=lambda t: 0 if t == "folder" else 1)

    def test_excluded_entries_omitted(self, sample_tree):
        s = DiskScanner()
        result = s.quick_scan(str(sample_tree))
        names = [c["name"] for c in result["children"]]
        assert "node_modules" not in names
        assert ".git" not in names

    def test_invalid_path_raises(self, tmp_path):
        s = DiskScanner()
        with pytest.raises(FileNotFoundError):
            s.quick_scan(str(tmp_path / "nope"))


# ---------------------------------------------------------------- deep scan

class TestDeepScan:
    def test_size_aggregation_bottom_up(self, sample_tree):
        s = DiskScanner()
        s.scan_path(str(sample_tree))
        assert s.state == "done", s.error_message
        root = s.last_result
        assert root["size"] == 450  # 100 + 300 + 50; excluded content ignored
        sub = next(c for c in root["children"] if c["name"] == "sub")
        assert sub["size"] == 350
        deep = next(c for c in sub["children"] if c["name"] == "deep")
        assert deep["size"] == 50

    def test_tree_structure_and_types(self, sample_tree):
        s = DiskScanner()
        s.scan_path(str(sample_tree))
        root = s.last_result
        assert root["type"] == "folder"
        assert root["name"] == sample_tree.name
        a = next(c for c in root["children"] if c["name"] == "a.txt")
        assert a["type"] == "file" and a["ext"] == ".txt" and a["size"] == 100

    def test_counters(self, sample_tree):
        s = DiskScanner()
        s.scan_path(str(sample_tree))
        assert s.scanned_files == 3
        assert s.scanned_folders == 3  # sub, sub/deep, empty
        assert s.total_bytes == 450

    def test_excluded_never_in_tree(self, sample_tree):
        s = DiskScanner()
        s.scan_path(str(sample_tree))
        names = []

        def walk(n):
            names.append(n["name"])
            for c in n.get("children", []):
                walk(c)
        walk(s.last_result)
        assert "node_modules" not in names
        assert ".git" not in names
        assert "junk.js" not in names  # contents never descended into
        assert s.excluded_count == 2

    def test_custom_exclusions(self, sample_tree):
        s = DiskScanner()
        s.scan_path(str(sample_tree), extra_exclusions=["SUB"])
        assert s.state == "done"
        names = [c["name"] for c in s.last_result["children"]]
        assert "sub" not in names
        assert s.last_result["size"] == 100

    def test_empty_directory_included_with_zero(self, sample_tree):
        s = DiskScanner()
        s.scan_path(str(sample_tree))
        empty = next(c for c in s.last_result["children"] if c["name"] == "empty")
        assert empty["size"] == 0
        assert empty["children"] == []

    def test_children_sorted_folders_first_then_size_desc(self, sample_tree):
        s = DiskScanner()
        s.scan_path(str(sample_tree))
        children = s.last_result["children"]
        # folders first (sub before empty is size-independent, both 350 and 0:
        # sorted by size desc), then files
        assert children[-1]["type"] == "file"
        assert children[0]["name"] == "sub"

    def test_nonexistent_path_sets_error(self, tmp_path):
        s = DiskScanner()
        s.scan_path(str(tmp_path / "missing"))
        assert s.state == "error"
        assert "does not exist" in s.error_message

    @pytest.mark.skipif(sys.platform == "win32",
                        reason="symlink creation needs privileges on Windows")
    def test_symlink_loop_does_not_hang_or_recurse(self, sample_tree):
        # A symlink pointing at its own parent must be skipped entirely
        os.symlink(str(sample_tree), str(sample_tree / "sub" / "loop"))
        s = DiskScanner()
        s.scan_path(str(sample_tree))
        assert s.state == "done"
        names = []

        def walk(n):
            names.append(n["name"])
            for c in n.get("children", []):
                walk(c)
        walk(s.last_result)
        assert "loop" not in names

    @pytest.mark.skipif(sys.platform == "win32",
                        reason="POSIX permission bits not meaningful on Windows")
    @pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0,
                        reason="root ignores permission bits")
    def test_unreadable_subdir_skipped_without_failing(self, sample_tree):
        locked = sample_tree / "sub" / "locked"
        locked.mkdir()
        (locked / "secret.txt").write_bytes(b"s" * 999)
        locked.chmod(0)
        try:
            s = DiskScanner()
            s.scan_path(str(sample_tree))
            assert s.state == "done", s.error_message
            sub = next(c for c in s.last_result["children"] if c["name"] == "sub")
            names = [c["name"] for c in sub["children"]]
            assert "locked" in names  # listed, but contributes 0 bytes
            locked_node = next(c for c in sub["children"] if c["name"] == "locked")
            assert locked_node["children"] == []
        finally:
            locked.chmod(0o755)


# ---------------------------------------------------------------- concurrency

class TestConcurrency:
    def test_second_claim_refused_while_scanning(self):
        s = DiskScanner()
        gen = s.begin_scan()
        assert gen == 1
        assert s.begin_scan() is None

    def test_cancel_then_reclaim(self):
        s = DiskScanner()
        g1 = s.begin_scan()
        s.cancel()
        g2 = s.begin_scan()
        assert g2 == 2
        assert not s._is_current(g1)
        assert s._is_current(g2)

    def test_cancel_mid_scan_returns_promptly_with_idle_state(self, big_tree):
        s = DiskScanner()
        gen = s.begin_scan()
        t = threading.Thread(target=s.scan_path, args=(str(big_tree), gen), daemon=True)
        t.start()
        # Wait until the scan is genuinely in flight, then cancel
        deadline = time.time() + 5
        while s.scanned_files < 20 and time.time() < deadline:
            time.sleep(0.005)
        s.cancel()
        t.join(timeout=10)
        assert not t.is_alive(), "scan thread did not stop after cancel"
        assert s.state == "idle"

    def test_superseded_generation_discards_result(self, big_tree, tmp_path):
        s = DiskScanner()
        g1 = s.begin_scan()
        t1 = threading.Thread(target=s.scan_path, args=(str(big_tree), g1), daemon=True)
        t1.start()
        deadline = time.time() + 5
        while s.scanned_files < 20 and time.time() < deadline:
            time.sleep(0.005)
        # Force a new scan, superseding the first
        s.cancel()
        (tmp_path / "only.txt").write_bytes(b"q" * 10)
        g2 = s.begin_scan()
        t2 = threading.Thread(target=s.scan_path, args=(str(tmp_path), g2), daemon=True)
        t2.start()
        t2.join(timeout=10)
        t1.join(timeout=10)
        assert s.state == "done"
        # Final tree must be the g2 scan of tmp_path, not the big tree
        assert s.last_result["name"] == tmp_path.name
        assert [c["name"] for c in s.last_result["children"]] == ["only.txt"]
