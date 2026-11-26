# Disk Atlas — macOS Signing & Notarization Guide

`packaging/build_macos.sh` already automates signing, DMG packaging,
Apple notarization, and stapling. This guide covers the one-time
Apple-side setup, configured entirely through environment variables —
no secrets in the repo.

> **Why it matters:** an unsigned build shows the "damaged" /
> "unidentified developer" Gatekeeper dialog and most users will never
> open it. A signed + notarized + stapled DMG opens with one clean
> confirmation.

## Step 1 — Apple Developer account (do this first, $99/yr)

Enroll at https://developer.apple.com/programs/enroll/
Approval is usually 24–48h for individuals; up to 2 weeks for
organizations (needs a D-U-N-S number).

## Step 2 — Create the "Developer ID Application" certificate

1. Open **Keychain Access → Certificate Assistant → Request a
   Certificate From a Certificate Authority…**, save the CSR.
2. In https://developer.apple.com/account/resources/certificates/add
   choose **Developer ID Application**, upload the CSR, download the
   issued certificate, and double-click it into a keychain.
3. Find its identity string:
   ```bash
   security find-identity -v -p codesigning
   # -> 11C18E64447791E70602F0C2EC9B25BA6D04BA46 "Developer ID Application: Meruva LLC (A1B2C3D4E5)"
   ```
4. Configure:
   ```bash
   export DISK_ATLAS_MAC_SIGN_IDENTITY="Developer ID Application: Meruva LLC (A1B2C3D4E5)"
   ```

## Step 3 — Configure notarization credentials (pick one)

**Option A — keychain profile (recommended for the local Mac):**
```bash
# First create an app-specific password at https://appleid.apple.com
xcrun notarytool store-credentials "disk-atlas-notary" \
    --apple-id "you@example.com" \
    --team-id "A1B2C3D4E5" \
    --password "<app-specific-password>"
export DISK_ATLAS_MAC_NOTARY_PROFILE="disk-atlas-notary"
```

**Option B — App Store Connect API key (recommended for CI):**
Create a key at https://appstoreconnect.apple.com/access/integrations/api,
download `AuthKey_<KEY_ID>.p8` (gitignored as *.p8 — never commit it), then:
```bash
export DISK_ATLAS_NOTARY_KEY_ID="ABC123XYZ"
export DISK_ATLAS_NOTARY_ISSUER_ID="57246542-96fe-1a63-e053-0824d011072a"
export DISK_ATLAS_NOTARY_KEY_PATH="$HOME/keys/AuthKey_ABC123XYZ.p8"
```

## Step 4 — Build

```bash
./packaging/build_macos.sh                  # full pipeline
./packaging/build_macos.sh --require-sign   # fail loudly if no identity (release/CI)
./packaging/build_macos.sh --skip-notarize  # sign only, useful while credentials are pending
```

The script signs `DiskAtlas.app` with the hardened runtime and the
entitlements in `packaging/macos_entitlements.plist` (required because
PyInstaller bundles libraries Apple hasn't individually approved),
verifies the signature, builds `DiskAtlas_macOS_<version>.dmg` with an
/Applications drag-target, signs the DMG, submits it to Apple with
`--wait`, staples the ticket, and runs a final Gatekeeper assessment.

Without an identity it falls back to ad-hoc signing (runs on the build
Mac only) and prints a warning — fine for local dev.

## Verify a finished build

```bash
codesign --verify --deep --strict dist/DiskAtlas.app
spctl --assess --type execute dist/DiskAtlas.app        # "accepted"
spctl --assess --type open --verbose dist/DiskAtlas_macOS_2.0.0.dmg
```

## Troubleshooting

- **Notarization rejected**: get Apple's log with
  `xcrun notarytool log <submission-id> --keychain-profile ...` —
  the usual culprits are missing `--options runtime` or unsigned
  nested binaries; both are handled by this pipeline, so rejection
  usually means a spec change introduced an unsigned helper.
- **"malware" prompt on another Mac**: the star step was skipped —
  check the pipeline output for `NOTARIZED`.
