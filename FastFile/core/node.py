#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core/node.py - Nó P2P: orquestra servidor, descoberta e transferências
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
from core.transfer import FileSender, FileReceiver, TransferRecord, DOWNLOADS_DIR

WORK_DIR = Path.home() / ".fastfile"


class P2PNode:
    """
    Nó P2P completo:
    - identidade anônima
    - TLS 1.3 obrigatório
    - servidor de recebimento
    - descoberta de peers
    - envio single / batch
    - histórico de transferências
    - auto-destruição
    """

    def __init__(self):
        self.node_id     = generate_anonymous_id()
        self.alias       = anonymize_hostname("")
        self.ip_list     = get_local_ips()
        self.port        = SERVICE_PORT
        self._started    = False
        self._history: List[TransferRecord] = []
        self._history_lock = __import__('threading').Lock()

        # Componentes (instanciados em start())
        self.registry:   Optional[PeerRegistry]    = None
        self.server:     Optional[P2PServer]        = None
        self.discovery:  Optional[DiscoveryManager] = None
        self.sender:     Optional[FileSender]       = None
        self.receiver:   Optional[FileReceiver]     = None
        self._fingerprint = ""

    # ──────────────────────────────────────────
    #  Inicialização
    # ──────────────────────────────────────────

    def start(self) -> dict:
        """
        Inicia todos os serviços.
        Retorna dict com info de status.
        """
        if self._started:
            return {'status': 'already_running'}

        if not CRYPTO_AVAILABLE:
            return {
                'status': 'error',
                'msg': "Pacote 'cryptography' não encontrado.\n"
                       "Instale com:  pip install cryptography"
            }

        # Preparar certificado TLS
        generate_tls_cert(self.node_id)
        self._fingerprint = get_cert_fingerprint(self.node_id)

        # SSL contexts
        server_ctx = create_server_ssl_context(self.node_id)
        client_ctx = create_client_ssl_context(self.node_id)

        # Receptor de arquivos
        self.receiver = FileReceiver(history_callback=self._add_to_history)

        # Registro de peers
        self.registry = PeerRegistry(on_new_peer=self._on_new_peer)

        # Servidor TLS
        self.server = P2PServer(
            node_id=self.node_id,
            ssl_ctx=server_ctx,
            connection_handler=self.receiver.handle,
            port=SERVICE_PORT,
        )
        self.server.start()
        time.sleep(0.5)
        self.port = self.server.port  # pode ter mudado se a porta estava ocupada

        # Descoberta
        self.discovery = DiscoveryManager(
            node_id=self.node_id,
            alias=self.alias,
            fingerprint=self._fingerprint,
            registry=self.registry,
            port=self.port,
        )
        disc_mode = self.discovery.start()

        # Sender
        self.sender = FileSender(self.node_id, client_ctx)

        self._started = True
        return {
            'status':      'ok',
            'node_id':     self.node_id,
            'alias':       self.alias,
            'fingerprint': self._fingerprint,
            'ips':         self.ip_list,
            'port':        self.port,
            'disc_mode':   disc_mode,
            'downloads':   str(DOWNLOADS_DIR),
        }

    # ──────────────────────────────────────────
    #  Peers
    # ──────────────────────────────────────────

    def _on_new_peer(self, peer: Peer):
        print(f"\n  ✔ Novo peer: {peer.alias} ({peer.ip})")

    def list_peers(self) -> list:
        if not self.registry:
            return []
        return self.registry.all_alive()

    # ──────────────────────────────────────────
    #  Envio de arquivos
    # ──────────────────────────────────────────

    def send_file(self, peer_id: str, filepath: str) -> bool:
        """Envia um único arquivo"""
        peer = self._resolve_peer(peer_id)
        if not peer or not self.sender:
            return False
        record = self.sender.send_single(peer, Path(filepath))
        self._add_to_history(record)
        return record.success

    def send_files(self, peer_id: str, filepaths: list) -> list:
        """Envia vários arquivos em lote"""
        peer = self._resolve_peer(peer_id)
        if not peer or not self.sender:
            return []
        records = self.sender.send_batch(peer, [Path(f) for f in filepaths])
        for r in records:
            self._add_to_history(r)
        return records

    def _resolve_peer(self, peer_id_or_alias: str) -> Optional[Peer]:
        if not self.registry:
            print("  ✘ Nó não iniciado.")
            return None
        for p in self.registry.all_alive():
            if p.node_id == peer_id_or_alias or p.alias == peer_id_or_alias:
                return p
        print(f"  ✘ Peer não encontrado: {peer_id_or_alias}")
        return None

    # ──────────────────────────────────────────
    #  Histórico
    # ──────────────────────────────────────────

    def _add_to_history(self, record: TransferRecord):
        with self._history_lock:
            self._history.append(record)

    def get_history(self) -> list:
        with self._history_lock:
            return list(self._history)

    # ──────────────────────────────────────────
    #  Sistema
    # ──────────────────────────────────────────

    def system_info(self) -> dict:
        return {
            'node_id':     self.node_id,
            'alias':       self.alias,
            'fingerprint': self._fingerprint,
            'ips':         self.ip_list,
            'port':        self.port,
            'running':     self._started,
            'downloads':   str(DOWNLOADS_DIR),
            'work_dir':    str(WORK_DIR),
            'crypto':      CRYPTO_AVAILABLE,
            'platform':    f"{platform.system()} {platform.release()}",
            'app':         'FastFile v3.1',
        }

    # ──────────────────────────────────────────
    #  Encerramento limpo
    # ──────────────────────────────────────────

    def shutdown(self):
        if self.discovery:
            self.discovery.stop()
        if self.server:
            self.server.stop()
        self._started = False

    # ──────────────────────────────────────────
    #  Auto-destruição
    # ──────────────────────────────────────────

    def self_destruct(self):
        """
        Remove todos os dados e o próprio script.
        Só executa após confirmação explícita do usuário.
        """
        self.shutdown()
        time.sleep(0.5)

        # Remover downloads e work dir
        for d in [DOWNLOADS_DIR, WORK_DIR]:
            try:
                if d.exists():
                    shutil.rmtree(d, ignore_errors=True)
            except Exception as e:
                print(f"  ! Erro ao remover {d}: {e}")

        # Auto-deletar o script
        import sys
        script_path = Path(sys.argv[0]).resolve()

        try:
            if platform.system() == "Windows":
                bat = Path(tempfile.gettempdir()) / "_p2p_destruct.bat"
                bat.write_text(
                    f"@echo off\r\n"
                    f"timeout /t 2 /nobreak >nul\r\n"
                    f"rd /s /q \"{script_path.parent}\"\r\n"
                    f"del /f /q \"%~f0\"\r\n"
                )
                subprocess.Popen(str(bat), shell=True,
                                 creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                # Apagar pasta do projeto inteira
                proj_dir = script_path.parent
                script_path.unlink(missing_ok=True)
                # Tentar remover a pasta se contiver só arquivos do projeto
                try:
                    shutil.rmtree(proj_dir)
                except Exception:
                    pass
        except Exception as e:
            print(f"  ! Erro ao remover script: {e}")
            print(f"  → Remova manualmente: {script_path}")
