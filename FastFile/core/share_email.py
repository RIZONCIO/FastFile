#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core/share_email.py - Share FastFile via email
Strategy: compress project to ZIP + open system email client (mailto:)
No SMTP relay — works everywhere, no DNS errors, no authentication needed.
"""

import os
import re
import sys
import zipfile
import tempfile
import platform
import subprocess
import webbrowser
import urllib.parse
from pathlib import Path
from typing import Tuple

# ── Blocked providers ─────────────────────────────────────────────────────────

BLOCKED_DOMAINS = {
    'gmail.com','googlemail.com','google.com',
    'outlook.com','hotmail.com','hotmail.co.uk','hotmail.fr',
    'live.com','live.co.uk','msn.com',
    'yahoo.com','yahoo.co.uk','yahoo.fr','yahoo.com.br','ymail.com',
    'icloud.com','me.com','mac.com',
    'uol.com.br','bol.com.br','terra.com.br','ig.com.br',
    'globo.com','r7.com','oi.com.br',
    'zoho.com','zohomail.com',
    'aol.com','yandex.com','yandex.ru',
    'gmx.com','gmx.net','gmx.de',
    'protonmail.com','proton.me',
    'tutanota.com','tuta.io',
    'mail.com','email.com',
}

ALLOWED_TEMP_DOMAINS = {
    # Guerrilla Mail
    'guerrillamail.com','guerrillamail.net','guerrillamail.org',
    'guerrillamail.biz','guerrillamail.de','guerrillamail.info',
    'grr.la','spam4.me','sharklasers.com',
    # Temp Mail
    'tempmail.com','temp-mail.org','temp-mail.io','tempail.com','tempr.email',
    # 10 Minute Mail
    '10minutemail.com','10minutemail.net','10minutemail.org','10mail.org',
    # Mailinator / Trash
    'mailinator.com','trashmail.com','trashmail.me','trashmail.net',
    'trashmail.io','trashmail.at','trashmail.xyz',
    # Yopmail
    'yopmail.com','yopmail.fr',
    # Others
    'throwam.com','discard.email','mailnesia.com',
    'maildrop.cc','mailsac.com','nada.email',
    'mohmal.com','spambox.us','spamfree24.org',
    'wegwerfmail.de','wegwerfmail.net','wegwerfmail.org',
    'mailbolt.com','tempinbox.com','inboxalias.com',
    'fakeinbox.com','spamgourmet.com','spamgourmet.net',
}


def validate_email(email: str) -> Tuple[bool, str]:
    email = email.strip().lower()
    if not re.match(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$', email):
        return False, "Invalid email format."
    domain = email.split('@')[1]
    if domain in BLOCKED_DOMAINS:
        return False, (
            f"'{domain}' is a tracked provider — not allowed.\n"
            f"  Use a disposable address. Examples:\n"
            f"    guerrillamail.com  mailinator.com  yopmail.com\n"
            f"    10minutemail.com   maildrop.cc     trashmail.com"
        )
    if domain not in ALLOWED_TEMP_DOMAINS:
        return False, (
            f"'{domain}' is not on the approved temporary email list.\n"
            f"  FastFile only accepts known disposable providers.\n"
            f"  Accepted examples:\n"
            f"    guerrillamail.com  mailinator.com  yopmail.com\n"
            f"    10minutemail.com   maildrop.cc     trashmail.com\n"
            f"    sharklasers.com    discard.email   mailsac.com"
        )
    return True, ""


def zip_project(project_dir: Path, output_path: Path) -> Tuple[bool, str]:
    """Compress the FastFile project into a ZIP. Returns (ok, info_or_error)."""
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
        return True, f"{count} files · {size_mb:.1f} MB"
    except Exception as e:
        return False, str(e)


def send_fastfile_email(recipient: str, project_dir: Path,
                        progress_cb=None) -> Tuple[bool, str]:
    """
    1. Creates FastFile.zip in Downloads folder
    2. Opens the system email client with a pre-filled draft (mailto:)
    3. Opens the file manager so the user can attach the ZIP
    Returns (success, message_for_display).
    """
    valid, reason = validate_email(recipient)
    if not valid:
        return False, reason

    # Save ZIP to Downloads or temp
    downloads = Path.home() / "Downloads"
    if not downloads.exists():
        downloads = Path(tempfile.gettempdir())
    zip_path = downloads / "FastFile.zip"

    if progress_cb:
        progress_cb("Compressing FastFile project...")

    ok, info = zip_project(project_dir, zip_path)
    if not ok:
        return False, f"Could not create ZIP: {info}"

    if progress_cb:
        progress_cb(f"ZIP ready: {zip_path.name}  ({info})")
        progress_cb("Opening your email app...")

    # Open mailto: with pre-filled subject + body
    subject = urllib.parse.quote("FastFile — Secure P2P File Transfer")
    body = urllib.parse.quote(
        f"Hi!\n\n"
        f"I'm sharing FastFile with you.\n\n"
        f"Please find FastFile.zip attached (location: {zip_path})\n\n"
        f"To use it:\n"
        f"  1. Extract FastFile.zip\n"
        f"  2. Run: python main.py\n"
        f"  3. Start the node and share your Code with your contact\n\n"
        f"TLS 1.3 encrypted. No logs. No tracking.\n"
    )
    mailto = f"mailto:{recipient}?subject={subject}&body={body}"
    try:
        webbrowser.open(mailto)
        email_opened = True
    except Exception:
        email_opened = False

    # Open file manager at ZIP location so user can attach it
    try:
        system = platform.system()
        if system == "Windows":
            subprocess.Popen(f'explorer /select,"{zip_path}"', shell=True)
        elif system == "Darwin":
            subprocess.Popen(["open", "-R", str(zip_path)])
        else:
            subprocess.Popen(["xdg-open", str(zip_path.parent)])
    except Exception:
        pass

    steps = (
        f"ZIP saved at:\n"
        f"  {zip_path}\n\n"
        f"Next steps:\n"
        f"  1. Your email app {'opened' if email_opened else 'could not open — open it manually'}\n"
        f"  2. The file manager opened at the ZIP location\n"
        f"  3. Attach FastFile.zip to the draft\n"
        f"  4. Send to: {recipient}"
    )
    return True, steps
