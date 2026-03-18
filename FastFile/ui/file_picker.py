#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ui/file_picker.py - Seletor de arquivos para FastFile
Modo 1: janela gráfica nativa via tkinter (Windows/Mac/Linux)
Modo 2: navegador de pastas no terminal (fallback automático)

Permite selecionar 1 arquivo ou múltiplos de uma vez,
sem ter que digitar caminhos inteiros.
"""

import os
import sys
import platform
from pathlib import Path
from typing import List, Optional

# ─────────────────────────────────────────────
#  Detectar disponibilidade do tkinter
# ─────────────────────────────────────────────

def _tkinter_available() -> bool:
    """Verifica se tkinter está disponível e display existe."""
    try:
        import tkinter as tk
        # Em servidores sem display, tkinter importa mas Tk() falha
        root = tk.Tk()
        root.withdraw()
        root.destroy()
        return True
    except Exception:
        return False


# ─────────────────────────────────────────────
#  Seleção via janela gráfica (tkinter)
# ─────────────────────────────────────────────

def _pick_single_gui(initial_dir: str = None) -> Optional[str]:
    """
    Abre o explorador de arquivos nativo do sistema operacional.
    Retorna o caminho selecionado ou None se cancelado.
    """
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)   # Garante que a janela fica na frente

    path = filedialog.askopenfilename(
        title="FastFile — Selecione um arquivo para enviar",
        initialdir=initial_dir or str(Path.home()),
        filetypes=[
            ("Todos os arquivos", "*.*"),
            ("Imagens",           "*.jpg *.jpeg *.png *.gif *.webp *.bmp *.svg"),
            ("Documentos",        "*.pdf *.docx *.xlsx *.pptx *.txt *.odt"),
            ("Código",            "*.py *.js *.ts *.html *.css *.c *.cpp *.rs *.go"),
            ("Compactados",       "*.zip *.tar.gz *.7z *.rar"),
            ("Áudio",             "*.mp3 *.wav *.flac *.ogg *.aac"),
        ],
    )
    root.destroy()
    return path if path else None


def _pick_multiple_gui(initial_dir: str = None) -> List[str]:
    """
    Abre o explorador de arquivos nativo permitindo seleção múltipla.
    Retorna lista de caminhos ou lista vazia se cancelado.
    Ctrl+Click / Shift+Click seleciona múltiplos.
    """
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)

    paths = filedialog.askopenfilenames(
        title="FastFile — Selecione os arquivos (Ctrl+clique para múltiplos)",
        initialdir=initial_dir or str(Path.home()),
        filetypes=[
            ("Todos os arquivos", "*.*"),
            ("Imagens",           "*.jpg *.jpeg *.png *.gif *.webp *.bmp *.svg"),
            ("Documentos",        "*.pdf *.docx *.xlsx *.pptx *.txt *.odt"),
            ("Código",            "*.py *.js *.ts *.html *.css *.c *.cpp *.rs *.go"),
            ("Compactados",       "*.zip *.tar.gz *.7z *.rar"),
            ("Áudio",             "*.mp3 *.wav *.flac *.ogg *.aac"),
        ],
    )
    root.destroy()
    return list(paths) if paths else []


# ─────────────────────────────────────────────
#  Navegador de pastas no terminal (fallback)
# ─────────────────────────────────────────────

try:
    from colorama import Fore, Style
    _C = {
        'DIR':  Fore.CYAN  + Style.BRIGHT,
        'FILE': Fore.WHITE,
        'SEL':  Fore.GREEN + Style.BRIGHT,
        'NUM':  Fore.BLUE  + Style.BRIGHT,
        'WARN': Fore.YELLOW,
        'ERR':  Fore.RED,
        'DIM':  Style.DIM,
        'RST':  Style.RESET_ALL,
    }
except ImportError:
    _C = {k: '' for k in ('DIR','FILE','SEL','NUM','WARN','ERR','DIM','RST')}


def _list_dir(path: Path) -> tuple:
    """
    Lista o conteúdo de um diretório.
    Retorna (dirs, files) ordenados alfabeticamente.
    """
    dirs, files = [], []
    try:
        for item in sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
            if item.name.startswith('.'):
                continue   # ocultar arquivos ocultos por padrão
            if item.is_dir():
                dirs.append(item)
            elif item.is_file():
                files.append(item)
    except PermissionError:
        pass
    return dirs, files


def _fmt_size(n: int) -> str:
    if n >= 1024**3:
        return f"{n/1024**3:.1f}G"
    if n >= 1024**2:
        return f"{n/1024**2:.1f}M"
    if n >= 1024:
        return f"{n/1024:.1f}K"
    return f"{n}B"


def _browse_terminal(start_dir: Path = None,
                     multi: bool = False) -> List[str]:
    """
    Navegador interativo de arquivos no terminal.
    Navega por pastas, seleciona arquivo(s) e retorna caminhos.
    """
    current = start_dir or Path.home()
    selected: List[Path] = []

    while True:
        # ── Limpar e desenhar tela ──
        os.system('cls' if platform.system() == 'Windows' else 'clear')

        dirs, files = _list_dir(current)

        print(f"\n{_C['DIR']}  📂  {current}{_C['RST']}")
        print(_C['DIM'] + "  " + "─" * 56 + _C['RST'])

        items = []   # lista unificada para indexar

        # Opção de voltar
        if current.parent != current:
            print(f"  {_C['NUM']}  0{_C['RST']}  {_C['DIR']}..  (pasta acima){_C['RST']}")

        # Pastas
        for d in dirs:
            idx = len(items)
            items.append(('dir', d))
            print(f"  {_C['NUM']}{idx+1:>3}{_C['RST']}  {_C['DIR']}📁 {d.name}/{_C['RST']}")

        # Arquivos
        for f in files:
            idx = len(items)
            items.append(('file', f))
            size_s = _fmt_size(f.stat().st_size)
            mark = f"  {_C['SEL']}✔{_C['RST']}" if f in selected else "   "
            print(f"  {_C['NUM']}{idx+1:>3}{_C['RST']}{mark}  {f.name}  "
                  f"{_C['DIM']}({size_s}){_C['RST']}")

        print(_C['DIM'] + "  " + "─" * 56 + _C['RST'])

        if multi:
            sel_names = [f.name for f in selected]
            print(f"\n  Selecionados: {_C['SEL']}{len(selected)}{_C['RST']}"
                  + (f"  {_C['DIM']}{', '.join(sel_names[:3])}"
                     + ("..." if len(sel_names) > 3 else "") + _C['RST']
                     if sel_names else ""))
            print(f"\n  {_C['DIM']}[número] Navegar/selecionar  "
                  f"[0] Pasta acima  "
                  f"[Enter] Confirmar seleção  "
                  f"[q] Cancelar{_C['RST']}")
        else:
            print(f"\n  {_C['DIM']}[número] Navegar/abrir  "
                  f"[0] Pasta acima  "
                  f"[q] Cancelar{_C['RST']}")

        try:
            choice = input(f"\n  Escolha: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return []

        if choice == 'q':
            return []

        if choice == '' and multi and selected:
            return [str(p) for p in selected]

        if choice == '' and not multi:
            continue

        if choice == '0':
            if current.parent != current:
                current = current.parent
            continue

        # Permitir digitar caminho direto
        if os.sep in choice or (platform.system() == 'Windows' and ':' in choice):
            direct = Path(choice.strip('"').strip("'"))
            if direct.is_file():
                if multi:
                    if direct not in selected:
                        selected.append(direct)
                    continue
                else:
                    return [str(direct)]
            elif direct.is_dir():
                current = direct
            else:
                print(f"  {_C['ERR']}Caminho não encontrado.{_C['RST']}")
                input("  Enter para continuar...")
            continue

        try:
            idx = int(choice) - 1
        except ValueError:
            continue

        if idx < 0 or idx >= len(items):
            continue

        kind, item = items[idx]

        if kind == 'dir':
            current = item
        elif kind == 'file':
            if multi:
                # Toggle seleção
                if item in selected:
                    selected.remove(item)
                else:
                    selected.append(item)
            else:
                return [str(item)]


# ─────────────────────────────────────────────
#  API pública
# ─────────────────────────────────────────────

_gui_available: Optional[bool] = None


def _check_gui() -> bool:
    global _gui_available
    if _gui_available is None:
        _gui_available = _tkinter_available()
    return _gui_available


def pick_file(start_dir: str = None) -> Optional[str]:
    """
    Seleciona 1 arquivo.
    Usa janela gráfica se disponível, senão navega no terminal.
    Retorna caminho ou None se cancelado.
    """
    if _check_gui():
        return _pick_single_gui(start_dir)
    else:
        results = _browse_terminal(
            Path(start_dir) if start_dir else None,
            multi=False
        )
        return results[0] if results else None


def pick_files(start_dir: str = None) -> List[str]:
    """
    Seleciona múltiplos arquivos.
    GUI: Ctrl+clique para múltiplos.
    Terminal: navegar e selecionar com toggle, Enter confirma.
    Retorna lista de caminhos ou lista vazia se cancelado.
    """
    if _check_gui():
        return _pick_multiple_gui(start_dir)
    else:
        return _browse_terminal(
            Path(start_dir) if start_dir else None,
            multi=True
        )


def gui_mode_label() -> str:
    """Retorna string descrevendo o modo de seleção ativo."""
    if _check_gui():
        return "janela gráfica nativa"
    else:
        return "navegador terminal (tkinter indisponível)"
