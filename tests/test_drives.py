"""Tests for mount-point parsing and drive detection (Phase 3.2)."""
import sys

import pytest

from disk_atlas import (
    _home_entry,
    _mount_label,
    _parse_proc_mounts,
    _unescape_mount_field,
    list_system_drives,
)


SAMPLE_MOUNTS = """\
/dev/sda1 / ext4 rw,relatime 0 0
proc /proc proc rw,nosuid,nodev,noexec,relatime 0 0
sysfs /sys sysfs rw,nosuid,nodev,noexec,relatime 0 0
tmpfs /run tmpfs rw,nosuid,nodev 0 0
overlay / overlay rw,lowerdir=/l1,upperdir=/l2 0 0
/dev/sda1 /home ext4 rw,relatime 0 0
/dev/sdb1 /media/user/My\\040Passport exfat rw,nosuid,nodev 0 0
/dev/loop0 /snap/core/123 squashfs ro 0 0
server:/share /mnt/nas nfs4 rw,relatime 0 0
//nas/media /mnt/media cifs rw 0 0
/dev/sdc2 /mnt/data btrfs rw,relatime 0 0
cgroup2 /sys/fs/cgroup cgroup2 rw 0 0
"""


class TestProcMountsParser:
    def test_keeps_real_block_devices(self):
        mounts = _parse_proc_mounts(SAMPLE_MOUNTS)
        assert ("/dev/sda1", "/", "ext4") in mounts
        assert ("/dev/sda1", "/home", "ext4") in mounts
        assert ("/dev/sdc2", "/mnt/data", "btrfs") in mounts

    def test_filters_pseudo_filesystems(self):
        mounts = _parse_proc_mounts(SAMPLE_MOUNTS)
        fstypes = {fs for _, _, fs in mounts}
        assert fstypes.isdisjoint(
            {"proc", "sysfs", "tmpfs", "overlay", "squashfs", "cgroup2"})

    def test_filters_network_filesystems(self):
        mounts = _parse_proc_mounts(SAMPLE_MOUNTS)
        fstypes = {fs for _, _, fs in mounts}
        assert fstypes.isdisjoint({"nfs4", "cifs"})
        assert all(m != "/mnt/nas" for _, m, _ in mounts)

    def test_filters_loop_devices(self):
        mounts = _parse_proc_mounts(SAMPLE_MOUNTS)
        assert not any("loop" in dev for dev, _, _ in mounts)

    def test_unescapes_octal_sequences(self):
        mounts = _parse_proc_mounts(SAMPLE_MOUNTS)
        assert ("/dev/sdb1", "/media/user/My Passport", "exfat") in mounts

    def test_unescape_helper(self):
        assert _unescape_mount_field("/a\\040b") == "/a b"
        assert _unescape_mount_field("/a\\134b") == "/a\\b"

    def test_malformed_lines_tolerated(self):
        assert _parse_proc_mounts("garbage\n\n/dev/sda1 / ext4 rw 0 0\n") == \
            [("/dev/sda1", "/", "ext4")]


class TestMountLabel:
    def test_root_is_system_volume(self):
        assert _mount_label("/") == "System volume"

    def test_basename_used(self):
        assert _mount_label("/media/user/My Passport") == "My Passport"
        assert _mount_label("/mnt/data") == "data"

    def test_trailing_slash_handled(self):
        assert _mount_label("/mnt/data/") == "data"


class TestHomeEntry:
    def test_shape(self):
        entry = _home_entry()
        assert set(entry) == {"path", "kind", "label", "total", "free", "used"}
        assert entry["kind"] == "home"
        assert entry["label"] == "Home folder"

    def test_capacity_nonnegative(self):
        entry = _home_entry()
        assert entry["total"] >= 0
        assert entry["free"] >= 0


@pytest.mark.skipif(sys.platform == "win32",
                    reason="POSIX-specific assertions")
class TestListSystemDrivesPosix:
    def test_home_first_then_root(self):
        drives = list_system_drives()
        assert drives[0]["kind"] == "home"
        assert any(d["path"] == "/" and d["kind"] == "drive" for d in drives)

    def test_no_duplicate_paths(self):
        drives = list_system_drives()
        paths = [d["path"] for d in drives]
        assert len(paths) == len(set(paths))

    def test_all_entries_have_capacity(self):
        for d in list_system_drives():
            assert d["total"] > 0, d["path"]
