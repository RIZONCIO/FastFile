#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_easter_egg.py — FastFile Easter Egg preview tool
Run this to preview all Easter Egg effects without starting the full app.
DELETE this file before releasing publicly.

Usage:
    python test_easter_egg.py
    python test_easter_egg.py neo
    python test_easter_egg.py "mr. robot"
"""

import sys
import os

# Make sure we can import from the project
sys.path.insert(0, os.path.dirname(__file__))

try:
    from core.easter_egg import (
        TIER1_ALIASES, MATRIX_ALIASES, MRROBOT_ALIASES,
        detect_egg, egg_limits, show_startup_egg, show_matrix_egg,
        EGG_SINGLE, EGG_BATCH
    )
except ImportError as e:
    print(f"Error importing easter_egg: {e}")
    print("Make sure you run this from the FastFile folder.")
    sys.exit(1)

from core.transfer import MAX_SINGLE_FILE, MAX_BATCH_TOTAL

G  = "\033[92m"
Y  = "\033[93m"
R  = "\033[91m"
B  = "\033[94m"
M  = "\033[95m"
C  = "\033[96m"
W  = "\033[1m"
D  = "\033[2m"
RST= "\033[0m"

def divider(ch="─", w=60):
    print(D + ch * w + RST)

def show_all():
    print(f"\n{W}{'═'*60}{RST}")
    print(f"{C}  FastFile Easter Egg — Preview Tool{RST}")
    print(f"{W}{'═'*60}{RST}\n")

    print(f"{Y}  All known Easter Egg aliases:{RST}\n")

    print(f"  {G}Tier 1{RST} — File limits unlocked only:")
    for a in sorted(TIER1_ALIASES):
        lim = egg_limits(a)
        print(f"    {W}{a:<16}{RST}  → {G}{lim[0]//1024//1024} MB / {lim[1]//1024//1024} MB batch{RST}")

    print()
    print(f"  {G}Tier 2 — Matrix effect{RST} (green rain + quote):")
    for a in sorted(MATRIX_ALIASES):
        lim = egg_limits(a)
        print(f"    {W}{a:<16}{RST}  → {G}{lim[0]//1024//1024} MB / {lim[1]//1024//1024} MB batch{RST}")

    print()
    print(f"  {R}Tier 3 — Mr. Robot effect{RST} (red rain + ASCII title):")
    for a in sorted(MRROBOT_ALIASES):
        lim = egg_limits(a)
        print(f"    {W}{a:<16}{RST}  → {G}{lim[0]//1024//1024} MB / {lim[1]//1024//1024} MB batch{RST}")

    print()
    print(f"  {D}Normal limits: {MAX_SINGLE_FILE//1024//1024} MB / {MAX_BATCH_TOTAL//1024//1024} MB batch{RST}")
    print(f"  {D}Egg limits:    {EGG_SINGLE//1024//1024} MB / {EGG_BATCH//1024//1024} MB batch{RST}")

    divider()
    print(f"\n  {W}Commands:{RST}")
    print(f"    {C}python test_easter_egg.py{RST}              — show this list")
    print(f"    {C}python test_easter_egg.py neo{RST}          — preview Matrix effect")
    print(f"    {C}python test_easter_egg.py ghost{RST}        — preview Tier 1 (limits only)")
    print(f"    {C}python test_easter_egg.py \"mr. robot\"{RST}  — preview Mr. Robot effect")
    print(f"    {C}python test_easter_egg.py all{RST}          — preview ALL effects in sequence\n")


def preview_alias(alias: str):
    tier = detect_egg(alias)
    lims = egg_limits(alias)

    print(f"\n{W}{'═'*60}{RST}")
    print(f"  Preview for alias: {W}{alias}{RST}")
    print(f"  Tier: {W}{tier or 'none (no egg)'}{RST}")
    if lims:
        print(f"  Limits: {G}{lims[0]//1024//1024} MB per file / {lims[1]//1024//1024} MB batch{RST}")
    print(f"{W}{'═'*60}{RST}\n")

    if tier == 'none' or not tier:
        print(f"  {Y}No Easter Egg for alias '{alias}'.{RST}\n")
        return

    input(f"  Press Enter to play the effect for '{alias}'...")
    show_startup_egg(alias)
    print(f"\n  {G}Effect finished.{RST}\n")


def preview_all():
    aliases_to_show = [
        ('ghost',    'Tier 1 — limits only'),
        ('neo',      'Tier 2 — Matrix green'),
        ('anonymous','Tier 2 — Matrix green'),
        ('mr. robot','Tier 3 — Mr. Robot red'),
    ]
    for alias, label in aliases_to_show:
        print(f"\n{W}{'─'*60}{RST}")
        print(f"  Next: {C}{label}{RST}  (alias: {W}{alias}{RST})")
        print(f"{W}{'─'*60}{RST}")
        input("  Press Enter to play...")
        show_startup_egg(alias)
        print(f"\n  {G}Done. Next one coming up...{RST}")
        import time; time.sleep(1)
    print(f"\n  {G}All effects previewed!{RST}\n")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        show_all()
    elif sys.argv[1].lower() == 'all':
        show_all()
        print()
        preview_all()
    else:
        alias = ' '.join(sys.argv[1:]).lower()
        preview_alias(alias)
