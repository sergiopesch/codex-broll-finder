from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = Path.home() / ".codex" / "skills" / ".system" / "skill-creator" / "scripts" / "quick_validate.py"


def main() -> int:
    if not VALIDATOR.exists():
        print("skill validator not available in CI environment; skipping")
        return 0
    return subprocess.call([sys.executable, str(VALIDATOR), str(ROOT / "broll-finder")])


if __name__ == "__main__":
    raise SystemExit(main())
