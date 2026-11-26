"""Tests for the macOS packaging assets (Phase 5.4).

The pipeline itself (codesign / hdiutil / notarytool) is macOS-only, so
these tests cover what can be validated anywhere: the hardened-runtime
entitlements plist and the build script's integrity.
"""

import plistlib
import subprocess
from pathlib import Path

PACKAGING_DIR = Path(__file__).resolve().parent.parent / "packaging"
ENTITLEMENTS = PACKAGING_DIR / "macos_entitlements.plist"
BUILD_SCRIPT = PACKAGING_DIR / "build_macos.sh"


# ------------------------------------------------------------ entitlements ---

def test_entitlements_is_valid_plist():
    with ENTITLEMENTS.open("rb") as f:
        data = plistlib.load(f)
    assert isinstance(data, dict) and data, "entitlements plist must be a non-empty dict"


def test_entitlements_required_for_pyinstaller():
    # PyInstaller bundles Python and third-party libraries Apple has not
    # individually approved — without these, notarization gets rejected.
    with ENTITLEMENTS.open("rb") as f:
        data = plistlib.load(f)
    assert data.get("com.apple.security.cs.disable-library-validation") is True
    assert data.get("com.apple.security.cs.allow-unsigned-executable-memory") is True


# ------------------------------------------------------------- build script ---

def test_build_script_is_valid_bash():
    result = subprocess.run(
        ["bash", "-n", str(BUILD_SCRIPT)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"bash syntax error: {result.stderr}"


def test_build_script_is_executable():
    assert BUILD_SCRIPT.stat().st_mode & 0o111, "build_macos.sh must be executable"


def test_build_script_pipeline_stages():
    text = BUILD_SCRIPT.read_text(encoding="utf-8")
    # Hardened-runtime signing with entitlements
    assert "--options runtime" in text
    assert "--entitlements" in text
    # DMG creation and signing
    assert "hdiutil create" in text
    # Notarization + stapling + Gatekeeper check
    assert "xcrun notarytool submit" in text
    assert "xcrun stapler staple" in text
    assert "spctl --assess" in text


def test_build_script_uses_env_credentials_only():
    text = BUILD_SCRIPT.read_text(encoding="utf-8")
    for var in (
        "DISK_ATLAS_MAC_SIGN_IDENTITY",
        "DISK_ATLAS_MAC_NOTARY_PROFILE",
        "DISK_ATLAS_NOTARY_KEY_ID",
        "DISK_ATLAS_NOTARY_ISSUER_ID",
        "DISK_ATLAS_NOTARY_KEY_PATH",
    ):
        assert var in text


def test_build_script_supports_release_flags():
    text = BUILD_SCRIPT.read_text(encoding="utf-8")
    for flag in ("--require-sign", "--skip-notarize", "--app-only", "--skip-build"):
        assert flag in text
