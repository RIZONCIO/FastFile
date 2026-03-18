#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main.py - FastFile  •  Transferência Segura de Arquivos P2P
Instala dependências ANTES de qualquer import interno ou CLI.
"""

import sys
import os
import subprocess
import platform

APP_NAME = "FastFile"
APP_VERSION = "1.5"

# ─────────────────────────────────────────────
#  Verificação de Python
# ─────────────────────────────────────────────

if sys.version_info < (3, 8):
    print(f"[{APP_NAME}] ERRO: Python 3.8+ necessário. Versão atual: {sys.version}")
    sys.exit(1)

REQUIRED = {
    "cryptography": "cryptography>=41.0",
    "colorama": "colorama>=0.4",
    "netifaces": "netifaces>=0.11",
    "zeroconf": "zeroconf>=0.60",
}

_WIDTH = 54


def _box(lines: list, color_code: str = "\033[96m", rst: str = "\033[0m"):
    """Imprime caixa simples ANSI (funciona em CMD Win10+, Linux e Mac)."""
    print(color_code + "╔" + "═" * _WIDTH + "╗" + rst)
    for line in lines:
        pad = _WIDTH - len(line)
        print(color_code + "║ " + rst + line + " " * (pad - 1) + color_code + "║" + rst)
    print(color_code + "╚" + "═" * _WIDTH + "╝" + rst)


def _try_import(module: str) -> bool:
    try:
        __import__(module)
        return True
    except ImportError:
        return False


def _pip_install(package: str) -> bool:
    """Tenta instalar via pip. Retorna True se bem-sucedido."""
    # Tentativa 1 — padrão
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            package,
            "--disable-pip-version-check",
        ],
        capture_output=False,  # mostra output do pip em tempo real
    )
    if result.returncode == 0:
        return True

    # Tentativa 2 — --user (ambientes sem permissão de sistema)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            package,
            "--user",
            "--disable-pip-version-check",
        ],
        capture_output=False,
    )
    return result.returncode == 0


def ensure_dependencies():
    missing = {mod: pkg for mod, pkg in REQUIRED.items() if not _try_import(mod)}

    if not missing:
        # Todas presentes — exibir confirmação rápida e seguir
        print(f"\033[92m[{APP_NAME}] Dependências OK — iniciando...\033[0m\n")
        return

    os.system("cls" if platform.system() == "Windows" else "clear")
    _box(
        [
            f"{APP_NAME} v{APP_VERSION}  —  Instalando dependências",
            "",
            "Isso ocorre apenas na PRIMEIRA execução.",
            "As próximas inicializações serão instantâneas.",
            "",
            f"Plataforma: {platform.system()} {platform.release()}",
            f"Python    : {sys.version.split()[0]}",
        ]
    )
    print()

    failed = []
    for i, (module, package) in enumerate(missing.items(), 1):
        print(f"  [{i}/{len(missing)}]  Instalando  \033[93m{package}\033[0m ...")
        print("  " + "─" * 50)
        success = _pip_install(package)
        print("  " + "─" * 50)
        if success:
            print(f"  \033[92m✔  {package} instalado com sucesso!\033[0m\n")
        else:
            print(f"  \033[91m✘  Falha ao instalar {package}\033[0m")
            print(f"     Instale manualmente:  pip install {package}\n")
            failed.append(package)

    if failed:
        print("\033[91m" + "─" * 56 + "\033[0m")
        print("\033[91mALGUMAS DEPENDÊNCIAS FALHARAM:\033[0m")
        for f in failed:
            print(f"  pip install {f}")
        print("\033[91m" + "─" * 56 + "\033[0m")
        input("\nPressione Enter para tentar iniciar mesmo assim...")
    else:
        _box(
            [
                "✔  Todas as dependências foram instaladas!",
                "",
                "Pressione Enter para iniciar o FastFile...",
            ],
            color_code="\033[92m",
        )
        input()


# ─────────────────────────────────────────────
#  PONTO DE ENTRADA
# ─────────────────────────────────────────────


def main():
    # 1. Instalar deps PRIMEIRO — antes de qualquer import interno
    ensure_dependencies()

    # 2. Só agora importar módulos que dependem dos pacotes instalados
    from core.node import P2PNode
    from ui.menu import (
        main_menu,
        cls,
        screen_start,
        screen_peers,
        screen_send,
        screen_history,
        screen_sysinfo,
        screen_destruct,
        screen_formats,
        err,
        warn,
        C,
    )

    node = P2PNode()

    while True:
        try:
            peer_count = node.registry.count() if node.registry else 0
            alias = node.alias if node._started else "-"
            choice = main_menu(node._started, peer_count, alias)

            if choice == "1":
                screen_start(node)

            elif choice == "2":
                screen_peers(node)

            elif choice == "3":
                screen_send(node)

            elif choice == "4":
                screen_history(node)

            elif choice == "5":
                screen_sysinfo(node)

            elif choice == "6":
                screen_formats()

            elif choice == "7":
                screen_destruct(node)

            elif choice == "8":
                cls()
                print(f"\n  {C['G']}Encerrando FastFile...{C['RST']}")
                node.shutdown()
                print(f"  {C['G']}Até logo!{C['RST']}\n")
                break

            else:
                warn("Opção inválida.")
                import time

                time.sleep(1)

        except KeyboardInterrupt:
            cls()
            print(f"\n  {C['Y']}Interrompido (Ctrl+C). Encerrando...{C['RST']}")
            node.shutdown()
            break
        except Exception as e:
            err(f"Erro inesperado: {e}")
            import traceback

            traceback.print_exc()
            input("  Pressione Enter para continuar...")


if __name__ == "__main__":
    main()
