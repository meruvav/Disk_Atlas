#!/usr/bin/env python3
"""
Disk Atlas — Windows Authenticode signing helpers.

Used by build_windows.py to sign DiskAtlas.exe and the Inno Setup
installer with signtool (Windows SDK). Signing is configured purely
through environment variables — no secrets live in the repo. See
packaging/SIGNING.md for the full setup guide.

Configuration (first match wins):
    DISK_ATLAS_SIGN_PFX            Path to a .pfx/.p12 code-signing file
    DISK_ATLAS_SIGN_PFX_PASSWORD   Password for that file (omit only if none)

    DISK_ATLAS_SIGN_SUBJECT        Certificate subject name in the Windows
                                   certificate store (signtool /n ...)

    DISK_ATLAS_SIGN_THUMBPRINT     SHA-1 thumbprint in the certificate
                                   store (signtool /sha1 ...)

    DISK_ATLAS_TIMESTAMP_URL       RFC 3161 timestamp server.
                                   Default: http://timestamp.digicert.com

Tool discovery:
    SIGNTOOL_PATH env var -> PATH (signtool.exe) -> standard Windows SDK
    kits directory (newest version first).
"""

import os
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

DEFAULT_TIMESTAMP_URL = "http://timestamp.digicert.com"

KITS_ROOT = Path(r"C:\Program Files (x86)\Windows Kits\10\bin")


@dataclass(frozen=True)
class SigningConfig:
    """How signtool should select the certificate."""
    mode: str                    # "pfx", "subject", or "thumbprint"
    value: str                   # pfx path, subject name, or thumbprint
    password: Optional[str] = None
    timestamp_url: str = DEFAULT_TIMESTAMP_URL


def get_signing_config(env: Optional[dict] = None) -> Optional[SigningConfig]:
    """Read signing configuration from the environment.

    Returns None when signing is not configured, which build_windows.py
    treats as 'sign if possible, otherwise warn' unless --require-sign
    was given.
    """
    if env is None:
        env = os.environ

    ts_url = env.get("DISK_ATLAS_TIMESTAMP_URL", DEFAULT_TIMESTAMP_URL)

    pfx = env.get("DISK_ATLAS_SIGN_PFX")
    if pfx:
        return SigningConfig(
            mode="pfx",
            value=pfx,
            password=env.get("DISK_ATLAS_SIGN_PFX_PASSWORD"),
            timestamp_url=ts_url,
        )

    subject = env.get("DISK_ATLAS_SIGN_SUBJECT")
    if subject:
        return SigningConfig(mode="subject", value=subject, timestamp_url=ts_url)

    thumbprint = env.get("DISK_ATLAS_SIGN_THUMBPRINT")
    if thumbprint:
        cleaned = thumbprint.replace(" ", "").lower()
        return SigningConfig(mode="thumbprint", value=cleaned, timestamp_url=ts_url)

    return None


def find_signtool(env: Optional[dict] = None) -> Optional[str]:
    """Locate the Windows SDK signtool.exe. Returns None when absent.

    Only searched on Windows (except an explicit SIGNTOOL_PATH override):
    Linux distributions ship unrelated 'signtool' binaries (Mono strong-
    naming tools) that would be mistaken for the SDK tool.
    """
    if env is None:
        env = os.environ

    env_path = env.get("SIGNTOOL_PATH")
    if env_path and Path(env_path).is_file():
        return env_path

    if platform.system() != "Windows":
        return None

    from shutil import which
    on_path = which("signtool.exe") or which("signtool")
    if on_path:
        return on_path

    # Standard SDK install: newest x64 build first
    if KITS_ROOT.is_dir():
        kits = sorted(
            (p for p in KITS_ROOT.iterdir() if p.is_dir()),
            key=lambda p: [int(x) if x.isdigit() else 0 for x in p.name.split(".")],
            reverse=True,
        )
        for kit in kits:
            for arch in ("x64", ""):
                candidate = kit / arch / "signtool.exe" if arch else kit / "signtool.exe"
                if candidate.is_file():
                    return str(candidate)

    return None


def build_sign_command(signtool: str, config: SigningConfig, target: str) -> Sequence[str]:
    """Construct the signtool command line for one file.

    SHA-256 file digest + RFC 3161 timestamp so the signature stays valid
    after the certificate itself expires.
    """
    cmd = [
        signtool, "sign",
        "/fd", "sha256",
        "/tr", config.timestamp_url,
        "/td", "sha256",
        "/d", "Disk Atlas",
        "/v",
    ]
    if config.mode == "pfx":
        cmd += ["/f", config.value]
        if config.password:
            cmd += ["/p", config.password]
    elif config.mode == "subject":
        cmd += ["/n", config.value]
    elif config.mode == "thumbprint":
        cmd += ["/sha1", config.value]
    else:
        raise ValueError(f"Unknown signing mode: {config.mode}")
    cmd.append(target)
    return cmd
