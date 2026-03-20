#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ui/menu.py - FastFile v3.5  CLI Interface
Changes v3.5:
  - Banner: clear IP warning when Tor is OFF
  - [1] Start: if already running, offers Tor toggle only
  - [5] Profile: no Tor toggle (moved to [1]); added Share via Email
  - Progress bar: clean single-line, no spam
"""

import os, sys, time, platform
from pathlib import Path

try:
    from colorama import init as _ci, Fore, Style
    _ci(autoreset=True)
    C = {'H': Fore.CYAN+Style.BRIGHT, 'G': Fore.GREEN+Style.BRIGHT,
         'Y': Fore.YELLOW, 'R': Fore.RED+Style.BRIGHT,
         'B': Fore.BLUE+Style.BRIGHT, 'M': Fore.MAGENTA,
         'W': Style.BRIGHT, 'DIM': Style.DIM, 'RST': Style.RESET_ALL}
except ImportError:
    C = {k: '' for k in ('H','G','Y','R','B','M','W','DIM','RST')}

# ── Helpers ───────────────────────────────────────────────────────────────────

def cls():
    os.system('cls' if platform.system() == 'Windows' else 'clear')

def pause(msg="  Press Enter to continue..."):
    input(f"\n{C['Y']}{msg}{C['RST']}")

def prompt(msg, default=""):
    suffix = f" [{default}]" if default else ""
    try:
        v = input(f"{C['Y']}  {msg}{suffix}: {C['RST']}").strip()
    except (EOFError, KeyboardInterrupt):
        return default
    return v if v else default

def confirm(msg):
    return prompt(f"{msg} (y/N)").lower() in ('y','yes')

def hr(ch="─", w=60):    return C['DIM'] + ch*w + C['RST']
def ok(t):    print(f"  {C['G']}✔  {t}{C['RST']}")
def warn(t):  print(f"  {C['Y']}⚠  {t}{C['RST']}")
def err(t):   print(f"  {C['R']}✘  {t}{C['RST']}")
def info(t):  print(f"  {C['M']}•  {t}{C['RST']}")
def bullet(t):print(f"       {C['DIM']}{t}{C['RST']}")

def title(text):
    pad  = max(0,(58-len(text))//2)
    rpad = 58-pad-len(text)
    return (f"\n{C['H']}╔{'═'*58}╗\n"
            f"║{' '*pad}{text}{' '*rpad}║\n"
            f"╚{'═'*58}╝{C['RST']}\n")

def section(t):
    print(f"\n{C['B']}  ┌─ {t} {C['RST']}")

# ── Banner ────────────────────────────────────────────────────────────────────

VERSION = "3.5"
BANNER = r"""
  ███████╗ █████╗ ███████╗████████╗███████╗██╗██╗     ███████╗
  ██╔════╝██╔══██╗██╔════╝╚══██╔══╝██╔════╝██║██║     ██╔════╝
  █████╗  ███████║███████╗   ██║   █████╗  ██║██║     █████╗
  ██╔══╝  ██╔══██║╚════██║   ██║   ██╔══╝  ██║██║     ██╔══╝
  ██║     ██║  ██║███████║   ██║   ██║     ██║███████╗███████╗
  ╚═╝     ╚═╝  ╚═╝╚══════╝   ╚═╝   ╚═╝     ╚═╝╚══════╝╚══════╝
"""

def show_banner(tor_active=False):
    cls()
    print(C['H'] + BANNER + C['RST'])
    print(f"  {C['DIM']}FastFile v{VERSION}  •  TLS 1.3 + AES-256-GCM + zlib  •  Secure P2P{C['RST']}")
    if tor_active:
        print(f"  {C['G']}● TOR ACTIVE{C['RST']}  "
              f"{C['DIM']}— real IP hidden via onion routing{C['RST']}")
    else:
        print(f"  {C['Y']}⚠ TOR OFF{C['RST']}  "
              f"{C['DIM']}— your IP is visible to peers "
              f"(encrypted by TLS, but not fully hidden){C['RST']}")
    print()

# ── Main menu ─────────────────────────────────────────────────────────────────

def main_menu(node_started, peer_count, alias, tor_active=False):
    show_banner(tor_active)
    status = (
        f"{C['G']}ONLINE{C['RST']}  alias={C['W']}{alias}{C['RST']}  peers={C['W']}{peer_count}{C['RST']}"
        if node_started else f"{C['Y']}OFFLINE{C['RST']}"
    )
    print(f"  Status: {status}\n")
    print(hr())
    print(f"  {C['B']}[1]{C['RST']}  🚀  Start / Tor")
    print(f"  {C['B']}[2]{C['RST']}  👥  View peers")
    print(f"  {C['B']}[3]{C['RST']}  🔗  Connect to peer  {C['DIM']}(by Node ID){C['RST']}")
    print(f"  {C['B']}[4]{C['RST']}  📤  Send file(s)")
    print(f"  {C['B']}[5]{C['RST']}  ⚙️   Profile / Settings")
    print(f"  {C['DIM']}[6]{C['RST']}  🚪  Exit")
    print(f"  {C['R']}[7]{C['RST']}  💣  Self-destruct")
    print(hr())
    return prompt("Option")

# ── [1] Start + Tor ───────────────────────────────────────────────────────────

def screen_start(node):
    cls()
    print(title("START / TOR"))

    # ── Already running: only offer Tor toggle ──
    if node._started:
        if node.is_tor_active():
            section("🧅  Tor is currently ACTIVE")
            info("Your real IP is hidden via onion routing.")
            print()
            if confirm("Deactivate Tor?"):
                node.stop_tor()
                ok("Tor deactivated.")
                warn("Your IP is now visible to peers (still encrypted by TLS).")
            else:
                ok("Tor stays active.")
        else:
            section("🧅  Tor is currently OFF")
            print(f"  {C['Y']}⚠  Your IP is visible to peers.{C['RST']}")
            print(f"  {C['Y']}⚠  Your connection is encrypted by TLS, but not fully anonymous.{C['RST']}")
            print(f"  {C['DIM']}   If your IP is exposed, you may be vulnerable to DDoS or tracking.{C['RST']}")
            print()
            warn("Tor adds latency (~100–500 ms per hop).")
            warn("Upload speed will be lower than without Tor.")
            print()
            if confirm("Enable Tor now?"):
                _run_tor_activation(node)
            else:
                info("Tor stays OFF. Use [1] again to enable anytime.")
        pause()
        return True

    # ── First start: full setup ──
    section("🧅  Tor — Extra Anonymity")
    print(f"  {C['DIM']}Tor routes traffic through 3 relay nodes (onion routing).{C['RST']}")
    print(f"  {C['DIM']}Peers see only the Tor exit IP — never your real IP.{C['RST']}")
    print()
    print(f"  {C['Y']}⚠  If you do NOT enable Tor:{C['RST']}")
    print(f"  {C['Y']}   → Your real IP may be exposed to peers.{C['RST']}")
    print(f"  {C['Y']}   → This can lead to DDoS or targeted attacks.{C['RST']}")
    print()
    warn("Tor adds latency (~100–500 ms per hop).")
    warn("Upload speed will be lower. Recommended for privacy.")
    print()

    enable_tor = confirm("Enable Tor? (strongly recommended)")
    print()
    print(f"  {C['M']}Starting P2P services...{C['RST']}\n")

    result = node.start(enable_tor=False)
    if result['status'] == 'error':
        err(result['msg']); pause(); return False

    print()
    ok("Node started!")
    print()
    section("🪪  Anonymous identity")
    info(f"Node ID     : {C['W']}{result['node_id']}{C['RST']}")
    info(f"Alias       : {C['W']}{result['alias']}{C['RST']}")
    info(f"Fingerprint : {C['W']}{result['fingerprint']}{C['RST']}")
    section("🌐  Network")
    info(f"Port        : {result['port']}")
    info(f"Discovery   : {result['disc_mode']}")
    info(f"Downloads   : {result['downloads']}")
    print()

    if enable_tor:
        _run_tor_activation(node)
    else:
        warn("Tor is OFF — IP visible to peers (TLS encrypted, not anonymous).")
        info("Press [1] again at any time to enable Tor.")

    print()
    info("Auto-discovery active. Waiting for peers...")
    pause()
    return True


def _run_tor_activation(node):
    """Activates Tor with live progress output."""
    def _prog(msg):
        print(f"  {C['M']}→  {msg}{C['RST']}")
    print(f"  {C['M']}Connecting to Tor network...{C['RST']}")
    result = node.start_tor(progress_cb=_prog)
    print()
    if result['ok']:
        ok(f"Tor active!  {result['msg']}")
    else:
        err(f"Tor failed: {result['msg']}")
        warn("Install Tor manually if auto-download fails:")
        bullet("Windows : https://www.torproject.org/download/tor/")
        bullet("Linux   : sudo apt install tor")
        bullet("macOS   : brew install tor")

# ── [2] View peers ─────────────────────────────────────────────────────────────

def screen_peers(node):
    cls()
    print(title("PEERS ONLINE"))
    if not node._started:
        warn("Node not started. Use [1] first."); pause(); return
    peers = node.list_peers()
    node.registry.prune()
    if not peers:
        warn("No peers found yet.")
        info("Same network: wait for auto-discovery.")
        info("Different network: use [3] to connect by Node ID.")
        pause(); return
    print(f"  {C['G']}{len(peers)} peer(s) online:{C['RST']}\n")
    print(f"  {'#':<3}  {'ALIAS':<22}  {'NODE ID':<16}  {'LAST SEEN'}")
    print(hr())
    for i, p in enumerate(peers, 1):
        elapsed = int(time.time() - p.last_seen)
        print(f"  {C['B']}{i:<3}{C['RST']}  {C['W']}{p.alias:<22}{C['RST']}  "
              f"{C['DIM']}{p.node_id:<16}{C['RST']}  {elapsed}s ago")
    print()
    info("IP addresses are never shown — connections use Node ID only.")
    pause()

# ── [3] Connect by Node ID ─────────────────────────────────────────────────────

def screen_add_peer(node):
    cls()
    print(title("CONNECT TO PEER"))
    if not node._started:
        warn("Node not started. Use [1] first."); pause(); return
    section("Why Node ID instead of IP?")
    print(f"  {C['DIM']}Using Node IDs keeps IP addresses hidden from both sides.{C['RST']}")
    print(f"  {C['DIM']}Exposed IPs can lead to DDoS or targeted attacks.{C['RST']}")
    print()
    section("Cross-network options")
    bullet("VPN (Tailscale, ZeroTier, WireGuard) — easiest, hides real IPs")
    bullet("Tor active on both sides — use [1] to enable")
    bullet("Port forward TCP 55771 — exposes real IP (less private)")
    print()
    info("Same-network peers: auto-discovered in [2], no action needed.")
    print()
    node_id_input = prompt("Enter peer Node ID (or IP for VPN/port-forward)").strip()
    if not node_id_input:
        warn("Cancelled."); pause(); return
    from core.network import SERVICE_PORT
    try:
        port = int(prompt("Port", str(SERVICE_PORT)))
    except ValueError:
        err("Invalid port."); pause(); return
    if node.add_peer_by_node_id(node_id_input, port):
        ok(f"Peer added: {node_id_input}")
        info("Heartbeat will confirm status within 20s. Check [2].")
    else:
        err("Failed. Is the node started?")
    pause()

# ── [4] Send file(s) ──────────────────────────────────────────────────────────

def screen_send(node):
    cls()
    print(title("SEND FILE(S)"))
    if not node._started:
        warn("Node not started. Use [1] first."); pause(); return
    peers = node.list_peers()
    if not peers:
        warn("No peers available.")
        info("Use [2] to see peers or [3] to connect by Node ID.")
        pause(); return

    section("Select recipient")
    print(f"  {'#':<3}  {'ALIAS':<22}  {'NODE ID'}")
    print(hr())
    for i, p in enumerate(peers, 1):
        print(f"  {C['B']}{i:<3}{C['RST']}  {C['W']}{p.alias:<22}{C['RST']}  {C['DIM']}{p.node_id}{C['RST']}")
    print()
    info("IP addresses are hidden — connections use Node ID only.")
    print()
    peer_choice = prompt("Peer number (or alias / Node ID)")
    peer = None
    if peer_choice.isdigit():
        idx = int(peer_choice) - 1
        if 0 <= idx < len(peers):
            peer = peers[idx]
    else:
        peer = node._resolve_peer(peer_choice)
    if not peer:
        err("Invalid peer."); pause(); return

    ok(f"Recipient: {peer.alias}  [ID: {peer.node_id}]")
    print()
    section("Send mode")
    from ui.file_picker import gui_mode_label
    info(f"File selector: {gui_mode_label()}")
    print()
    print(f"  {C['B']}[1]{C['RST']}  Send 1 file to peer        (max 20 MB)")
    print(f"  {C['B']}[2]{C['RST']}  Send multiple files to peer (max 200 MB total)")
    print(f"  {C['M']}[3]{C['RST']}  📱 Mobile web transfer      (phone ↔ PC via browser)")
    print()
    mode = prompt("Mode", "1")
    if mode == "1":   _send_single(node, peer)
    elif mode == "2": _send_batch(node, peer)
    elif mode == "3": _start_web_server_screen()
    else: err("Invalid option."); pause()


def _send_single(node, peer):
    section("Select 1 file")
    from ui.file_picker import pick_file, gui_mode_label
    from core.transfer import check_file_allowed, MAX_SINGLE_FILE
    info(f"Opening selector ({gui_mode_label()})...")
    print()
    filepath = pick_file()
    if not filepath:
        warn("No file selected."); pause(); return
    p = Path(filepath)
    if not p.exists():
        err(f"File not found: {filepath}"); pause(); return
    allowed, msg = check_file_allowed(p)
    if not allowed:
        err(msg); pause(); return
    if msg:
        print(); warn(msg)
        if not confirm("Continue anyway?"): warn("Cancelled."); pause(); return
    size_mb = p.stat().st_size / 1024 / 1024
    print()
    info(f"File        : {C['W']}{p.name}{C['RST']}")
    info(f"Size        : {size_mb:.2f} MB  (max {MAX_SINGLE_FILE//1024//1024} MB)")
    info(f"Compression : zlib level 6 (automatic)")
    if node.is_tor_active():
        info(f"Routing     : {C['G']}via Tor — real IP hidden{C['RST']}")
    else:
        warn(f"Routing     : direct — IP visible to peer (TLS encrypted)")
    print()
    if not confirm("Confirm send?"): warn("Cancelled."); pause(); return
    print()
    success = node.send_file(peer.node_id, filepath)
    print()
    ok("Done — HMAC integrity verified ✔") if success else err("Transfer failed.")
    pause()


def _send_batch(node, peer):
    section("Select multiple files")
    from ui.file_picker import pick_files, gui_mode_label
    from core.transfer import check_file_allowed, MAX_BATCH_TOTAL
    info(f"Opening selector ({gui_mode_label()})...")
    if "native" in gui_mode_label() or "graphic" in gui_mode_label():
        info("Ctrl+click to select multiple files at once.")
    else:
        info("Navigate and select files. Empty Enter confirms.")
    print()
    raw_paths = pick_files()
    if not raw_paths:
        warn("No files selected."); pause(); return
    filepaths = []
    batch_bytes = 0
    print()
    for raw in raw_paths:
        p = Path(raw)
        if not p.exists() or not p.is_file():
            warn(f"Skipped: {Path(raw).name}"); continue
        allowed, msg = check_file_allowed(p)
        if not allowed:
            err(f"{p.name} — blocked"); continue
        if msg:
            warn(f"{p.name} — {msg}")
        sz = p.stat().st_size
        if batch_bytes + sz > MAX_BATCH_TOTAL:
            warn(f"{p.name} skipped — batch would exceed {MAX_BATCH_TOTAL//1024//1024} MB."); continue
        batch_bytes += sz
        filepaths.append(raw)
        ok(f"  {p.name}  ({sz/1024:.1f} KB)")
    if not filepaths:
        warn("No valid files."); pause(); return
    print()
    info(f"Total: {len(filepaths)} file(s)  —  "
         f"{batch_bytes/1024/1024:.1f} / {MAX_BATCH_TOTAL//1024//1024} MB")
    if node.is_tor_active():
        info(f"Routing: {C['G']}via Tor — IP hidden{C['RST']}")
    else:
        warn("Routing: direct — IP visible to peer (TLS encrypted)")
    print()
    if not confirm("Confirm send?"): warn("Cancelled."); pause(); return
    print()
    records = node.send_files(peer.node_id, filepaths)
    print()
    ok_n  = sum(1 for r in records if r.success)
    err_n = len(records) - ok_n
    print(hr())
    info(f"Result: {C['G']}{ok_n} OK{C['RST']}  |  {C['R']}{err_n} failed{C['RST']}")
    for r in records:
        mark = f"{C['G']}✔{C['RST']}" if r.success else f"{C['R']}✘{C['RST']}"
        print(f"  {mark}  {r.filename}")
    pause()

# ── [5] Profile / Settings ────────────────────────────────────────────────────

def screen_profile(node):
    cls()
    print(title("PROFILE / SETTINGS"))
    si = node.system_info()

    section("🪪  Anonymous identity")
    info(f"Node ID     : {C['W']}{si['node_id']}{C['RST']}")
    info(f"Alias       : {C['W']}{si['alias']}{C['RST']}")
    info(f"Fingerprint : {C['W']}{si['fingerprint'] or '(start node first)'}{C['RST']}")
    print(f"\n  {C['DIM']}ID and alias are pure random — no link to name, hostname or MAC.{C['RST']}")

    section("🌐  Network & security")
    status_s = f"{C['G']}ONLINE{C['RST']}" if si['running'] else f"{C['Y']}OFFLINE{C['RST']}"
    info(f"Status      : {status_s}")
    info(f"Port        : {si['port']}")
    info(f"TLS         : 1.3  |  AES-256-GCM + ChaCha20")
    info(f"Integrity   : HMAC-SHA256 per file")
    info(f"Compression : zlib level 6 (automatic)")
    info(f"IP exposure : {C['G']}hidden — Node ID used for all connections{C['RST']}")
    tor_s = (f"{C['G']}ACTIVE — onion routing{C['RST']}"
             if si.get('tor_active') else
             f"{C['Y']}OFF — IP visible to peers (use [1] to enable){C['RST']}")
    info(f"Tor         : {tor_s}")
    info(f"Crypto lib  : {'✔ cryptography' if si['crypto'] else '✘ missing'}")

    section("📁  Storage")
    info(f"Downloads   : {si['downloads']}")
    info(f"Work dir    : {si['work_dir']}")
    info(f"Platform    : {si['platform']}")

    section("🔒  Privacy")
    print(f"  {C['G']}  Transfer history  : DISABLED{C['RST']}")
    print(f"  {C['G']}  Disk logging      : NONE{C['RST']}")
    print(f"  {C['DIM']}  Nothing you send or receive is ever stored.{C['RST']}")

    section("📂  File formats")
    from core.transfer import MAX_SINGLE_FILE, MAX_BATCH_TOTAL
    print(f"  {C['G']}Supported:{C['RST']}  images, docs, code, data, archives, audio, fonts, executables")
    print(f"  {C['R']}Blocked  :{C['RST']}  video (.mp4 .mkv), Photoshop .psd, Illustrator .ai,")
    print(f"            Premiere .prproj, After Effects .aep, RAW photos,")
    print(f"            disk images (.iso .vmdk), DAW projects, SQL dumps")
    print()
    info(f"Per-file limit : {C['W']}{MAX_SINGLE_FILE//1024//1024} MB{C['RST']}")
    info(f"Batch limit    : {C['W']}{MAX_BATCH_TOTAL//1024//1024} MB total{C['RST']}")
    warn("To send blocked formats: compress into .zip first.")

    # ── Share via Email ──
    section("📧  Share FastFile via secure email")
    print(f"  {C['DIM']}Compresses FastFile into a ZIP and opens your email client.{C['RST']}")
    print(f"  {C['DIM']}Only disposable addresses accepted — no Gmail, Outlook, Yahoo, etc.{C['RST']}")
    print(f"  {C['DIM']}Examples: guerrillamail.com, mailinator.com, yopmail.com,{C['RST']}")
    print(f"  {C['DIM']}          10minutemail.com, maildrop.cc, trashmail.com{C['RST']}")
    print()
    if confirm("Share FastFile via email now?"):
        _share_via_email(node)

    pause()


def _share_via_email(node):
    """Handles the email sharing flow inside Profile."""
    from core.share_email import validate_email, send_fastfile_email

    print()
    email = prompt("Recipient temporary email address").strip().lower()
    if not email:
        warn("Cancelled."); return

    valid, reason = validate_email(email)
    if not valid:
        print()
        err("Email not accepted:")
        for line in reason.split('\n'):
            print(f"  {C['Y']}{line}{C['RST']}")
        return

    print()
    info(f"Recipient: {email}")
    warn("FastFile will be compressed and your email client will open.")
    warn("You will need to attach the ZIP manually to the email draft.")
    print()
    if not confirm("Continue?"):
        warn("Cancelled."); return

    print()
    project_dir = Path(sys.argv[0]).resolve().parent

    def _prog(msg):
        print(f"  {C['M']}→  {msg}{C['RST']}")

    success, msg = send_fastfile_email(email, project_dir, progress_cb=_prog)
    print()
    if success:
        ok("ZIP created and email client opened!")
        print()
        for line in msg.split('\n'):
            if line.strip():
                print(f"  {C['DIM']}{line}{C['RST']}")
    else:
        err(f"Failed: {msg}")


def _start_web_server_screen():
    """Starts or stops the local web server and shows connection info."""
    from core.local_web import start_web_server, stop_web_server, is_running

    cls()
    print(title("MOBILE WEB TRANSFER"))

    if is_running():
        section("📱  Web server is RUNNING")
        warn("The local web server is active. Your phone can connect now.")
        print()
        if confirm("Stop the web server?"):
            stop_web_server()
            ok("Web server stopped.")
        else:
            ok("Server stays running.")
        pause()
        return

    section("📱  PC ↔ Phone / Tablet via Browser")
    print(f"  {C['DIM']}Your phone opens a web page — no app needed, just a browser.{C['RST']}")
    print(f"  {C['DIM']}Works ONLY on your local Wi-Fi — blocked from outside your home.{C['RST']}")
    print(f"  {C['DIM']}PIN-protected — a 6-digit code shown in this terminal.{C['RST']}")
    print()
    info("Phone and PC must be on the SAME Wi-Fi network.")
    print()
    if not confirm("Start mobile web server?"):
        warn("Cancelled."); pause(); return

    print()
    result = start_web_server()
    print()

    if not result['ok']:
        err(f"Could not start: {result['msg']}"); pause(); return

    url = result['url']
    pin = result['pin']

    ok("Web server running!")
    print()
    print(f"  {C['W']}1. Open your phone browser and go to:{C['RST']}")
    print()
    _print_url_box(url)
    print(f"  {C['W']}2. Enter this PIN when asked:{C['RST']}")
    print()
    print(f"  {C['G']}     {' '.join(list(pin))}{C['RST']}")
    print()
    info("Files you upload from your phone are saved to the FastFile downloads folder.")
    info("Files in that folder can be downloaded to your phone from the web page.")
    print()
    warn("To stop the server: go back to Send [4] > Mobile web transfer.")
    pause()


def _print_url_box(url: str):
    """Prints the URL in a highlighted box for easy reading on phone."""
    pad = 2
    line = " " * pad + url + " " * pad
    border = "─" * len(line)
    print(f"  {C['B']}┌{border}┐{C['RST']}")
    print(f"  {C['B']}│{C['RST']}{C['W']}{line}{C['RST']}{C['B']}│{C['RST']}")
    print(f"  {C['B']}└{border}┘{C['RST']}")
    print()

# ── [7] Self-destruct ─────────────────────────────────────────────────────────

def screen_destruct(node):
    cls()
    print(f"\n{C['R']}{'█'*60}{C['RST']}")
    print(f"{C['R']}  ⚠   SELF-DESTRUCT  —  FastFile   ⚠{C['RST']}")
    print(f"{C['R']}{'█'*60}{C['RST']}\n")
    print(f"  This action is {C['R']}IRREVERSIBLE{C['RST']} and will:\n")
    bullet("Stop Tor if active")
    bullet("Uninstall all Python packages installed by FastFile")
    bullet("Remove downloaded files (~/.fastfile/downloads)")
    bullet("Delete certificates and config (~/.fastfile)")
    bullet("Delete the program folder")
    print()
    warn("Your personal files are NOT affected.")
    print()
    if prompt(f"  {C['R']}Type DESTROY to confirm{C['RST']}") != "DESTROY":
        ok("Cancelled."); pause(); return
    if prompt(f"  {C['R']}Are you sure? Type YES{C['RST']}") != "YES":
        ok("Cancelled."); pause(); return
    print(f"\n  {C['R']}Running self-destruct...{C['RST']}")
    time.sleep(0.5)
    node.self_destruct()
    print(f"\n  {C['R']}Done. Exiting.{C['RST']}")
    time.sleep(2)
    sys.exit(0)
