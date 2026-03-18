#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core/transfer.py - Motor de transferência de arquivos
Suporta envio único e envio em lote (batch).
Protocolo: handshake JSON → chunks encriptados → confirmação HMAC.
"""

import os
import json
import ssl
import zlib
import tempfile
import threading
import time
import secrets
import struct
from pathlib import Path
from typing import List, Optional, Callable
from datetime import datetime

from core.network import (
    Peer, send_message, recv_message,
    send_raw_chunk, recv_raw_chunk,
    connect_to_peer, BUFFER_SIZE
)
from core.crypto import (
    FileEncryptor, derive_session_key,
    compute_file_hmac, verify_file_hmac,
    compute_file_hash
)

# ─────────────────────────────────────────────
#  Constantes
# ─────────────────────────────────────────────

MAX_SINGLE_FILE  = 500 * 1024 * 1024   # 500 MB por arquivo
WARN_SIZE_THRESH =  50 * 1024 * 1024   # avisa acima de 50 MB
CHUNK_SIZE       = 256 * 1024           # 256 KB de chunk de envio

DOWNLOADS_DIR = Path.home() / ".fastfile" / "downloads"
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

# Extensões bloqueadas — muito pesadas ou formatos proprietários
BLOCKED_EXTENSIONS = {
    # Vídeo
    '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm',
    '.m4v', '.mpg', '.mpeg', '.ts', '.vob', '.3gp', '.m2ts',
    # Projetos de áudio (DAW)
    '.aup', '.aup3', '.ptx', '.ptf', '.als', '.flp',
    # Design / gráficos profissionais
    '.psd', '.ai', '.indd', '.xd', '.aep', '.prproj',
    '.afdesign', '.afphoto',
    # RAW fotográfico
    '.nef', '.cr2', '.cr3', '.arw', '.raf', '.dng',
    # Imagens de disco / VM
    '.iso', '.img', '.vmdk', '.vhd', '.vhdx', '.ova', '.ovf',
    # Dumps / backups pesados
    '.bak', '.dump', '.sql',
}


def check_file_allowed(filepath: Path) -> tuple:
    """
    Verifica se o arquivo pode ser enviado.
    Retorna (allowed: bool, message: str | None).
    'message' é um aviso (não bloqueia) quando allowed=True,
    ou o motivo da recusa quando allowed=False.
    """
    ext  = filepath.suffix.lower()
    size = filepath.stat().st_size if filepath.exists() else 0

    if ext in BLOCKED_EXTENSIONS:
        return False, (
            f"Extensão '{ext}' não é suportada pelo FastFile.\n"
            f"  Use a opção [6] do menu para ver todos os formatos bloqueados."
        )

    if size > MAX_SINGLE_FILE:
        mb = size / 1024 / 1024
        return False, (
            f"Arquivo excede o limite de {MAX_SINGLE_FILE // 1024 // 1024} MB.\n"
            f"  Tamanho detectado: {mb:.1f} MB — envio recusado."
        )

    if size > WARN_SIZE_THRESH:
        mb = size / 1024 / 1024
        return True, (
            f"AVISO DE TAMANHO: {filepath.name} tem {mb:.1f} MB.\n"
            f"  A compressão e o envio podem levar alguns minutos."
        )

    return True, None

# ─────────────────────────────────────────────
#  Callbacks de progresso
# ─────────────────────────────────────────────

class TransferProgress:
    """Callback simples de progresso"""

    def __init__(self, filename: str, total: int, direction: str = "↑"):
        self.filename  = filename
        self.total     = total
        self.direction = direction
        self.done      = 0
        self._start    = time.time()
        self._lock     = threading.Lock()

    def update(self, n_bytes: int):
        with self._lock:
            self.done += n_bytes
        self._print()

    def _print(self):
        if self.total <= 0:
            return
        pct  = min(100.0, self.done / self.total * 100)
        bar  = int(pct / 3.33)        # 30 chars
        fill = "█" * bar + "░" * (30 - bar)
        elapsed = time.time() - self._start + 1e-9
        speed   = self.done / elapsed
        speed_s = self._fmt_speed(speed)
        eta     = (self.total - self.done) / speed if speed > 0 else 0
        print(
            f"\r  {self.direction} {self.filename[:20]:<20} "
            f"|{fill}| {pct:5.1f}%  {speed_s}  ETA {eta:4.0f}s",
            end='', flush=True
        )

    def finish(self, success: bool = True):
        if success:
            elapsed = time.time() - self._start
            speed   = self.total / elapsed if elapsed > 0 else 0
            print(
                f"\r  ✔  {self.filename[:20]:<20} "
                f"{'█'*30}  100.0%  {self._fmt_speed(speed)}  OK          "
            )
        else:
            print(f"\r  ✘  {self.filename[:20]:<20}  ERRO                                    ")

    @staticmethod
    def _fmt_speed(bps: float) -> str:
        if bps >= 1024**2:
            return f"{bps/1024**2:6.1f} MB/s"
        if bps >= 1024:
            return f"{bps/1024:6.1f} KB/s"
        return f"{bps:6.0f}  B/s"


# ─────────────────────────────────────────────
#  Registro de histórico
# ─────────────────────────────────────────────

class TransferRecord:
    def __init__(self, direction: str, filename: str, peer_alias: str,
                 size: int, success: bool):
        self.direction  = direction   # 'sent' | 'received'
        self.filename   = filename
        self.peer_alias = peer_alias
        self.size       = size
        self.success    = success
        self.timestamp  = datetime.now().isoformat(timespec='seconds')

    def display(self) -> str:
        arrow = "📤" if self.direction == "sent" else "📥"
        status = "✔" if self.success else "✘"
        size_s = self._fmt_size(self.size)
        return (f"  {status} {arrow} {self.filename}  "
                f"({size_s})  ↔ {self.peer_alias}  [{self.timestamp}]")

    @staticmethod
    def _fmt_size(n: int) -> str:
        if n >= 1024**3:
            return f"{n/1024**3:.1f} GB"
        if n >= 1024**2:
            return f"{n/1024**2:.1f} MB"
        if n >= 1024:
            return f"{n/1024:.1f} KB"
        return f"{n} B"


# ─────────────────────────────────────────────
#  Protocolo de transferência
# ─────────────────────────────────────────────
#
#  SENDER → RECEIVER:
#    1. send_message({type:'offer', batch_id, file_index, file_count,
#                     filename, size, hmac_key_hex, salt_hex})
#    2. recv_message → {type:'accept'} ou {type:'reject', reason}
#    3. stream encriptado em chunks: send_raw_chunk(encrypted_chunk) × N
#    4. send_message({type:'done', hmac})
#    5. recv_message → {type:'ok'} ou {type:'error', reason}
#
# ─────────────────────────────────────────────

def _encrypt_and_send(sock: ssl.SSLSocket, src_path: Path,
                      encryptor: FileEncryptor,
                      progress: Optional[TransferProgress]):
    """
    Lê src_path em chunks, COMPRIME com zlib (nível 6), encripta com
    AES-256-GCM e envia. Compressão é obrigatória — reduz dados na rede.
    """
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    aesgcm = AESGCM(encryptor.key)

    with open(src_path, 'rb') as f:
        idx = 0
        while True:
            plaintext = f.read(CHUNK_SIZE)
            if not plaintext:
                break
            # 1. Comprimir (zlib nível 6 — equilíbrio velocidade/tamanho)
            compressed = zlib.compress(plaintext, level=6)
            # 2. Prefixo de 4 bytes com tamanho original (para descompressão)
            payload = struct.pack(">I", len(plaintext)) + compressed
            # 3. Encriptar payload inteiro
            nonce = secrets.token_bytes(4) + idx.to_bytes(8, 'big')
            ct    = aesgcm.encrypt(nonce, payload, None)
            chunk = nonce + struct.pack(">I", len(ct)) + ct
            send_raw_chunk(sock, chunk)
            idx += 1
            if progress:
                progress.update(len(plaintext))

    # Sinaliza fim do stream
    send_raw_chunk(sock, b'')


def _recv_and_decrypt(sock: ssl.SSLSocket, dst_path: Path,
                      encryptor: FileEncryptor, expected_size: int,
                      progress: Optional[TransferProgress]):
    """
    Recebe chunks encriptados, decripta e DESCOMPRIME (zlib) antes de gravar.
    """
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    aesgcm   = AESGCM(encryptor.key)

    with open(dst_path, 'wb') as f:
        while True:
            raw = recv_raw_chunk(sock)
            if raw == b'':
                break          # fim de stream
            nonce  = raw[:12]
            ct_len = struct.unpack(">I", raw[12:16])[0]
            ct     = raw[16:16 + ct_len]
            # 1. Decriptar
            payload = aesgcm.decrypt(nonce, ct, None)
            # 2. Extrair tamanho original e descomprimir
            orig_len   = struct.unpack(">I", payload[:4])[0]
            compressed = payload[4:]
            plain      = zlib.decompress(compressed)
            f.write(plain)
            if progress:
                progress.update(len(plain))


# ─────────────────────────────────────────────
#  Enviador
# ─────────────────────────────────────────────

class FileSender:

    def __init__(self, my_id: str, ssl_ctx: ssl.SSLContext):
        self.my_id   = my_id
        self.ssl_ctx = ssl_ctx

    def send_single(self, peer: Peer, filepath: Path,
                    on_progress: bool = True) -> TransferRecord:
        """Envia um único arquivo"""
        return self._send_batch(peer, [filepath], on_progress)[0]

    def send_batch(self, peer: Peer, filepaths: List[Path],
                   on_progress: bool = True) -> List[TransferRecord]:
        """Envia múltiplos arquivos em sequência na mesma conexão TLS"""
        return self._send_batch(peer, filepaths, on_progress)

    def _send_batch(self, peer: Peer, filepaths: List[Path],
                    on_progress: bool) -> List[TransferRecord]:
        records = []

        # Validar arquivos
        valid = []
        for fp in filepaths:
            fp = Path(fp)
            if not fp.exists():
                print(f"  ✘ Arquivo não encontrado: {fp}")
                records.append(TransferRecord('sent', fp.name, peer.alias, 0, False))
                continue
            if not fp.is_file():
                print(f"  ✘ Não é um arquivo: {fp}")
                records.append(TransferRecord('sent', fp.name, peer.alias, 0, False))
                continue

            allowed, msg = check_file_allowed(fp)
            if not allowed:
                print(f"  ✘ {msg}")
                records.append(TransferRecord('sent', fp.name, peer.alias, fp.stat().st_size, False))
                continue
            if msg:
                # É um aviso (não bloqueia)
                print(f"  ⚠  {msg}")

            valid.append(fp)

        if not valid:
            return records

        # Conectar
        try:
            sock = connect_to_peer(peer, self.ssl_ctx)
        except Exception as e:
            print(f"  ✘ Falha ao conectar: {e}")
            for fp in valid:
                records.append(TransferRecord('sent', fp.name, peer.alias, fp.stat().st_size, False))
            return records

        try:
            batch_id = secrets.token_hex(8)

            for idx, fp in enumerate(valid):
                filesize = fp.stat().st_size

                # Gerar chave de sessão única por arquivo
                salt        = secrets.token_bytes(32)
                hmac_key    = secrets.token_bytes(32)
                session_key = derive_session_key(hmac_key, salt)
                encryptor   = FileEncryptor(session_key)

                # Oferta
                send_message(sock, {
                    'type':       'offer',
                    'batch_id':   batch_id,
                    'file_index': idx,
                    'file_count': len(valid),
                    'filename':   fp.name,
                    'size':       filesize,
                    'hmac_key':   hmac_key.hex(),
                    'salt':       salt.hex(),
                    'sender_id':  self.my_id,
                    'compressed': True,   # compressão zlib obrigatória
                })

                resp = recv_message(sock, timeout=15.0)
                if resp.get('type') != 'accept':
                    reason = resp.get('reason', '?')
                    print(f"  ✘ Recusado pelo peer: {reason}")
                    records.append(TransferRecord('sent', fp.name, peer.alias, filesize, False))
                    continue

                # Progresso
                prog = TransferProgress(fp.name, filesize, "↑") if on_progress else None

                # Stream encriptado
                try:
                    _encrypt_and_send(sock, fp, encryptor, prog)
                except Exception as e:
                    if prog:
                        prog.finish(False)
                    records.append(TransferRecord('sent', fp.name, peer.alias, filesize, False))
                    continue

                # HMAC de integridade
                file_hmac = compute_file_hmac(fp, hmac_key)
                send_message(sock, {'type': 'done', 'hmac': file_hmac})

                conf = recv_message(sock, timeout=30.0)
                success = conf.get('type') == 'ok'
                if prog:
                    prog.finish(success)
                records.append(TransferRecord('sent', fp.name, peer.alias, filesize, success))

        finally:
            try:
                sock.close()
            except Exception:
                pass

        return records


# ─────────────────────────────────────────────
#  Recebedor (handler do servidor)
# ─────────────────────────────────────────────

class FileReceiver:

    def __init__(self, history_callback: Optional[Callable] = None):
        self._history_cb = history_callback

    def handle(self, sock: ssl.SSLSocket, addr):
        """Processa uma conexão entrante (chamado pela thread do servidor)"""
        try:
            while True:
                try:
                    msg = recv_message(sock, timeout=60.0)
                except Exception:
                    break   # cliente desconectou

                if msg.get('type') != 'offer':
                    break

                filename   = os.path.basename(msg['filename'])
                filesize   = int(msg['size'])
                hmac_key   = bytes.fromhex(msg['hmac_key'])
                salt       = bytes.fromhex(msg['salt'])
                sender_id  = msg.get('sender_id', 'unknown')
                file_index = msg.get('file_index', 0)
                file_count = msg.get('file_count', 1)

                # Aceitar
                send_message(sock, {'type': 'accept'})

                # Determinar caminho de destino (sem sobrescrever)
                save_path = self._unique_path(DOWNLOADS_DIR / filename)

                session_key = derive_session_key(hmac_key, salt)
                encryptor   = FileEncryptor(session_key)

                prog = TransferProgress(
                    filename, filesize, "↓"
                )
                prog_label = f"  [{file_index+1}/{file_count}]"
                print(f"\n{prog_label} Recebendo de {addr[0]}  →  {filename}")

                success = False
                try:
                    _recv_and_decrypt(sock, save_path, encryptor, filesize, prog)

                    # Verificar HMAC
                    done_msg = recv_message(sock, timeout=15.0)
                    expected_hmac = done_msg.get('hmac', '')
                    ok = verify_file_hmac(save_path, hmac_key, expected_hmac)
                    send_message(sock, {'type': 'ok' if ok else 'error',
                                        'reason': '' if ok else 'hmac_mismatch'})
                    success = ok
                    prog.finish(success)
                    if success:
                        print(f"  ✔ Salvo em: {save_path}")
                    else:
                        print(f"  ✘ Integridade falhou — arquivo removido")
                        save_path.unlink(missing_ok=True)

                except Exception as e:
                    prog.finish(False)
                    send_message(sock, {'type': 'error', 'reason': str(e)})
                    save_path.unlink(missing_ok=True)

                # Registrar
                if self._history_cb:
                    self._history_cb(TransferRecord(
                        'received', filename, addr[0], filesize, success
                    ))

                # Se há mais arquivos no batch, continuar loop
                if file_index + 1 >= file_count:
                    break

        except Exception:
            pass
        finally:
            try:
                sock.close()
            except Exception:
                pass

    @staticmethod
    def _unique_path(p: Path) -> Path:
        if not p.exists():
            return p
        stem, suffix = p.stem, p.suffix
        i = 1
        while True:
            candidate = p.parent / f"{stem}_{i}{suffix}"
            if not candidate.exists():
                return candidate
            i += 1
