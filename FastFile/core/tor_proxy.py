#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core/tor_proxy.py - Integração Tor para FastFile
Usa stem (controle do Tor) + PySocks (roteamento SOCKS5).
O binário do Tor é baixado automaticamente se não estiver instalado.

Fluxo:
  1. Verifica se 'tor' está no PATH do sistema
  2. Se não, tenta baixar o Expert Bundle (Windows) ou orientar no Linux/Mac
  3. Lança processo Tor em background com porta SOCKS5 local (9150)
  4. Todas as conexões TCP do FastFile passam pelo onion routing

Anonimato fornecido:
  - IP real nunca exposto ao peer destinatário
  - Tráfego cifrado em 3 camadas (circuito Tor) + TLS 1.3 do FastFile
  - Peer vê apenas o nó de saída Tor, não o IP real
"""

import os
import sys
import time
import socket
import struct
import threading
import subprocess
import platform
import tempfile
import zipfile
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

# ─────────────────────────────────────────────
#  Constantes
# ─────────────────────────────────────────────

TOR_SOCKS_PORT   = 9150   # porta SOCKS5 local do Tor
TOR_CONTROL_PORT = 9151   # porta de controle stem
TOR_DATA_DIR     = Path.home() / ".fastfile" / "tor_data"
TOR_BIN_DIR      = Path.home() / ".fastfile" / "tor_bin"

# URLs do Expert Bundle do Tor Project (apenas binários, sem browser)
_TOR_WIN_URL = (
    "https://archive.torproject.org/tor-package-archive/torbrowser/"
    "13.5.9/tor-expert-bundle-windows-x86_64-13.5.9.tar.gz"
)
_TOR_LINUX_URL = (
    "https://archive.torproject.org/tor-package-archive/torbrowser/"
    "13.5.9/tor-expert-bundle-linux-x86_64-13.5.9.tar.gz"
)
_TOR_MAC_URL = (
    "https://archive.torproject.org/tor-package-archive/torbrowser/"
    "13.5.9/tor-expert-bundle-macos-x86_64-13.5.9.tar.gz"
)

# Dependências Python necessárias para Tor
TOR_PYTHON_DEPS = {
    'stem':    'stem>=1.8',
    'socks':   'PySocks>=1.7',
}

# ─────────────────────────────────────────────
#  Estado global
# ─────────────────────────────────────────────

_tor_process:  Optional[subprocess.Popen] = None
_tor_enabled:  bool = False
_tor_lock      = threading.Lock()


# ─────────────────────────────────────────────
#  Verificação de dependências Python
# ─────────────────────────────────────────────

def _check_python_deps() -> list:
    """Retorna lista de módulos Python ausentes para o Tor."""
    missing = []
    for mod, pkg in TOR_PYTHON_DEPS.items():
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)
    return missing


def install_tor_python_deps() -> bool:
    """Instala stem e PySocks. Retorna True se OK."""
    missing = _check_python_deps()
    if not missing:
        return True
    print("  Instalando dependências Python para Tor...")
    for pkg in missing:
        print(f"    pip install {pkg}")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", pkg,
             "--disable-pip-version-check"],
            capture_output=False,
        )
        if result.returncode != 0:
            # Tentar --user
            subprocess.run(
                [sys.executable, "-m", "pip", "install", pkg,
                 "--user", "--disable-pip-version-check"],
                capture_output=False,
            )
    return not _check_python_deps()


# ─────────────────────────────────────────────
#  Localizar ou baixar o binário Tor
# ─────────────────────────────────────────────

def _find_system_tor() -> Optional[str]:
    """Procura 'tor' no PATH do sistema."""
    import shutil
    return shutil.which("tor")


def _find_bundled_tor() -> Optional[str]:
    """Procura o binário Tor no diretório local do FastFile."""
    system = platform.system()
    if system == "Windows":
        candidates = [
            TOR_BIN_DIR / "tor" / "tor.exe",
            TOR_BIN_DIR / "tor.exe",
        ]
    else:
        candidates = [
            TOR_BIN_DIR / "tor" / "tor",
            TOR_BIN_DIR / "tor",
        ]
    for c in candidates:
        if c.exists():
            return str(c)
    return None


def _download_tor_bundle(progress_cb=None) -> Optional[str]:
    """
    Baixa o Expert Bundle do Tor Project e extrai o binário.
    Retorna o caminho do binário ou None se falhar.
    """
    system = platform.system()
    if system == "Windows":
        url = _TOR_WIN_URL
    elif system == "Darwin":
        url = _TOR_MAC_URL
    else:
        url = _TOR_LINUX_URL

    TOR_BIN_DIR.mkdir(parents=True, exist_ok=True)
    archive_path = TOR_BIN_DIR / "tor_bundle.tar.gz"

    if progress_cb:
        progress_cb("Conectando ao torproject.org...")

    try:
        # Download com progresso
        def _reporthook(count, block_size, total_size):
            if total_size > 0 and progress_cb:
                pct = min(100, count * block_size * 100 // total_size)
                progress_cb(f"Baixando Tor Expert Bundle... {pct}%")

        urllib.request.urlretrieve(url, str(archive_path), _reporthook)

        if progress_cb:
            progress_cb("Extraindo binário...")

        # Extrair
        import tarfile
        with tarfile.open(str(archive_path), 'r:gz') as tf:
            tf.extractall(str(TOR_BIN_DIR))

        archive_path.unlink(missing_ok=True)

        # Localizar binário extraído
        binary = _find_bundled_tor()
        if binary and platform.system() != "Windows":
            os.chmod(binary, 0o755)

        return binary

    except Exception as e:
        if progress_cb:
            progress_cb(f"Erro ao baixar Tor: {e}")
        return None


def find_or_get_tor(progress_cb=None) -> Optional[str]:
    """
    Retorna o caminho do binário Tor, tentando nesta ordem:
    1. Sistema (PATH)
    2. Bundle local já baixado
    3. Download automático do torproject.org
    """
    # 1. Sistema
    path = _find_system_tor()
    if path:
        return path

    # 2. Bundle local
    path = _find_bundled_tor()
    if path:
        return path

    # 3. Download
    if progress_cb:
        progress_cb("Tor não encontrado — iniciando download...")
    return _download_tor_bundle(progress_cb)


# ─────────────────────────────────────────────
#  Gerenciamento do processo Tor
# ─────────────────────────────────────────────

def _write_torrc() -> str:
    """Escreve arquivo de configuração mínimo do Tor."""
    TOR_DATA_DIR.mkdir(parents=True, exist_ok=True)
    torrc_path = TOR_DATA_DIR / "torrc"
    torrc_path.write_text(
        f"SocksPort {TOR_SOCKS_PORT}\n"
        f"ControlPort {TOR_CONTROL_PORT}\n"
        f"DataDirectory {TOR_DATA_DIR}\n"
        f"Log notice stderr\n"
        f"CookieAuthentication 0\n"
        f"HashedControlPassword \"\"\n"
        # Menor latência — sacrifica um pouco de anonimato por velocidade
        f"CircuitBuildTimeout 30\n"
        f"LearnCircuitBuildTimeout 0\n"
    )
    return str(torrc_path)


def start_tor(progress_cb=None) -> dict:
    """
    Inicia o processo Tor em background.
    Retorna {'ok': True/False, 'msg': str}.
    """
    global _tor_process, _tor_enabled

    with _tor_lock:
        if _tor_enabled and _tor_process and _tor_process.poll() is None:
            return {'ok': True, 'msg': 'Tor já está ativo'}

        # Verificar deps Python
        if not install_tor_python_deps():
            return {'ok': False, 'msg': 'Falha ao instalar stem/PySocks'}

        # Localizar binário
        if progress_cb:
            progress_cb("Localizando binário do Tor...")
        tor_bin = find_or_get_tor(progress_cb)
        if not tor_bin:
            return {
                'ok': False,
                'msg': (
                    "Binário do Tor não encontrado e download falhou.\n"
                    "  Instale manualmente:\n"
                    "    Windows: https://www.torproject.org/download/tor/\n"
                    "    Linux  : sudo apt install tor\n"
                    "    macOS  : brew install tor"
                )
            }

        torrc = _write_torrc()

        if progress_cb:
            progress_cb("Iniciando processo Tor...")

        try:
            _tor_process = subprocess.Popen(
                [tor_bin, "-f", torrc],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
        except Exception as e:
            return {'ok': False, 'msg': f"Erro ao iniciar Tor: {e}"}

        # Aguardar bootstrap
        if progress_cb:
            progress_cb("Aguardando Tor conectar à rede (pode levar até 60s)...")

        deadline = time.time() + 90
        bootstrapped = False
        while time.time() < deadline:
            if _tor_process.poll() is not None:
                return {'ok': False, 'msg': 'Processo Tor encerrou inesperadamente'}
            try:
                line = _tor_process.stdout.readline()
                if "Bootstrapped 100%" in line or "Done" in line:
                    bootstrapped = True
                    break
                if progress_cb and "Bootstrapped" in line:
                    # Extrair % do log
                    try:
                        pct = line.split("Bootstrapped")[1].split("%")[0].strip()
                        progress_cb(f"Tor conectando... {pct}%")
                    except Exception:
                        pass
            except Exception:
                break
            time.sleep(0.1)

        if not bootstrapped:
            # Verificar se porta SOCKS está aberta mesmo assim
            bootstrapped = _socks_port_open()

        if bootstrapped:
            _tor_enabled = True
            return {'ok': True, 'msg': f'Tor ativo — SOCKS5 em 127.0.0.1:{TOR_SOCKS_PORT}'}
        else:
            _tor_process.terminate()
            _tor_process = None
            return {'ok': False, 'msg': 'Tor não completou bootstrap no tempo limite'}


def stop_tor():
    """Para o processo Tor."""
    global _tor_process, _tor_enabled
    with _tor_lock:
        _tor_enabled = False
        if _tor_process:
            try:
                _tor_process.terminate()
                _tor_process.wait(timeout=5)
            except Exception:
                try:
                    _tor_process.kill()
                except Exception:
                    pass
            _tor_process = None


def _socks_port_open() -> bool:
    """Verifica se a porta SOCKS5 do Tor está respondendo."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect(('127.0.0.1', TOR_SOCKS_PORT))
        s.close()
        return True
    except Exception:
        return False


def is_tor_active() -> bool:
    """Retorna True se Tor está ativo e a porta SOCKS5 responde."""
    global _tor_enabled, _tor_process
    if not _tor_enabled:
        return False
    if _tor_process and _tor_process.poll() is not None:
        # Processo morreu
        _tor_enabled = False
        return False
    return _socks_port_open()


def get_tor_ip() -> Optional[str]:
    """Retorna o IP de saída atual do Tor (para exibir ao usuário)."""
    if not is_tor_active():
        return None
    try:
        import socks as _socks
        s = _socks.socksocket()
        s.set_proxy(_socks.SOCKS5, "127.0.0.1", TOR_SOCKS_PORT)
        s.settimeout(15)
        s.connect(("check.torproject.org", 80))
        s.sendall(b"GET / HTTP/1.0\r\nHost: check.torproject.org\r\n\r\n")
        resp = s.recv(4096).decode(errors='ignore')
        s.close()
        # Extrair IP da resposta HTML básica
        for line in resp.split('\n'):
            if 'Your IP address appears to be' in line or 'Congratulations' in line:
                return line.strip()
        return "Conectado via Tor ✔"
    except Exception:
        return "Conectado via Tor (IP oculto)"


# ─────────────────────────────────────────────
#  Socket com proxy Tor (SOCKS5)
# ─────────────────────────────────────────────

def create_tor_socket(target_ip: str, target_port: int,
                      timeout: float = 30.0) -> socket.socket:
    """
    Cria um socket TCP roteado pelo Tor (SOCKS5).
    Levanta exceção se Tor não estiver ativo ou falhar.
    """
    try:
        import socks as _socks
    except ImportError:
        raise RuntimeError("PySocks não instalado. Execute: pip install PySocks")

    if not is_tor_active():
        raise RuntimeError("Tor não está ativo. Ative-o no menu [T] antes de conectar.")

    s = _socks.socksocket(socket.AF_INET, socket.SOCK_STREAM)
    s.set_proxy(_socks.SOCKS5, "127.0.0.1", TOR_SOCKS_PORT)
    s.settimeout(timeout)
    s.connect((target_ip, target_port))
    return s


def status_str() -> str:
    """Resumo de status para exibir no menu."""
    if is_tor_active():
        return "\033[92m● TOR ATIVO\033[0m  (IP real oculto)"
    else:
        return "\033[33m○ Tor inativo\033[0m  (usando IP real + TLS)"
