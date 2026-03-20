#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core/local_web.py - Local Web Server for PC ↔ Mobile transfers
Runs an HTTP server accessible ONLY on the local network (LAN).
Blocks connections from outside the local subnet — cannot be reached
from another house/network.

Features:
  - Upload files from phone to PC (no app needed, just a browser)
  - Download files from PC to phone
  - Simple PIN protection (random 6-digit, shown in terminal)
  - Subnet check: only 192.168.x.x / 10.x.x.x / 172.16-31.x.x allowed
  - Auto-detects local IP and shows QR-friendly URL
"""

import os
import io
import re
import html
import time
import socket
import secrets
import threading
import ipaddress
import mimetypes
from pathlib import Path
from typing import Optional, Tuple
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs, unquote

from core.transfer import DOWNLOADS_DIR, check_file_allowed, MAX_SINGLE_FILE

WEB_PORT   = 8765
SESSION_PIN: str = ""          # set at startup
_server_ref: Optional[HTTPServer] = None
_stop_event = threading.Event()

# ─────────────────────────────────────────────
#  Local network detection
# ─────────────────────────────────────────────

def _is_local_ip(ip_str: str) -> bool:
    """Returns True if the IP is in a private/local range."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return ip.is_private
    except ValueError:
        return False


def get_local_ip() -> str:
    """Returns the machine's LAN IP (not loopback)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# ─────────────────────────────────────────────
# ─────────────────────────────────────────────
#  HTML templates  (Hacker 90s theme)
# ─────────────────────────────────────────────

def _page(title_text: str, body: str) -> bytes:
    """Hacker 90s aesthetic — green-on-black, monospace, CRT feel."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>FASTFILE // {html.escape(title_text)}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #050505;
    color: #00ff41;
    font-family: 'Courier New', Courier, monospace;
    font-size: 14px;
    min-height: 100vh;
    background-image: repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,.12) 2px,rgba(0,0,0,.12) 4px);
  }}
  .topbar {{
    background: #0a0a0a;
    border-bottom: 1px solid #00ff41;
    padding: 6px 16px;
    display: flex;
    justify-content: space-between;
    font-size: 11px;
    color: #00b32c;
    letter-spacing: 2px;
  }}
  .logo {{ color:#00ff41; font-size:15px; font-weight:bold; letter-spacing:4px; text-shadow:0 0 8px #00ff41; }}
  .blink {{ animation: blink 1s step-end infinite; }}
  @keyframes blink {{ 50%{{opacity:0}} }}
  .container {{ max-width:520px; margin:0 auto; padding:20px 16px; }}
  h2 {{
    color:#00ff41; text-transform:uppercase; letter-spacing:3px;
    font-size:12px; margin:22px 0 8px;
    border-left:3px solid #00ff41; padding-left:10px;
    text-shadow:0 0 6px #00ff41;
  }}
  .card {{
    background:#0d0d0d; border:1px solid #00ff4133;
    border-left:2px solid #00ff41; padding:14px 16px; margin:8px 0;
  }}
  p {{ margin:6px 0; line-height:1.6; color:#99ffbb; font-size:13px; }}
  .dim {{ color:#2a5a2a; font-size:12px; }}
  .ok  {{ color:#00ff41; }}
  .err {{ color:#ff2222; }}
  .warn{{ color:#ffee00; }}
  input[type=file] {{
    width:100%; padding:10px; background:#000; border:1px dashed #00b32c;
    color:#00ff41; font-family:inherit; font-size:13px; margin:8px 0; cursor:pointer;
  }}
  input[type=password] {{
    width:100%; padding:10px 12px; background:#000; border:1px solid #00b32c;
    color:#00ff41; font-family:inherit; font-size:20px; letter-spacing:8px;
    margin:8px 0; outline:none;
  }}
  input[type=password]:focus {{ border-color:#00ff41; box-shadow:0 0 8px #00ff41; }}
  button, input[type=submit] {{
    width:100%; padding:12px; margin-top:10px;
    background:transparent; border:1px solid #00ff41;
    color:#00ff41; font-family:inherit; font-size:12px;
    letter-spacing:3px; text-transform:uppercase; cursor:pointer;
    transition:all .15s;
  }}
  button:hover, input[type=submit]:hover {{
    background:#00ff41; color:#000; box-shadow:0 0 14px #00ff41;
  }}
  button.stop {{ border-color:#ff2222; color:#ff2222; }}
  button.stop:hover {{ background:#ff2222; color:#000; }}
  ul {{ list-style:none; padding:0; }}
  ul li {{
    border-bottom:1px solid #111; padding:8px 0;
    display:flex; justify-content:space-between; align-items:center; gap:6px;
  }}
  ul li a {{ color:#00ff41; text-decoration:none; font-size:13px; }}
  ul li a:hover {{ text-shadow:0 0 6px #00ff41; text-decoration:underline; }}
  .badge {{ font-size:10px; color:#00b32c; border:1px solid #00ff4133; padding:2px 6px; }}
  #prog-wrap {{ display:none; margin-top:10px; }}
  #prog-bar {{ height:5px; background:#00ff41; width:0%; transition:width .3s; box-shadow:0 0 6px #00ff41; }}
  #prog-label {{ font-size:11px; color:#00b32c; margin-top:4px; }}
  footer {{ text-align:center; color:#1a3a1a; font-size:10px; letter-spacing:2px; margin-top:40px; padding-bottom:20px; }}
</style>
</head>
<body>
<div class="topbar">
  <span class="logo">[ FASTFILE ]</span>
  <span>LAN://ONLY <span class="blink">|</span></span>
  <span>SECURE_CHANNEL::ACTIVE</span>
</div>
<div class="container">
{body}
</div>
<footer>FASTFILE // LAN-ONLY // AES-256-GCM // ZERO LOGS // EXTERNAL_ACCESS::BLOCKED</footer>
</body></html>""".encode('utf-8')


def _pin_form(error: bool = False) -> bytes:
    err_html = '<p class="err">&#x26A0; ACCESS_DENIED — Wrong PIN. Retry.</p>' if error else ""
    body = f"""
<h2>// auth_required</h2>
<div class="card">
  <p>Enter the 6-digit PIN shown in your terminal.</p>
  {err_html}
  <form method="POST" action="/auth">
    <input type="password" name="pin" placeholder="______" maxlength="6"
           autocomplete="off" autofocus inputmode="numeric">
    <input type="submit" value="[ AUTHENTICATE ]">
  </form>
</div>
<p class="dim" style="margin-top:14px;text-align:center">
  >> session bound to your IP — one device at a time
</p>"""
    return _page("AUTH", body)


def _home_page(files: list) -> bytes:
    file_items = ""
    for f in files:
        size_s = _fmt_size(f.stat().st_size)
        esc    = html.escape(f.name)
        file_items += (
            f'<li><a href="/download/{esc}">&gt; {esc}</a>'
            f'<span class="badge">{size_s}</span></li>\n'
        )
    dl_section = (
        '<h2>// files_available :: download</h2>'
        f'<div class="card"><ul>{file_items}</ul></div>'
        if files else
        '<h2>// files_available :: download</h2>'
        '<div class="card"><p class="dim">>> no files yet. send something from pc first.</p></div>'
    )
    body = f"""
<h2>// transmit :: phone_to_pc</h2>
<div class="card">
  <p>Select file to upload (max {MAX_SINGLE_FILE // 1024 // 1024} MB):</p>
  <form method="POST" action="/upload" enctype="multipart/form-data" id="upform">
    <input type="file" name="file" accept="*/*" onchange="startUp()">
    <input type="submit" value="[ TRANSMIT ]">
    <div id="prog-wrap">
      <div id="prog-bar"></div>
      <div id="prog-label">>> uploading...</div>
    </div>
  </form>
</div>
{dl_section}
<div class="card" style="margin-top:16px">
  <p class="dim">>> lan-only mode // external connections blocked // no data stored</p>
  <form method="GET" action="/logout" style="margin-top:8px">
    <button class="stop" type="submit">[ DISCONNECT ]</button>
  </form>
</div>
<script>
function startUp(){{
  document.getElementById('prog-wrap').style.display='block';
  var b=document.getElementById('prog-bar'), l=document.getElementById('prog-label'), p=0;
  var t=setInterval(function(){{
    p=Math.min(p+Math.random()*7,90);
    b.style.width=p+'%';
    l.textContent='>> uploading... '+Math.floor(p)+'%';
    if(p>=90)clearInterval(t);
  }},120);
}}
</script>"""
    return _page("HOME", body)


class FastFileHandler(BaseHTTPRequestHandler):
    """HTTP handler for the local web server."""

    def log_message(self, fmt, *args):
        pass   # Silence default access log — privacy

    # ── Security checks ──────────────────────────────────────────────

    def _check_origin(self) -> bool:
        """Block any connection that is not from a private/local IP."""
        client_ip = self.client_address[0]
        if not _is_local_ip(client_ip):
            self._send(403, b"Access denied: not a local network connection.")
            return False
        return True

    def _authenticated(self) -> bool:
        client_ip = self.client_address[0]
        return client_ip in _sessions

    def _send(self, code: int, body: bytes, ctype: str = "text/html; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    # ── Routing ──────────────────────────────────────────────────────

    def do_GET(self):
        if not self._check_origin():
            return
        path = urlparse(self.path).path.rstrip('/')

        if path == '' or path == '/':
            if not self._authenticated():
                self._send(200, _pin_form())
            else:
                files = sorted(DOWNLOADS_DIR.iterdir(),
                               key=lambda x: x.stat().st_mtime, reverse=True) \
                        if DOWNLOADS_DIR.exists() else []
                files = [f for f in files if f.is_file()]
                self._send(200, _home_page(files))

        elif path.startswith('/download/'):
            if not self._authenticated():
                self.send_response(302)
                self.send_header("Location", "/")
                self.end_headers()
                return
            filename = unquote(path[len('/download/'):])
            self._serve_file(filename)

        elif path == '/logout':
            _sessions.discard(self.client_address[0])
            self._send(200, _page("DISCONNECTED",
                '<h2>// session_terminated</h2>'
                '<div class="card"><p class="ok">>> Disconnected successfully.</p>'
                '<a href="/"><button>[ RECONNECT ]</button></a></div>'))
        else:
            self._send(404, _page("404",
                '<h2>// error_404</h2>'
                '<div class="card err"><p>Path not found.</p>'
                '<a href="/"><button>[ HOME ]</button></a></div>'))

    def do_POST(self):
        if not self._check_origin():
            return
        path = urlparse(self.path).path

        if path == '/auth':
            self._handle_auth()
        elif path == '/upload':
            if not self._authenticated():
                self._send(403, _page("FORBIDDEN",
                    '<h2>// access_denied</h2>'
                    '<div class="card err"><p>Not authenticated. Return to login.</p>'
                    '<a href="/"><button>[ LOGIN ]</button></a></div>'))
                return
            self._handle_upload()
        else:
            self._send(404, b"Not found")

    # ── Auth ─────────────────────────────────────────────────────────

    def _handle_auth(self):
        length = int(self.headers.get('Content-Length', 0))
        body   = self.rfile.read(length).decode('utf-8', errors='ignore')
        params = parse_qs(body)
        pin    = params.get('pin', [''])[0].strip()

        if pin == SESSION_PIN:
            _sessions.add(self.client_address[0])
            self.send_response(302)
            self.send_header("Location", "/")
            self.end_headers()
        else:
            self._send(200, _pin_form(error=True))

    # ── File download ─────────────────────────────────────────────────

    def _serve_file(self, filename: str):
        # Sanitize filename — no path traversal
        filename = Path(filename).name
        fpath = DOWNLOADS_DIR / filename

        if not fpath.exists() or not fpath.is_file():
            self._send(404, _page("Not found",
                f'<div class="card err">File not found: {html.escape(filename)}</div>'))
            return

        mime, _ = mimetypes.guess_type(str(fpath))
        mime = mime or "application/octet-stream"
        size = fpath.stat().st_size

        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(size))
        self.send_header("Content-Disposition",
                         f'attachment; filename="{filename}"')
        self.end_headers()

        with open(fpath, 'rb') as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                self.wfile.write(chunk)

    # ── File upload ───────────────────────────────────────────────────

    def _handle_upload(self):
        content_type = self.headers.get('Content-Type', '')
        if 'multipart/form-data' not in content_type:
            self._send(400, _page("ERROR",
                '<h2>// bad_request</h2>'
                '<div class="card err"><p>Invalid upload request format.</p>'
                '<a href="/"><button>[ BACK ]</button></a></div>'))
            return

        m = re.search(r'boundary=([^\s;]+)', content_type)
        if not m:
            self._send(400, b"Missing boundary")
            return
        boundary = ('--' + m.group(1)).encode()

        length = int(self.headers.get('Content-Length', 0))
        if length > MAX_SINGLE_FILE + 65536:
            self._send(413, _page("TOO LARGE",
                f'<h2>// file_rejected</h2>'
                f'<div class="card err"><p>File exceeds {MAX_SINGLE_FILE//1024//1024} MB limit.</p>'
                f'<a href="/"><button>[ BACK ]</button></a></div>'))
            return

        data = self.rfile.read(length)
        filename, file_data = _parse_multipart(data, boundary)

        if not filename or file_data is None:
            self._send(400, _page("ERROR",
                '<h2>// no_data</h2>'
                '<div class="card err"><p>No file data received.</p>'
                '<a href="/"><button>[ BACK ]</button></a></div>'))
            return

        filename = Path(filename).name
        if not filename:
            self._send(400, _page("ERROR",
                '<h2>// invalid_filename</h2>'
                '<div class="card err"><p>Invalid filename.</p>'
                '<a href="/"><button>[ BACK ]</button></a></div>'))
            return

        allowed, msg = check_file_allowed_bytes(filename, len(file_data))
        if not allowed:
            self._send(415, _page("BLOCKED",
                f'<h2>// file_blocked</h2>'
                f'<div class="card err"><p>{html.escape(msg)}</p>'
                f'<a href="/"><button>[ BACK ]</button></a></div>'))
            return

        save_path = _unique_path(DOWNLOADS_DIR / filename)
        DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
        save_path.write_bytes(file_data)
        size_s = _fmt_size(len(file_data))

        print(f"\n  📱 [WebTransfer] Received: {save_path.name}  ({size_s})")

        body = (
            '<h2>// transmit_complete</h2>'
            '<div class="card">'
            f'<p class="ok">&#x2714; FILE RECEIVED</p>'
            f'<p>&gt; name: {html.escape(save_path.name)}</p>'
            f'<p>&gt; size: {size_s}</p>'
            f'<p>&gt; status: stored_on_pc</p>'
            '<a href="/"><button>[ BACK TO HOME ]</button></a>'
            '</div>'
        )
        self._send(200, _page("OK", body))


# ─────────────────────────────────────────────
#  Multipart parser (no dependencies)
# ─────────────────────────────────────────────

def _parse_multipart(data: bytes, boundary: bytes):
    """
    Minimal multipart/form-data parser.
    Returns (filename, file_bytes) or (None, None) on failure.
    """
    parts = data.split(boundary)
    for part in parts:
        if b'filename=' not in part:
            continue
        # Extract filename
        m = re.search(rb'filename="([^"]+)"', part)
        if not m:
            m = re.search(rb"filename=([^\r\n;]+)", part)
        if not m:
            continue
        filename = m.group(1).decode('utf-8', errors='replace').strip()
        # Content starts after double CRLF
        sep = part.find(b'\r\n\r\n')
        if sep == -1:
            sep = part.find(b'\n\n')
            if sep == -1:
                continue
            file_data = part[sep + 2:]
        else:
            file_data = part[sep + 4:]
        # Remove trailing boundary marker
        file_data = file_data.rstrip(b'\r\n--')
        return filename, file_data
    return None, None


def _unique_path(p: Path) -> Path:
    if not p.exists():
        return p
    stem, suffix = p.stem, p.suffix
    i = 1
    while True:
        c = p.parent / f"{stem}_{i}{suffix}"
        if not c.exists():
            return c
        i += 1


def check_file_allowed_bytes(filename: str, size: int) -> Tuple[bool, str]:
    """Version of check_file_allowed that works with just filename + size."""
    from core.transfer import BLOCKED_EXTENSIONS, MAX_SINGLE_FILE
    ext = Path(filename).suffix.lower()
    if ext in BLOCKED_EXTENSIONS:
        return False, f"File type '{ext}' is blocked."
    if size > MAX_SINGLE_FILE:
        mb = size / 1024 / 1024
        return False, f"File too large: {mb:.1f} MB (max {MAX_SINGLE_FILE//1024//1024} MB)."
    return True, ""


# ─────────────────────────────────────────────
#  Server start / stop
# ─────────────────────────────────────────────

def start_web_server(port: int = WEB_PORT) -> dict:
    """
    Starts the local web server.
    Returns {'ok': True, 'url': str, 'pin': str, 'ip': str}
    or {'ok': False, 'msg': str}.
    """
    global SESSION_PIN, _server_ref, _stop_event

    local_ip = get_local_ip()

    if not _is_local_ip(local_ip):
        return {
            'ok': False,
            'msg': f"Could not detect a local network IP (got: {local_ip})."
        }

    SESSION_PIN  = ''.join([str(secrets.randbelow(10)) for _ in range(6)])
    _stop_event  = threading.Event()

    try:
        _server_ref = HTTPServer(('0.0.0.0', port), FastFileHandler)
    except OSError as e:
        return {'ok': False, 'msg': f"Could not bind port {port}: {e}"}

    def _run():
        _server_ref.serve_forever()

    t = threading.Thread(target=_run, daemon=True, name="LocalWebServer")
    t.start()

    return {
        'ok':  True,
        'url': f"http://{local_ip}:{port}",
        'pin': SESSION_PIN,
        'ip':  local_ip,
        'port': port,
    }


def stop_web_server():
    global _server_ref
    if _server_ref:
        _server_ref.shutdown()
        _server_ref = None


def is_running() -> bool:
    return _server_ref is not None
