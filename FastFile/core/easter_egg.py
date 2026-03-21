#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core/easter_egg.py - FastFile hidden Easter Eggs
Special aliases unlock higher file limits and terminal effects.
"""

import time
import random
import sys
import os

# ─────────────────────────────────────────────
#  Alias groups
# ─────────────────────────────────────────────

# Tier 1 — higher limits only (50 MB / 500 MB)
TIER1_ALIASES = {
    'shadow', 'ghost', 'hunter', 'zero', 'l33t', 'shell', 'root',
}

# Tier 2 — Matrix effect + higher limits
MATRIX_ALIASES = {
    'omega', '0mega', 'anonymous', 'an0nym0us', 'neo', 'n3o',
}

# Tier 3 — Mr. Robot effect (red) + higher limits
MRROBOT_ALIASES = {
    'mr. robot', 'mr.robot', 'mrrobot',
}

# Easter egg limits
EGG_SINGLE = 50  * 1024 * 1024   # 50 MB
EGG_BATCH  = 500 * 1024 * 1024   # 500 MB

# ─────────────────────────────────────────────
#  Quotes (English)
# ─────────────────────────────────────────────

MATRIX_QUOTES = [
    "Welcome to the desert of the real.",
    "The Matrix is everywhere. It is all around us, even now in this very room.",
    "If you're talking about what you can feel, what you can smell, taste and see,\n"
    "  then real is simply electrical signals interpreted by your brain.",
    "I don't like the idea of not being in control of my life.",
    "As long as the Matrix exists, the human race will never be free.",
    "Do not try to bend the spoon. That's impossible.\n"
    "  Instead, only try to realize the truth: there is no spoon.\n"
    "  Then you'll see that it is not the spoon that bends, it is only yourself.",
    "You take the blue pill — the story ends, you wake up in your bed and believe whatever you want.\n"
    "  You take the red pill — you stay in Wonderland and I show you how deep the rabbit hole goes.",
    "Every mammal on this planet instinctively develops a natural equilibrium with the surrounding environment.\n"
    "  But you humans do not. You move to an area and you multiply until every natural resource is consumed.",
    "I'd like to share a revelation that I've been having during my time here.\n"
    "  It came to me when I tried to classify your species.\n"
    "  The purpose of life is to end.",
    "I don't know the future. I didn't come here to tell you how this is going to end.\n"
    "  I came here to tell you how it's going to begin.\n"
    "  I'm going to show these people a world without you.\n"
    "  A world without rules and controls, without borders or boundaries.\n"
    "  A world where anything is possible.",
]

MRROBOT_QUOTES = [
    "You've been staring at a computer screen for too long. Life is not binary code.",
    "Fantasy is an easy way to make sense of the world, an escape from our harsh reality.",
    "Money hasn't been real since we left the gold standard. It's become virtual.",
    "We all live in each other's paranoia.",
    "You can try to be righteous. You can try to be good. You can try to make a difference.\n"
    "  But it's all bullshit.",
    "I hate when the boss doesn't pick up on a hint.",
    "Every hacker loves attention.",
    "Sometimes I dream of saving the world. Saving everyone from the invisible hand.",
    "Give a man a gun and he can rob a bank.\n"
    "  Give a man a bank and he can rob the world.",
    "The world is a dangerous place, not because of those who do evil,\n"
    "  but because of those who look on and do nothing.",
]

# ─────────────────────────────────────────────
#  Detection
# ─────────────────────────────────────────────

def detect_egg(alias: str) -> str:
    """
    Returns the easter egg tier for an alias:
    'tier1', 'matrix', 'mrrobot', or '' (none).
    """
    a = alias.strip().lower()
    if a in MRROBOT_ALIASES:
        return 'mrrobot'
    if a in MATRIX_ALIASES:
        return 'matrix'
    if a in TIER1_ALIASES:
        return 'tier1'
    return ''


def egg_limits(alias: str):
    """
    Returns (max_single, max_batch) for the given alias.
    Returns None if no egg applies (use defaults).
    """
    tier = detect_egg(alias)
    if tier in ('tier1', 'matrix', 'mrrobot'):
        return EGG_SINGLE, EGG_BATCH
    return None


# ─────────────────────────────────────────────
#  Terminal effects
# ─────────────────────────────────────────────

def _supports_color() -> bool:
    """Check if terminal supports ANSI colors."""
    if os.environ.get('NO_COLOR'):
        return False
    if sys.platform == 'win32':
        try:
            import ctypes
            kernel = ctypes.windll.kernel32
            kernel.SetConsoleMode(kernel.GetStdHandle(-11), 7)
            return True
        except Exception:
            return False
    return hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()


def _matrix_rain(color_code: str = "\033[32m", duration: float = 2.5):
    """
    Prints a Matrix-style binary rain effect in the terminal.
    color_code: ANSI color (green for Matrix, red for Mr. Robot).
    """
    rst = "\033[0m"
    bright = "\033[1m"
    dim    = "\033[2m"
    cols   = min(os.get_terminal_size().columns, 80) if hasattr(os, 'get_terminal_size') else 60
    lines  = 14
    chars  = "01"

    print()
    start = time.time()
    rows_printed = 0
    while time.time() - start < duration and rows_printed < lines:
        row = ""
        for _ in range(cols // 2):
            if random.random() > 0.7:
                row += f"{bright}{color_code}{random.choice(chars)}{rst} "
            else:
                row += f"{dim}{color_code}{random.choice(chars)}{rst} "
        print(row)
        time.sleep(0.08)
        rows_printed += 1
    print()


def show_matrix_egg(alias: str):
    """
    Shows the Matrix binary rain then a quote.
    Green for Matrix aliases, red for Mr. Robot.
    """
    tier = detect_egg(alias)
    if tier not in ('matrix', 'mrrobot'):
        return

    use_color = _supports_color()
    GREEN  = "\033[32m" if use_color else ""
    RED    = "\033[31m" if use_color else ""
    BRIGHT = "\033[1m"  if use_color else ""
    DIM    = "\033[2m"  if use_color else ""
    CYAN   = "\033[36m" if use_color else ""
    RST    = "\033[0m"  if use_color else ""

    if tier == 'mrrobot':
        color = RED
        quote = random.choice(MRROBOT_QUOTES)
        # Rain effect
        _matrix_rain(RED, duration=2.0)
        # Big Mr. Robot title
        print(f"{BRIGHT}{RED}")
        print("  ███╗   ███╗██████╗       ██████╗  ██████╗ ██████╗  ██████╗ ████████╗")
        print("  ████╗ ████║██╔══██╗      ██╔══██╗██╔═══██╗██╔══██╗██╔═══██╗╚══██╔══╝")
        print("  ██╔████╔██║██████╔╝      ██████╔╝██║   ██║██████╔╝██║   ██║   ██║   ")
        print("  ██║╚██╔╝██║██╔══██╗      ██╔══██╗██║   ██║██╔══██╗██║   ██║   ██║   ")
        print("  ██║ ╚═╝ ██║██║  ██║      ██║  ██║╚██████╔╝██████╔╝╚██████╔╝   ██║   ")
        print("  ╚═╝     ╚═╝╚═╝  ╚═╝      ╚═╝  ╚═╝ ╚═════╝ ╚═════╝  ╚═════╝   ╚═╝   ")
        print(RST)
        print(f"{DIM}{RED}  {'─'*64}{RST}")
        for line in quote.split('\n'):
            print(f"  {BRIGHT}{RED}\"{line}\"{RST}")
        print(f"{DIM}{RED}  {'─'*64}{RST}")
        print()
        print(f"  {DIM}{RED}// fsociety mode engaged // file limits unlocked{RST}")

    else:
        # Matrix aliases
        color = GREEN
        quote = random.choice(MATRIX_QUOTES)
        _matrix_rain(GREEN, duration=2.5)
        # Quote in green
        print(f"{DIM}{GREEN}  {'─'*64}{RST}")
        for line in quote.split('\n'):
            print(f"  {BRIGHT}{GREEN}\"{line}\"{RST}")
        print(f"{DIM}{GREEN}  {'─'*64}{RST}")
        print()
        # Show which tier the alias gives
        print(f"  {DIM}{GREEN}// identity verified // file limits unlocked{RST}")

    print()
    time.sleep(0.5)


def show_startup_egg(alias: str):
    """
    Called at node start. Shows egg effect + unlock message if applicable.
    """
    tier = detect_egg(alias)
    if not tier:
        return

    use_color = _supports_color()
    GREEN  = "\033[32m" if use_color else ""
    YELLOW = "\033[33m" if use_color else ""
    BRIGHT = "\033[1m"  if use_color else ""
    RST    = "\033[0m"  if use_color else ""

    if tier in ('matrix', 'mrrobot'):
        show_matrix_egg(alias)

    print(f"  {BRIGHT}{YELLOW}🔓 EASTER EGG UNLOCKED{RST}")
    print(f"  {GREEN}  Per-file limit : 50 MB  (normal: 20 MB){RST}")
    print(f"  {GREEN}  Batch limit    : 500 MB (normal: 200 MB){RST}")
    print()
    time.sleep(1)


# ─────────────────────────────────────────────
#  Receiver-side effect
# ─────────────────────────────────────────────

def show_receive_egg(sender_alias: str):
    """
    Called on the RECEIVER when a file arrives from an egg alias.
    Shows the Matrix/Mr.Robot effect in the receiver's terminal.
    """
    tier = detect_egg(sender_alias)
    if tier in ('matrix', 'mrrobot'):
        show_matrix_egg(sender_alias)
