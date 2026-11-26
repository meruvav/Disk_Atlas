# Disk Atlas — Windows Code Signing Guide

Signing is already wired into `packaging/build_windows.py`. This guide
covers the one step that can't be automated from the repo: obtaining
and configuring a code-signing certificate.

> **Why it matters:** an unsigned installer triggers Windows SmartScreen
> ("Windows protected your PC"), scares users away, and cannot be
> published to winget. A signed installer shows the publisher name
> (Meruva) and downloads cleanly.

## Step 1 — Buy a certificate (do this first, it has lead time)

Two options:

| | OV (Organization Validation) | EV (Extended Validation) |
|---|---|---|
| Price | ~$80–300/yr | ~$250–400/yr |
| Issuance | Days | 1–2 weeks + hardware token/HSM |
| SmartScreen | Builds reputation gradually | Instant reputation |
| Hardware | Any | HSM or cloud HSM only |

Common sellers: SSL.com, DigiCert, Sectigo (via resellers like
codesigningstore.com for lower prices). Buy the cheapest compliant OV
cert to start; EV or Microsoft Azure Trusted Signing later if
SmartScreen reputation slows adoption.

## Step 2 — Install the Windows SDK (signtool)

`signtool.exe` ships with the Windows 10/11 SDK:
https://developer.microsoft.com/en-us/windows/downloads/windows-sdk/
(only the "Windows SDK Signing Tools for Desktop Apps" feature is
needed). `build_windows.py` finds it automatically; otherwise point
`SIGNTOOL_PATH` to it.

## Step 3 — Configure signing (environment variables)

Import the certificate into the Windows certificate store (double-click
the .pfx) and pick ONE of these setups — no secrets in the repo:

```powershell
# Option A: PFX file + password (simplest, works in CI)
$env:DISK_ATLAS_SIGN_PFX = "C:\certs\meruva-codesign.pfx"
$env:DISK_ATLAS_SIGN_PFX_PASSWORD = "<password>"

# Option B: certificate store, select by subject name
$env:DISK_ATLAS_SIGN_SUBJECT = "Meruva LLC"

# Option C: certificate store, select by thumbprint (most precise)
$env:DISK_ATLAS_SIGN_THUMBPRINT = "a1b2c3..."

# Optional: different RFC 3161 timestamp server
$env:DISK_ATLAS_TIMESTAMP_URL = "http://timestamp.digicert.com"
```

## Step 4 — Build

```bash
python packaging/build_windows.py --require-sign
```

The pipeline prints `Signing: ENABLED (...)`, signs `DiskAtlas.exe`
BEFORE it is packed into the installer (so the installer never ships an
unsigned payload), then signs `DiskAtlas_Setup_<version>.exe`.
SHA-256 digest + RFC 3161 timestamp means signatures stay valid after
the certificate expires.

Without `--require-sign` an unsigned build only prints a warning —
handy for local dev on machines without the certificate.

## Verify a signed build

```powershell
signtool verify /pa /v dist\DiskAtlas_Setup_2.0.0.exe
```

"Signature Index: 0 (Primary Signature)" + "Successfully verified" =
done. Also check: right-click exe → Properties → Digital Signatures.

## Notes for CI (Phase 5.6)

- OV PFX: store the base64-encoded .pfx and password as GitHub Actions
  secrets, decode into a temp file in the release workflow.
- EV/HSM: use the vendor's cloud tool (Azure Trusted Signing,
  DigiCert KeyLocker) — secrets stay off any machine.
- `.gitignore` permanently excludes *.pfx/*.p12/*.key files; never
  commit a certificate.
