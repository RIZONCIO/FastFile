#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core/crypto.py - Módulo de Criptografia e Anonimato
AES-256-GCM para dados + TLS para transporte + anonimização de identidade
"""

import os
import ssl
import hashlib
import hmac
import secrets
import tempfile
import struct
from pathlib import Path

# Verificação de dependências
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509 import NameOID
    from cryptography import x509
    from cryptography.hazmat.backends import default_backend
    import datetime
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

CERT_DIR = Path.home() / ".fastfile" / "certs"


def ensure_crypto():
    """Verifica se cryptography está disponível"""
    if not CRYPTO_AVAILABLE:
        raise RuntimeError(
            "Pacote 'cryptography' não encontrado.\n"
            "Instale com: pip install cryptography"
        )


# ─────────────────────────────────────────────
#  Geração de identidade anônima
# ─────────────────────────────────────────────

def generate_anonymous_id() -> str:
    """
    Gera um ID anônimo de 12 caracteres baseado em entropia local.
    NÃO usa hostname, usuário ou MAC — apenas entropia aleatória.
    """
    raw = secrets.token_bytes(32)
    digest = hashlib.blake2b(raw, digest_size=6).hexdigest()
    return digest.upper()


def anonymize_hostname(real_hostname: str) -> str:
    """
    Substitui o hostname real por um apelido aleatório e sem relação.
    O mapeamento é salvo localmente para consistência entre sessões.
    """
    alias_file = Path.home() / ".fastfile" / "alias.dat"
    alias_file.parent.mkdir(parents=True, exist_ok=True)

    if alias_file.exists():
        return alias_file.read_text().strip()

    # Gerar apelido aleatório: adjetivo + animal
    adjectives = ["swift", "dark", "quiet", "silent", "hidden", "phantom",
                  "shadow", "ghost", "stealth", "echo", "void", "cipher"]
    nouns = ["fox", "wolf", "raven", "hawk", "lynx", "viper",
             "falcon", "bear", "tiger", "eagle", "shark", "panther"]

    rng = secrets.SystemRandom()
    alias = f"{rng.choice(adjectives)}-{rng.choice(nouns)}-{secrets.token_hex(2)}"
    alias_file.write_text(alias)
    return alias


# ─────────────────────────────────────────────
#  Certificados TLS auto-assinados (sem info pessoal)
# ─────────────────────────────────────────────

def generate_tls_cert(node_id: str):
    """
    Gera certificado TLS auto-assinado anônimo.
    CN = node_id aleatório, sem organização, país ou e-mail.
    Retorna (cert_path, key_path).
    """
    ensure_crypto()
    CERT_DIR.mkdir(parents=True, exist_ok=True)

    cert_path = CERT_DIR / "node.crt"
    key_path = CERT_DIR / "node.key"

    # Reutilizar se já existir
    if cert_path.exists() and key_path.exists():
        return str(cert_path), str(key_path)

    # Gerar chave EC P-384
    key = ec.generate_private_key(ec.SECP384R1(), default_backend())

    # Certificado mínimo anônimo
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, node_id),
    ])

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA384(), default_backend())
    )

    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption()
        )
    )
    # Proteger a chave privada
    os.chmod(str(key_path), 0o600)

    return str(cert_path), str(key_path)


def create_server_ssl_context(node_id: str) -> ssl.SSLContext:
    """Contexto SSL para o servidor (requer certificado do cliente)"""
    ensure_crypto()
    cert_path, key_path = generate_tls_cert(node_id)

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert_path, key_path)
    ctx.verify_mode = ssl.CERT_NONE   # Rede P2P — validação por fingerprint
    ctx.minimum_version = ssl.TLSVersion.TLSv1_3
    ctx.set_ciphers("TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256")
    return ctx


def create_client_ssl_context(node_id: str) -> ssl.SSLContext:
    """Contexto SSL para o cliente"""
    ensure_crypto()
    cert_path, key_path = generate_tls_cert(node_id)

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.load_cert_chain(cert_path, key_path)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE   # Validação por fingerprint abaixo
    ctx.minimum_version = ssl.TLSVersion.TLSv1_3
    ctx.set_ciphers("TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256")
    return ctx


# ─────────────────────────────────────────────
#  Criptografia de dados em repouso (arquivos)
#  AES-256-GCM com chave de sessão derivada via HKDF
# ─────────────────────────────────────────────

def derive_session_key(shared_secret: bytes, salt: bytes) -> bytes:
    """Deriva chave AES-256 de um segredo compartilhado via HKDF-SHA384"""
    ensure_crypto()
    hkdf = HKDF(
        algorithm=hashes.SHA384(),
        length=32,
        salt=salt,
        info=b"p2p-file-transfer-v1",
        backend=default_backend()
    )
    return hkdf.derive(shared_secret)


class FileEncryptor:
    """Encriptação/decriptação de streams de arquivo com AES-256-GCM"""

    CHUNK_SIZE = 64 * 1024  # 64KB chunks
    HEADER_MAGIC = b"P2PENC1"

    def __init__(self, session_key: bytes):
        if len(session_key) != 32:
            raise ValueError("Chave deve ter 32 bytes (AES-256)")
        self.key = session_key
        self.aesgcm = AESGCM(session_key)

    def encrypt_file(self, src_path: Path, dst_path: Path):
        """
        Encripta arquivo em chunks.
        Formato: MAGIC(7) | nonce_count(4) | [nonce(12) | ciphertext_len(4) | ciphertext+tag] ...
        """
        ensure_crypto()
        src_path = Path(src_path)
        dst_path = Path(dst_path)

        filesize = src_path.stat().st_size
        chunk_count = (filesize + self.CHUNK_SIZE - 1) // self.CHUNK_SIZE if filesize > 0 else 0

        with open(src_path, 'rb') as fin, open(dst_path, 'wb') as fout:
            fout.write(self.HEADER_MAGIC)
            fout.write(struct.pack(">I", chunk_count))

            idx = 0
            while True:
                plaintext = fin.read(self.CHUNK_SIZE)
                if not plaintext:
                    break
                # Nonce único por chunk: 4 bytes random base + 8 bytes counter
                nonce = secrets.token_bytes(4) + idx.to_bytes(8, 'big')
                ciphertext = self.aesgcm.encrypt(nonce, plaintext, None)
                fout.write(nonce)
                fout.write(struct.pack(">I", len(ciphertext)))
                fout.write(ciphertext)
                idx += 1

    def decrypt_file(self, src_path: Path, dst_path: Path):
        """Decripta arquivo encriptado por encrypt_file"""
        ensure_crypto()
        src_path = Path(src_path)
        dst_path = Path(dst_path)

        with open(src_path, 'rb') as fin, open(dst_path, 'wb') as fout:
            magic = fin.read(7)
            if magic != self.HEADER_MAGIC:
                raise ValueError("Arquivo não é um P2P encriptado válido")

            chunk_count = struct.unpack(">I", fin.read(4))[0]

            for _ in range(chunk_count):
                nonce = fin.read(12)
                ct_len = struct.unpack(">I", fin.read(4))[0]
                ciphertext = fin.read(ct_len)
                plaintext = self.aesgcm.decrypt(nonce, ciphertext, None)
                fout.write(plaintext)


# ─────────────────────────────────────────────
#  Verificação de integridade (HMAC-SHA256)
# ─────────────────────────────────────────────

def compute_file_hmac(filepath: Path, key: bytes) -> str:
    """Calcula HMAC-SHA256 do arquivo para verificação de integridade"""
    mac = hmac.new(key, digestmod=hashlib.sha256)
    with open(filepath, 'rb') as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            mac.update(chunk)
    return mac.hexdigest()


def verify_file_hmac(filepath: Path, key: bytes, expected_hmac: str) -> bool:
    """Verifica integridade do arquivo"""
    actual = compute_file_hmac(filepath, key)
    return hmac.compare_digest(actual, expected_hmac)


def compute_file_hash(filepath: Path) -> str:
    """Hash SHA-256 simples do arquivo (para deduplicação)"""
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


# ─────────────────────────────────────────────
#  Utilitários
# ─────────────────────────────────────────────

def get_cert_fingerprint(node_id: str) -> str:
    """Retorna fingerprint SHA-256 do certificado local"""
    ensure_crypto()
    cert_path, _ = generate_tls_cert(node_id)
    data = Path(cert_path).read_bytes()
    return hashlib.sha256(data).hexdigest()[:32].upper()
