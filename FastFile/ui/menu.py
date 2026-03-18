#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ui/menu.py - Interface CLI completa do FastFile v3.3
Tor toggle, seletor gráfico de arquivos, perfil anônimo sem histórico.
"""

import os
import sys
import time
import platform
from pathlib import Path

try:
    from colorama import init as _cinit, Fore, Style
    _cinit(autoreset=True)
    C = {
        'H':   Fore.CYAN   + Style.BRIGHT,
        'G':   Fore.GREEN  + Style.BRIGHT,
        'Y':   Fore.YELLOW,
        'R':   Fore.RED    + Style.BRIGHT,
        'B':   Fore.BLUE   + Style.BRIGHT,
        'M':   Fore.MAGENTA,
        'W':   Style.BRIGHT,
        'DIM': Style.DIM,
        'RST': Style.RESET_ALL,
    }
except ImportError:
    C = {k: '' for k in ('H','G','Y','R','B','M','W','DIM','RST')}


def cls():
    os.system('cls' if platform.system() == 'Windows' else 'clear')

def pause(msg="  Pressione Enter para continuar..."):
    input(f"\n{C['Y']}{msg}{C['RST']}")

def prompt(msg, default=""):
    suffix = f" [{default}]" if default else ""
    try:
        val = input(f"{C['Y']}  {msg}{suffix}: {C['RST']}").strip()
    except (EOFError, KeyboardInterrupt):
        return default
    return val if val else default

def confirm(msg):
    return prompt(f"{msg} (s/N)").lower() in ('s','sim','y','yes')

def hr(char="─", width=60):
    return C['DIM'] + char * width + C['RST']

def title(text):
    pad = max(0, (58 - len(text)) // 2)
    rpad = 58 - pad - len(text)
    return (f"\n{C['H']}╔{'═'*58}╗\n"
            f"║{' '*pad}{text}{' '*rpad}║\n"
            f"╚{'═'*58}╝{C['RST']}\n")

def section(text):
    print(f"\n{C['B']}  ┌─ {text} {C['RST']}")

def ok(text):   print(f"  {C['G']}✔  {text}{C['RST']}")
def warn(text): print(f"  {C['Y']}⚠  {text}{C['RST']}")
def err(text):  print(f"  {C['R']}✘  {text}{C['RST']}")
def info(text): print(f"  {C['M']}•  {text}{C['RST']}")
def bullet(text): print(f"       {C['DIM']}{text}{C['RST']}")


VERSION = "3.3"
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
    print(f"  {C['DIM']}FastFile v{VERSION}  •  TLS 1.3 + AES-256-GCM + zlib  •  P2P Seguro{C['RST']}")
    if tor_active:
        print(f"  {C['G']}● TOR ATIVO{C['RST']}  {C['DIM']}— IP real oculto via onion routing{C['RST']}")
    else:
        print(f"  {C['Y']}○ Tor inativo{C['RST']}  {C['DIM']}— IP real + TLS 1.3{C['RST']}")
    print()

def main_menu(node_started, peer_count, alias, tor_active=False):
    show_banner(tor_active)
    status = (
        f"{C['G']}ONLINE{C['RST']}  alias={C['W']}{alias}{C['RST']}  peers={C['W']}{peer_count}{C['RST']}"
        if node_started else f"{C['Y']}OFFLINE{C['RST']}"
    )
    print(f"  Status: {status}\n")
    print(hr())
    print(f"  {C['B']}[1]{C['RST']}  🚀  Iniciar nó P2P")
    print(f"  {C['B']}[2]{C['RST']}  👥  Ver peers na rede")
    print(f"  {C['B']}[3]{C['RST']}  🔗  Adicionar peer por IP")
    print(f"  {C['B']}[4]{C['RST']}  📤  Enviar arquivo(s)")
    print(f"  {C['B']}[5]{C['RST']}  🪪  Perfil anônimo")
    if tor_active:
        print(f"  {C['G']}[6]{C['RST']}  🧅  Desativar Tor  {C['DIM']}(ATIVO){C['RST']}")
    else:
        print(f"  {C['M']}[6]{C['RST']}  🧅  Ativar Tor  {C['DIM']}(anonimato extra){C['RST']}")
    print(f"  {C['Y']}[7]{C['RST']}  📂  Formatos suportados / bloqueados")
    print(f"  {C['R']}[8]{C['RST']}  💣  AUTO-DESTRUIÇÃO")
    print(f"  {C['DIM']}[9]{C['RST']}  🚪  Sair")
    print(hr())
    return prompt("Opção")


# ── [1] Iniciar nó ────────────────────────────

def screen_start(node):
    cls()
    print(title("INICIAR NÓ P2P"))
    print("  Iniciando serviços...\n")
    result = node.start()
    if result['status'] == 'already_running':
        warn("Nó já está em execução.")
        pause(); return True
    if result['status'] == 'error':
        err(result['msg'])
        pause(); return False
    ok("Nó iniciado!")
    print()
    section("Identidade anônima")
    info(f"Node ID   : {C['W']}{result['node_id']}{C['RST']}")
    info(f"Alias     : {C['W']}{result['alias']}{C['RST']}")
    info(f"Fingerprt : {C['W']}{result['fingerprint']}{C['RST']}")
    section("Rede")
    info(f"IPs       : {', '.join(result['ips'])}")
    info(f"Porta     : {result['port']}")
    info(f"Descoberta: {result['disc_mode']}")
    info(f"Downloads : {result['downloads']}")
    print()
    info("Descoberta automática ativa. Aguardando peers...")
    pause(); return True


# ── [2] Peers ─────────────────────────────────

def screen_peers(node):
    cls()
    print(title("PEERS NA REDE"))
    if not node._started:
        warn("Nó não iniciado. Use [1] primeiro.")
        pause(); return
    peers = node.list_peers()
    node.registry.prune()
    if not peers:
        warn("Nenhum peer encontrado ainda.")
        info("Na mesma rede: aguarde a descoberta automática.")
        info("Em redes diferentes: use [3] para adicionar por IP.")
        pause(); return
    print(f"  {C['G']}{len(peers)} peer(s) online:{C['RST']}\n")
    print(f"  {'#':<3}  {'ALIAS':<22}  {'IP':<16}  {'NODE ID':<14}  {'VISTO HÁ'}")
    print(hr())
    for i, p in enumerate(peers, 1):
        elapsed = int(time.time() - p.last_seen)
        print(f"  {C['B']}{i:<3}{C['RST']}  {C['W']}{p.alias:<22}{C['RST']}  "
              f"{p.ip:<16}  {C['DIM']}{p.node_id:<14}{C['RST']}  {elapsed}s atrás")
    pause()


# ── [3] Adicionar peer por IP ─────────────────

def screen_add_peer(node):
    cls()
    print(title("ADICIONAR PEER POR IP"))
    if not node._started:
        warn("Nó não iniciado. Use [1] primeiro.")
        pause(); return
    section("Conexão manual entre redes")
    print(f"  {C['DIM']}Para funcionar entre redes diferentes:{C['RST']}")
    bullet("VPN (Tailscale, ZeroTier, WireGuard) — mais simples")
    bullet("Tor ativo nos dois lados — use [6]")
    bullet("Port forward na porta 55771 TCP do roteador")
    print()
    ip = prompt("IP do peer").strip()
    if not ip:
        warn("Cancelado."); pause(); return
    from core.network import SERVICE_PORT
    try:
        port = int(prompt("Porta", str(SERVICE_PORT)))
    except ValueError:
        err("Porta inválida."); pause(); return
    if node.add_peer_manual(ip, port):
        ok(f"Peer adicionado: {ip}:{port}")
        info("Heartbeat confirmará status em até 20s. Veja em [2].")
    else:
        err("Falha. Nó iniciado?")
    pause()


# ── [4] Enviar arquivo(s) ─────────────────────

def screen_send(node):
    cls()
    print(title("ENVIAR ARQUIVO(S)"))
    if not node._started:
        warn("Nó não iniciado. Use [1] primeiro.")
        pause(); return
    peers = node.list_peers()
    if not peers:
        warn("Nenhum peer disponível.")
        info("Use [2] para ver peers ou [3] para adicionar por IP.")
        pause(); return

    section("Selecionar destinatário")
    print(f"  {'#':<3}  {'ALIAS':<22}  {'IP'}")
    print(hr())
    for i, p in enumerate(peers, 1):
        print(f"  {C['B']}{i:<3}{C['RST']}  {C['W']}{p.alias:<22}{C['RST']}  {p.ip}")
    print()
    peer_choice = prompt("Número do peer (ou alias)")
    peer = None
    if peer_choice.isdigit():
        idx = int(peer_choice) - 1
        if 0 <= idx < len(peers):
            peer = peers[idx]
    else:
        peer = node._resolve_peer(peer_choice)
    if not peer:
        err("Peer inválido."); pause(); return

    ok(f"Destinatário: {peer.alias} ({peer.ip})")
    print()

    section("Modo de envio")
    from ui.file_picker import gui_mode_label
    info(f"Seletor ativo: {gui_mode_label()}")
    print()
    print(f"  {C['B']}[1]{C['RST']}  Enviar 1 arquivo          (máx 20 MB)")
    print(f"  {C['B']}[2]{C['RST']}  Enviar vários arquivos     (máx 200 MB total)")
    print()
    mode = prompt("Modo", "1")
    if mode == "1":
        _send_single(node, peer)
    elif mode == "2":
        _send_batch(node, peer)
    else:
        err("Opção inválida."); pause()


def _send_single(node, peer):
    section("Selecionar 1 arquivo")
    from ui.file_picker import pick_file, gui_mode_label
    from core.transfer import check_file_allowed, MAX_SINGLE_FILE
    info(f"Abrindo seletor ({gui_mode_label()})...")
    print()
    filepath = pick_file()
    if not filepath:
        warn("Nenhum arquivo selecionado."); pause(); return
    p = Path(filepath)
    if not p.exists():
        err(f"Não encontrado: {filepath}"); pause(); return
    allowed, msg = check_file_allowed(p)
    if not allowed:
        err(msg); pause(); return
    if msg:
        print(); warn(msg)
        if not confirm("Continuar?"):
            warn("Cancelado."); pause(); return
    size_mb = p.stat().st_size / 1024 / 1024
    print()
    info(f"Arquivo   : {C['W']}{p.name}{C['RST']}")
    info(f"Tamanho   : {size_mb:.2f} MB  (máx {MAX_SINGLE_FILE//1024//1024} MB)")
    info(f"Compressão: zlib nível 6 (automática)")
    if node.is_tor_active():
        info(f"Roteamento: {C['G']}via Tor — IP oculto{C['RST']}")
    print()
    if not confirm("Confirmar envio?"):
        warn("Cancelado."); pause(); return
    print()
    success = node.send_file(peer.node_id, filepath)
    print()
    ok("Concluído — integridade HMAC verificada ✔") if success else err("Falha na transferência.")
    pause()


def _send_batch(node, peer):
    section("Selecionar vários arquivos")
    from ui.file_picker import pick_files, gui_mode_label
    from core.transfer import check_file_allowed, MAX_SINGLE_FILE, MAX_BATCH_TOTAL
    info(f"Abrindo seletor ({gui_mode_label()})...")
    if "janela" in gui_mode_label():
        info("Ctrl+clique seleciona vários arquivos de uma vez.")
    else:
        info("Navegue e selecione. Enter vazio confirma.")
    print()
    raw_paths = pick_files()
    if not raw_paths:
        warn("Nenhum arquivo selecionado."); pause(); return

    filepaths = []
    batch_bytes = 0
    print()
    for raw in raw_paths:
        p = Path(raw)
        if not p.exists() or not p.is_file():
            warn(f"Ignorado: {Path(raw).name}"); continue
        allowed, msg = check_file_allowed(p)
        if not allowed:
            err(f"{p.name} — bloqueado"); continue
        if msg:
            warn(f"{p.name} — {msg}")
        sz = p.stat().st_size
        if batch_bytes + sz > MAX_BATCH_TOTAL:
            warn(f"{p.name} ignorado — lote atingiria {MAX_BATCH_TOTAL//1024//1024} MB."); continue
        batch_bytes += sz
        filepaths.append(raw)
        ok(f"  {p.name}  ({sz/1024:.1f} KB)")

    if not filepaths:
        warn("Nenhum arquivo válido."); pause(); return

    print()
    info(f"Total: {len(filepaths)} arquivo(s)  —  {batch_bytes/1024/1024:.1f} / {MAX_BATCH_TOTAL//1024//1024} MB")
    if node.is_tor_active():
        info(f"Roteamento: {C['G']}via Tor — IP oculto{C['RST']}")
    print()
    if not confirm("Confirmar envio?"):
        warn("Cancelado."); pause(); return
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


# ── [5] Perfil anônimo ────────────────────────

def screen_profile(node):
    cls()
    print(title("PERFIL ANONIMO"))
    si = node.system_info()
    section("🪪  Identidade")
    info(f"Node ID     : {C['W']}{si['node_id']}{C['RST']}")
    info(f"Alias       : {C['W']}{si['alias']}{C['RST']}")
    info(f"Fingerprint : {C['W']}{si['fingerprint'] or '(inicie o nó)'}{C['RST']}")
    print(f"\n  {C['DIM']}ID e alias são entropia pura — sem relação com nome, hostname ou MAC.{C['RST']}")
    section("🌐  Rede & segurança")
    status_s = f"{C['G']}ONLINE{C['RST']}" if si['running'] else f"{C['Y']}OFFLINE{C['RST']}"
    info(f"Status      : {status_s}")
    info(f"IPs locais  : {', '.join(si['ips'])}")
    info(f"Porta TCP   : {si['port']}")
    info(f"TLS         : 1.3  |  AES-256-GCM + ChaCha20")
    info(f"Integridade : HMAC-SHA256 por arquivo")
    info(f"Compressão  : zlib nível 6 (automática)")
    tor_s = (f"{C['G']}ATIVO — onion routing{C['RST']}"
             if si.get('tor_active') else f"{C['Y']}Inativo — use [6]{C['RST']}")
    info(f"Tor         : {tor_s}")
    section("📁  Armazenamento")
    info(f"Downloads   : {si['downloads']}")
    info(f"Work dir    : {si['work_dir']}")
    info(f"Plataforma  : {si['platform']}")
    section("🔒  Privacidade")
    print(f"  {C['G']}  Histórico de transferências : DESATIVADO{C['RST']}")
    print(f"  {C['G']}  Logging em disco            : NENHUM{C['RST']}")
    print(f"  {C['DIM']}  Nada do que você envia ou recebe é registrado.{C['RST']}")
    pause()


# ── [6] Tor toggle ────────────────────────────

def screen_tor(node):
    cls()
    print(title("TOR — ANONIMATO EXTRA"))
    if node.is_tor_active():
        section("● Tor está ATIVO")
        info("Tráfego roteado via onion routing — IP real oculto.")
        print()
        if confirm("Desativar Tor?"):
            node.stop_tor()
            ok("Tor desativado. Usando IP real + TLS 1.3.")
        else:
            warn("Cancelado — Tor continua ativo.")
        pause(); return

    section("O que o Tor faz")
    print(f"  {C['DIM']}Roteia o tráfego por 3 nós intermediários (onion routing).{C['RST']}")
    print(f"  {C['DIM']}O peer vê apenas o IP do nó de saída Tor, nunca o seu IP real.{C['RST']}")
    print(f"  {C['DIM']}FastFile ainda usa TLS 1.3 sobre o Tor — segurança dupla.{C['RST']}")
    print()
    section("⚠  Desempenho")
    warn("Tor adiciona latência (~100–500 ms por hop).")
    warn("Velocidade de upload será reduzida.")
    print()
    section("Processo de ativação")
    info("1. Verifica stem e PySocks (já instalados pelo FastFile)")
    info("2. Localiza Tor no sistema ou baixa o Expert Bundle (~5 MB)")
    info("3. Aguarda bootstrap na rede Tor (até 60 s)")
    print()
    if not confirm("Ativar Tor agora?"):
        warn("Cancelado."); pause(); return
    print()

    def _progress(msg):
        print(f"  {C['M']}→  {msg}{C['RST']}")

    result = node.start_tor(progress_cb=_progress)
    print()
    if result['ok']:
        ok(f"Tor ativo!  {result['msg']}")
        info("Todas as conexões agora passam pelo onion routing.")
    else:
        err(f"Falha: {result['msg']}")
        print()
        warn("Instale o Tor manualmente:")
        bullet("Windows : https://www.torproject.org/download/tor/")
        bullet("Linux   : sudo apt install tor")
        bullet("macOS   : brew install tor")
        warn("Com Tor no sistema o FastFile o detecta automaticamente.")
    pause()


# ── [7] Formatos ──────────────────────────────

def screen_formats():
    cls()
    print(title("FORMATOS DE ARQUIVO"))
    from core.transfer import MAX_SINGLE_FILE, MAX_BATCH_TOTAL
    section("✔  Suportados (exemplos)")
    for cat, exts in [
        ("Imagens",     ".jpg .jpeg .png .gif .webp .bmp .svg .tiff"),
        ("Documentos",  ".pdf .docx .xlsx .pptx .odt .txt .rtf .epub"),
        ("Código",      ".py .js .ts .html .css .c .cpp .rs .go .sh"),
        ("Dados",       ".json .xml .csv .yaml .toml .env .ini"),
        ("Compactados", ".zip .tar.gz .7z .rar .bz2"),
        ("Áudio",       ".mp3 .wav .flac .ogg .aac .m4a"),
        ("Executáveis", ".exe .msi .deb .apk .jar"),
    ]:
        print(f"  {C['G']}  {cat:<14}{C['RST']}  {C['DIM']}{exts}{C['RST']}")
    print()
    section("✘  Bloqueados")
    for cat, exts in [
        ("Vídeo",          ".mp4 .mkv .avi .mov .wmv .flv .webm .m4v .mpg .3gp"),
        ("Projetos DAW",   ".aup .aup3 .ptx .als .flp"),
        ("Adobe",          ".psd .ai .indd .xd .aep .prproj"),
        ("Affinity",       ".afdesign .afphoto"),
        ("RAW foto",       ".nef .cr2 .cr3 .arw .raf .dng"),
        ("Disco/VM",       ".iso .img .vmdk .vhd .vhdx .ova"),
        ("Dumps",          ".bak .dump .sql"),
    ]:
        print(f"  {C['R']}  {cat:<16}{C['RST']}  {C['DIM']}{exts}{C['RST']}")
    print()
    section("ℹ  Limites")
    info(f"Por arquivo : {C['W']}{MAX_SINGLE_FILE // 1024 // 1024} MB{C['RST']}")
    info(f"Por lote    : {C['W']}{MAX_BATCH_TOTAL // 1024 // 1024} MB total{C['RST']}")
    info(f"Compressão  : {C['W']}zlib nível 6 — automática{C['RST']}")
    warn("Para arquivos bloqueados, compacte em .zip antes de enviar.")
    pause()


# ── [8] Auto-destruição ───────────────────────

def screen_destruct(node):
    cls()
    print(f"\n{C['R']}{'█'*60}{C['RST']}")
    print(f"{C['R']}  ⚠   AUTO-DESTRUIÇÃO  —  FastFile   ⚠{C['RST']}")
    print(f"{C['R']}{'█'*60}{C['RST']}\n")
    print(f"  Esta ação é {C['R']}IRREVERSÍVEL{C['RST']} e irá:\n")
    bullet("Parar Tor se ativo")
    bullet("Remover downloads (~/.fastfile/downloads)")
    bullet("Apagar certificados e configuração (~/.fastfile)")
    bullet("Deletar a pasta do programa")
    print()
    warn("Seus arquivos pessoais NÃO são afetados.")
    print()
    if prompt(f"  {C['R']}Digite DESTRUIR{C['RST']}") != "DESTRUIR":
        ok("Cancelado."); pause(); return
    if prompt(f"  {C['R']}Certeza? Digite SIM{C['RST']}") != "SIM":
        ok("Cancelado."); pause(); return
    print(f"\n  {C['R']}Executando...{C['RST']}")
    time.sleep(0.5)
    node.self_destruct()
    print(f"\n  {C['R']}Concluído. Encerrando.{C['RST']}")
    time.sleep(2)
    sys.exit(0)
