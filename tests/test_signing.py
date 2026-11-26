"""Tests for the Windows code-signing configuration (packaging/signing.py).

signtool itself is Windows-only, so these tests cover the pure-Python
parts: env-var configuration parsing and signtool command construction.
"""

import sys
from pathlib import Path

import pytest

PACKAGING_DIR = Path(__file__).resolve().parent.parent / "packaging"
sys.path.insert(0, str(PACKAGING_DIR))

import signing  # noqa: E402


# ---------------------------------------------------------------- config ---

def test_no_config_returns_none():
    assert signing.get_signing_config({}) is None


def test_pfx_mode_with_password():
    cfg = signing.get_signing_config({
        "DISK_ATLAS_SIGN_PFX": r"C:\certs\meruva.pfx",
        "DISK_ATLAS_SIGN_PFX_PASSWORD": "hunter2",
    })
    assert cfg.mode == "pfx"
    assert cfg.value == r"C:\certs\meruva.pfx"
    assert cfg.password == "hunter2"
    assert cfg.timestamp_url == signing.DEFAULT_TIMESTAMP_URL


def test_pfx_mode_without_password():
    cfg = signing.get_signing_config({"DISK_ATLAS_SIGN_PFX": "cert.pfx"})
    assert cfg.mode == "pfx"
    assert cfg.password is None


def test_subject_mode():
    cfg = signing.get_signing_config({"DISK_ATLAS_SIGN_SUBJECT": "Meruva LLC"})
    assert cfg.mode == "subject"
    assert cfg.value == "Meruva LLC"


def test_thumbprint_mode_normalized():
    cfg = signing.get_signing_config({
        "DISK_ATLAS_SIGN_THUMBPRINT": "AA:11 BB 22 Cc",
    })
    assert cfg.mode == "thumbprint"
    assert cfg.value == "aa:11bb22cc"


def test_pfx_takes_priority_over_subject():
    cfg = signing.get_signing_config({
        "DISK_ATLAS_SIGN_PFX": "cert.pfx",
        "DISK_ATLAS_SIGN_SUBJECT": "Meruva LLC",
    })
    assert cfg.mode == "pfx"


def test_custom_timestamp_server():
    cfg = signing.get_signing_config({
        "DISK_ATLAS_SIGN_SUBJECT": "Meruva",
        "DISK_ATLAS_TIMESTAMP_URL": "http://timestamp.example.com",
    })
    assert cfg.timestamp_url == "http://timestamp.example.com"


# ------------------------------------------------------------- commands ---

SIGNTOOL = r"C:\signtool.exe"
TARGET = r"C:\dist\DiskAtlas.exe"


def _cmd(env_mode):
    cfg = signing.get_signing_config(env_mode)
    return signing.build_sign_command(SIGNTOOL, cfg, TARGET)


def test_pfx_command_shape():
    cmd = _cmd({
        "DISK_ATLAS_SIGN_PFX": "cert.pfx",
        "DISK_ATLAS_SIGN_PFX_PASSWORD": "pw",
    })
    # SHA-256 digest + RFC 3161 timestamp so signatures outlive the cert
    for flag in ("/fd", "sha256", "/tr", "/td", "/d"):
        assert flag in cmd
    assert signing.DEFAULT_TIMESTAMP_URL in cmd
    assert "/f" in cmd and "cert.pfx" in cmd
    assert "/p" in cmd and "pw" in cmd
    assert cmd[0] == SIGNTOOL and cmd[-1] == TARGET


def test_pfx_command_omits_password_when_unset():
    cmd = _cmd({"DISK_ATLAS_SIGN_PFX": "cert.pfx"})
    assert "/p" not in cmd


def test_subject_command_uses_n_flag():
    cmd = _cmd({"DISK_ATLAS_SIGN_SUBJECT": "Meruva LLC"})
    assert cmd[cmd.index("/n") + 1] == "Meruva LLC"
    assert "/f" not in cmd


def test_thumbprint_command_uses_sha1_flag():
    cmd = _cmd({"DISK_ATLAS_SIGN_THUMBPRINT": "DEADBEEF"})
    assert cmd[cmd.index("/sha1") + 1] == "deadbeef"


def test_unknown_mode_rejected():
    cfg = signing.SigningConfig(mode="magic", value="x")
    with pytest.raises(ValueError):
        signing.build_sign_command(SIGNTOOL, cfg, TARGET)


# ----------------------------------------------------------- tool lookup ---

def test_signtool_env_path_preferred(tmp_path):
    fake = tmp_path / "signtool.exe"
    fake.write_text("x")
    assert signing.find_signtool({"SIGNTOOL_PATH": str(fake)}) == str(fake)


def test_signtool_bogus_env_path_ignored(tmp_path, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: None)
    result = signing.find_signtool({"SIGNTOOL_PATH": str(tmp_path / "missing.exe")})
    # Falls through to PATH / SDK search; must never return the bogus path
    assert result != str(tmp_path / "missing.exe")


def test_signtool_path_search_skipped_off_windows(monkeypatch):
    # Linux distros ship unrelated 'signtool' binaries (mono strong-naming);
    # they must never be mistaken for the Windows SDK tool.
    monkeypatch.setattr(signing.platform, "system", lambda: "Linux")
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/signtool")
    assert signing.find_signtool({}) is None


def test_signtool_env_override_works_on_any_platform(tmp_path, monkeypatch):
    monkeypatch.setattr(signing.platform, "system", lambda: "Linux")
    fake = tmp_path / "signtool.exe"
    fake.write_text("x")
    assert signing.find_signtool({"SIGNTOOL_PATH": str(fake)}) == str(fake)
