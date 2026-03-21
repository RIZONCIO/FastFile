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

MAX_SINGLE_FILE  =  20 * 1024 * 1024   # 20 MB por arquivo
MAX_BATCH_TOTAL  = 200 * 1024 * 1024   # 200 MB total por lote
WARN_SIZE_THRESH =  10 * 1024 * 1024   # avisa acima de 10 MB
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


def check_file_allowed(filepath: Path, max_size: int = None) -> tuple:
    """
    Verifica se o arquivo pode ser enviado.
    max_size: override de limite (Easter Egg). Se None, usa MAX_SINGLE_FILE.
    """
    ext   = filepath.suffix.lower()
    size  = filepath.stat().st_size if filepath.exists() else 0
    limit = max_size if max_size is not None else MAX_SINGLE_FILE

    if ext in BLOCKED_EXTENSIONS:
        return False, (
            f"Extension '{ext}' is not supported by FastFile.\n"
            f"  Use [5] Profile to see all blocked formats."
        )

    if size > limit:
        mb     = size / 1024 / 1024
        lim_mb = limit // 1024 // 1024
        return False, (
            f"File exceeds the {lim_mb} MB limit.\n"
            f"  Detected size: {mb:.1f} MB — rejected."
        )

    if size > WARN_SIZE_THRESH:
        mb = size / 1024 / 1024
        return True, f"Size warning: {filepath.name} is {mb:.1f} MB."

    return True, None

# ─────────────────────────────────────────────
#  Callbacks de progresso
# ─────────────────────────────────────────────

class TransferProgress:
    """
    Single clean progress bar — one line, no spam.
    Shows [X/N] counter when part of a batch.
    """

    def __init__(self, filename: str, total: int, direction: str = "↑",
                 file_index: int = 0, file_count: int = 1):
        self.filename   = filename
        self.total      = total
        self.direction  = direction
        self.file_index = file_index   # 0-based
        self.file_count = file_count
        self.done       = 0
        self._start     = time.time()
        self._lock      = threading.Lock()
        self._printed   = False

        # Print header once before the bar
        counter = f"[{file_index+1}/{file_count}]" if file_count > 1 else ""
        label   = f"{direction} {counter} {filename[:28]}"
        print(f"\n  {label}")

    def update(self, n_bytes: int):
        with self._lock:
            self.done += n_bytes
        self._draw()

    def _draw(self):
        if self.total <= 0:
            return
        pct     = min(100.0, self.done / self.total * 100)
        filled  = int(pct / 3.34)        # 30 chars wide bar
        bar     = "█" * filled + "░" * (30 - filled)
        elapsed = time.time() - self._start + 1e-9
        speed   = self.done / elapsed
        eta     = max(0, (self.total - self.done) / speed) if speed > 0 else 0
        # Overwrite the SAME line each update — no spam
        print(
            f"\r  |{bar}| {pct:5.1f}%  {self._fmt(speed)}  ETA {eta:3.0f}s   ",
            end='', flush=True
        )
        self._printed = True

    def finish(self, success: bool = True):
        if success:
            elapsed = time.time() - self._start + 1e-9
            speed   = self.total / elapsed
            # Overwrite bar with final OK line
            print(f"\r  {'█'*30}  100%  {self._fmt(speed)}  ✔ OK          ")
        else:
            print(f"\r  {'░'*30}  FAILED                              ")

    @staticmethod
    def _fmt(bps: float) -> str:
        if bps >= 1024**2: return f"{bps/1024**2:5.1f} MB/s"
        if bps >= 1024:    return f"{bps/1024:5.1f} KB/s"
        return f"{bps:5.0f}  B/s"


# ─────────────────────────────────────────────
#  Resultado de transferência (sem logging/histórico)
# ─────────────────────────────────────────────

class TransferResult:
    """
    Resultado imediato de uma transferência.
    Não é armazenado em disco nem em memória persistente —
    zero logging para preservar privacidade.
    """
    __slots__ = ('filename', 'size', 'success', 'peer_alias', 'direction')

    def __init__(self, filename: str, size: int, success: bool,
                 peer_alias: str = '', direction: str = 'sent'):
        self.filename   = filename
        self.size       = size
        self.success    = success
        self.peer_alias = peer_alias
        self.direction  = direction

    def display(self) -> str:
        mark  = "✔" if self.success else "✘"
        sz    = self._fmt(self.size)
        arrow = "📤" if self.direction == 'sent' else "📥"
        return f"  {mark} {arrow} {self.filename}  ({sz})"

    @staticmethod
    def _fmt(n: int) -> str:
        if n >= 1024**2:
            return f"{n/1024**2:.1f} MB"
        if n >= 1024:
            return f"{n/1024:.1f} KB"
        return f"{n} B"


# Alias para compatibilidade com código existente
TransferRecord = TransferResult


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

    def __init__(self, my_id: str, ssl_ctx: ssl.SSLContext,
                 my_alias: str = '', max_single: int = None, max_batch: int = None):
        self.my_id      = my_id
        self.my_alias   = my_alias
        self.ssl_ctx    = ssl_ctx
        self.max_single = max_single or MAX_SINGLE_FILE
        self.max_batch  = max_batch  or MAX_BATCH_TOTAL

    def send_single(self, peer: Peer, filepath: Path,
                    on_progress: bool = True) -> TransferRecord:
        return self._send_batch(peer, [filepath], on_progress)[0]

    def send_batch(self, peer: Peer, filepaths: List[Path],
                   on_progress: bool = True) -> List[TransferRecord]:
        return self._send_batch(peer, filepaths, on_progress)

    def _send_batch(self, peer: Peer, filepaths: List[Path],
                    on_progress: bool) -> List[TransferResult]:
        records = []

        # Validar arquivos + limite total do batch
        valid = []
        batch_total = 0
        for fp in filepaths:
            fp = Path(fp)
            if not fp.exists():
                print(f"  ✘ File not found: {fp}")
                records.append(TransferResult(fp.name, 0, False, peer.alias, 'sent'))
                continue
            if not fp.is_file():
                print(f"  ✘ Not a file: {fp}")
                records.append(TransferResult(fp.name, 0, False, peer.alias, 'sent'))
                continue

            allowed, msg = check_file_allowed(fp, self.max_single)
            if not allowed:
                print(f"  ✘ {msg}")
                records.append(TransferResult(fp.name, fp.stat().st_size, False, peer.alias, 'sent'))
                continue
            if msg:
                print(f"  ⚠  {msg}")

            # Checar total do lote
            batch_total += fp.stat().st_size
            if batch_total > self.max_batch:
                mb_lim = self.max_batch // 1024 // 1024
                print(f"  ✘ Batch would exceed {mb_lim} MB — {fp.name} skipped.")
                records.append(TransferResult(fp.name, fp.stat().st_size, False, peer.alias, 'sent'))
                batch_total -= fp.stat().st_size
                continue

            valid.append(fp)

        if not valid:
            return records

        # Connect
        try:
            sock = connect_to_peer(peer, self.ssl_ctx)
        except Exception as e:
            print(f"  ✘ Connection failed: {e}")
            for fp in valid:
                records.append(TransferResult(fp.name, fp.stat().st_size, False, peer.alias, 'sent'))
            return records

        try:
            batch_id = secrets.token_hex(8)

            for idx, fp in enumerate(valid):
                filesize = fp.stat().st_size

                salt        = secrets.token_bytes(32)
                hmac_key    = secrets.token_bytes(32)
                session_key = derive_session_key(hmac_key, salt)
                encryptor   = FileEncryptor(session_key)

                # Offer — includes sender alias for Easter Egg detection on receiver
                send_message(sock, {
                    'type':         'offer',
                    'batch_id':     batch_id,
                    'file_index':   idx,
                    'file_count':   len(valid),
                    'filename':     fp.name,
                    'size':         filesize,
                    'hmac_key':     hmac_key.hex(),
                    'salt':         salt.hex(),
                    'sender_id':    self.my_id,
                    'sender_alias': self.my_alias,
                    'compressed':   True,
                })

                resp = recv_message(sock, timeout=15.0)
                if resp.get('type') != 'accept':
                    reason = resp.get('reason', '?')
                    print(f"  ✘ Rejected by peer: {reason}")
                    records.append(TransferResult(fp.name, filesize, False, peer.alias, 'sent'))
                    continue

                # Progress — single clean bar with batch counter
                prog = TransferProgress(
                    fp.name, filesize, "↑",
                    file_index=idx,
                    file_count=len(valid)
                ) if on_progress else None

                # Stream encriptado
                try:
                    _encrypt_and_send(sock, fp, encryptor, prog)
                except Exception as e:
                    if prog:
                        prog.finish(False)
                    records.append(TransferResult(fp.name, filesize, False, peer.alias, 'sent'))
                    continue

                # HMAC de integridade
                file_hmac = compute_file_hmac(fp, hmac_key)
                send_message(sock, {'type': 'done', 'hmac': file_hmac})

                conf = recv_message(sock, timeout=30.0)
                success = conf.get('type') == 'ok'
                if prog:
                    prog.finish(success)
                records.append(TransferResult(fp.name, filesize, success, peer.alias, 'sent'))

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
    """
    Processa conexões entrantes e recebe arquivos.
    Sem logging, sem histórico persistente — privacidade total.
    """

    def __init__(self, on_receive: Optional[Callable] = None):
        self._on_receive = on_receive  # callback opcional apenas para notificação na tela

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

                filename     = os.path.basename(msg['filename'])
                filesize     = int(msg['size'])
                hmac_key     = bytes.fromhex(msg['hmac_key'])
                salt         = bytes.fromhex(msg['salt'])
                file_index   = msg.get('file_index', 0)
                file_count   = msg.get('file_count', 1)
                sender_alias = msg.get('sender_alias', '')

                # Easter Egg: show Matrix/MrRobot effect on first file of batch
                if file_index == 0 and sender_alias:
                    try:
                        from core.easter_egg import show_receive_egg
                        show_receive_egg(sender_alias)
                    except Exception:
                        pass

                # Accept
                send_message(sock, {'type': 'accept'})

                save_path = self._unique_path(DOWNLOADS_DIR / filename)
                session_key = derive_session_key(hmac_key, salt)
                encryptor   = FileEncryptor(session_key)

                prog = TransferProgress(
                    filename, filesize, "↓",
                    file_index=file_index,
                    file_count=file_count
                )

                success = False
                try:
                    _recv_and_decrypt(sock, save_path, encryptor, filesize, prog)
                    done_msg = recv_message(sock, timeout=15.0)
                    expected_hmac = done_msg.get('hmac', '')
                    ok = verify_file_hmac(save_path, hmac_key, expected_hmac)
                    send_message(sock, {'type': 'ok' if ok else 'error',
                                        'reason': '' if ok else 'hmac_mismatch'})
                    success = ok
                    prog.finish(success)
                    if success:
                        print(f"  ✔ Saved: {save_path.name}")
                    else:
                        print(f"  ✘ Integrity check failed — file removed")
                        save_path.unlink(missing_ok=True)

                except Exception as e:
                    prog.finish(False)
                    send_message(sock, {'type': 'error', 'reason': str(e)})
                    save_path.unlink(missing_ok=True)

                if self._on_receive and success:
                    self._on_receive(filename, addr[0], filesize)

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
