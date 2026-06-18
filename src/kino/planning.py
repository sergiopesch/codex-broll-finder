from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping, TypeAlias

from kino.edit import BeatCandidate, EditError, KinoEdit, Transcript, validate_edit

BeatInput: TypeAlias = BeatCandidate | Mapping[str, Any]


def transcript_from_dict(data: Mapping[str, Any]) -> Transcript:
    """Build a validated transcript from a transcript object or KINO-EDIT-like object."""
    payload = _transcript_payload(data)
    transcript = Transcript.from_dict(payload)
    validate_edit(KinoEdit(id=transcript.id, transcript=transcript))
    return transcript


def transcript_from_json(text: str) -> Transcript:
    data = _json_mapping(json.loads(text), "transcript JSON")
    return transcript_from_dict(data)


def load_transcript_json(path: str | Path) -> Transcript:
    return transcript_from_json(Path(path).read_text())


def initialize_edit_from_transcript(
    transcript: Transcript,
    *,
    edit_id: str | None = None,
) -> KinoEdit:
    edit = KinoEdit(id=edit_id or transcript.id, transcript=transcript)
    validate_edit(edit)
    return edit


def initialize_edit_from_transcript_dict(
    data: Mapping[str, Any],
    *,
    edit_id: str | None = None,
) -> KinoEdit:
    transcript = transcript_from_dict(data)
    source_id = _edit_id_from_payload(data)
    return initialize_edit_from_transcript(transcript, edit_id=edit_id or source_id or transcript.id)


def initialize_edit_from_transcript_json(
    text: str,
    *,
    edit_id: str | None = None,
) -> KinoEdit:
    data = _json_mapping(json.loads(text), "transcript JSON")
    return initialize_edit_from_transcript_dict(data, edit_id=edit_id)


def load_edit_from_transcript_json(
    path: str | Path,
    *,
    edit_id: str | None = None,
) -> KinoEdit:
    return initialize_edit_from_transcript_json(Path(path).read_text(), edit_id=edit_id)


def add_beat_candidates(
    edit: KinoEdit,
    candidates: BeatInput | list[BeatInput] | tuple[BeatInput, ...],
) -> KinoEdit:
    if isinstance(candidates, BeatCandidate) or isinstance(candidates, Mapping):
        candidate_items = (candidates,)
    else:
        candidate_items = tuple(candidates)

    proposed = tuple(_as_proposed_beat(candidate) for candidate in candidate_items)
    updated = replace(edit, beats=(*edit.beats, *proposed))
    validate_edit(updated)
    return updated


def add_proposed_beat_candidates(
    edit: KinoEdit,
    candidates: BeatInput | list[BeatInput] | tuple[BeatInput, ...],
) -> KinoEdit:
    return add_beat_candidates(edit, candidates)


def approve_beat(edit: KinoEdit, beat_id: str, selected_asset_id: str) -> KinoEdit:
    beat = _find_beat(edit, beat_id)
    approved = replace(
        beat,
        selected_asset_id=selected_asset_id,
        status="approved",
        rejection_reason=None,
    )
    updated = _replace_beat(edit, beat_id, approved)
    validate_edit(updated)
    return updated


def reject_beat(edit: KinoEdit, beat_id: str, rejection_reason: str) -> KinoEdit:
    beat = _find_beat(edit, beat_id)
    rejected = replace(
        beat,
        selected_asset_id=None,
        status="rejected",
        rejection_reason=rejection_reason,
    )
    updated = _replace_beat(edit, beat_id, rejected)
    validate_edit(updated)
    return updated


def _transcript_payload(data: Mapping[str, Any]) -> dict[str, Any]:
    if "transcript" in data:
        return _json_mapping(data["transcript"], "transcript")
    return dict(data)


def _edit_id_from_payload(data: Mapping[str, Any]) -> str | None:
    value = data.get("id")
    if value is None or "transcript" not in data:
        return None
    if not isinstance(value, str):
        raise EditError("id must be a string")
    return value


def _as_proposed_beat(candidate: BeatInput) -> BeatCandidate:
    beat = candidate if isinstance(candidate, BeatCandidate) else BeatCandidate.from_dict(dict(candidate))
    return replace(
        beat,
        selected_asset_id=None,
        status="proposed",
        rejection_reason=None,
    )


def _find_beat(edit: KinoEdit, beat_id: str) -> BeatCandidate:
    for beat in edit.beats:
        if beat.id == beat_id:
            return beat
    raise EditError(f"unknown beat id: {beat_id}")


def _replace_beat(edit: KinoEdit, beat_id: str, replacement: BeatCandidate) -> KinoEdit:
    return replace(
        edit,
        beats=tuple(replacement if beat.id == beat_id else beat for beat in edit.beats),
    )


def _json_mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EditError(f"{label} must be an object")
    return value
