from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .manifest import Beat, Manifest

RECEIPT_FILENAME = "KINO-RENDER.json"
SCHEMA = "kino.render.receipt.v1"


@dataclass(frozen=True)
class RenderReceipt:
    timestamp: str
    input_hash: str
    graph_hash: str
    command_hash: str
    command: tuple[str, ...]
    tool_versions: dict[str, str | None]
    manifest_path: Path
    source_path: Path
    output_path: Path
    formatted_paths: tuple[Path, ...]
    asset_paths: tuple[Path, ...]
    formatted_commands: tuple[tuple[str, ...], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "timestamp": self.timestamp,
            "input": {
                "type": "manifest",
                "hash": self.input_hash,
                "path": str(self.manifest_path),
            },
            "graph_hash": self.graph_hash,
            "command_hash": self.command_hash,
            "command": list(self.command),
            "formatted_commands": [list(command) for command in self.formatted_commands],
            "tool_versions": self.tool_versions,
            "paths": {
                "manifest": str(self.manifest_path),
                "source": str(self.source_path),
                "output": str(self.output_path),
                "formatted": [str(path) for path in self.formatted_paths],
                "assets": [str(path) for path in self.asset_paths],
            },
        }


def build_render_receipt(
    manifest: Manifest,
    command: list[str],
    formatted_paths: list[Path],
    *,
    base_duration: float | None = None,
    formatted_commands: list[list[str]] | None = None,
    timestamp: str | None = None,
    tool_versions: dict[str, str | None] | None = None,
) -> RenderReceipt:
    return RenderReceipt(
        timestamp=timestamp or utc_timestamp(),
        input_hash=manifest_hash(manifest),
        graph_hash=manifest_graph_hash(manifest, base_duration=base_duration),
        command_hash=command_graph_hash(command),
        command=tuple(command),
        formatted_commands=tuple(tuple(command) for command in formatted_commands or []),
        tool_versions=collect_tool_versions() if tool_versions is None else tool_versions,
        manifest_path=manifest.path,
        source_path=manifest.base,
        output_path=manifest.output,
        formatted_paths=tuple(formatted_paths),
        asset_paths=tuple(beat.asset for beat in manifest.beats),
    )


def write_render_receipt(receipt: RenderReceipt, directory: Path) -> Path:
    path = directory / RECEIPT_FILENAME
    path.write_text(json.dumps(receipt.to_dict(), indent=2, sort_keys=True) + "\n")
    return path


def manifest_hash(manifest: Manifest) -> str:
    if manifest.path.exists():
        return file_sha256(manifest.path)
    data = {
        "base": str(manifest.base),
        "output": str(manifest.output),
        "size": list(manifest.size),
        "fps": manifest.fps,
        "version": manifest.version,
        "beats": [_beat_hash_input(beat) for beat in manifest.beats],
        "removed": list(manifest.removed),
    }
    return value_sha256(data)


def beat_asset_timing_hash(beat: Beat, vf: str) -> str:
    data = {
        "id": beat.id,
        "asset": str(beat.asset),
        "asset_hash": file_sha256(beat.asset) if beat.asset.exists() else None,
        "kind": beat.kind,
        "source_in": beat.source_in,
        "start": beat.start,
        "end": beat.end,
        "duration": beat.duration,
        "vf": vf,
    }
    return value_sha256(data)[:16]


def command_graph_hash(command: list[str]) -> str:
    graph = _command_value(command, "-filter_complex")
    return value_sha256(graph if graph is not None else command)


def manifest_graph_hash(manifest: Manifest, *, base_duration: float | None = None) -> str:
    from .graph import manifest_to_graph

    return manifest_to_graph(manifest, base_duration=base_duration).stable_hash()


def collect_tool_versions() -> dict[str, str | None]:
    return {
        "ffmpeg": tool_version("ffmpeg"),
        "ffprobe": tool_version("ffprobe"),
    }


def tool_version(tool: str) -> str | None:
    try:
        result = subprocess.run([tool, "-version"], capture_output=True, text=True)
    except OSError:
        return None
    if result.returncode:
        return None
    return result.stdout.splitlines()[0] if result.stdout else None


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def value_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(payload).hexdigest()


def _beat_hash_input(beat: Beat) -> dict[str, Any]:
    return {
        "id": beat.id,
        "start": beat.start,
        "end": beat.end,
        "line": beat.line,
        "interpretation": beat.interpretation,
        "route": beat.route,
        "asset": str(beat.asset),
        "kind": beat.kind,
        "source_in": beat.source_in,
        "status": beat.status,
        "credit": beat.credit,
    }


def _command_value(command: list[str], option: str) -> str | None:
    try:
        index = command.index(option)
    except ValueError:
        return None
    value_index = index + 1
    return command[value_index] if value_index < len(command) else None
