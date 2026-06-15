from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

from .video import ToolError


@dataclass(frozen=True)
class VideoStream:
    codec_name: str | None
    width: int | None
    height: int | None
    avg_frame_rate: float | None
    sample_aspect_ratio: str | None
    display_aspect_ratio: str | None
    pix_fmt: str | None
    field_order: str | None


@dataclass(frozen=True)
class AudioStream:
    codec_name: str | None
    sample_rate: int | None
    channels: int | None
    channel_layout: str | None


@dataclass(frozen=True)
class MediaProbe:
    path: str
    format_name: str | None
    format_tags: dict[str, str]
    duration: float | None
    bit_rate: int | None
    size_bytes: int | None
    video: VideoStream | None
    audio: AudioStream | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def probe_media(path: str | Path) -> MediaProbe:
    media_path = Path(path)
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(media_path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise ToolError(result.stderr.strip())
    return parse_ffprobe_json(json.loads(result.stdout), media_path)


def parse_ffprobe_json(data: dict[str, Any], path: Path) -> MediaProbe:
    streams = data.get("streams", [])
    video_raw = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    audio_raw = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    fmt = data.get("format", {})
    return MediaProbe(
        path=str(path),
        format_name=_str_or_none(fmt.get("format_name")),
        format_tags={str(key): str(value) for key, value in fmt.get("tags", {}).items()},
        duration=_float_or_none(fmt.get("duration")),
        bit_rate=_int_or_none(fmt.get("bit_rate")),
        size_bytes=_int_or_none(fmt.get("size")),
        video=_parse_video(video_raw) if video_raw else None,
        audio=_parse_audio(audio_raw) if audio_raw else None,
    )


def parse_frame_rate(value: str | None) -> float | None:
    if not value or value == "0/0":
        return None
    try:
        fraction = Fraction(value)
    except (ValueError, ZeroDivisionError):
        return None
    return round(float(fraction), 3)


def _parse_video(raw: dict[str, Any]) -> VideoStream:
    return VideoStream(
        codec_name=_str_or_none(raw.get("codec_name")),
        width=_int_or_none(raw.get("width")),
        height=_int_or_none(raw.get("height")),
        avg_frame_rate=parse_frame_rate(_str_or_none(raw.get("avg_frame_rate") or raw.get("r_frame_rate"))),
        sample_aspect_ratio=_str_or_none(raw.get("sample_aspect_ratio")),
        display_aspect_ratio=_str_or_none(raw.get("display_aspect_ratio")),
        pix_fmt=_str_or_none(raw.get("pix_fmt")),
        field_order=_str_or_none(raw.get("field_order")),
    )


def _parse_audio(raw: dict[str, Any]) -> AudioStream:
    return AudioStream(
        codec_name=_str_or_none(raw.get("codec_name")),
        sample_rate=_int_or_none(raw.get("sample_rate")),
        channels=_int_or_none(raw.get("channels")),
        channel_layout=_str_or_none(raw.get("channel_layout")),
    )


def _str_or_none(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _int_or_none(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float_or_none(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
