#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main.py - FastFile v3.4
Installs dependencies BEFORE any internal import or CLI starts.
Linux fix: tries --break-system-packages when needed (PEP 668).
"""

import sys
import os
import subprocess
import platform

APP_NAME = "FastFile"
APP_VERSION = "1.5"

if sys.version_info < (3, 8):
    print(f"[{APP_NAME}] ERROR: Python 3.8+ required. Current: {sys.version}")
    sys.exit(1)

REQUIRED = {
    "cryptography": "cryptography>=41.0",
    "colorama": "colorama>=0.4",
    "zeroconf": "zeroconf>=0.60",
    "stem": "stem>=1.8",
    "socks": "PySocks>=1.7",
    "pyzipper": "pyzipper>=0.3",
}

# Optional — netifaces needs C compiler on Windows, so we try but don't fail
OPTIONAL = {
    "netifaces": "netifaces>=0.11",
    "ifaddr": "ifaddr>=0.1",
}

_W = 54


def _box(lines, color="\033[96m", rst="\033[0m"):
    print(color + "╔" + "═" * _W + "╗" + rst)
    for line in lines:
        pad = _W - len(line)
        print(color + "║ " + rst + line + " " * max(0, pad - 1) + color + "║" + rst)
    print(color + "╚" + "═" * _W + "╝" + rst)


def _try_import(module):
    try:
        __import__(module)
        return True
    except ImportError:
        return False


def _pip_install(package):
    """
    Tries to install a package.
    Order: normal → --user → --break-system-packages (Linux PEP 668 fix).
    """
    base_cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        package,
        "--disable-pip-version-check",
    ]

    # Attempt 1: normal
    r = subprocess.run(base_cmd, capture_output=False)
    if r.returncode == 0:
        return True

    # Attempt 2: --user
    r = subprocess.run(base_cmd + ["--user"], capture_output=False)
    if r.returncode == 0:
        return True

    # Attempt 3: --break-system-packages (Debian/Ubuntu with PEP 668)
    r = subprocess.run(base_cmd + ["--break-system-packages"], capture_output=False)
    if r.returncode == 0:
        return True

    # Attempt 4: --user + --break-system-packages
    r = subprocess.run(
        base_cmd + ["--user", "--break-system-packages"], capture_output=False
    )
    return r.returncode == 0


def ensure_dependencies():
    missing = {mod: pkg for mod, pkg in REQUIRED.items() if not _try_import(mod)}
    if not missing:
        print(f"\033[92m[{APP_NAME}] All dependencies OK — starting...\033[0m\n")
        # Try optional deps silently
        for mod, pkg in OPTIONAL.items():
            if not _try_import(mod):
                subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "pip",
                        "install",
                        pkg,
                        "--quiet",
                        "--disable-pip-version-check",
                    ],
                    capture_output=True,
                )
        return

    os.system("cls" if platform.system() == "Windows" else "clear")
    _box(
        [
            f"{APP_NAME} v{APP_VERSION}  —  Installing dependencies",
            "",
            "This only runs on the FIRST launch.",
            "Next startups will be instant.",
            "",
            f"Platform : {platform.system()} {platform.release()}",
            f"Python   : {sys.version.split()[0]}",
        ]
    )
    print()

    failed = []
    for i, (module, package) in enumerate(missing.items(), 1):
        print(f"  [{i}/{len(missing)}]  Installing  \033[93m{package}\033[0m ...")
        print("  " + "─" * 50)
        success = _pip_install(package)
        print("  " + "─" * 50)
        if success:
            print(f"  \033[92m✔  {package} installed!\033[0m\n")
        else:
            print(f"  \033[91m✘  Failed to install {package}\033[0m")
            print(f"     Install manually:  pip install {package}\n")
            failed.append(package)

    if failed:
        print("\033[91m" + "─" * 56 + "\033[0m")
        print("\033[91mSOME DEPENDENCIES FAILED:\033[0m")
        for f in failed:
            print(f"  pip install {f}")
        print("\033[91m" + "─" * 56 + "\033[0m")
        input("\nPress Enter to try starting anyway...")
    else:
        _box(
            [
                "✔  All dependencies installed!",
                "",
                "Press Enter to start FastFile...",
            ],
            color="\033[92m",
        )
        input()

    # Try optional packages silently — failure is OK
    for mod, pkg in OPTIONAL.items():
        if not _try_import(mod):
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    pkg,
                    "--quiet",
                    "--disable-pip-version-check",
                ],
                capture_output=True,
            )


def main():
    ensure_dependencies()

    from core.node import P2PNode
    from ui.menu import (
        main_menu,
        cls,
        screen_start,
        screen_peers,
        screen_add_peer,
        screen_send,
        screen_profile,
        screen_destruct,
        err,
        warn,
        C,
    )

    node = P2PNode()

    while True:
        try:
            peer_count = node.registry.count() if node.registry else 0
            alias = node.alias if node._started else "-"
            tor_active = node.is_tor_active()
            choice = main_menu(node._started, peer_count, alias, tor_active)

            if choice == "1":
                screen_start(node)
            elif choice == "2":
                screen_peers(node)
            elif choice == "3":
                screen_add_peer(node)
            elif choice == "4":
                screen_send(node)
            elif choice == "5":
                screen_profile(node)
            elif choice == "6":
                cls()
                print(f"\n  {C['G']}Shutting down FastFile...{C['RST']}")
                node.shutdown()
                print(f"  {C['G']}Goodbye!{C['RST']}\n")
                break
            elif choice == "7":
                screen_destruct(node)
            else:
                warn("Invalid option.")
                import time as _t

                _t.sleep(1)

        except KeyboardInterrupt:
            cls()
            print(f"\n  {C['Y']}Interrupted (Ctrl+C). Shutting down...{C['RST']}")
            node.shutdown()
            break
        except Exception as e:
            err(f"Unexpected error: {e}")
            import traceback

            traceback.print_exc()
            input("  Press Enter to continue...")


if __name__ == "__main__":
    main()
