#!/bin/bash
#
# Disk Atlas — macOS Build Pipeline
#
# Stages:
#   1. Build dist/DiskAtlas.app with PyInstaller (packaging/DiskAtlas.spec)
#   2. Sign the .app (hardened runtime + entitlements, or ad-hoc fallback)
#   3. Build dist/DiskAtlas_macOS_<version>.dmg with an /Applications link
#   4. Sign the .dmg
#   5. Notarize with Apple's notarytool and staple the ticket
#
# Configuration via environment variables (no secrets in the repo; see
# packaging/NOTARIZATION.md for the full setup guide):
#   DISK_ATLAS_MAC_SIGN_IDENTITY    e.g. "Developer ID Application: Meruva (TEAMID)"
#   DISK_ATLAS_MAC_NOTARY_PROFILE   notarytool keychain profile name
#                                   (xcrun notarytool store-credentials ...)
#   -- or App Store Connect API key instead of a profile: --
#   DISK_ATLAS_NOTARY_KEY_ID        API key ID
#   DISK_ATLAS_NOTARY_ISSUER_ID     API issuer ID
#   DISK_ATLAS_NOTARY_KEY_PATH      path to AuthKey_<KEY_ID>.p8
#
# Flags:
#   --app-only         build the .app, skip sign/DMG/notarization
#   --skip-build       reuse an existing dist/DiskAtlas.app
#   --skip-notarize    sign + DMG but don't submit to Apple
#   --require-sign     fail instead of falling back to ad-hoc signing
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
DIST_DIR="$ROOT_DIR/dist"
BUILD_DIR="$ROOT_DIR/build"
APP="$DIST_DIR/DiskAtlas.app"
ENTITLEMENTS="$SCRIPT_DIR/macos_entitlements.plist"

die()  { echo "[-] Error: $*" >&2; exit 1; }
warn() { echo "[!] $*" >&2; }

SKIP_BUILD=0
APP_ONLY=0
SKIP_NOTARIZE=0
REQUIRE_SIGN=0
for arg in "$@"; do
    case "$arg" in
        --app-only)      APP_ONLY=1 ;;
        --skip-build)    SKIP_BUILD=1 ;;
        --skip-notarize) SKIP_NOTARIZE=1 ;;
        --require-sign)  REQUIRE_SIGN=1 ;;
        -h|--help)       grep '^#' "$0" | head -n 32; exit 0 ;;
        *)               die "unknown flag: $arg" ;;
    esac
done

# Signing and notarization are inherently macOS operations; building the
# .app on other systems is not supported either (BUNDLE is darwin-only).
[[ "$(uname)" == "Darwin" ]] || die "build_macos.sh must run on macOS"
command -v pyinstaller >/dev/null || die "pyinstaller not found (pip install -r requirements.txt)"

VERSION="$(python3 -c "
ns = {}
exec(open('$ROOT_DIR/src/version.py', encoding='utf-8').read(), ns)
print(ns['__version__'])")"
DMG="$DIST_DIR/DiskAtlas_macOS_$VERSION.dmg"
IDENTITY="${DISK_ATLAS_MAC_SIGN_IDENTITY:-}"
NOTARY_PROFILE="${DISK_ATLAS_MAC_NOTARY_PROFILE:-}"

echo "============================================================"
echo "         Disk Atlas — macOS Automated Build Pipeline"
echo "============================================================"
echo "  Version: $VERSION"

# ------------------------------------------------------------ 1. build ---
if [[ "$SKIP_BUILD" -eq 0 ]]; then
    echo ""
    echo "[+] Building DiskAtlas.app..."
    mkdir -p "$DIST_DIR" "$BUILD_DIR"
    pyinstaller --noconfirm \
        --distpath "$DIST_DIR" \
        --workpath "$BUILD_DIR" \
        "$SCRIPT_DIR/DiskAtlas.spec"
fi
[[ -d "$APP" ]] || die "$APP not found — run without --skip-build first"
[[ "$APP_ONLY" -eq 0 ]] || { echo ""; echo "  --app-only: done ($APP)"; exit 0; }

# ------------------------------------------------------------- 2. sign ---
SIGNED=0
if [[ -n "$IDENTITY" ]]; then
    echo ""
    echo "[+] Signing .app with hardened runtime (identity: $IDENTITY)..."
    codesign --deep --force --options runtime --timestamp \
        --entitlements "$ENTITLEMENTS" \
        --sign "$IDENTITY" "$APP"
    codesign --verify --deep --strict --verbose=2 "$APP"
    echo "    .app signature verified."
    SIGNED=1
elif [[ "$REQUIRE_SIGN" -eq 1 ]]; then
    die "--require-sign given but DISK_ATLAS_MAC_SIGN_IDENTITY is not set (see NOTARIZATION.md)"
else
    warn "DISK_ATLAS_MAC_SIGN_IDENTITY not set — ad-hoc signing (runs locally, Gatekeeper will block it elsewhere)"
    codesign --deep --force -s - "$APP"
fi

# ------------------------------------------------- 3./4. DMG (signed) ---
export TMPDIR="${TMPDIR:-/tmp}"
STAGING="$(mktemp -d "${TMPDIR%/}/diskatlas-dmg.XXXXXX")"
trap 'rm -rf "$STAGING"' EXIT

echo ""
echo "[+] Building DMG: $(basename "$DMG")..."
cp -R "$APP" "$STAGING/DiskAtlas.app"
ln -s /Applications "$STAGING/Applications"
hdiutil create -volname "Disk Atlas" -srcfolder "$STAGING" -ov -format UDZO "$DMG" >/dev/null

if [[ "$SIGNED" -eq 1 ]]; then
    echo "[+] Signing DMG..."
    codesign --force --timestamp --sign "$IDENTITY" "$DMG"
    codesign --verify --verbose=2 "$DMG"
fi

# -------------------------------------------------------- 5. notarize ---
NOTARIZED=0
if [[ "$SIGNED" -eq 1 && "$SKIP_NOTARIZE" -eq 0 ]]; then
    if [[ -n "$NOTARY_PROFILE" ]]; then
        NOTARY_ARGS=(--keychain-profile "$NOTARY_PROFILE")
    elif [[ -n "${DISK_ATLAS_NOTARY_KEY_ID:-}" && -n "${DISK_ATLAS_NOTARY_ISSUER_ID:-}" && -n "${DISK_ATLAS_NOTARY_KEY_PATH:-}" ]]; then
        NOTARY_ARGS=(--key-id "$DISK_ATLAS_NOTARY_KEY_ID" \
                     --issuer "$DISK_ATLAS_NOTARY_ISSUER_ID" \
                     --key "$DISK_ATLAS_NOTARY_KEY_PATH")
    else
        NOTARY_ARGS=()
        warn "No notary credentials (DISK_ATLAS_MAC_NOTARY_PROFILE or API key env vars) — skipping notarization"
    fi

    if [[ "${#NOTARY_ARGS[@]}" -gt 0 ]]; then
        echo ""
        echo "[+] Submitting to Apple notarization service (this can take minutes)..."
        xcrun notarytool submit "$DMG" "${NOTARY_ARGS[@]}" --wait
        echo "[+] Stapling notarization ticket..."
        xcrun stapler staple "$DMG"
        xcrun stapler validate "$DMG"
        echo "[+] Gatekeeper assessment:"
        spctl --assess --type open --verbose "$DMG"
        NOTARIZED=1
    fi
fi

echo ""
echo "============================================================"
echo "  BUILD SUCCESSFUL!"
echo "  DMG:       $DMG ($(du -h "$DMG" | cut -f1))"
if [[ "$SIGNED" -eq 1 ]]; then
    if [[ "$NOTARIZED" -eq 1 ]]; then
        echo "  Status:    SIGNED + NOTARIZED + STAPLED — ready to distribute"
    else
        echo "  Status:    SIGNED but NOT notarized — Gatekeeper will warn users"
    fi
else
    echo "  Status:    ad-hoc signed (dev builds only)"
fi
echo "============================================================"
