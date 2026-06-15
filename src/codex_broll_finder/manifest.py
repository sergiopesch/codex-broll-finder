from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

BeatKind = Literal["video", "still"]


@dataclass(frozen=True)
class Beat:
    id: str
    start: float
    end: float
    line: str
    interpretation: str
    route: str
    asset: Path
    kind: BeatKind
    source_in: float = 0.0
    status: str = "planned"
    credit: str | None = None

    @property
    def duration(self) -> float:
        return round(self.end - self.start, 3)


@dataclass(frozen=True)
class Manifest:
    path: Path
    base: Path
    output: Path
    beats: tuple[Beat, ...]
    size: tuple[int, int] = (1920, 1080)
    fps: int = 30
    version: int = 1
    removed: tuple[dict[str, Any], ...] = ()


class ManifestError(ValueError):
    pass


def load_manifest(path: str | Path) -> Manifest:
    manifest_path = Path(path)
    data = json.loads(manifest_path.read_text())
    root = manifest_path.parent

    size_raw = data.get("size", [1920, 1080])
    if not isinstance(size_raw, list | tuple) or len(size_raw) != 2:
        raise ManifestError("size must be a two-item list, e.g. [1920, 1080]")

    beats = tuple(_parse_beat(item, root) for item in data.get("beats", []))
    manifest = Manifest(
        path=manifest_path,
        base=_resolve(root, data["base"]),
        output=_resolve(root, data.get("output", "output_with_broll.mp4")),
        beats=beats,
        size=(int(size_raw[0]), int(size_raw[1])),
        fps=int(data.get("fps", 30)),
        version=int(data.get("version", 1)),
        removed=tuple(data.get("removed", [])),
    )
    validate_manifest(manifest)
    return manifest


def validate_manifest(manifest: Manifest) -> None:
    if manifest.version != 1:
        raise ManifestError(f"unsupported manifest version: {manifest.version}")
    if manifest.fps <= 0:
        raise ManifestError("fps must be positive")
    if manifest.size[0] <= 0 or manifest.size[1] <= 0:
        raise ManifestError("size dimensions must be positive")

    seen: set[str] = set()
    last_end = 0.0
    for beat in manifest.beats:
        if beat.id in seen:
            raise ManifestError(f"duplicate beat id: {beat.id}")
        seen.add(beat.id)
        if beat.start < 0:
            raise ManifestError(f"{beat.id}: start must be >= 0")
        if beat.end <= beat.start:
            raise ManifestError(f"{beat.id}: end must be after start")
        if beat.start < last_end:
            raise ManifestError(f"{beat.id}: beats must be sorted and non-overlapping")
        if beat.kind not in ("video", "still"):
            raise ManifestError(f"{beat.id}: kind must be video or still")
        last_end = beat.end


def _parse_beat(raw: dict[str, Any], root: Path) -> Beat:
    missing = [
        key
        for key in ("id", "start", "end", "line", "interpretation", "route", "asset", "kind")
        if key not in raw
    ]
    if missing:
        raise ManifestError(f"beat is missing required keys: {', '.join(missing)}")
    return Beat(
        id=str(raw["id"]),
        start=float(raw["start"]),
        end=float(raw["end"]),
        line=str(raw["line"]),
        interpretation=str(raw["interpretation"]),
        route=str(raw["route"]),
        asset=_resolve(root, raw["asset"]),
        kind=str(raw["kind"]),  # type: ignore[arg-type]
        source_in=float(raw.get("source_in", 0.0)),
        status=str(raw.get("status", "planned")),
        credit=raw.get("credit"),
    )


def _resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path
