from __future__ import annotations

import json
from pathlib import Path

from .edit import AssetCandidate, BeatCandidate, KinoEdit, SourceReceipt, WordToken, validate_edit
from .manifest import Beat, BeatKind, Manifest, validate_manifest


class CompileError(ValueError):
    pass


def compile_edit_to_manifest(
    edit: KinoEdit,
    base: str | Path,
    output: str | Path,
    size: tuple[int, int] = (1920, 1080),
    fps: int = 30,
) -> Manifest:
    validate_edit(edit)
    normalized_size = _normalize_size(size)

    assets_by_id = {asset.id: asset for asset in edit.assets}
    sources_by_id = {source.id: source for source in edit.sources}

    beats = tuple(
        sorted(
            (
                _compile_beat(beat, edit, assets_by_id, sources_by_id)
                for beat in edit.beats
                if beat.status == "approved" and beat.selected_asset_id is not None
            ),
            key=lambda item: (item.start, item.end, item.id),
        )
    )
    manifest = Manifest(
        path=Path("KINO-MANIFEST.json"),
        base=Path(base),
        output=Path(output),
        beats=beats,
        size=normalized_size,
        fps=fps,
    )
    validate_manifest(manifest)
    return manifest


def write_manifest_json(manifest: Manifest, path: str | Path) -> Path:
    validate_manifest(manifest)
    out = Path(path)
    out.write_text(json.dumps(_manifest_to_dict(manifest), indent=2, sort_keys=True) + "\n")
    return out


def _compile_beat(
    beat: BeatCandidate,
    edit: KinoEdit,
    assets_by_id: dict[str, AssetCandidate],
    sources_by_id: dict[str, SourceReceipt],
) -> Beat:
    if beat.selected_asset_id is None:
        raise CompileError(f"{beat.id}: approved beats require selected_asset_id")

    asset = assets_by_id.get(beat.selected_asset_id)
    if asset is None:
        raise CompileError(f"{beat.id}: selected asset not found: {beat.selected_asset_id}")

    words = edit.transcript.words[beat.token_start : beat.token_end]
    if not words:
        raise CompileError(f"{beat.id}: token range does not contain transcript words")

    return Beat(
        id=beat.id,
        start=words[0].start,
        end=words[-1].end,
        line=_line_from_words(words),
        interpretation=beat.interpretation,
        route=beat.route,
        asset=Path(asset.uri),
        kind=_manifest_kind(asset),
        source_in=asset.start or 0.0,
        credit=_credit_for_asset(asset, sources_by_id.get(asset.source_id)),
    )


def _manifest_kind(asset: AssetCandidate) -> BeatKind:
    if asset.kind == "video":
        return "video"
    if asset.kind in ("still", "image", "web", "document"):
        return "still"
    raise CompileError(f"{asset.id}: unsupported selected asset kind for manifest: {asset.kind}")


def _line_from_words(words: tuple[WordToken, ...]) -> str:
    return " ".join(str(word.text) for word in words)


def _credit_for_asset(asset: AssetCandidate, source: SourceReceipt | None) -> str | None:
    parts: list[str] = []
    if asset.credit:
        parts.append(asset.credit)

    if source is not None:
        for value in (source.title, source.author, source.publisher, source.license, source.locator):
            if value and value not in parts:
                parts.append(value)

    return "; ".join(parts) if parts else None


def _manifest_to_dict(manifest: Manifest) -> dict[str, object]:
    data: dict[str, object] = {
        "version": manifest.version,
        "base": _path_to_json(manifest.base),
        "output": _path_to_json(manifest.output),
        "size": [manifest.size[0], manifest.size[1]],
        "fps": manifest.fps,
        "beats": [_beat_to_dict(beat) for beat in manifest.beats],
    }
    if manifest.removed:
        data["removed"] = list(manifest.removed)
    return data


def _beat_to_dict(beat: Beat) -> dict[str, object]:
    data: dict[str, object] = {
        "id": beat.id,
        "start": beat.start,
        "end": beat.end,
        "line": beat.line,
        "interpretation": beat.interpretation,
        "route": beat.route,
        "asset": _path_to_json(beat.asset),
        "kind": beat.kind,
        "source_in": beat.source_in,
        "status": beat.status,
    }
    if beat.credit is not None:
        data["credit"] = beat.credit
    return data


def _path_to_json(path: Path) -> str:
    return path.as_posix()


def _normalize_size(size: tuple[int, int]) -> tuple[int, int]:
    if len(size) != 2:
        raise CompileError("size must contain exactly two dimensions")
    return int(size[0]), int(size[1])
