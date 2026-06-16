from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

KINO_EDIT_VERSION = 2

ApprovalState = Literal["proposed", "approved", "rejected"]
AssetKind = Literal["video", "still", "image", "web", "audio", "document", "other"]
SourceKind = Literal["url", "file", "capture", "user", "generated", "other"]

_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")


class EditError(ValueError):
    pass


@dataclass(frozen=True)
class WordToken:
    id: str
    text: str
    start: float
    end: float
    speaker: str | None = None
    confidence: float | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WordToken:
        return cls(
            id=_required_str(data, "id"),
            text=_required_str(data, "text"),
            start=_required_float(data, "start"),
            end=_required_float(data, "end"),
            speaker=_optional_str(data, "speaker"),
            confidence=_optional_float(data, "confidence"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "text": self.text,
            "start": self.start,
            "end": self.end,
            "speaker": self.speaker,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class Transcript:
    id: str
    words: tuple[WordToken, ...]
    language: str | None = None
    source: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "words", tuple(self.words))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Transcript:
        words = _required_sequence(data, "words")
        return cls(
            id=_required_str(data, "id"),
            words=tuple(WordToken.from_dict(_required_mapping(word, "word token")) for word in words),
            language=_optional_str(data, "language"),
            source=_optional_str(data, "source"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "language": self.language,
            "source": self.source,
            "words": [word.to_dict() for word in self.words],
        }


@dataclass(frozen=True)
class SourceReceipt:
    id: str
    kind: SourceKind
    locator: str
    title: str | None = None
    author: str | None = None
    publisher: str | None = None
    license: str | None = None
    captured_at: str | None = None
    notes: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SourceReceipt:
        return cls(
            id=_required_str(data, "id"),
            kind=_required_str(data, "kind"),  # type: ignore[arg-type]
            locator=_required_str(data, "locator"),
            title=_optional_str(data, "title"),
            author=_optional_str(data, "author"),
            publisher=_optional_str(data, "publisher"),
            license=_optional_str(data, "license"),
            captured_at=_optional_str(data, "captured_at"),
            notes=_optional_str(data, "notes"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "kind": self.kind,
            "locator": self.locator,
            "title": self.title,
            "author": self.author,
            "publisher": self.publisher,
            "license": self.license,
            "captured_at": self.captured_at,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class AssetCandidate:
    id: str
    source_id: str
    kind: AssetKind
    uri: str
    start: float | None = None
    end: float | None = None
    width: int | None = None
    height: int | None = None
    score: float | None = None
    credit: str | None = None
    notes: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AssetCandidate:
        return cls(
            id=_required_str(data, "id"),
            source_id=_required_str(data, "source_id"),
            kind=_required_str(data, "kind"),  # type: ignore[arg-type]
            uri=_required_str(data, "uri"),
            start=_optional_float(data, "start"),
            end=_optional_float(data, "end"),
            width=_optional_int(data, "width"),
            height=_optional_int(data, "height"),
            score=_optional_float(data, "score"),
            credit=_optional_str(data, "credit"),
            notes=_optional_str(data, "notes"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "kind": self.kind,
            "uri": self.uri,
            "start": self.start,
            "end": self.end,
            "width": self.width,
            "height": self.height,
            "score": self.score,
            "credit": self.credit,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class BeatCandidate:
    id: str
    token_start: int
    token_end: int
    route: str
    interpretation: str
    source_plan: str
    fallback: str | None = None
    source_ids: tuple[str, ...] = ()
    asset_ids: tuple[str, ...] = ()
    selected_asset_id: str | None = None
    status: ApprovalState = "proposed"
    rejection_reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_ids", tuple(self.source_ids))
        object.__setattr__(self, "asset_ids", tuple(self.asset_ids))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BeatCandidate:
        return cls(
            id=_required_str(data, "id"),
            token_start=_required_int(data, "token_start"),
            token_end=_required_int(data, "token_end"),
            route=_required_str(data, "route"),
            interpretation=_required_str(data, "interpretation"),
            source_plan=_required_str(data, "source_plan"),
            fallback=_optional_str(data, "fallback"),
            source_ids=_str_tuple(data.get("source_ids", ()), "source_ids"),
            asset_ids=_str_tuple(data.get("asset_ids", ()), "asset_ids"),
            selected_asset_id=_optional_str(data, "selected_asset_id"),
            status=_required_str(data, "status") if "status" in data else "proposed",  # type: ignore[arg-type]
            rejection_reason=_optional_str(data, "rejection_reason"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "token_start": self.token_start,
            "token_end": self.token_end,
            "route": self.route,
            "interpretation": self.interpretation,
            "source_plan": self.source_plan,
            "fallback": self.fallback,
            "source_ids": list(self.source_ids),
            "asset_ids": list(self.asset_ids),
            "selected_asset_id": self.selected_asset_id,
            "status": self.status,
            "rejection_reason": self.rejection_reason,
        }


@dataclass(frozen=True)
class KinoEdit:
    id: str
    transcript: Transcript
    sources: tuple[SourceReceipt, ...] = ()
    assets: tuple[AssetCandidate, ...] = ()
    beats: tuple[BeatCandidate, ...] = ()
    version: int = KINO_EDIT_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "sources", tuple(self.sources))
        object.__setattr__(self, "assets", tuple(self.assets))
        object.__setattr__(self, "beats", tuple(self.beats))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KinoEdit:
        edit = cls(
            id=_required_str(data, "id"),
            version=_required_int(data, "version") if "version" in data else KINO_EDIT_VERSION,
            transcript=Transcript.from_dict(_required_mapping(data.get("transcript"), "transcript")),
            sources=tuple(
                SourceReceipt.from_dict(_required_mapping(source, "source receipt"))
                for source in _sequence(data.get("sources", ()), "sources")
            ),
            assets=tuple(
                AssetCandidate.from_dict(_required_mapping(asset, "asset candidate"))
                for asset in _sequence(data.get("assets", ()), "assets")
            ),
            beats=tuple(
                BeatCandidate.from_dict(_required_mapping(beat, "beat candidate"))
                for beat in _sequence(data.get("beats", ()), "beats")
            ),
        )
        validate_edit(edit)
        return edit

    @classmethod
    def from_json(cls, text: str) -> KinoEdit:
        data = json.loads(text)
        return cls.from_dict(_required_mapping(data, "KINO-EDIT document"))

    def validate(self) -> None:
        validate_edit(self)

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "id": self.id,
            "transcript": self.transcript.to_dict(),
            "sources": [source.to_dict() for source in self.sources],
            "assets": [asset.to_dict() for asset in self.assets],
            "beats": [beat.to_dict() for beat in self.beats],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"


def load_edit(path: str | Path) -> KinoEdit:
    return KinoEdit.from_json(Path(path).read_text())


def write_edit_json(edit: KinoEdit, path: str | Path) -> Path:
    validate_edit(edit)
    out = Path(path)
    out.write_text(edit.to_json())
    return out


def validate_edit(edit: KinoEdit) -> None:
    if edit.version != KINO_EDIT_VERSION:
        raise EditError(f"unsupported KINO-EDIT version: {edit.version}")

    _validate_id(edit.id, "edit id")
    _validate_transcript(edit.transcript)

    source_ids = _validate_unique_ids((source.id for source in edit.sources), "source")
    asset_ids = _validate_unique_ids((asset.id for asset in edit.assets), "asset")
    asset_sources = {asset.id: asset.source_id for asset in edit.assets}
    _validate_unique_ids((beat.id for beat in edit.beats), "beat")

    for source in edit.sources:
        _validate_source(source)

    for asset in edit.assets:
        _validate_asset(asset, source_ids)

    word_count = len(edit.transcript.words)
    for beat in edit.beats:
        _validate_beat(beat, word_count, source_ids, asset_ids, asset_sources)


def _validate_transcript(transcript: Transcript) -> None:
    _validate_id(transcript.id, "transcript id")
    token_ids = _validate_unique_ids((word.id for word in transcript.words), "word token")
    last_end = 0.0
    for word in transcript.words:
        _validate_word(word)
        if word.id not in token_ids:
            raise EditError(f"word token has unknown id: {word.id}")
        if word.start < last_end:
            raise EditError(f"{word.id}: word tokens must be sorted and non-overlapping")
        last_end = word.end


def _validate_word(word: WordToken) -> None:
    _validate_id(word.id, "word token id")
    if word.text == "":
        raise EditError(f"{word.id}: text must not be empty")
    if word.start < 0:
        raise EditError(f"{word.id}: start must be >= 0")
    if word.end <= word.start:
        raise EditError(f"{word.id}: end must be after start")
    if word.confidence is not None and not 0 <= word.confidence <= 1:
        raise EditError(f"{word.id}: confidence must be between 0 and 1")


def _validate_source(source: SourceReceipt) -> None:
    _validate_id(source.id, "source id")
    if source.kind not in ("url", "file", "capture", "user", "generated", "other"):
        raise EditError(f"{source.id}: unsupported source kind: {source.kind}")
    if source.locator == "":
        raise EditError(f"{source.id}: locator must not be empty")


def _validate_asset(asset: AssetCandidate, source_ids: set[str]) -> None:
    _validate_id(asset.id, "asset id")
    if asset.kind not in ("video", "still", "image", "web", "audio", "document", "other"):
        raise EditError(f"{asset.id}: unsupported asset kind: {asset.kind}")
    if asset.source_id not in source_ids:
        raise EditError(f"{asset.id}: source_id references unknown source: {asset.source_id}")
    if asset.uri == "":
        raise EditError(f"{asset.id}: uri must not be empty")
    if asset.start is not None and asset.start < 0:
        raise EditError(f"{asset.id}: start must be >= 0")
    if asset.end is not None and asset.end < 0:
        raise EditError(f"{asset.id}: end must be >= 0")
    if asset.start is not None and asset.end is not None and asset.end <= asset.start:
        raise EditError(f"{asset.id}: end must be after start")
    if asset.width is not None and asset.width <= 0:
        raise EditError(f"{asset.id}: width must be positive")
    if asset.height is not None and asset.height <= 0:
        raise EditError(f"{asset.id}: height must be positive")
    if asset.score is not None and not 0 <= asset.score <= 1:
        raise EditError(f"{asset.id}: score must be between 0 and 1")


def _validate_beat(
    beat: BeatCandidate,
    word_count: int,
    source_ids: set[str],
    asset_ids: set[str],
    asset_sources: dict[str, str],
) -> None:
    _validate_id(beat.id, "beat id")
    if beat.token_start < 0:
        raise EditError(f"{beat.id}: token_start must be >= 0")
    if beat.token_end <= beat.token_start:
        raise EditError(f"{beat.id}: token_end must be after token_start")
    if beat.token_end > word_count:
        raise EditError(f"{beat.id}: token range exceeds transcript length")
    if beat.route == "":
        raise EditError(f"{beat.id}: route must not be empty")
    if beat.interpretation == "":
        raise EditError(f"{beat.id}: interpretation must not be empty")
    if beat.source_plan == "":
        raise EditError(f"{beat.id}: source_plan must not be empty")
    if beat.status not in ("proposed", "approved", "rejected"):
        raise EditError(f"{beat.id}: unsupported approval status: {beat.status}")

    beat_source_ids = _validate_unique_ids(beat.source_ids, f"{beat.id} source reference")
    beat_asset_ids = _validate_unique_ids(beat.asset_ids, f"{beat.id} asset reference")

    for source_id in beat_source_ids:
        if source_id not in source_ids:
            raise EditError(f"{beat.id}: source_ids references unknown source: {source_id}")

    for asset_id in beat_asset_ids:
        if asset_id not in asset_ids:
            raise EditError(f"{beat.id}: asset_ids references unknown asset: {asset_id}")
        asset_source_id = asset_sources[asset_id]
        if beat_source_ids and asset_source_id not in beat_source_ids:
            raise EditError(f"{beat.id}: asset {asset_id} references source not listed in source_ids: {asset_source_id}")

    if beat.selected_asset_id is not None:
        _validate_id(beat.selected_asset_id, f"{beat.id} selected asset reference")
        if beat.selected_asset_id not in asset_ids:
            raise EditError(f"{beat.id}: selected_asset_id references unknown asset: {beat.selected_asset_id}")
        if beat.selected_asset_id not in beat.asset_ids:
            raise EditError(f"{beat.id}: selected_asset_id must also be listed in asset_ids")

    if beat.status == "approved" and beat.selected_asset_id is None:
        raise EditError(f"{beat.id}: approved beats require selected_asset_id")
    if beat.status == "rejected" and not beat.rejection_reason:
        raise EditError(f"{beat.id}: rejected beats require rejection_reason")


def _validate_id(value: str, label: str) -> None:
    if not isinstance(value, str) or not _ID_PATTERN.match(value):
        raise EditError(f"{label} must be a stable id matching {_ID_PATTERN.pattern}: {value!r}")


def _validate_unique_ids(ids: object, label: str) -> set[str]:
    seen: set[str] = set()
    for id_ in ids:
        if not isinstance(id_, str):
            raise EditError(f"{label} id must be a string: {id_!r}")
        _validate_id(id_, f"{label} id")
        if id_ in seen:
            raise EditError(f"duplicate {label} id: {id_}")
        seen.add(id_)
    return seen


def _required_mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EditError(f"{label} must be an object")
    return value


def _required_sequence(data: dict[str, Any], key: str) -> tuple[object, ...]:
    if key not in data:
        raise EditError(f"missing required key: {key}")
    return _sequence(data[key], key)


def _sequence(value: object, key: str) -> tuple[object, ...]:
    if not isinstance(value, list | tuple):
        raise EditError(f"{key} must be a list")
    return tuple(value)


def _required_str(data: dict[str, Any], key: str) -> str:
    if key not in data:
        raise EditError(f"missing required key: {key}")
    value = data[key]
    if not isinstance(value, str):
        raise EditError(f"{key} must be a string")
    return value


def _optional_str(data: dict[str, Any], key: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise EditError(f"{key} must be a string")
    return value


def _required_float(data: dict[str, Any], key: str) -> float:
    if key not in data:
        raise EditError(f"missing required key: {key}")
    return _number(data[key], key)


def _optional_float(data: dict[str, Any], key: str) -> float | None:
    value = data.get(key)
    if value is None:
        return None
    return _number(value, key)


def _number(value: object, key: str) -> float:
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise EditError(f"{key} must be a number")
    return float(value)


def _required_int(data: dict[str, Any], key: str) -> int:
    if key not in data:
        raise EditError(f"missing required key: {key}")
    return _integer(data[key], key)


def _optional_int(data: dict[str, Any], key: str) -> int | None:
    value = data.get(key)
    if value is None:
        return None
    return _integer(value, key)


def _integer(value: object, key: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise EditError(f"{key} must be an integer")
    return value


def _str_tuple(value: object, key: str) -> tuple[str, ...]:
    items = _sequence(value, key)
    for item in items:
        if not isinstance(item, str):
            raise EditError(f"{key} values must be strings")
    return tuple(items)
