#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core/local_web.py - Local HTTP server for PC <-> Phone transfers.
Plain HTTP (not HTTPS) — correct for LAN use. PIN protects access.
Blocks all connections from outside the local network.
"""

import os
import re
import html
import socket
import secrets
import threading
import ipaddress
import mimetypes
from pathlib import Path
from typing import Optional, Tuple
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs, unquote

from core.transfer import DOWNLOADS_DIR, MAX_SINGLE_FILE

WEB_PORT      = 8765
SESSION_PIN   = ""
_server_ref: Optional[HTTPServer] = None
_sessions: set = set()

# ─────────────────────────────────────────────
#  Network helpers
# ─────────────────────────────────────────────

def _is_local(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip).is_private
    except ValueError:
        return False

def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def get_all_local_ips() -> list:
    """Returns all non-loopback local IPs."""
    ips = []
    try:
        import netifaces
        for iface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(iface)
            if netifaces.AF_INET in addrs:
                for a in addrs[netifaces.AF_INET]:
                    ip = a.get('addr', '')
                    if ip and not ip.startswith('127.') and not ip.startswith('169.254.'):
                        ips.append(ip)
    except Exception:
        fallback = get_local_ip()
        if fallback != '127.0.0.1':
            ips.append(fallback)
    return list(dict.fromkeys(ips))

# ─────────────────────────────────────────────
#  HTML — hacker 90s theme (compact)
# ─────────────────────────────────────────────

_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{background:#050505;color:#00ff41;font-family:'Courier New',monospace;font-size:14px;
     background-image:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,.1) 2px,rgba(0,0,0,.1) 4px)}
.bar{background:#0a0a0a;border-bottom:1px solid #00ff41;padding:6px 14px;display:flex;
     justify-content:space-between;font-size:11px;color:#00b32c;letter-spacing:2px}
.logo{color:#00ff41;font-size:14px;font-weight:bold;letter-spacing:4px;text-shadow:0 0 8px #00ff41}
.blink{animation:blink 1s step-end infinite}
@keyframes blink{50%{opacity:0}}
.wrap{max-width:500px;margin:0 auto;padding:18px 14px}
h2{color:#00ff41;text-transform:uppercase;letter-spacing:3px;font-size:12px;
   margin:20px 0 8px;border-left:3px solid #00ff41;padding-left:10px;text-shadow:0 0 6px #00ff41}
.card{background:#0d0d0d;border:1px solid #00ff4133;border-left:2px solid #00ff41;padding:14px;margin:8px 0}
p{margin:5px 0;line-height:1.6;color:#99ffbb;font-size:13px}
.dim{color:#2a5a2a;font-size:12px}.ok{color:#00ff41}.err{color:#ff2222}.warn{color:#ffee00}
input[type=file]{width:100%;padding:10px;background:#000;border:1px dashed #00b32c;
   color:#00ff41;font-family:inherit;font-size:13px;margin:8px 0;cursor:pointer}
input[type=password]{width:100%;padding:10px;background:#000;border:1px solid #00b32c;
   color:#00ff41;font-family:inherit;font-size:20px;letter-spacing:8px;margin:8px 0;outline:none}
input[type=password]:focus{border-color:#00ff41;box-shadow:0 0 8px #00ff41}
button,input[type=submit]{width:100%;padding:12px;margin-top:10px;background:transparent;
   border:1px solid #00ff41;color:#00ff41;font-family:inherit;font-size:12px;
   letter-spacing:3px;text-transform:uppercase;cursor:pointer;transition:all .15s}
button:hover,input[type=submit]:hover{background:#00ff41;color:#000;box-shadow:0 0 12px #00ff41}
button.stop{border-color:#ff2222;color:#ff2222}
button.stop:hover{background:#ff2222;color:#000}
ul{list-style:none;padding:0}
li{border-bottom:1px solid #111;padding:8px 0;display:flex;justify-content:space-between;align-items:center;gap:6px}
li a{color:#00ff41;text-decoration:none;font-size:13px}
li a:hover{text-shadow:0 0 6px #00ff41;text-decoration:underline}
.badge{font-size:10px;color:#00b32c;border:1px solid #00ff4133;padding:2px 6px}
#pw{display:none;margin-top:8px}
#pb{height:5px;background:#00ff41;width:0%;transition:width .3s;box-shadow:0 0 6px #00ff41}
#pl{font-size:11px;color:#00b32c;margin-top:4px}
footer{text-align:center;color:#1a3a1a;font-size:10px;letter-spacing:2px;margin-top:30px;padding-bottom:16px}
"""

def _page(title: str, body: str) -> bytes:
    return (
        f'<!DOCTYPE html><html lang="en"><head>'
        f'<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>FASTFILE // {html.escape(title)}</title>'
        f'<style>{_CSS}</style></head><body>'
        f'<div class="bar"><span class="logo">[ FASTFILE ]</span>'
        f'<span>LAN_ONLY <span class="blink">|</span></span>'
        f'<span>SECURE::CHANNEL</span></div>'
        f'<div class="wrap">{body}</div>'
        f'<footer>FASTFILE // HTTP-LAN // PIN-PROTECTED // NO_LOGS</footer>'
        f'</body></html>'
    ).encode('utf-8')

def _pin_page(error: bool = False) -> bytes:
    err = '<p class="err">&#x26A0; Wrong PIN — try again.</p>' if error else ''
    body = (
        '<h2>// auth_required</h2>'
        '<div class="card">'
        f'<p>Enter the 6-digit PIN from your terminal.</p>{err}'
        '<form method="POST" action="/auth">'
        '<input type="password" name="pin" placeholder="______" maxlength="6" '
        'autocomplete="off" autofocus inputmode="numeric">'
        '<input type="submit" value="[ AUTHENTICATE ]">'
        '</form></div>'
        '<p class="dim" style="margin-top:12px;text-align:center">'
        '>> one session per device</p>'
    )
    return _page("AUTH", body)

def _home_page(files: list) -> bytes:
    max_mb = MAX_SINGLE_FILE // 1024 // 1024
    items = ''.join(
        f'<li><a href="/dl/{html.escape(f.name)}">&gt; {html.escape(f.name)}</a>'
        f'<span class="badge">{_fmt(f.stat().st_size)}</span></li>'
        for f in files
    )
    dl = (
        '<h2>// files :: download_to_phone</h2>'
        f'<div class="card"><ul>{items}</ul></div>'
        if files else
        '<h2>// files :: download_to_phone</h2>'
        '<div class="card"><p class="dim">>> no files yet</p></div>'
    )
    body = (
        '<h2>// upload :: phone_to_pc</h2>'
        '<div class="card">'
        f'<p>Select file (max {max_mb} MB):</p>'
        '<form method="POST" action="/up" enctype="multipart/form-data" id="uf">'
        '<input type="file" name="file" accept="*/*" id="fi">'
        '<div id="btn-wrap">'
        '<input type="submit" id="sub" value="[ SELECT A FILE FIRST ]" disabled>'
        '</div>'
        '<div id="pw" style="display:none;margin-top:10px">'
        '<div id="pb" style="height:5px;background:#00ff41;width:100%;'
        'animation:pulse 1s ease-in-out infinite;box-shadow:0 0 6px #00ff41"></div>'
        '<div id="pl" style="font-size:11px;color:#00b32c;margin-top:4px">'
        '>> uploading — please wait...</div>'
        '</div>'
        '</form>'
        '<style>@keyframes pulse{0%,100%{opacity:.4}50%{opacity:1}}</style>'
        '</div>'
        + dl +
        '<div class="card" style="margin-top:14px">'
        '<p class="dim">>> lan-only // no external access // pin-protected</p>'
        '<form method="GET" action="/out" style="margin-top:8px">'
        '<button class="stop" type="submit">[ DISCONNECT ]</button>'
        '</form></div>'
        '<script>'
        'var fi=document.getElementById("fi");'
        'var sub=document.getElementById("sub");'
        'var pw=document.getElementById("pw");'
        'fi.addEventListener("change",function(){'
        '  if(fi.files.length>0){'
        '    sub.value="[ TRANSMIT: "+fi.files[0].name+" ]";'
        '    sub.disabled=false;'
        '  }'
        '});'
        'document.getElementById("uf").addEventListener("submit",function(){'
        '  sub.disabled=true;'
        '  sub.value="[ TRANSMITTING... ]";'
        '  pw.style.display="block";'
        '});'
        '</script>'
    )
    return _page("HOME", body)

def _fmt(n: int) -> str:
    if n >= 1<<20: return f"{n/(1<<20):.1f}MB"
    if n >= 1<<10: return f"{n/(1<<10):.1f}KB"
    return f"{n}B"

# ─────────────────────────────────────────────
#  Request handler
# ─────────────────────────────────────────────

class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass  # silence logs

    def handle(self):
        """Override to suppress ConnectionResetError on Windows."""
        try:
            super().handle()
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
            pass  # client disconnected — normal on mobile browsers

    def _ok(self, body: bytes, ct="text/html; charset=utf-8"):
        self.send_response(200)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, to="/"):
        self.send_response(302)
        self.send_header("Location", to)
        self.end_headers()

    def _local_only(self) -> bool:
        if not _is_local(self.client_address[0]):
            self._ok(b"Access denied.", "text/plain")
            return False
        return True

    def _authed(self) -> bool:
        return self.client_address[0] in _sessions

    def do_GET(self):
        if not self._local_only(): return
        p = urlparse(self.path).path.rstrip('/') or '/'

        if p == '/':
            self._ok(_pin_page() if not self._authed() else _home_page(self._files()))
        elif p.startswith('/dl/'):
            if not self._authed(): self._redirect(); return
            self._serve(unquote(p[4:]))
        elif p == '/out':
            _sessions.discard(self.client_address[0])
            self._redirect()
        else:
            self._ok(_page("404", '<div class="card err"><p>Not found.</p>'
                           '<a href="/"><button>[ HOME ]</button></a></div>'))

    def do_POST(self):
        if not self._local_only(): return
        p = urlparse(self.path).path
        if p == '/auth':   self._auth()
        elif p == '/up':
            if not self._authed():
                self._redirect(); return
            self._upload()
        else:
            self._ok(b"Not found.", "text/plain")

    def _files(self):
        if not DOWNLOADS_DIR.exists(): return []
        return sorted(
            [f for f in DOWNLOADS_DIR.iterdir() if f.is_file()],
            key=lambda x: x.stat().st_mtime, reverse=True
        )

    def _auth(self):
        n = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(n).decode('utf-8', errors='ignore')
        pin = parse_qs(body).get('pin', [''])[0].strip()
        if pin == SESSION_PIN:
            _sessions.add(self.client_address[0])
            self._redirect()
        else:
            self._ok(_pin_page(error=True))

    def _serve(self, filename: str):
        filename = Path(filename).name
        fpath = DOWNLOADS_DIR / filename
        if not fpath.exists() or not fpath.is_file():
            self._ok(_page("404", '<div class="card err"><p>File not found.</p>'
                           '<a href="/"><button>[ BACK ]</button></a></div>'))
            return
        mime = mimetypes.guess_type(str(fpath))[0] or "application/octet-stream"
        data = fpath.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(data)

    def _upload(self):
        ct = self.headers.get('Content-Type', '')
        m  = re.search(r'boundary=([^\s;]+)', ct)
        if not m:
            self._ok(_page("ERR", '<div class="card err"><p>Bad request.</p>'
                           '<a href="/"><button>[ BACK ]</button></a></div>')); return
        boundary = ('--' + m.group(1)).encode()
        n = int(self.headers.get('Content-Length', 0))
        if n > MAX_SINGLE_FILE + 65536:
            self._ok(_page("TOO LARGE",
                f'<div class="card err"><p>File exceeds {MAX_SINGLE_FILE//1024//1024} MB.</p>'
                '<a href="/"><button>[ BACK ]</button></a></div>')); return
        data = self.rfile.read(n)
        filename, fdata = _parse_mp(data, boundary)
        if not filename or fdata is None:
            self._ok(_page("ERR", '<div class="card err"><p>No file received.</p>'
                           '<a href="/"><button>[ BACK ]</button></a></div>')); return
        filename = Path(filename).name
        from core.transfer import BLOCKED_EXTENSIONS
        if Path(filename).suffix.lower() in BLOCKED_EXTENSIONS:
            self._ok(_page("BLOCKED",
                f'<div class="card err"><p>File type blocked.</p>'
                '<a href="/"><button>[ BACK ]</button></a></div>')); return
        DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
        sp = _unique(DOWNLOADS_DIR / filename)
        sp.write_bytes(fdata)
        sz = _fmt(len(fdata))
        print(f"\n  📱 [WebTransfer] Received: {sp.name}  ({sz})")
        body = (
            '<h2>// transmit_complete</h2>'
            '<div class="card">'
            f'<p class="ok">&#x2714; FILE RECEIVED</p>'
            f'<p>&gt; {html.escape(sp.name)}</p>'
            f'<p>&gt; {sz}</p>'
            '<a href="/"><button>[ BACK ]</button></a>'
            '</div>'
        )
        self._ok(_page("OK", body))

# ─────────────────────────────────────────────
#  Multipart parser
# ─────────────────────────────────────────────

def _parse_mp(data: bytes, boundary: bytes):
    for part in data.split(boundary):
        if b'filename=' not in part: continue
        m = re.search(rb'filename="([^"]+)"', part) or re.search(rb'filename=([^\r\n;]+)', part)
        if not m: continue
        fname = m.group(1).decode('utf-8', errors='replace').strip()
        sep = part.find(b'\r\n\r\n')
        if sep == -1:
            sep = part.find(b'\n\n')
            if sep == -1: continue
            fdata = part[sep+2:]
        else:
            fdata = part[sep+4:]
        fdata = fdata.rstrip(b'\r\n--')
        return fname, fdata
    return None, None

def _unique(p: Path) -> Path:
    if not p.exists(): return p
    i = 1
    while True:
        c = p.parent / f"{p.stem}_{i}{p.suffix}"
        if not c.exists(): return c
        i += 1

# ─────────────────────────────────────────────
#  Start / stop
# ─────────────────────────────────────────────

def start_web_server(port: int = WEB_PORT, chosen_ip: str = None) -> dict:
    global SESSION_PIN, _server_ref, _sessions
    local_ip  = chosen_ip or get_local_ip()
    _sessions = set()
    if not _is_local(local_ip):
        return {'ok': False, 'msg': f"{local_ip} is not a local network IP."}
    SESSION_PIN = ''.join(str(secrets.randbelow(10)) for _ in range(6))
    for p in [port, port+1, port+2]:
        try:
            srv = HTTPServer(('0.0.0.0', p), _Handler)
            _server_ref = srv
            threading.Thread(target=srv.serve_forever, daemon=True,
                             name="WebServer").start()
            return {'ok': True, 'url': f"http://{local_ip}:{p}",
                    'pin': SESSION_PIN, 'ip': local_ip, 'port': p}
        except OSError:
            continue
    return {'ok': False, 'msg': f"Could not bind port {port}."}

def stop_web_server():
    global _server_ref
    if _server_ref:
        _server_ref.shutdown()
        _server_ref = None

def is_running() -> bool:
    return _server_ref is not None
