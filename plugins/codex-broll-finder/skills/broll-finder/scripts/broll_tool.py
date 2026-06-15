#!/usr/bin/env python3
"""Wrapper for the bundled b-roll helper CLI."""
from __future__ import annotations

import sys
from pathlib import Path

for parent in Path(__file__).resolve().parents:
    src = parent / "src"
    if (src / "codex_broll_finder").is_dir():
        if str(src) not in sys.path:
            sys.path.insert(0, str(src))
        break

if __name__ == "__main__":
    from codex_broll_finder.cli import main

    raise SystemExit(main())
