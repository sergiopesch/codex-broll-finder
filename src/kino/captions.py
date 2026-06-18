from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal, Mapping

from .archetypes import ArchetypeId
from .edit import KinoEdit, WordToken, validate_edit
from .video import run

KINO_CAPTIONS_VERSION = 1
KINO_CAPTIONS_SCHEMA = "kino.captions.v1"

CaptionPreset = Literal["social-short-bold", "founder-explainer-clean"]


class CaptionError(ValueError):
    pass


@dataclass(frozen=True)
class CaptionStyle:
    preset: CaptionPreset
    font: str
    font_size: int
    alignment: int
    margin_v: int
    max_chars_per_line: int
    max_lines: int
    uppercase: bool = False

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CaptionStyle:
        return cls(
            preset=_preset(_required_str(data, "preset")),
            font=_required_str(data, "font"),
            font_size=_required_int(data, "font_size"),
            alignment=_required_int(data, "alignment"),
            margin_v=_required_int(data, "margin_v"),
            max_chars_per_line=_required_int(data, "max_chars_per_line"),
            max_lines=_required_int(data, "max_lines"),
            uppercase=bool(data.get("uppercase", False)),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "preset": self.preset,
            "font": self.font,
            "font_size": self.font_size,
            "alignment": self.alignment,
            "margin_v": self.margin_v,
            "max_chars_per_line": self.max_chars_per_line,
            "max_lines": self.max_lines,
            "uppercase": self.uppercase,
        }


@dataclass(frozen=True)
class CaptionSegment:
    id: str
    token_start: int
    token_end: int
    word_start_id: str
    word_end_id: str
    start: float
    end: float
    text: str
    emphasized_words: tuple[str, ...]
    confidence: float
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "emphasized_words", tuple(self.emphasized_words))
        object.__setattr__(self, "reasons", tuple(self.reasons))
        if self.token_start < 0:
            raise CaptionError(f"{self.id}: token_start must be >= 0")
        if self.token_end <= self.token_start:
            raise CaptionError(f"{self.id}: token_end must be after token_start")
        if self.start < 0:
            raise CaptionError(f"{self.id}: start must be >= 0")
        if self.end <= self.start:
            raise CaptionError(f"{self.id}: end must be after start")
        if not self.word_start_id:
            raise CaptionError(f"{self.id}: word_start_id must not be empty")
        if not self.word_end_id:
            raise CaptionError(f"{self.id}: word_end_id must not be empty")
        if not self.text:
            raise CaptionError(f"{self.id}: text must not be empty")
        if not 0 <= self.confidence <= 1:
            raise CaptionError(f"{self.id}: confidence must be between 0 and 1")
        if not self.reasons:
            raise CaptionError(f"{self.id}: reasons must not be empty")

    @property
    def duration(self) -> float:
        return round(self.end - self.start, 3)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CaptionSegment:
        anchor = _mapping(data.get("anchor"), "anchor") if "anchor" in data else data
        return cls(
            id=_required_str(data, "id"),
            token_start=_required_int(anchor, "token_start"),
            token_end=_required_int(anchor, "token_end"),
            word_start_id=_required_str(anchor, "word_start_id"),
            word_end_id=_required_str(anchor, "word_end_id"),
            start=_required_float(data, "start"),
            end=_required_float(data, "end"),
            text=_required_str(data, "text"),
            emphasized_words=_str_tuple(data.get("emphasized_words", ()), "emphasized_words"),
            confidence=_required_float(data, "confidence"),
            reasons=_str_tuple(data.get("reasons", ()), "reasons"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "anchor": {
                "token_start": self.token_start,
                "token_end": self.token_end,
                "word_start_id": self.word_start_id,
                "word_end_id": self.word_end_id,
            },
            "start": self.start,
            "end": self.end,
            "text": self.text,
            "emphasized_words": list(self.emphasized_words),
            "confidence": self.confidence,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class KinoCaptions:
    id: str
    edit_id: str
    transcript_id: str
    transcript_hash: str
    archetype_id: ArchetypeId
    style: CaptionStyle
    segments: tuple[CaptionSegment, ...]
    version: int = KINO_CAPTIONS_VERSION
    schema: str = KINO_CAPTIONS_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(self, "segments", tuple(self.segments))
        validate_captions(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> KinoCaptions:
        return cls(
            version=_required_int(data, "version") if "version" in data else KINO_CAPTIONS_VERSION,
            schema=_required_str(data, "schema") if "schema" in data else KINO_CAPTIONS_SCHEMA,
            id=_required_str(data, "id"),
            edit_id=_required_str(data, "edit_id"),
            transcript_id=_required_str(data, "transcript_id"),
            transcript_hash=_required_str(data, "transcript_hash"),
            archetype_id=_archetype_id(_required_str(data, "archetype_id")),
            style=CaptionStyle.from_dict(_mapping(data.get("style"), "style")),
            segments=tuple(
                CaptionSegment.from_dict(_mapping(item, "caption segment"))
                for item in _sequence(data.get("segments", ()), "segments")
            ),
        )

    @classmethod
    def from_json(cls, text: str) -> KinoCaptions:
        return cls.from_dict(_mapping(json.loads(text), "KINO-CAPTIONS document"))

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "schema": self.schema,
            "id": self.id,
            "edit_id": self.edit_id,
            "transcript_id": self.transcript_id,
            "transcript_hash": self.transcript_hash,
            "archetype_id": self.archetype_id,
            "style": self.style.to_dict(),
            "segments": [segment.to_dict() for segment in self.segments],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"


def load_captions(path: str | Path) -> KinoCaptions:
    return KinoCaptions.from_json(Path(path).read_text())


def write_captions_json(captions: KinoCaptions, path: str | Path) -> Path:
    validate_captions(captions)
    out = Path(path)
    out.write_text(captions.to_json())
    return out


def plan_captions(edit: KinoEdit, *, archetype_id: ArchetypeId) -> KinoCaptions:
    validate_edit(edit)
    if not edit.transcript.words:
        raise CaptionError("cannot plan captions without transcript words")
    style = default_caption_style(archetype_id)
    segments = tuple(_caption_segments(edit.transcript.words, style))
    return KinoCaptions(
        id=f"{edit.id}:{archetype_id}:captions",
        edit_id=edit.id,
        transcript_id=edit.transcript.id,
        transcript_hash=_transcript_hash(edit),
        archetype_id=archetype_id,
        style=style,
        segments=segments,
    )


def default_caption_style(archetype_id: ArchetypeId) -> CaptionStyle:
    archetype_id = _archetype_id(archetype_id)
    if archetype_id == "social-short":
        return CaptionStyle(
            preset="social-short-bold",
            font="Arial",
            font_size=64,
            alignment=2,
            margin_v=150,
            max_chars_per_line=18,
            max_lines=2,
            uppercase=True,
        )
    return CaptionStyle(
        preset="founder-explainer-clean",
        font="Arial",
        font_size=44,
        alignment=2,
        margin_v=84,
        max_chars_per_line=32,
        max_lines=2,
    )


def validate_captions(captions: KinoCaptions) -> None:
    if captions.version != KINO_CAPTIONS_VERSION:
        raise CaptionError(f"unsupported KINO-CAPTIONS version: {captions.version}")
    if captions.schema != KINO_CAPTIONS_SCHEMA:
        raise CaptionError(f"unsupported KINO-CAPTIONS schema: {captions.schema}")
    if not captions.id:
        raise CaptionError("captions id must not be empty")
    if not captions.edit_id:
        raise CaptionError(f"{captions.id}: edit_id must not be empty")
    if not captions.transcript_id:
        raise CaptionError(f"{captions.id}: transcript_id must not be empty")
    if not captions.transcript_hash.startswith("sha256:"):
        raise CaptionError(f"{captions.id}: transcript_hash must be a sha256 digest")
    if not captions.segments:
        raise CaptionError(f"{captions.id}: at least one caption segment is required")
    _validate_style(captions.style)

    seen: set[str] = set()
    last_end = 0.0
    for segment in captions.segments:
        if segment.id in seen:
            raise CaptionError(f"duplicate caption segment id: {segment.id}")
        seen.add(segment.id)
        if segment.start < last_end:
            raise CaptionError(f"{segment.id}: caption segments must be sorted and non-overlapping")
        if segment.duration < 0.18:
            raise CaptionError(f"{segment.id}: caption duration is too short to read")
        if segment.duration > 4.5:
            raise CaptionError(f"{segment.id}: caption duration is too long")
        for line in wrap_caption_text(segment.text, captions.style):
            if len(line) > captions.style.max_chars_per_line:
                raise CaptionError(f"{segment.id}: caption line exceeds max_chars_per_line")
        if len(wrap_caption_text(segment.text, captions.style)) > captions.style.max_lines:
            raise CaptionError(f"{segment.id}: caption exceeds max_lines")
        last_end = segment.end


def validate_captions_for_edit(captions: KinoCaptions, edit: KinoEdit) -> None:
    validate_captions(captions)
    validate_edit(edit)
    if captions.edit_id != edit.id:
        raise CaptionError(f"{captions.id}: edit_id does not match edit id: {edit.id}")
    if captions.transcript_id != edit.transcript.id:
        raise CaptionError(f"{captions.id}: transcript_id does not match edit transcript id: {edit.transcript.id}")
    if captions.transcript_hash != _transcript_hash(edit):
        raise CaptionError(f"{captions.id}: transcript_hash does not match edit transcript")
    word_count = len(edit.transcript.words)
    for segment in captions.segments:
        if segment.token_end > word_count:
            raise CaptionError(f"{segment.id}: token range exceeds transcript length")
        if edit.transcript.words[segment.token_start].id != segment.word_start_id:
            raise CaptionError(f"{segment.id}: word_start_id does not match transcript")
        if edit.transcript.words[segment.token_end - 1].id != segment.word_end_id:
            raise CaptionError(f"{segment.id}: word_end_id does not match transcript")


def wrap_caption_text(text: str, style: CaptionStyle) -> tuple[str, ...]:
    words = text.split()
    if not words:
        return ()
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if len(candidate) <= style.max_chars_per_line:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return tuple(lines)


def captions_to_ass(captions: KinoCaptions, *, size: tuple[int, int] = (1080, 1920)) -> str:
    validate_captions(captions)
    width, height = _size(size)
    style = captions.style
    border = max(2, round(style.font_size * 0.08))
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "",
        "[V4+ Styles]",
        (
            "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,"
            "Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,"
            "Alignment,MarginL,MarginR,MarginV,Encoding"
        ),
        (
            f"Style: Default,{style.font},{style.font_size},&H00FFFFFF,&H000000FF,&H00111111,&H7F000000,"
            f"-1,0,0,0,100,100,0,0,1,{border},1,{style.alignment},72,72,{style.margin_v},1"
        ),
        "",
        "[Events]",
        "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
    ]
    for segment in captions.segments:
        text = segment.text.upper() if style.uppercase else segment.text
        wrapped = r"\N".join(_ass_escape(line) for line in wrap_caption_text(text, style))
        lines.append(
            f"Dialogue: 0,{_ass_time(segment.start)},{_ass_time(segment.end)},Default,,0,0,0,,{wrapped}"
        )
    return "\n".join(lines) + "\n"


def write_ass(captions: KinoCaptions, path: str | Path, *, size: tuple[int, int] = (1080, 1920)) -> Path:
    out = Path(path)
    out.write_text(captions_to_ass(captions, size=size))
    return out


def build_render_captions_command(input_path: Path, ass_path: Path, output_path: Path) -> list[str]:
    return [
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-i",
        str(input_path),
        "-vf",
        f"subtitles={_filter_path(ass_path)}",
        "-c:v",
        "libx264",
        "-crf",
        "18",
        "-preset",
        "fast",
        "-c:a",
        "copy",
        "-movflags",
        "+faststart",
        str(output_path),
    ]


def render_captions(
    input_path: str | Path,
    captions: KinoCaptions,
    output_path: str | Path,
    *,
    ass_path: str | Path | None = None,
    size: tuple[int, int] = (1080, 1920),
) -> Path:
    input_file = Path(input_path)
    output_file = Path(output_path)
    ass_file = Path(ass_path) if ass_path else output_file.with_suffix(".ass")
    write_ass(captions, ass_file, size=size)
    run(build_render_captions_command(input_file, ass_file, output_file))
    return output_file


def _caption_segments(words: tuple[WordToken, ...], style: CaptionStyle) -> list[CaptionSegment]:
    max_words = 5 if style.preset == "social-short-bold" else 8
    max_duration = 1.9 if style.preset == "social-short-bold" else 2.8
    segments: list[CaptionSegment] = []
    start = 0
    while start < len(words):
        end = min(start + max_words, len(words))
        while end > start + 1 and words[end - 1].end - words[start].start > max_duration:
            end -= 1
        text = " ".join(word.text for word in words[start:end])
        if len(wrap_caption_text(_style_text(text, style), style)) > style.max_lines and end > start + 1:
            end -= 1
            text = " ".join(word.text for word in words[start:end])
        chunk = words[start:end]
        segments.append(
            CaptionSegment(
                id=f"cap:{len(segments) + 1:03d}",
                token_start=start,
                token_end=end,
                word_start_id=chunk[0].id,
                word_end_id=chunk[-1].id,
                start=round(chunk[0].start, 3),
                end=round(chunk[-1].end, 3),
                text=_style_text(text, style),
                emphasized_words=_emphasized_words(chunk),
                confidence=_segment_confidence(chunk),
                reasons=(
                    f"Grouped {len(chunk)} transcript token(s) for {style.preset}.",
                    "Caption timing is derived from word alignment.",
                ),
            )
        )
        start = end
    return segments


def _style_text(text: str, style: CaptionStyle) -> str:
    return text.upper() if style.uppercase else text


def _emphasized_words(words: tuple[WordToken, ...]) -> tuple[str, ...]:
    candidates = [
        word.text.strip(".,!?;:").lower()
        for word in words
        if len(word.text.strip(".,!?;:")) >= 5 or word.text.lower() in {"proof", "demo", "mistake", "watch"}
    ]
    return tuple(dict.fromkeys(candidates[:3]))


def _segment_confidence(words: tuple[WordToken, ...]) -> float:
    confidences = [word.confidence for word in words if word.confidence is not None]
    if not confidences:
        return 0.72
    return round(sum(confidences) / len(confidences), 3)


def _validate_style(style: CaptionStyle) -> None:
    _preset(style.preset)
    if not style.font:
        raise CaptionError("caption font must not be empty")
    if style.font_size <= 0:
        raise CaptionError("caption font_size must be positive")
    if style.alignment not in range(1, 10):
        raise CaptionError("caption alignment must be an ASS alignment value from 1 to 9")
    if style.margin_v < 0:
        raise CaptionError("caption margin_v must be >= 0")
    if style.max_chars_per_line <= 0:
        raise CaptionError("caption max_chars_per_line must be positive")
    if style.max_lines <= 0:
        raise CaptionError("caption max_lines must be positive")


def _transcript_hash(edit: KinoEdit) -> str:
    payload = json.dumps(edit.transcript.to_dict(), sort_keys=True, separators=(",", ":")).encode()
    return f"sha256:{sha256(payload).hexdigest()}"


def _ass_time(value: float) -> str:
    centiseconds = round(value * 100)
    hours, remainder = divmod(centiseconds, 360000)
    minutes, remainder = divmod(remainder, 6000)
    seconds, centiseconds = divmod(remainder, 100)
    return f"{hours:d}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"


def _ass_escape(value: str) -> str:
    return value.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")


def _filter_path(path: Path) -> str:
    text = path.resolve().as_posix()
    return text.replace("\\", "\\\\").replace(":", r"\:").replace("'", r"\'")


def _size(size: tuple[int, int]) -> tuple[int, int]:
    if len(size) != 2:
        raise CaptionError("size must contain exactly two dimensions")
    width, height = int(size[0]), int(size[1])
    if width <= 0 or height <= 0:
        raise CaptionError("size dimensions must be positive")
    return width, height


def _archetype_id(value: str) -> ArchetypeId:
    if value not in ("social-short", "founder-product-explainer"):
        raise CaptionError(f"unsupported archetype id: {value}")
    return value  # type: ignore[return-value]


def _preset(value: str) -> CaptionPreset:
    if value not in ("social-short-bold", "founder-explainer-clean"):
        raise CaptionError(f"unsupported caption preset: {value}")
    return value  # type: ignore[return-value]


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CaptionError(f"{label} must be an object")
    return value


def _sequence(value: object, key: str) -> tuple[object, ...]:
    if not isinstance(value, list | tuple):
        raise CaptionError(f"{key} must be a list")
    return tuple(value)


def _required_str(data: Mapping[str, Any], key: str) -> str:
    if key not in data:
        raise CaptionError(f"missing required key: {key}")
    value = data[key]
    if not isinstance(value, str):
        raise CaptionError(f"{key} must be a string")
    return value


def _required_int(data: Mapping[str, Any], key: str) -> int:
    if key not in data:
        raise CaptionError(f"missing required key: {key}")
    value = data[key]
    if not isinstance(value, int) or isinstance(value, bool):
        raise CaptionError(f"{key} must be an integer")
    return value


def _required_float(data: Mapping[str, Any], key: str) -> float:
    if key not in data:
        raise CaptionError(f"missing required key: {key}")
    value = data[key]
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise CaptionError(f"{key} must be a number")
    return float(value)


def _str_tuple(value: object, key: str) -> tuple[str, ...]:
    items = _sequence(value, key)
    for item in items:
        if not isinstance(item, str):
            raise CaptionError(f"{key} values must be strings")
    return tuple(items)


__all__ = [
    "CaptionError",
    "CaptionPreset",
    "CaptionSegment",
    "CaptionStyle",
    "KINO_CAPTIONS_SCHEMA",
    "KINO_CAPTIONS_VERSION",
    "KinoCaptions",
    "build_render_captions_command",
    "captions_to_ass",
    "default_caption_style",
    "load_captions",
    "plan_captions",
    "render_captions",
    "validate_captions",
    "validate_captions_for_edit",
    "wrap_caption_text",
    "write_ass",
    "write_captions_json",
]
