#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core/node.py - P2P Node: orchestrates server, discovery, Tor and transfers
"""

import sys
import time
import shutil
import subprocess
import platform
import tempfile
from pathlib import Path
from typing import List, Optional

from core.crypto import (
    generate_anonymous_id,
    anonymize_hostname,
    generate_tls_cert,
    create_server_ssl_context,
    create_client_ssl_context,
    get_cert_fingerprint,
    CRYPTO_AVAILABLE,
)
from core.network import (
    P2PServer, DiscoveryManager, PeerRegistry,
    Peer, get_local_ips, SERVICE_PORT,
)
from core.transfer import FileSender, FileReceiver, TransferResult, DOWNLOADS_DIR
import core.tor_proxy as tor_proxy
import core.easter_egg as easter_egg

WORK_DIR = Path.home() / ".fastfile"


class P2PNode:
    def __init__(self):
        self.node_id     = generate_anonymous_id()
        self.alias       = anonymize_hostname("")
        self.ip_list     = get_local_ips()
        self.port        = SERVICE_PORT
        self._started    = False
        self._tor_active = False
        self._egg_tier   = easter_egg.detect_egg(self.alias)

        self.registry:  Optional[PeerRegistry]    = None
        self.server:    Optional[P2PServer]        = None
        self.discovery: Optional[DiscoveryManager] = None
        self.sender:    Optional[FileSender]       = None
        self.receiver:  Optional[FileReceiver]     = None
        self._fingerprint = ""

    def get_file_limits(self):
        """Returns (max_single_bytes, max_batch_bytes) — boosted for egg aliases."""
        egg = easter_egg.egg_limits(self.alias)
        if egg:
            return egg
        from core.transfer import MAX_SINGLE_FILE, MAX_BATCH_TOTAL
        return MAX_SINGLE_FILE, MAX_BATCH_TOTAL

    # ── Start ────────────────────────────────────

    def start(self, enable_tor: bool = False) -> dict:
        if self._started:
            return {'status': 'already_running'}
        if not CRYPTO_AVAILABLE:
            return {'status': 'error',
                    'msg': "'cryptography' package not found.\nRun: pip install cryptography"}

        generate_tls_cert(self.node_id)
        self._fingerprint = get_cert_fingerprint(self.node_id)

        server_ctx = create_server_ssl_context(self.node_id)
        client_ctx = create_client_ssl_context(self.node_id)

        self.receiver = FileReceiver(on_receive=self._on_file_received)
        self.registry = PeerRegistry(on_new_peer=self._on_new_peer)

        # Show Easter Egg effect at startup if alias matches
        easter_egg.show_startup_egg(self.alias)

        self.server = P2PServer(
            node_id=self.node_id,
            ssl_ctx=server_ctx,
            connection_handler=self.receiver.handle,
            port=SERVICE_PORT,
        )
        self.server.start()
        time.sleep(0.5)
        self.port = self.server.port

        self.discovery = DiscoveryManager(
            node_id=self.node_id,
            alias=self.alias,
            fingerprint=self._fingerprint,
            registry=self.registry,
            port=self.port,
        )
        disc_mode = self.discovery.start()
        self.sender = FileSender(
            self.node_id, client_ctx,
            my_alias=self.alias,
            max_single=lims[0] if (lims := easter_egg.egg_limits(self.alias)) else None,
            max_batch =lims[1] if lims else None,
        )
        self._started = True

        result = {
            'status':      'ok',
            'node_id':     self.node_id,
            'alias':       self.alias,
            'fingerprint': self._fingerprint,
            'port':        self.port,
            'disc_mode':   disc_mode,
            'downloads':   str(DOWNLOADS_DIR),
            'tor_result':  None,
        }

        if enable_tor:
            tor_result = tor_proxy.start_tor()
            if tor_result['ok']:
                self._tor_active = True
            result['tor_result'] = tor_result

        return result

    # ── Tor ──────────────────────────────────────

    def start_tor(self, progress_cb=None) -> dict:
        result = tor_proxy.start_tor(progress_cb)
        if result['ok']:
            self._tor_active = True
        return result

    def stop_tor(self):
        tor_proxy.stop_tor()
        self._tor_active = False

    def is_tor_active(self) -> bool:
        return tor_proxy.is_tor_active()

    # ── Peers ─────────────────────────────────────

    def _on_new_peer(self, peer: Peer):
        # Show only node_id — never expose IP in notifications
        print(f"\n  ✔ New peer online: {peer.alias}  [ID: {peer.node_id}]")

    def _on_file_received(self, filename: str, from_ip: str, size: int):
        mb = size / 1024 / 1024
        print(f"\n  📥 Received: {filename}  ({mb:.2f} MB)")

    def list_peers(self) -> list:
        return self.registry.all_alive() if self.registry else []

    def add_peer_by_node_id(self, node_id_input: str, port: int = None) -> bool:
        """
        Adds a peer by Node ID (resolves from known peers) or by raw IP if given.
        Node ID is preferred for privacy — IP is never shown to the user.
        """
        if not self.registry:
            return False
        # Check if it matches a known peer's node_id
        for p in self.registry.all_alive():
            if p.node_id == node_id_input:
                return True  # already known
        # Fallback: treat as IP (for cross-network via VPN/Tor)
        peer = self.registry.add_manual(node_id_input, port or SERVICE_PORT)
        return peer is not None

    # ── Send ─────────────────────────────────────

    def send_file(self, peer_id: str, filepath: str) -> bool:
        peer = self._resolve_peer(peer_id)
        if not peer or not self.sender:
            return False
        return self.sender.send_single(peer, Path(filepath)).success

    def send_files(self, peer_id: str, filepaths: list) -> list:
        peer = self._resolve_peer(peer_id)
        if not peer or not self.sender:
            return []
        return self.sender.send_batch(peer, [Path(f) for f in filepaths])

    def _resolve_peer(self, peer_id_or_alias: str) -> Optional[Peer]:
        if not self.registry:
            return None
        for p in self.registry.all_alive():
            if p.node_id == peer_id_or_alias or p.alias == peer_id_or_alias:
                return p
        return None

    # ── Info ──────────────────────────────────────

    def system_info(self) -> dict:
        return {
            'node_id':     self.node_id,
            'alias':       self.alias,
            'fingerprint': self._fingerprint,
            'port':        self.port,
            'running':     self._started,
            'tor_active':  self.is_tor_active(),
            'downloads':   str(DOWNLOADS_DIR),
            'work_dir':    str(WORK_DIR),
            'crypto':      CRYPTO_AVAILABLE,
            'platform':    f"{platform.system()} {platform.release()}",
            'app':         'FastFile v3.4',
        }

    # ── Shutdown ──────────────────────────────────

    def shutdown(self):
        if self.discovery: self.discovery.stop()
        if self.server:    self.server.stop()
        if self._tor_active: tor_proxy.stop_tor()
        # Stop local web server if running
        try:
            from core.local_web import stop_web_server, is_running
            if is_running():
                stop_web_server()
        except Exception:
            pass
        self._started = False

    # ── Self-destruct ─────────────────────────────

    def self_destruct(self):
        self.shutdown()
        time.sleep(0.5)

        # Uninstall Python packages that were installed by FastFile
        packages = ['cryptography', 'colorama', 'netifaces', 'zeroconf', 'stem', 'PySocks']
        print("  Uninstalling packages...")
        for pkg in packages:
            try:
                r = subprocess.run(
                    [sys.executable, "-m", "pip", "uninstall", pkg, "-y",
                     "--disable-pip-version-check"],
                    capture_output=True
                )
                status = "✔" if r.returncode == 0 else "~"
                print(f"    {status}  {pkg}")
            except Exception:
                print(f"    ~  {pkg} (skip)")

        # Remove data dirs
        for d in [DOWNLOADS_DIR, WORK_DIR]:
            try:
                if d.exists():
                    shutil.rmtree(d, ignore_errors=True)
            except Exception as e:
                print(f"  ! Could not remove {d}: {e}")

        # Delete the script/folder
        script_path = Path(sys.argv[0]).resolve()
        try:
            if platform.system() == "Windows":
                bat = Path(tempfile.gettempdir()) / "_ff_destruct.bat"
                bat.write_text(
                    f"@echo off\r\n"
                    f"timeout /t 2 /nobreak >nul\r\n"
                    f"rd /s /q \"{script_path.parent}\"\r\n"
                    f"del /f /q \"%~f0\"\r\n"
                )
                subprocess.Popen(str(bat), shell=True,
                                 creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                script_path.unlink(missing_ok=True)
                try:
                    shutil.rmtree(script_path.parent)
                except Exception:
                    pass
        except Exception as e:
            print(f"  ! Could not delete script: {e}")
            print(f"  → Remove manually: {script_path}")
