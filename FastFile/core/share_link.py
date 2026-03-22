#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core/share_link.py - Share FastFile via anonymous upload link
Uploads FastFile.zip to a free anonymous file host and returns a
short-lived download link that can be shared via any channel
(WhatsApp, Telegram, Signal, etc.).

Services used (tried in order, no account needed):
  1. https://0x0.st       — anonymous, files expire after 30 days
  2. https://transfer.sh  — anonymous, files expire after 14 days
  3. https://file.io      — one-time download link, expires after 1 download

Privacy notes:
  - The ZIP contains only FastFile's .py source files — no personal data
  - Your IP is sent to the upload server (use Tor to avoid this)
  - The link can be shared via any private/encrypted chat
"""

import zipfile
import tempfile
import urllib.request
import urllib.error
import json
import ssl
from pathlib import Path
from typing import Tuple

# ── ZIP creation (same logic as share_email) ─────────────────────────────────

def zip_project(project_dir: Path, output_path: Path) -> Tuple[bool, str]:
    SKIP_DIRS = {'__pycache__', '.git', 'tor_data', 'tor_bin', 'downloads'}
    SKIP_EXTS = {'.pyc', '.pyo', '.log', '.tmp'}
    try:
        with zipfile.ZipFile(str(output_path), 'w', zipfile.ZIP_DEFLATED) as zf:
            count = 0
            for item in sorted(project_dir.rglob('*')):
                if any(part in SKIP_DIRS for part in item.parts): continue
                if item.suffix in SKIP_EXTS: continue
                if '.fastfile' in str(item): continue
                if item.is_file():
                    zf.write(str(item), str(item.relative_to(project_dir.parent)))
                    count += 1
        size_mb = output_path.stat().st_size / 1024 / 1024
        return True, f"{count} files · {size_mb:.2f} MB"
    except Exception as e:
        return False, str(e)


# ── Upload services ───────────────────────────────────────────────────────────

def _upload_0x0(zip_path: Path) -> Tuple[bool, str]:
    """Upload to 0x0.st — free, anonymous, 30-day expiry."""
    try:
        ctx = ssl.create_default_context()
        boundary = b'----FastFileBoundary'
        with open(zip_path, 'rb') as f:
            file_data = f.read()

        body = (
            b'--' + boundary + b'\r\n'
            b'Content-Disposition: form-data; name="file"; filename="FastFile.zip"\r\n'
            b'Content-Type: application/zip\r\n\r\n'
            + file_data + b'\r\n'
            b'--' + boundary + b'--\r\n'
        )
        req = urllib.request.Request(
            'https://0x0.st',
            data=body,
            headers={
                'Content-Type': f'multipart/form-data; boundary={boundary.decode()}',
                'User-Agent': 'FastFile/3.8',
            },
            method='POST'
        )
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            link = resp.read().decode().strip()
            if link.startswith('http'):
                return True, link
            return False, f"Unexpected response: {link}"
    except Exception as e:
        return False, str(e)


def _upload_transfersh(zip_path: Path) -> Tuple[bool, str]:
    """Upload to transfer.sh — free, anonymous, 14-day expiry."""
    try:
        ctx = ssl.create_default_context()
        with open(zip_path, 'rb') as f:
            file_data = f.read()
        req = urllib.request.Request(
            'https://transfer.sh/FastFile.zip',
            data=file_data,
            headers={
                'Content-Type': 'application/zip',
                'User-Agent': 'FastFile/3.8',
                'Max-Days': '14',
            },
            method='PUT'
        )
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            link = resp.read().decode().strip()
            if link.startswith('http'):
                return True, link
            return False, f"Unexpected response: {link}"
    except Exception as e:
        return False, str(e)


def _upload_fileio(zip_path: Path) -> Tuple[bool, str]:
    """Upload to file.io — one-time download, auto-deleted after 1 download."""
    try:
        ctx = ssl.create_default_context()
        boundary = b'----FastFileBoundary2'
        with open(zip_path, 'rb') as f:
            file_data = f.read()
        body = (
            b'--' + boundary + b'\r\n'
            b'Content-Disposition: form-data; name="file"; filename="FastFile.zip"\r\n'
            b'Content-Type: application/zip\r\n\r\n'
            + file_data + b'\r\n'
            b'--' + boundary + b'--\r\n'
        )
        req = urllib.request.Request(
            'https://file.io/?expires=14d',
            data=body,
            headers={
                'Content-Type': f'multipart/form-data; boundary={boundary.decode()}',
                'User-Agent': 'FastFile/3.8',
            },
            method='POST'
        )
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            if data.get('success') and data.get('link'):
                return True, data['link']
            return False, str(data)
    except Exception as e:
        return False, str(e)


SERVICES = [
    ("0x0.st (30-day link)",       _upload_0x0),
    ("transfer.sh (14-day link)",  _upload_transfersh),
    ("file.io (one-time link)",    _upload_fileio),
]


# ── QR code in terminal ───────────────────────────────────────────────────────

def print_qr_terminal(data: str):
    """
    Prints a QR code in the terminal using only ASCII block characters.
    Uses the qrcode library if available, otherwise prints the URL only.
    """
    try:
        import qrcode  # type: ignore
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=1,
            border=1,
        )
        qr.add_data(data)
        qr.make(fit=True)
        # Print with block chars
        matrix = qr.get_matrix()
        print()
        for row in matrix:
            line = ""
            for cell in row:
                line += "██" if cell else "  "
            print(f"    {line}")
        print()
    except ImportError:
        # qrcode not installed — just show the URL prominently
        print(f"\n  {data}\n")
    except Exception:
        print(f"\n  {data}\n")


# ── Main entry point ──────────────────────────────────────────────────────────

def upload_and_get_link(project_dir: Path,
                        progress_cb=None) -> Tuple[bool, str, str]:
    """
    Compresses the project and uploads it to an anonymous file host.
    Returns (success: bool, link: str, service_name: str).
    """
    # Create ZIP
    tmp_dir  = Path(tempfile.mkdtemp())
    zip_path = tmp_dir / "FastFile.zip"

    if progress_cb:
        progress_cb("Compressing FastFile project...")

    ok, info = zip_project(project_dir, zip_path)
    if not ok:
        return False, f"ZIP error: {info}", ""

    size_mb = zip_path.stat().st_size / 1024 / 1024
    if progress_cb:
        progress_cb(f"ZIP ready: {info}")

    # Try each service
    for name, upload_fn in SERVICES:
        if progress_cb:
            progress_cb(f"Uploading to {name}...")
        success, result = upload_fn(zip_path)
        if success:
            # Cleanup
            try:
                zip_path.unlink(missing_ok=True)
                tmp_dir.rmdir()
            except Exception:
                pass
            return True, result, name

    # All failed — save ZIP locally and return path
    try:
        from pathlib import Path as _P
        import shutil
        downloads = _P.home() / "Downloads"
        downloads.mkdir(exist_ok=True)
        local_zip = downloads / "FastFile.zip"
        shutil.copy(str(zip_path), str(local_zip))
        msg = (
            f"All upload services failed.\n"
            f"FastFile.zip saved locally at:\n"
            f"  {local_zip}\n"
            f"Share this file manually via USB, cloud storage, or messaging app."
        )
        return False, msg, ""
    except Exception as e:
        return False, f"Upload failed and could not save locally: {e}", ""
