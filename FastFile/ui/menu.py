#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ui/menu.py - Interface de linha de comando completa
100% funcional no CMD (Windows) e terminal (Linux/Mac).
"""

import os
import sys
import time
import platform
from pathlib import Path
from typing import Optional

# Colorama para suporte a cores no Windows CMD
try:
    from colorama import init as _cinit, Fore, Style, Back
    _cinit(autoreset=True)
    C = {
        'H':  Fore.CYAN  + Style.BRIGHT,   # header
        'G':  Fore.GREEN + Style.BRIGHT,    # ok / verde
        'Y':  Fore.YELLOW,                  # aviso / info
        'R':  Fore.RED   + Style.BRIGHT,    # erro / perigo
        'B':  Fore.BLUE  + Style.BRIGHT,    # destaque azul
        'M':  Fore.MAGENTA,                 # detalhe
        'W':  Style.BRIGHT,                 # branco brilhante
        'DIM': Style.DIM,
        'RST': Style.RESET_ALL,
    }
except ImportError:
    C = {k: '' for k in ('H','G','Y','R','B','M','W','DIM','RST')}


# ─────────────────────────────────────────────
#  Utilidades de terminal
# ─────────────────────────────────────────────

def cls():
    os.system('cls' if platform.system() == 'Windows' else 'clear')


def pause(msg: str = "  Pressione Enter para continuar..."):
    input(f"\n{C['Y']}{msg}{C['RST']}")


def prompt(msg: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        val = input(f"{C['Y']}  {msg}{suffix}: {C['RST']}").strip()
    except (EOFError, KeyboardInterrupt):
        return default
    return val if val else default


def confirm(msg: str) -> bool:
    ans = prompt(f"{msg} (s/N)").lower()
    return ans in ('s', 'sim', 'y', 'yes')


def hr(char: str = "─", width: int = 60) -> str:
    return C['DIM'] + char * width + C['RST']


def title(text: str) -> str:
    pad = (58 - len(text)) // 2
    return (
        f"\n{C['H']}╔{'═'*58}╗\n"
        f"║{' '*pad}{text}{' '*(58 - pad - len(text))}║\n"
        f"╚{'═'*58}╝{C['RST']}\n"
    )


def section(text: str):
    print(f"\n{C['B']}  ┌─ {text} {C['RST']}")


def ok(text: str):
    print(f"  {C['G']}✔  {text}{C['RST']}")


def warn(text: str):
    print(f"  {C['Y']}⚠  {text}{C['RST']}")


def err(text: str):
    print(f"  {C['R']}✘  {text}{C['RST']}")


def info(text: str):
    print(f"  {C['M']}•  {text}{C['RST']}")


def bullet(text: str):
    print(f"       {C['DIM']}{text}{C['RST']}")


# ─────────────────────────────────────────────
#  Tela principal
# ─────────────────────────────────────────────

VERSION = "3.1"

BANNER = r"""
  ███████╗ █████╗ ███████╗████████╗███████╗██╗██╗     ███████╗
  ██╔════╝██╔══██╗██╔════╝╚══██╔══╝██╔════╝██║██║     ██╔════╝
  █████╗  ███████║███████╗   ██║   █████╗  ██║██║     █████╗
  ██╔══╝  ██╔══██║╚════██║   ██║   ██╔══╝  ██║██║     ██╔══╝
  ██║     ██║  ██║███████║   ██║   ██║     ██║███████╗███████╗
  ╚═╝     ╚═╝  ╚═╝╚══════╝   ╚═╝   ╚═╝     ╚═╝╚══════╝╚══════╝
"""

def show_banner():
    cls()
    print(C['H'] + BANNER + C['RST'])
    print(f"  {C['DIM']}FastFile v{VERSION}  •  TLS 1.3 + AES-256-GCM + zlib  •  P2P Seguro{C['RST']}")
    print(f"  {C['DIM']}Criptografia de ponta a ponta  •  Identidade anônima{C['RST']}")
    print()


def main_menu(node_started: bool, peer_count: int, alias: str) -> str:
    show_banner()
    status = (
        f"{C['G']}ONLINE{C['RST']}  alias={C['W']}{alias}{C['RST']}  peers={C['W']}{peer_count}{C['RST']}"
        if node_started else f"{C['Y']}OFFLINE{C['RST']}"
    )
    print(f"  Status: {status}\n")
    print(hr())
    print(f"  {C['B']}[1]{C['RST']}  🚀  Iniciar nó P2P")
    print(f"  {C['B']}[2]{C['RST']}  👥  Ver quem está na rede")
    print(f"  {C['B']}[3]{C['RST']}  📤  Enviar arquivo(s)")
    print(f"  {C['B']}[4]{C['RST']}  📋  Histórico de transferências")
    print(f"  {C['B']}[5]{C['RST']}  ℹ️   Informações do sistema")
    print(f"  {C['Y']}[6]{C['RST']}  📂  Formatos suportados / bloqueados")
    print(f"  {C['R']}[7]{C['RST']}  💣  AUTO-DESTRUIÇÃO")
    print(f"  {C['DIM']}[8]{C['RST']}  🚪  Sair")
    print(hr())
    return prompt("Opção")


# ─────────────────────────────────────────────
#  Tela: iniciar nó
# ─────────────────────────────────────────────

def screen_start(node) -> bool:
    cls()
    print(title("INICIAR NÓ P2P"))
    print("  Iniciando serviços...")
    print()

    result = node.start()

    if result['status'] == 'already_running':
        warn("Nó já está em execução.")
        pause()
        return True

    if result['status'] == 'error':
        err(result['msg'])
        pause()
        return False

    ok(f"Nó iniciado com sucesso!")
    print()
    section("Identidade")
    info(f"Node ID   : {C['W']}{result['node_id']}{C['RST']}")
    info(f"Alias     : {C['W']}{result['alias']}{C['RST']}")
    info(f"Fingerprt : {C['W']}{result['fingerprint']}{C['RST']}")
    print()
    section("Rede")
    info(f"IPs       : {', '.join(result['ips'])}")
    info(f"Porta     : {result['port']}")
    info(f"Descoberta: {result['disc_mode']}")
    info(f"Downloads : {result['downloads']}")
    print()
    info("Aguardando outros nós na rede...")
    pause()
    return True


# ─────────────────────────────────────────────
#  Tela: listar peers
# ─────────────────────────────────────────────

def screen_peers(node):
    cls()
    print(title("PEERS NA REDE"))

    if not node._started:
        warn("Nó não iniciado. Use a opção [1] primeiro.")
        pause()
        return

    peers = node.list_peers()
    node.registry.prune()

    if not peers:
        warn("Nenhum peer encontrado ainda.")
        info("Certifique-se de que outros nós estão ativos na mesma rede.")
        pause()
        return

    print(f"  {C['G']}{len(peers)} peer(s) online:{C['RST']}\n")
    print(f"  {'#':<3}  {'ALIAS':<22}  {'IP':<16}  {'NODE ID':<14}  {'VISTO HÁ'}")
    print(hr())
    for i, p in enumerate(peers, 1):
        elapsed = int(time.time() - p.last_seen)
        print(
            f"  {C['B']}{i:<3}{C['RST']}  "
            f"{C['W']}{p.alias:<22}{C['RST']}  "
            f"{p.ip:<16}  "
            f"{C['DIM']}{p.node_id:<14}{C['RST']}  "
            f"{elapsed}s atrás"
        )

    pause()


# ─────────────────────────────────────────────
#  Tela: enviar arquivo(s)
# ─────────────────────────────────────────────

def screen_send(node):
    cls()
    print(title("ENVIAR ARQUIVO(S)"))

    if not node._started:
        warn("Nó não iniciado. Use a opção [1] primeiro.")
        pause()
        return

    peers = node.list_peers()
    if not peers:
        warn("Nenhum peer disponível.")
        pause()
        return

    # Selecionar peer
    section("Selecionar destinatário")
    print(f"  {'#':<3}  {'ALIAS':<22}  {'IP'}")
    print(hr())
    for i, p in enumerate(peers, 1):
        print(f"  {C['B']}{i:<3}{C['RST']}  {C['W']}{p.alias:<22}{C['RST']}  {p.ip}")
    print()

    peer_choice = prompt("Número do peer (ou Node ID/alias)")
    peer = None

    if peer_choice.isdigit():
        idx = int(peer_choice) - 1
        if 0 <= idx < len(peers):
            peer = peers[idx]
    else:
        peer = node._resolve_peer(peer_choice)

    if not peer:
        err("Peer inválido.")
        pause()
        return

    ok(f"Destinatário: {peer.alias} ({peer.ip})")
    print()

    # Modo de envio
    section("Modo de envio")
    print(f"  {C['B']}[1]{C['RST']}  Enviar 1 arquivo")
    print(f"  {C['B']}[2]{C['RST']}  Enviar vários arquivos (lote)")
    print()
    mode = prompt("Modo", "1")

    if mode == "1":
        _send_single(node, peer)
    elif mode == "2":
        _send_batch(node, peer)
    else:
        err("Opção inválida.")
        pause()


def _send_single(node, peer):
    section("Envio de 1 arquivo")
    filepath = prompt("Caminho do arquivo").strip('"').strip("'")
    if not filepath:
        err("Caminho vazio.")
        pause()
        return

    p = Path(filepath)
    if not p.exists():
        err(f"Arquivo não encontrado: {filepath}")
        pause()
        return

    # Verificar extensão e tamanho
    from core.transfer import check_file_allowed
    allowed, msg = check_file_allowed(p)
    if not allowed:
        err(msg)
        pause()
        return
    if msg:
        print()
        print(f"  {C['Y']}⚠  {msg}{C['RST']}")
        if not confirm("Continuar mesmo assim?"):
            print("  Cancelado.")
            pause()
            return

    size_mb = p.stat().st_size / 1024 / 1024
    info(f"Arquivo   : {p.name}")
    info(f"Tamanho   : {size_mb:.2f} MB")
    info(f"Compressão: zlib nível 6  (obrigatória)")
    print()

    if not confirm("Confirmar envio?"):
        print("  Cancelado.")
        pause()
        return

    print()
    success = node.send_file(peer.node_id, filepath)
    print()
    if success:
        ok("Transferência concluída com integridade verificada ✔")
    else:
        err("Falha na transferência.")
    pause()


def _send_batch(node, peer):
    section("Envio em lote")
    info("Digite os caminhos dos arquivos, um por linha.")
    info("Linha vazia para finalizar.\n")

    from core.transfer import check_file_allowed

    filepaths = []
    while True:
        entry = prompt(f"  Arquivo {len(filepaths)+1} (vazio = pronto)").strip('"').strip("'")
        if not entry:
            break
        p = Path(entry)
        if not p.exists():
            warn(f"Não encontrado: {entry} — ignorado.")
            continue
        if not p.is_file():
            warn(f"Não é um arquivo: {entry} — ignorado.")
            continue

        allowed, msg = check_file_allowed(p)
        if not allowed:
            err(f"{msg}")
            warn("Arquivo ignorado.")
            continue
        if msg:
            print(f"  {C['Y']}⚠  {msg}{C['RST']}")

        filepaths.append(entry)
        ok(f"Adicionado: {p.name}  ({p.stat().st_size/1024:.1f} KB)")

    if not filepaths:
        warn("Nenhum arquivo válido.")
        pause()
        return

    print()
    info(f"Total: {len(filepaths)} arquivo(s) para enviar a {peer.alias}")
    for fp in filepaths:
        bullet(Path(fp).name)
    print()

    if not confirm("Confirmar envio?"):
        print("  Cancelado.")
        pause()
        return

    print()
    records = node.send_files(peer.node_id, filepaths)
    print()

    ok_n  = sum(1 for r in records if r.success)
    err_n = len(records) - ok_n
    print(hr())
    info(f"Resultado: {C['G']}{ok_n} OK{C['RST']}  |  {C['R']}{err_n} falhas{C['RST']}")
    for r in records:
        mark = f"{C['G']}✔{C['RST']}" if r.success else f"{C['R']}✘{C['RST']}"
        print(f"  {mark}  {r.filename}")
    pause()


# ─────────────────────────────────────────────
#  Tela: histórico
# ─────────────────────────────────────────────

def screen_history(node):
    cls()
    print(title("HISTÓRICO DE TRANSFERÊNCIAS"))

    history = node.get_history()
    if not history:
        warn("Nenhuma transferência registrada nesta sessão.")
        pause()
        return

    for r in reversed(history[-30:]):
        print(r.display())

    print()
    info(f"Total na sessão: {len(history)} transferência(s)")
    pause()


# ─────────────────────────────────────────────
#  Tela: info do sistema
# ─────────────────────────────────────────────

def screen_sysinfo(node):
    cls()
    print(title("INFORMAÇÕES DO SISTEMA"))

    si = node.system_info()
    section("Identidade (anônima)")
    info(f"Node ID       : {si['node_id']}")
    info(f"Alias         : {si['alias']}")
    info(f"Fingerprint   : {si['fingerprint'] or '(não iniciado)'}")

    section("Rede")
    info(f"IPs locais    : {', '.join(si['ips'])}")
    info(f"Porta TCP     : {si['port']}")
    info(f"Status        : {'ONLINE' if si['running'] else 'OFFLINE'}")

    section("Segurança")
    info(f"TLS           : 1.3 obrigatório")
    info(f"Criptografia  : AES-256-GCM (dados)  +  TLS (transporte)")
    info(f"Integridade   : HMAC-SHA256 por arquivo")
    info(f"Módulo crypto : {'✔ cryptography' if si['crypto'] else '✘ não instalado'}")

    section("Arquivos")
    info(f"Downloads     : {si['downloads']}")
    info(f"Work dir      : {si['work_dir']}")

    section("Plataforma")
    info(f"Sistema       : {si['platform']}")

    pause()


# ─────────────────────────────────────────────
#  Tela: formatos suportados / bloqueados
# ─────────────────────────────────────────────

def screen_formats():
    cls()
    print(title("FORMATOS DE ARQUIVO"))

    section("✔  Suportados (exemplos)")
    SUPPORTED = [
        ("Imagens",     ".jpg  .jpeg  .png  .gif  .webp  .bmp  .svg  .ico  .tiff"),
        ("Documentos",  ".pdf  .docx  .xlsx  .pptx  .odt  .ods  .odp  .txt  .rtf"),
        ("Código",      ".py  .js  .ts  .html  .css  .c  .cpp  .java  .rs  .go  .sh"),
        ("Dados",       ".json  .xml  .csv  .yaml  .toml  .env  .ini  .cfg"),
        ("Compactados", ".zip  .tar  .gz  .tar.gz  .tar.xz  .7z  .rar  .bz2"),
        ("Áudio",       ".mp3  .wav  .flac  .ogg  .aac  .m4a  .opus"),
        ("Executáveis", ".exe  .msi  .deb  .rpm  .apk  .jar"),
        ("Fontes",      ".ttf  .otf  .woff  .woff2"),
        ("E-books",     ".epub  .mobi  .azw3"),
        ("Outros",      "Qualquer arquivo até 500 MB não listado abaixo"),
    ]
    for cat, exts in SUPPORTED:
        print(f"  {C['G']}  {cat:<14}{C['RST']}  {C['DIM']}{exts}{C['RST']}")

    print()
    section("✘  Bloqueados — muito pesados ou proprietários")
    BLOCKED_DISPLAY = [
        ("Vídeo",             ".mp4  .mkv  .avi  .mov  .wmv  .flv  .webm  .m4v  .mpg  .mpeg  .ts  .3gp"),
        ("Projetos DAW",      ".aup  .aup3  .ptx  .ptf  .als  .flp  (Audacity, Pro Tools, Ableton, FL)"),
        ("Adobe / Design",    ".psd  .ai  .indd  .xd  .aep  .prproj  (Photoshop, Illustrator, InDesign, Premiere, AE)"),
        ("Affinity",          ".afdesign  .afphoto  (Affinity Designer / Photo)"),
        ("RAW fotográfico",   ".nef  .cr2  .cr3  .arw  .raf  .dng  (Nikon, Canon, Sony, Fuji, Adobe DNG)"),
        ("Imagem de disco/VM",".iso  .img  .vmdk  .vhd  .vhdx  .ova  .ovf"),
        ("Dumps / Backups",   ".bak  .dump  .sql"),
    ]
    for cat, exts in BLOCKED_DISPLAY:
        print(f"  {C['R']}  {cat:<20}{C['RST']}  {C['DIM']}{exts}{C['RST']}")

    print()
    section("ℹ  Limite de tamanho")
    info(f"Máximo por arquivo : {C['W']}500 MB{C['RST']}")
    info(f"Aviso exibido acima: {C['W']}50 MB{C['RST']}")
    info(f"Compressão         : {C['W']}zlib nível 6 — obrigatória em todos os envios{C['RST']}")
    print()
    warn("Para arquivos muito grandes ou bloqueados, use um serviço de cloud")
    warn("(Google Drive, Mega, etc.) ou divida o arquivo antes de enviar.")

    pause()


# ─────────────────────────────────────────────
#  Tela: auto-destruição
# ─────────────────────────────────────────────

def screen_destruct(node):
    cls()
    print(f"\n{C['R']}{'█'*60}{C['RST']}")
    print(f"{C['R']}  ⚠   AUTO-DESTRUIÇÃO  —  FastFile   ⚠{C['RST']}")
    print(f"{C['R']}{'█'*60}{C['RST']}\n")
    print(f"  Esta ação é {C['R']}IRREVERSÍVEL{C['RST']} e irá:\n")
    bullet("Remover todos os arquivos baixados")
    bullet("Apagar o diretório de configuração (~/.fastfile)")
    bullet("Deletar o script/pasta do programa permanentemente")
    print()
    warn("Seus dados pessoais NÃO serão afetados (apenas dados do FastFile).")
    print()

    confirm1 = prompt(f"  {C['R']}Digite DESTRUIR para confirmar{C['RST']}")
    if confirm1 != "DESTRUIR":
        print(f"\n  {C['G']}Auto-destruição cancelada.{C['RST']}")
        pause()
        return

    confirm2 = prompt(f"  {C['R']}Tem certeza absoluta? Digite SIM{C['RST']}")
    if confirm2 != "SIM":
        print(f"\n  {C['G']}Auto-destruição cancelada.{C['RST']}")
        pause()
        return

    print(f"\n  {C['R']}Executando auto-destruição...{C['RST']}")
    time.sleep(0.5)

    node.self_destruct()

    print(f"\n  {C['R']}Concluído. O programa será encerrado.{C['RST']}")
    time.sleep(2)
    sys.exit(0)
