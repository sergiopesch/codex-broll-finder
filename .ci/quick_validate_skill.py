from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = Path.home() / ".codex" / "skills" / ".system" / "skill-creator" / "scripts" / "quick_validate.py"


def main() -> int:
    if not VALIDATOR.exists():
        return validate_skill(ROOT / "kino")
    return subprocess.call([sys.executable, str(VALIDATOR), str(ROOT / "kino")])


def validate_skill(skill_root: Path) -> int:
    errors = skill_errors(skill_root)
    if errors:
        print("Skill validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Skill is valid!")
    return 0


def skill_errors(skill_root: Path) -> list[str]:
    errors: list[str] = []
    skill_md = skill_root / "SKILL.md"
    if not skill_md.is_file():
        return [f"missing {skill_md}"]
    contents = skill_md.read_text(encoding="utf-8")
    if not contents.startswith("---\n"):
        return ["SKILL.md must start with YAML frontmatter"]
    end = contents.find("\n---", 4)
    if end == -1:
        return ["SKILL.md frontmatter is not closed"]
    frontmatter = yaml.safe_load(contents[4:end])
    if not isinstance(frontmatter, dict):
        return ["SKILL.md frontmatter must be an object"]
    for field in ("name", "description"):
        if not isinstance(frontmatter.get(field), str) or not frontmatter[field].strip():
            errors.append(f"frontmatter field {field!r} must be a non-empty string")
    return errors


if __name__ == "__main__":
    raise SystemExit(main())
