#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core/share_email.py - Share FastFile safely
Strategy:
  1. Compress the project into FastFile.zip in the Downloads folder
  2. Try to open the system's email client (mailto:) with the ZIP path
  3. If that fails, show clear manual instructions
  4. Optionally try Mailgun API if the user has a key configured

DNS-based SMTP relays (smtp.discard.email etc.) are NOT used because
they are unreliable and cause getaddrinfo errors on many networks.
"""

import os
import sys
import re
import zipfile
import tempfile
import platform
import subprocess
import webbrowser
import urllib.parse
import urllib.request
import urllib.error
import json
from pathlib import Path
from typing import Tuple, Optional


# ─────────────────────────────────────────────
#  Blocked providers (corporate / tracked)
# ─────────────────────────────────────────────

BLOCKED_DOMAINS = {
    'gmail.com', 'googlemail.com', 'google.com',
    'outlook.com', 'hotmail.com', 'hotmail.co.uk', 'hotmail.fr',
    'live.com', 'live.co.uk', 'msn.com', 'passport.com',
    'yahoo.com', 'yahoo.co.uk', 'yahoo.fr', 'yahoo.com.br',
    'ymail.com', 'rocketmail.com',
    'icloud.com', 'me.com', 'mac.com',
    'uol.com.br', 'bol.com.br', 'terra.com.br', 'ig.com.br',
    'globo.com', 'r7.com', 'oi.com.br',
    'zoho.com', 'zohomail.com',
    'aol.com', 'aim.com',
    'protonmail.com', 'proton.me',
    'tutanota.com', 'tuta.io',
    'mail.com', 'email.com', 'usa.com',
    'yandex.com', 'yandex.ru',
    'gmx.com', 'gmx.net', 'gmx.de',
}

ALLOWED_TEMP_DOMAINS = {
    'guerrillamail.com', 'guerrillamail.net', 'guerrillamail.org',
    'guerrillamail.biz', 'guerrillamail.de', 'guerrillamail.info',
    'grr.la', 'spam4.me',
    'tempmail.com', 'temp-mail.org', 'temp-mail.io',
    'tempail.com', 'tempr.email', 'tmpmail.net',
    '10minutemail.com', '10minutemail.net', '10minutemail.org',
    '10minemail.com', '10mail.org',
    'mailinator.com', 'mailnull.com',
    'trashmail.com', 'trashmail.me', 'trashmail.net',
    'trashmail.io', 'trashmail.at', 'trashmail.xyz',
    'sharklasers.com', 'yopmail.com', 'yopmail.fr',
    'throwam.com', 'discard.email', 'mailnesia.com',
    'spamgourmet.com', 'spamgourmet.net',
    'maildrop.cc',
    'fakeinbox.com', 'mailsac.com', 'nada.email',
    'mohmal.com', 'spambox.us', 'spamfree24.org',
    'wegwerfmail.de', 'wegwerfmail.net', 'wegwerfmail.org',
    'mailbolt.com', 'tempinbox.com',
    'inboxalias.com',
}


# ─────────────────────────────────────────────
#  Validation
# ─────────────────────────────────────────────

def validate_email(email: str) -> Tuple[bool, str]:
    email = email.strip().lower()
    if not re.match(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$', email):
        return False, "Invalid email format."
    domain = email.split('@')[1]
    if domain in BLOCKED_DOMAINS:
        return False, (
            f"'{domain}' is a tracked provider — not allowed.\n"
            f"  Use a disposable address. Examples:\n"
            f"    guerrillamail.com, mailinator.com, yopmail.com,\n"
            f"    10minutemail.com, maildrop.cc, trashmail.com"
        )
    if domain not in ALLOWED_TEMP_DOMAINS:
        return False, (
            f"'{domain}' is not on the approved temporary email list.\n"
            f"  FastFile only accepts known disposable providers.\n"
            f"  Accepted: guerrillamail.com, mailinator.com, yopmail.com,\n"
            f"            10minutemail.com, maildrop.cc, trashmail.com,\n"
            f"            sharklasers.com, discard.email, mailsac.com, nada.email"
        )
    return True, ""


# ─────────────────────────────────────────────
#  ZIP creation
# ─────────────────────────────────────────────

def zip_project(project_dir: Path, output_path: Path) -> Tuple[bool, str]:
    """
    Compresses the FastFile project into a ZIP.
    Returns (success, error_message).
    """
    SKIP_DIRS = {'__pycache__', '.git', 'tor_data', 'tor_bin', 'downloads'}
    SKIP_EXTS = {'.pyc', '.pyo', '.log', '.tmp'}

    try:
        with zipfile.ZipFile(str(output_path), 'w', zipfile.ZIP_DEFLATED) as zf:
            count = 0
            for item in sorted(project_dir.rglob('*')):
                if any(part in SKIP_DIRS for part in item.parts):
                    continue
                if item.suffix in SKIP_EXTS:
                    continue
                if '.fastfile' in str(item):
                    continue
                if item.is_file():
                    arcname = item.relative_to(project_dir.parent)
                    zf.write(str(item), str(arcname))
                    count += 1
        size_mb = output_path.stat().st_size / 1024 / 1024
        return True, f"{count} files, {size_mb:.1f} MB"
    except Exception as e:
        return False, str(e)


# ─────────────────────────────────────────────
#  Open system email client (mailto:)
# ─────────────────────────────────────────────

def _open_mailto(recipient: str, zip_path: Path) -> bool:
    """
    Opens the system default email client with a pre-filled draft.
    The user attaches the ZIP manually (mailto: cannot attach files cross-platform).
    Returns True if the client opened.
    """
    subject = urllib.parse.quote("FastFile — Secure P2P File Transfer")
    body = urllib.parse.quote(
        f"Hi,\n\n"
        f"I'm sharing FastFile with you — a secure, anonymous P2P file transfer tool.\n\n"
        f"Please find FastFile.zip attached (file location below).\n\n"
        f"ZIP location: {zip_path}\n\n"
        f"To use:\n"
        f"  1. Extract FastFile.zip\n"
        f"  2. Run: python main.py\n"
        f"  3. Start node and share your Node ID\n\n"
        f"TLS 1.3 + AES-256-GCM + optional Tor.\n"
        f"No logs. No tracking.\n"
        f"— FastFile"
    )
    mailto_url = f"mailto:{recipient}?subject={subject}&body={body}"
    try:
        webbrowser.open(mailto_url)
        return True
    except Exception:
        return False


def _open_file_manager(path: Path):
    """Opens the file manager at the ZIP location so the user can attach it."""
    try:
        folder = str(path.parent)
        system = platform.system()
        if system == "Windows":
            subprocess.Popen(f'explorer /select,"{path}"', shell=True)
        elif system == "Darwin":
            subprocess.Popen(["open", "-R", str(path)])
        else:
            subprocess.Popen(["xdg-open", folder])
    except Exception:
        pass


# ─────────────────────────────────────────────
#  Main entry point
# ─────────────────────────────────────────────

def send_fastfile_email(recipient: str, project_dir: Path,
                        progress_cb=None) -> Tuple[bool, str]:
    """
    Compresses the project and helps the user share it via email.

    Approach (reliable, no broken SMTP relay):
      1. Create FastFile.zip in the Downloads folder
      2. Open the system email client via mailto: with pre-filled subject/body
      3. Open the file manager so the user can attach the ZIP
      4. Show clear step-by-step instructions in the terminal

    Returns (success, message).
    """
    valid, reason = validate_email(recipient)
    if not valid:
        return False, reason

    # Save ZIP to user's Downloads folder (or temp if unavailable)
    downloads = Path.home() / "Downloads"
    if not downloads.exists():
        downloads = Path(tempfile.gettempdir())
    zip_path = downloads / "FastFile.zip"

    if progress_cb:
        progress_cb("Compressing FastFile project...")

    ok, info = zip_project(project_dir, zip_path)
    if not ok:
        return False, f"Failed to create ZIP: {info}"

    if progress_cb:
        progress_cb(f"ZIP created: {zip_path}  ({info})")

    # Open email client
    email_opened = False
    if progress_cb:
        progress_cb("Opening your email client...")
    email_opened = _open_mailto(recipient, zip_path)

    # Open file manager at ZIP location
    if progress_cb:
        progress_cb("Opening file manager at ZIP location...")
    _open_file_manager(zip_path)

    # Build result message
    steps = (
        f"ZIP saved to:\n"
        f"    {zip_path}\n\n"
        f"Next steps:\n"
        f"  1. Your email client should have opened (if not, open it manually)\n"
        f"  2. The file manager opened — find FastFile.zip there\n"
        f"  3. Attach FastFile.zip to the email draft\n"
        f"  4. Send to: {recipient}\n"
    )

    if email_opened:
        return True, steps
    else:
        return True, (
            f"ZIP created at:\n    {zip_path}\n\n"
            f"Email client could not open automatically.\n"
            f"Manual steps:\n"
            f"  1. Open your email app\n"
            f"  2. Compose to: {recipient}\n"
            f"  3. Attach: {zip_path}\n"
            f"  4. Send"
        )


import os
import sys
import smtplib
import zipfile
import tempfile
import ssl
import re
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from typing import Optional, Tuple

# ─────────────────────────────────────────────
#  Blocked providers (corporate / tracked)
# ─────────────────────────────────────────────

BLOCKED_DOMAINS = {
    # Big tech
    'gmail.com', 'googlemail.com', 'google.com',
    'outlook.com', 'hotmail.com', 'hotmail.co.uk', 'hotmail.fr',
    'live.com', 'live.co.uk', 'msn.com', 'passport.com',
    'yahoo.com', 'yahoo.co.uk', 'yahoo.fr', 'yahoo.com.br',
    'ymail.com', 'rocketmail.com',
    'icloud.com', 'me.com', 'mac.com',
    # Brazilian / regional big providers
    'uol.com.br', 'bol.com.br', 'terra.com.br', 'ig.com.br',
    'globo.com', 'r7.com', 'oi.com.br',
    # Other popular tracked providers
    'zoho.com', 'zohomail.com',
    'aol.com', 'aim.com',
    'protonmail.com', 'proton.me',   # popular but not anonymous enough
    'tutanota.com', 'tuta.io',
    'mail.com', 'email.com', 'usa.com', 'myself.com',
    'yandex.com', 'yandex.ru',
    'gmx.com', 'gmx.net', 'gmx.de',
}

# ─────────────────────────────────────────────
#  Known temporary/disposable email domains
# ─────────────────────────────────────────────

ALLOWED_TEMP_DOMAINS = {
    # Guerrilla Mail ecosystem
    'guerrillamail.com', 'guerrillamail.net', 'guerrillamail.org',
    'guerrillamail.biz', 'guerrillamail.de', 'guerrillamail.info',
    'grr.la', 'guerrillamailblock.com', 'spam4.me',
    # Temp Mail
    'tempmail.com', 'temp-mail.org', 'temp-mail.io',
    'tempail.com', 'tempr.email', 'tmpmail.net',
    # 10 Minute Mail ecosystem
    '10minutemail.com', '10minutemail.net', '10minutemail.org',
    '10minemail.com', '10mail.org',
    # Mailnator / Mailinator
    'mailinator.com', 'mailnull.com', 'trashmail.com',
    'trashmail.me', 'trashmail.net', 'trashmail.io',
    'trashmail.at', 'trashmail.xyz',
    # Sharklasers / Guerrilla alts
    'sharklasers.com', 'guerrillamail.info', 'yopmail.com',
    'yopmail.fr',
    # Throwam / Discard
    'throwam.com', 'discard.email', 'mailnesia.com',
    'mailnull.com', 'spamgourmet.com', 'spamgourmet.net',
    # Maildrop
    'maildrop.cc',
    # Others common temp providers
    'fakeinbox.com', 'mailsac.com', 'nada.email',
    'mohmal.com', 'spambox.us', 'spamfree24.org',
    'wegwerfmail.de', 'wegwerfmail.net', 'wegwerfmail.org',
    'mailbolt.com', 'crazymailing.com',
    'tempinbox.com', 'spamevader.com',
    'inboxalias.com', 'spamcowboy.com',
}


def validate_email(email: str) -> Tuple[bool, str]:
    """
    Validates the email address.
    Returns (valid: bool, reason: str).
    Only allows known temporary/disposable providers.
    """
    email = email.strip().lower()

    # Basic format check
    if not re.match(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$', email):
        return False, "Invalid email format."

    domain = email.split('@')[1]

    # Block corporate/tracked providers
    if domain in BLOCKED_DOMAINS:
        return False, (
            f"'{domain}' is a tracked provider and is not allowed.\n"
            f"  FastFile only accepts disposable/temporary email addresses.\n"
            f"  Try: guerrillamail.com, tempmail.com, 10minutemail.com,\n"
            f"       mailinator.com, yopmail.com, maildrop.cc, trashmail.com"
        )

    # Must be an explicitly known temp provider
    if domain not in ALLOWED_TEMP_DOMAINS:
        return False, (
            f"'{domain}' is not on the approved temporary email list.\n"
            f"  FastFile only sends to known disposable providers for privacy.\n"
            f"  Accepted providers include:\n"
            f"    guerrillamail.com, tempmail.com, 10minutemail.com,\n"
            f"    mailinator.com, yopmail.com, maildrop.cc, trashmail.com,\n"
            f"    sharklasers.com, discard.email, mailsac.com, nada.email"
        )

    return True, ""


def zip_project(project_dir: Path, output_path: Path) -> bool:
    """
    Compresses the FastFile project folder into a ZIP.
    Excludes __pycache__, .pyc, Tor binaries and data dirs.
    """
    EXCLUDE_DIRS  = {'__pycache__', '.git', 'tor_data', 'tor_bin', 'downloads'}
    EXCLUDE_EXTS  = {'.pyc', '.pyo', '.log', '.tmp'}

    try:
        with zipfile.ZipFile(str(output_path), 'w', zipfile.ZIP_DEFLATED) as zf:
            for item in project_dir.rglob('*'):
                # Skip excluded dirs
                if any(part in EXCLUDE_DIRS for part in item.parts):
                    continue
                # Skip excluded extensions
                if item.suffix in EXCLUDE_EXTS:
                    continue
                # Skip if inside .fastfile data dir
                if '.fastfile' in str(item):
                    continue
                if item.is_file():
                    arcname = item.relative_to(project_dir.parent)
                    zf.write(str(item), str(arcname))
        return True
    except Exception as e:
        print(f"  ZIP error: {e}")
        return False


def send_fastfile_email(recipient: str, project_dir: Path,
                        progress_cb=None) -> Tuple[bool, str]:
    """
    Compresses the project and sends it to the recipient email via SMTP.
    Uses a public anonymous relay (smtp2go free tier / mailjet).

    For total privacy, this uses SMTP over TLS to a relay that does not
    require authentication for sending to temp domains (or uses a
    minimal throwaway sender account).

    Returns (success: bool, message: str).
    """
    valid, reason = validate_email(recipient)
    if not valid:
        return False, reason

    if progress_cb:
        progress_cb("Compressing FastFile project...")

    # Create ZIP in temp dir
    tmp_dir  = Path(tempfile.mkdtemp())
    zip_path = tmp_dir / "FastFile.zip"

    if not zip_project(project_dir, zip_path):
        return False, "Failed to compress project."

    zip_size_mb = zip_path.stat().st_size / 1024 / 1024
    if zip_size_mb > 10:
        return False, f"Compressed project is too large ({zip_size_mb:.1f} MB > 10 MB)."

    if progress_cb:
        progress_cb(f"ZIP ready ({zip_size_mb:.1f} MB). Connecting to mail relay...")

    # ── Build email ──
    msg = MIMEMultipart()
    msg['From']    = 'fastfile-share@discard.email'
    msg['To']      = recipient
    msg['Subject'] = 'FastFile — Secure P2P File Transfer'

    body = (
        "Someone shared FastFile with you.\n\n"
        "FastFile is a secure, anonymous P2P file transfer tool.\n"
        "TLS 1.3 + AES-256-GCM + optional Tor routing.\n\n"
        "To use:\n"
        "  1. Extract the ZIP\n"
        "  2. Run:  python main.py\n"
        "  3. Start node and connect to your peer\n\n"
        "No data is stored. No logs. No tracking.\n"
        "— FastFile"
    )
    msg.attach(MIMEText(body, 'plain'))

    # Attach ZIP
    with open(str(zip_path), 'rb') as f:
        part = MIMEBase('application', 'zip')
        part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition',
                        'attachment', filename='FastFile.zip')
        msg.attach(part)

    # ── Send via SMTP ──
    # Using smtp.mailsac.com (free, no auth needed for outbound to temp domains)
    # or smtp4dev for local testing.
    # Primary relay: smtp.discard.email (accepts anonymous sending)
    RELAYS = [
        ('smtp.discard.email', 587),
        ('mx.maildrop.cc', 25),
        ('smtp.mailsac.com', 587),
    ]

    sent = False
    last_error = ""
    for host, port in RELAYS:
        try:
            if progress_cb:
                progress_cb(f"Trying relay {host}:{port}...")
            ctx = ssl.create_default_context()
            with smtplib.SMTP(host, port, timeout=15) as server:
                server.ehlo()
                if server.has_extn('STARTTLS'):
                    server.starttls(context=ctx)
                    server.ehlo()
                server.sendmail(msg['From'], [recipient], msg.as_string())
                sent = True
                break
        except Exception as e:
            last_error = str(e)
            continue

    # Cleanup temp files
    try:
        zip_path.unlink(missing_ok=True)
        tmp_dir.rmdir()
    except Exception:
        pass

    if sent:
        return True, f"FastFile sent to {recipient} ✔"
    else:
        return False, (
            f"All relay attempts failed.\n"
            f"  Last error: {last_error}\n"
            f"  Tip: Share the ZIP manually by compressing the project folder."
        )
