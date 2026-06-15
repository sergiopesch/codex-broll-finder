#!/usr/bin/env python3
"""Wrapper for the repo-local b-roll helper CLI."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

if __name__ == "__main__":
    from codex_broll_finder.cli import main

    raise SystemExit(main())
