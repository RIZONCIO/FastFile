#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ui/menu.py - FastFile v3.4  CLI Interface (English)
Menu: Start+Tor | Peers | Connect | Send | Profile+Formats | Exit | Self-destruct
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


# ── Terminal helpers ───────────────────────────────────────────────────────────

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
    return prompt(f"{msg} (y/N)").lower() in ('y', 'yes')

def hr(ch="─", w=60):   return C['DIM'] + ch * w + C['RST']
def ok(t):    print(f"  {C['G']}✔  {t}{C['RST']}")
def warn(t):  print(f"  {C['Y']}⚠  {t}{C['RST']}")
def err(t):   print(f"  {C['R']}✘  {t}{C['RST']}")
def info(t):  print(f"  {C['M']}•  {t}{C['RST']}")
def bullet(t):print(f"       {C['DIM']}{t}{C['RST']}")

def title(text):
    pad  = max(0, (58 - len(text)) // 2)
    rpad = 58 - pad - len(text)
    return (f"\n{C['H']}╔{'═'*58}╗\n"
            f"║{' '*pad}{text}{' '*rpad}║\n"
            f"╚{'═'*58}╝{C['RST']}\n")

def section(text):
    print(f"\n{C['B']}  ┌─ {text} {C['RST']}")


# ── Banner ────────────────────────────────────────────────────────────────────

VERSION = "3.4"
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
        print(f"  {C['G']}● TOR ACTIVE{C['RST']}  {C['DIM']}— real IP hidden via onion routing{C['RST']}")
    else:
        print(f"  {C['DIM']}○ Tor off  — real IP + TLS 1.3{C['RST']}")
    print()


# ── Main menu ─────────────────────────────────────────────────────────────────
#
#   [1] Start node (+ optional Tor)
#   [2] View peers
#   [3] Connect to peer (by Node ID)
#   [4] Send file(s)
#   [5] Profile / Settings
#   [6] Exit
#   [7] Self-destruct

def main_menu(node_started, peer_count, alias, tor_active=False):
    show_banner(tor_active)
    status = (
        f"{C['G']}ONLINE{C['RST']}  alias={C['W']}{alias}{C['RST']}  peers={C['W']}{peer_count}{C['RST']}"
        if node_started else f"{C['Y']}OFFLINE{C['RST']}"
    )
    print(f"  Status: {status}\n")
    print(hr())
    print(f"  {C['B']}[1]{C['RST']}  🚀  Start P2P node")
    print(f"  {C['B']}[2]{C['RST']}  👥  View peers online")
    print(f"  {C['B']}[3]{C['RST']}  🔗  Connect to peer  {C['DIM']}(by Node ID){C['RST']}")
    print(f"  {C['B']}[4]{C['RST']}  📤  Send file(s)")
    print(f"  {C['B']}[5]{C['RST']}  ⚙️   Profile / Settings")
    print(f"  {C['DIM']}[6]{C['RST']}  🚪  Exit")
    print(f"  {C['R']}[7]{C['RST']}  💣  Self-destruct")
    print(hr())
    return prompt("Option")


# ── [1] Start node + optional Tor ─────────────────────────────────────────────

def screen_start(node):
    cls()
    print(title("START P2P NODE"))

    if node._started:
        warn("Node is already running.")
        pause(); return True

    # ── Ask about Tor before starting ──
    section("🧅  Tor — Extra Anonymity")
    print(f"  {C['DIM']}Tor routes traffic through 3 relay nodes (onion routing).{C['RST']}")
    print(f"  {C['DIM']}Peers see only the Tor exit node IP — never your real IP.{C['RST']}")
    print()
    warn("Tor adds latency (~100–500 ms per hop).")
    warn("Upload speed will be lower than without Tor.")
    print()

    enable_tor = confirm("Enable Tor with this node? (recommended for privacy)")
    print()

    print(f"  {C['M']}Starting services...{C['RST']}\n")

    def _tor_progress(msg):
        print(f"  {C['M']}→  {msg}{C['RST']}")

    if enable_tor:
        # Pass progress only if Tor is being enabled
        result = node.start(enable_tor=False)  # start network first
        if result['status'] == 'ok':
            print(f"  {C['M']}→  Connecting to Tor network...{C['RST']}")
            tor_result = node.start_tor(progress_cb=_tor_progress)
            result['tor_result'] = tor_result
    else:
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

    tor_r = result.get('tor_result')
    if enable_tor:
        print()
        if tor_r and tor_r.get('ok'):
            ok(f"Tor active!  {tor_r['msg']}")
        else:
            msg = tor_r['msg'] if tor_r else "unknown error"
            warn(f"Tor failed: {msg}")
            warn("Running without Tor. You can retry via [5] Profile > Tor.")
    else:
        print()
        info("Tor is OFF. You can enable it later via [5] Profile > Tor.")

    print()
    info("Auto-discovery active. Waiting for peers...")
    pause(); return True


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
        print(f"  {C['B']}{i:<3}{C['RST']}  "
              f"{C['W']}{p.alias:<22}{C['RST']}  "
              f"{C['DIM']}{p.node_id:<16}{C['RST']}  "
              f"{elapsed}s ago")
    print()
    info("IP addresses are never displayed — Node ID is used for all connections.")
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
    print(f"  {C['DIM']}FastFile never shows or logs real IPs in the interface.{C['RST']}")
    print()
    section("Cross-network options")
    bullet("VPN (Tailscale, ZeroTier, WireGuard) — easiest, hides IPs")
    bullet("Tor active on both sides — use [1] to enable")
    bullet("Port forward TCP 55771 on router — uses real IP (less private)")
    print()

    info("For same-network peers: just use [2] — auto-discovery handles it.")
    print()
    node_id_input = prompt("Enter peer Node ID (or IP if using VPN/port-forward)").strip()
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
    print(f"  {C['B']}[1]{C['RST']}  Send 1 file            (max 20 MB)")
    print(f"  {C['B']}[2]{C['RST']}  Send multiple files     (max 200 MB total)")
    print()
    mode = prompt("Mode", "1")
    if mode == "1":   _send_single(node, peer)
    elif mode == "2": _send_batch(node, peer)
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
    info(f"File       : {C['W']}{p.name}{C['RST']}")
    info(f"Size       : {size_mb:.2f} MB  (max {MAX_SINGLE_FILE//1024//1024} MB)")
    info(f"Compression: zlib level 6 (automatic)")
    if node.is_tor_active():
        info(f"Routing    : {C['G']}via Tor — real IP hidden{C['RST']}")
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
    from core.transfer import check_file_allowed, MAX_SINGLE_FILE, MAX_BATCH_TOTAL
    info(f"Opening selector ({gui_mode_label()})...")
    if "graphic" in gui_mode_label() or "native" in gui_mode_label():
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
            warn(f"Skipped (not found): {Path(raw).name}"); continue
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

    # ── Identity ──
    section("🪪  Anonymous identity")
    info(f"Node ID     : {C['W']}{si['node_id']}{C['RST']}")
    info(f"Alias       : {C['W']}{si['alias']}{C['RST']}")
    info(f"Fingerprint : {C['W']}{si['fingerprint'] or '(start node first)'}{C['RST']}")
    print(f"\n  {C['DIM']}ID and alias are pure random — no link to name, hostname or MAC.{C['RST']}")

    # ── Network & Security ──
    section("🌐  Network & security")
    status_s = f"{C['G']}ONLINE{C['RST']}" if si['running'] else f"{C['Y']}OFFLINE{C['RST']}"
    info(f"Status      : {status_s}")
    info(f"Port        : {si['port']}")
    info(f"TLS         : 1.3  |  AES-256-GCM + ChaCha20")
    info(f"Integrity   : HMAC-SHA256 per file")
    info(f"Compression : zlib level 6 (automatic)")
    info(f"IP exposure : {C['G']}hidden — Node ID used for all connections{C['RST']}")
    tor_s = (f"{C['G']}ACTIVE — onion routing{C['RST']}"
             if si.get('tor_active') else f"{C['Y']}Inactive{C['RST']}")
    info(f"Tor         : {tor_s}")
    info(f"Crypto lib  : {'✔ cryptography' if si['crypto'] else '✘ missing'}")

    # ── Tor toggle ──
    print()
    if si.get('tor_active'):
        if confirm("  Tor is ACTIVE. Deactivate?"):
            node.stop_tor()
            ok("Tor deactivated.")
    else:
        if confirm("  Activate Tor now? (adds latency, hides IP)"):
            _activate_tor_inline(node)

    # ── Storage ──
    section("📁  Storage")
    info(f"Downloads   : {si['downloads']}")
    info(f"Work dir    : {si['work_dir']}")
    info(f"Platform    : {si['platform']}")

    # ── Privacy ──
    section("🔒  Privacy")
    print(f"  {C['G']}  Transfer history  : DISABLED{C['RST']}")
    print(f"  {C['G']}  Disk logging      : NONE{C['RST']}")
    print(f"  {C['DIM']}  Nothing you send or receive is ever stored.{C['RST']}")

    # ── Supported / Blocked formats ──
    section("📂  File formats")
    from core.transfer import MAX_SINGLE_FILE, MAX_BATCH_TOTAL
    print(f"  {C['G']}Supported:{C['RST']}  images, documents, code, data, archives, audio, fonts, executables")
    print(f"  {C['R']}Blocked  :{C['RST']}  video (.mp4 .mkv ...), Photoshop .psd, Illustrator .ai,")
    print(f"            Premiere .prproj, After Effects .aep, RAW photos,")
    print(f"            disk images (.iso .vmdk), DAW projects, SQL dumps")
    print()
    info(f"Per-file limit : {C['W']}{MAX_SINGLE_FILE // 1024 // 1024} MB{C['RST']}")
    info(f"Batch limit    : {C['W']}{MAX_BATCH_TOTAL // 1024 // 1024} MB total{C['RST']}")
    warn("To send blocked formats: compress into .zip first.")

    pause()


def _activate_tor_inline(node):
    """Activates Tor with inline progress — used inside Profile screen."""
    print()
    warn("Tor adds ~100–500 ms latency per hop and reduces upload speed.")
    print()

    def _progress(msg):
        print(f"  {C['M']}→  {msg}{C['RST']}")

    result = node.start_tor(progress_cb=_progress)
    print()
    if result['ok']:
        ok(f"Tor active!  {result['msg']}")
    else:
        err(f"Tor failed: {result['msg']}")
        warn("Install Tor manually:")
        bullet("Windows : https://www.torproject.org/download/tor/")
        bullet("Linux   : sudo apt install tor")
        bullet("macOS   : brew install tor")


# ── [7] Self-destruct ─────────────────────────────────────────────────────────

def screen_destruct(node):
    cls()
    print(f"\n{C['R']}{'█'*60}{C['RST']}")
    print(f"{C['R']}  ⚠   SELF-DESTRUCT  —  FastFile   ⚠{C['RST']}")
    print(f"{C['R']}{'█'*60}{C['RST']}\n")
    print(f"  This action is {C['R']}IRREVERSIBLE{C['RST']} and will:\n")
    bullet("Stop Tor if active")
    bullet("Uninstall all Python packages installed by FastFile")
    bullet("Remove all downloaded files (~/.fastfile/downloads)")
    bullet("Delete certificates and config (~/.fastfile)")
    bullet("Delete the program folder permanently")
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
