from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from quick_validate_skill import skill_errors


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "kino"
VALIDATOR = Path.home() / ".codex" / "skills" / ".system" / "plugin-creator" / "scripts" / "validate_plugin.py"
SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)")


def main() -> int:
    if VALIDATOR.exists():
        return subprocess.call([sys.executable, str(VALIDATOR), str(PLUGIN)])

    errors = plugin_errors(PLUGIN)
    if errors:
        print("Plugin validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Plugin validation passed!")
    return 0


def plugin_errors(plugin_root: Path) -> list[str]:
    errors: list[str] = []
    manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
    if not manifest_path.is_file():
        return ["missing .codex-plugin/plugin.json"]

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        return ["plugin.json must contain an object"]

    for field in ("name", "version", "description", "skills"):
        require_string(manifest, field, errors)
    if isinstance(manifest.get("version"), str) and SEMVER_RE.fullmatch(manifest["version"]) is None:
        errors.append("version must be strict semver")

    author = require_object(manifest, "author", errors)
    if author is not None:
        require_string(author, "name", errors, "author")

    interface = require_object(manifest, "interface", errors)
    if interface is not None:
        for field in ("displayName", "shortDescription", "longDescription", "developerName", "category"):
            require_string(interface, field, errors, "interface")
        prompts = interface.get("defaultPrompt")
        if not isinstance(prompts, (str, list)):
            errors.append("interface.defaultPrompt must be a string or list")

    skills_root = plugin_root / "skills"
    if not skills_root.is_dir():
        errors.append("missing skills directory")
    else:
        for skill_root in sorted(path for path in skills_root.iterdir() if path.is_dir() and not path.name.startswith(".")):
            errors.extend(f"{skill_root.name}: {error}" for error in skill_errors(skill_root))

    return errors


def require_string(payload: dict[str, Any], field: str, errors: list[str], prefix: str = "plugin") -> None:
    if not isinstance(payload.get(field), str) or not payload[field].strip():
        errors.append(f"{prefix}.{field} must be a non-empty string")


def require_object(payload: dict[str, Any], field: str, errors: list[str]) -> dict[str, Any] | None:
    value = payload.get(field)
    if not isinstance(value, dict):
        errors.append(f"{field} must be an object")
        return None
    return value


if __name__ == "__main__":
    raise SystemExit(main())
