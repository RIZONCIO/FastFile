#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core/network.py - Servidor P2P, descoberta de peers e gestão de conexões
Usa TLS 1.3 obrigatório. Descoberta via Zeroconf com fallback para broadcast UDP.
"""

import os
import sys
import json
import socket
import ssl
import threading
import time
import platform
import struct
from pathlib import Path
from typing import Dict, Optional, Callable

# Dependências opcionais
try:
    import netifaces
    NETIFACES_AVAILABLE = True
except ImportError:
    NETIFACES_AVAILABLE = False

try:
    from zeroconf import Zeroconf, ServiceInfo, ServiceBrowser, ServiceListener
    ZEROCONF_AVAILABLE = True
except ImportError:
    ZEROCONF_AVAILABLE = False

# ─────────────────────────────────────────────
#  Constantes
# ─────────────────────────────────────────────

SERVICE_TYPE     = "_p2psec._tcp.local."
SERVICE_PORT     = 55771          # Porta não-padrão para menor visibilidade
DISCOVERY_PORT   = SERVICE_PORT + 1337
BUFFER_SIZE      = 65536
PEER_TIMEOUT     = 60             # segundos sem ping → peer considerado offline
PING_INTERVAL    = 15             # segundos entre pings


# ─────────────────────────────────────────────
#  Detecção de IPs locais
# ─────────────────────────────────────────────

def get_local_ips() -> list:
    """Retorna lista de IPs locais (exceto loopback)"""
    ips = []

    if NETIFACES_AVAILABLE:
        try:
            for iface in netifaces.interfaces():
                addrs = netifaces.ifaddresses(iface)
                if netifaces.AF_INET in addrs:
                    for addr in addrs[netifaces.AF_INET]:
                        ip = addr.get('addr', '')
                        if ip and not ip.startswith('127.') and not ip.startswith('169.254.'):
                            ips.append(ip)
        except Exception:
            pass

    if not ips:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            if not ip.startswith('127.'):
                ips.append(ip)
        except Exception:
            pass

    if not ips:
        ips.append("127.0.0.1")

    return list(dict.fromkeys(ips))  # dedup mantendo ordem


# ─────────────────────────────────────────────
#  Peer
# ─────────────────────────────────────────────

class Peer:
    __slots__ = ('node_id', 'alias', 'ip', 'port', 'fingerprint', 'last_seen', 'latency_ms')

    def __init__(self, node_id: str, alias: str, ip: str, port: int,
                 fingerprint: str = "", last_seen: float = 0.0):
        self.node_id    = node_id
        self.alias      = alias
        self.ip         = ip
        self.port       = port
        self.fingerprint = fingerprint
        self.last_seen  = last_seen or time.time()
        self.latency_ms = -1

    def is_alive(self) -> bool:
        return (time.time() - self.last_seen) < PEER_TIMEOUT

    def touch(self):
        self.last_seen = time.time()

    def to_dict(self) -> dict:
        return {
            'node_id':     self.node_id,
            'alias':       self.alias,
            'ip':          self.ip,
            'port':        self.port,
            'fingerprint': self.fingerprint,
        }

    @classmethod
    def from_dict(cls, d: dict) -> 'Peer':
        return cls(
            node_id=d['node_id'],
            alias=d.get('alias', 'unknown'),
            ip=d['ip'],
            port=d.get('port', SERVICE_PORT),
            fingerprint=d.get('fingerprint', ''),
        )


# ─────────────────────────────────────────────
#  Listener Zeroconf
# ─────────────────────────────────────────────

class _ZeroconfListener(ServiceListener):
    def __init__(self, registry: 'PeerRegistry', my_id: str):
        self.registry = registry
        self.my_id    = my_id

    def add_service(self, zc, type_, name):
        try:
            info = zc.get_service_info(type_, name)
            if not info or not info.properties:
                return
            nid = info.properties.get(b'nid', b'').decode()
            if nid and nid != self.my_id:
                alias = info.properties.get(b'alias', b'unknown').decode()
                fp    = info.properties.get(b'fp', b'').decode()
                port  = info.port
                if info.addresses:
                    ip = socket.inet_ntoa(info.addresses[0])
                    self.registry.add_or_update(Peer(nid, alias, ip, port, fp))
        except Exception:
            pass

    def remove_service(self, zc, type_, name):
        pass

    def update_service(self, zc, type_, name):
        self.add_service(zc, type_, name)


# ─────────────────────────────────────────────
#  Registro de Peers
# ─────────────────────────────────────────────

class PeerRegistry:
    def __init__(self, on_new_peer: Optional[Callable] = None):
        self._peers: Dict[str, Peer] = {}
        self._lock  = threading.Lock()
        self._on_new = on_new_peer

    def add_or_update(self, peer: Peer):
        with self._lock:
            is_new = peer.node_id not in self._peers
            self._peers[peer.node_id] = peer
        if is_new and self._on_new:
            self._on_new(peer)

    def get(self, node_id: str) -> Optional[Peer]:
        with self._lock:
            return self._peers.get(node_id)

    def all_alive(self) -> list:
        with self._lock:
            alive = [p for p in self._peers.values() if p.is_alive()]
        return alive

    def prune(self):
        with self._lock:
            dead = [k for k, p in self._peers.items() if not p.is_alive()]
            for k in dead:
                del self._peers[k]
        return len(dead)

    def count(self) -> int:
        return len(self.all_alive())


# ─────────────────────────────────────────────
#  Servidor P2P
# ─────────────────────────────────────────────

class P2PServer:
    """
    Servidor TCP com TLS 1.3.
    Cada conexão aceita é despachada para um handler em thread separada.
    """

    def __init__(self, node_id: str, ssl_ctx: ssl.SSLContext,
                 connection_handler: Callable, port: int = SERVICE_PORT):
        self.node_id  = node_id
        self.ssl_ctx  = ssl_ctx
        self.handler  = connection_handler
        self.port     = port
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._sock    = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._serve, daemon=True, name="P2PServer")
        self._thread.start()

    def stop(self):
        self._running = False
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass

    def _serve(self):
        for attempt_port in [self.port, self.port + 1, self.port + 2]:
            try:
                raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                raw.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                raw.settimeout(1.0)
                raw.bind(('0.0.0.0', attempt_port))
                raw.listen(10)
                self.port = attempt_port
                self._sock = raw
                break
            except OSError:
                try:
                    raw.close()
                except Exception:
                    pass

        if not self._sock:
            return

        while self._running:
            try:
                client_raw, addr = self._sock.accept()
                try:
                    client_tls = self.ssl_ctx.wrap_socket(client_raw, server_side=True)
                except ssl.SSLError:
                    client_raw.close()
                    continue

                t = threading.Thread(
                    target=self.handler,
                    args=(client_tls, addr),
                    daemon=True
                )
                t.start()
            except socket.timeout:
                continue
            except OSError:
                break


# ─────────────────────────────────────────────
#  Gerenciador de Descoberta
# ─────────────────────────────────────────────

class DiscoveryManager:
    """
    Gerencia descoberta de peers via Zeroconf (mDNS) ou broadcast UDP.
    """

    def __init__(self, node_id: str, alias: str, fingerprint: str,
                 registry: PeerRegistry, port: int):
        self.node_id     = node_id
        self.alias       = alias
        self.fingerprint = fingerprint
        self.registry    = registry
        self.port        = port
        self._running    = False
        self._zc         = None
        self._sinfo      = None

    def start(self) -> str:
        self._running = True
        if ZEROCONF_AVAILABLE:
            return self._start_zeroconf()
        else:
            return self._start_broadcast()

    def stop(self):
        self._running = False
        if self._zc and self._sinfo:
            try:
                self._zc.unregister_service(self._sinfo)
                self._zc.close()
            except Exception:
                pass

    def _start_zeroconf(self) -> str:
        try:
            self._zc = Zeroconf()
            ips = get_local_ips()
            addrs = []
            for ip in ips:
                if ip != '127.0.0.1':
                    try:
                        addrs.append(socket.inet_aton(ip))
                    except Exception:
                        pass
            if not addrs:
                addrs = [socket.inet_aton('127.0.0.1')]

            self._sinfo = ServiceInfo(
                SERVICE_TYPE,
                f"{self.node_id}.{SERVICE_TYPE}",
                addresses=addrs,
                port=self.port,
                properties={
                    b'nid':   self.node_id.encode(),
                    b'alias': self.alias.encode(),
                    b'fp':    self.fingerprint.encode(),
                },
            )
            self._zc.register_service(self._sinfo)
            listener = _ZeroconfListener(self.registry, self.node_id)
            ServiceBrowser(self._zc, SERVICE_TYPE, listener)
            return "zeroconf"
        except Exception:
            return self._start_broadcast()

    def _start_broadcast(self) -> str:
        my_ip = get_local_ips()[0]
        announce_data = json.dumps({
            'type': 'ann',
            'nid':  self.node_id,
            'alias': self.alias,
            'fp':   self.fingerprint,
            'ip':   my_ip,
            'port': self.port,
        }).encode()

        def _listener():
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.bind(('', DISCOVERY_PORT))
                sock.settimeout(1.0)
                while self._running:
                    try:
                        data, addr = sock.recvfrom(2048)
                        msg = json.loads(data.decode())
                        if msg.get('nid') != self.node_id and msg.get('type') == 'ann':
                            peer = Peer(
                                msg['nid'], msg.get('alias', 'unknown'),
                                msg.get('ip', addr[0]), msg.get('port', SERVICE_PORT),
                                msg.get('fp', '')
                            )
                            self.registry.add_or_update(peer)
                    except (socket.timeout, json.JSONDecodeError):
                        pass
                    except Exception:
                        pass
                sock.close()
            except Exception:
                pass

        def _announcer():
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                while self._running:
                    try:
                        sock.sendto(announce_data, ('255.255.255.255', DISCOVERY_PORT))
                    except Exception:
                        pass
                    time.sleep(5)
                sock.close()
            except Exception:
                pass

        threading.Thread(target=_listener, daemon=True, name="BcastListen").start()
        threading.Thread(target=_announcer, daemon=True, name="BcastAnn").start()
        return "broadcast"


# ─────────────────────────────────────────────
#  Utilitários de conexão de saída
# ─────────────────────────────────────────────

def connect_to_peer(peer: Peer, ssl_ctx: ssl.SSLContext,
                    timeout: float = 10.0) -> ssl.SSLSocket:
    """
    Abre conexão TLS 1.3 com o peer.
    Levanta exceção se falhar.
    """
    raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    raw.settimeout(timeout)
    raw.connect((peer.ip, peer.port))
    tls_sock = ssl_ctx.wrap_socket(raw, server_hostname=None)
    return tls_sock


def send_message(sock: ssl.SSLSocket, msg: dict):
    """Envia mensagem JSON com prefixo de tamanho (4 bytes big-endian)"""
    data = json.dumps(msg).encode('utf-8')
    sock.sendall(struct.pack(">I", len(data)) + data)


def recv_message(sock: ssl.SSLSocket, timeout: float = 30.0) -> dict:
    """Recebe mensagem JSON com prefixo de tamanho"""
    sock.settimeout(timeout)
    header = _recv_exact(sock, 4)
    length = struct.unpack(">I", header)[0]
    if length > 64 * 1024 * 1024:
        raise ValueError(f"Mensagem muito grande: {length} bytes")
    data = _recv_exact(sock, length)
    return json.loads(data.decode('utf-8'))


def send_raw_chunk(sock: ssl.SSLSocket, data: bytes):
    """Envia bloco raw com prefixo de tamanho"""
    sock.sendall(struct.pack(">I", len(data)) + data)


def recv_raw_chunk(sock: ssl.SSLSocket) -> bytes:
    """Recebe bloco raw com prefixo de tamanho"""
    header = _recv_exact(sock, 4)
    length = struct.unpack(">I", header)[0]
    return _recv_exact(sock, length)


def _recv_exact(sock, n: int) -> bytes:
    """Lê exatamente n bytes do socket"""
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("Conexão encerrada pelo peer")
        buf.extend(chunk)
    return bytes(buf)
