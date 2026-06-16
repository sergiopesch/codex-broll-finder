from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .manifest import Beat, Manifest

MediaType = Literal["video", "audio", "image"]
SourceRole = Literal["base", "cutaway"]
TrackType = Literal["video", "audio"]
ClipDurationMode = Literal["fixed", "to_source_end"]
ClipOperation = Literal["base", "replace"]
ClipFit = Literal["cover", "none"]
AudioPolicy = Literal["none", "preserve", "muted"]
ValidationPointKind = Literal["beat_start", "beat_mid", "beat_end", "joint"]


class GraphError(ValueError):
    pass


@dataclass(frozen=True)
class MetadataItem:
    key: str
    value: str

    def to_dict(self) -> dict[str, str]:
        return {"key": self.key, "value": self.value}


@dataclass(frozen=True)
class RenderSource:
    id: str
    path: Path
    media_type: MediaType
    role: SourceRole

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", Path(self.path))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "path": str(self.path),
            "media_type": self.media_type,
            "role": self.role,
        }


@dataclass(frozen=True)
class RenderClip:
    id: str
    source_id: str
    timeline_start: float
    duration: float | None
    source_start: float = 0.0
    duration_mode: ClipDurationMode = "fixed"
    operation: ClipOperation = "base"
    fit: ClipFit = "cover"
    audio_policy: AudioPolicy = "none"
    metadata: tuple[MetadataItem, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "timeline_start", _seconds(self.timeline_start))
        object.__setattr__(self, "source_start", _seconds(self.source_start))
        if self.duration is not None:
            object.__setattr__(self, "duration", _seconds(self.duration))
        object.__setattr__(self, "metadata", tuple(self.metadata))

    @property
    def timeline_end(self) -> float | None:
        if self.duration is None:
            return None
        return _seconds(self.timeline_start + self.duration)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "timeline_start": self.timeline_start,
            "duration": self.duration,
            "source_start": self.source_start,
            "duration_mode": self.duration_mode,
            "operation": self.operation,
            "fit": self.fit,
            "audio_policy": self.audio_policy,
            "metadata": [item.to_dict() for item in self.metadata],
        }


@dataclass(frozen=True)
class RenderTrack:
    id: str
    media_type: TrackType
    clips: tuple[RenderClip, ...]
    name: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "clips", tuple(self.clips))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "media_type": self.media_type,
            "name": self.name,
            "clips": [clip.to_dict() for clip in self.clips],
        }


@dataclass(frozen=True)
class RenderOutput:
    id: str
    path: Path
    width: int
    height: int
    fps: int
    container: str = "mp4"
    video_codec: str = "libx264"
    video_crf: int = 18
    video_preset: str = "fast"
    audio_codec: str = "aac"
    audio_bitrate: str = "192k"
    movflags: str = "+faststart"

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", Path(self.path))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "path": str(self.path),
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "container": self.container,
            "video_codec": self.video_codec,
            "video_crf": self.video_crf,
            "video_preset": self.video_preset,
            "audio_codec": self.audio_codec,
            "audio_bitrate": self.audio_bitrate,
            "movflags": self.movflags,
        }


@dataclass(frozen=True)
class ValidationPoint:
    id: str
    time: float
    kind: ValidationPointKind
    beat_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "time", _seconds(self.time))
        object.__setattr__(self, "beat_ids", tuple(self.beat_ids))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "time": self.time,
            "kind": self.kind,
            "beat_ids": list(self.beat_ids),
        }


@dataclass(frozen=True)
class ValidationExpectations:
    output_width: int
    output_height: int
    output_fps: int
    preserve_audio_source_id: str | None = "base"
    muted_source_roles: tuple[SourceRole, ...] = ("cutaway",)
    output_duration: float | None = None
    output_duration_source_id: str | None = "base"
    points: tuple[ValidationPoint, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "muted_source_roles", tuple(self.muted_source_roles))
        if self.output_duration is not None:
            object.__setattr__(self, "output_duration", _seconds(self.output_duration))
        object.__setattr__(self, "points", tuple(self.points))

    def to_dict(self) -> dict[str, Any]:
        return {
            "output_width": self.output_width,
            "output_height": self.output_height,
            "output_fps": self.output_fps,
            "preserve_audio_source_id": self.preserve_audio_source_id,
            "muted_source_roles": list(self.muted_source_roles),
            "output_duration": self.output_duration,
            "output_duration_source_id": self.output_duration_source_id,
            "points": [point.to_dict() for point in self.points],
        }


@dataclass(frozen=True)
class RenderGraph:
    sources: tuple[RenderSource, ...]
    tracks: tuple[RenderTrack, ...]
    outputs: tuple[RenderOutput, ...]
    validation: ValidationExpectations
    version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "sources", tuple(self.sources))
        object.__setattr__(self, "tracks", tuple(self.tracks))
        object.__setattr__(self, "outputs", tuple(self.outputs))
        self.validate()

    @classmethod
    def from_manifest(cls, manifest: Manifest, *, base_duration: float | None = None) -> RenderGraph:
        return manifest_to_graph(manifest, base_duration=base_duration)

    def validate(self) -> None:
        if self.version != 1:
            raise GraphError(f"unsupported render graph version: {self.version}")

        source_ids = _require_unique("source", (source.id for source in self.sources))
        for source in self.sources:
            if not source.id:
                raise GraphError("source id must not be empty")
            if source.media_type not in ("video", "audio", "image"):
                raise GraphError(f"{source.id}: unsupported source media type: {source.media_type}")
            if source.role not in ("base", "cutaway"):
                raise GraphError(f"{source.id}: unsupported source role: {source.role}")

        _require_unique("track", (track.id for track in self.tracks))
        clip_ids: list[str] = []
        for track in self.tracks:
            if track.media_type not in ("video", "audio"):
                raise GraphError(f"{track.id}: unsupported track media type: {track.media_type}")
            last_end: float | None = None
            for index, clip in enumerate(track.clips):
                clip_ids.append(clip.id)
                if clip.source_id not in source_ids:
                    raise GraphError(f"{clip.id}: unknown source id: {clip.source_id}")
                if clip.timeline_start < 0:
                    raise GraphError(f"{clip.id}: timeline_start must be >= 0")
                if clip.source_start < 0:
                    raise GraphError(f"{clip.id}: source_start must be >= 0")
                if clip.duration_mode == "fixed":
                    if clip.duration is None or clip.duration <= 0:
                        raise GraphError(f"{clip.id}: fixed clips must have a positive duration")
                elif clip.duration_mode == "to_source_end":
                    if clip.duration is not None:
                        raise GraphError(f"{clip.id}: to_source_end clips must not set duration")
                    if index != len(track.clips) - 1:
                        raise GraphError(f"{clip.id}: open-ended clips must be last on their track")
                else:
                    raise GraphError(f"{clip.id}: unsupported duration mode: {clip.duration_mode}")

                if clip.operation not in ("base", "replace"):
                    raise GraphError(f"{clip.id}: unsupported clip operation: {clip.operation}")
                if clip.fit not in ("cover", "none"):
                    raise GraphError(f"{clip.id}: unsupported fit: {clip.fit}")
                if clip.audio_policy not in ("none", "preserve", "muted"):
                    raise GraphError(f"{clip.id}: unsupported audio policy: {clip.audio_policy}")

                source = next(source for source in self.sources if source.id == clip.source_id)
                _validate_track_source_compatibility(track, clip, source)

                if last_end is not None and clip.timeline_start < last_end:
                    raise GraphError(f"{clip.id}: clips on track {track.id} must be sorted and non-overlapping")
                last_end = clip.timeline_end

        _require_unique("clip", clip_ids)
        _require_unique("output", (output.id for output in self.outputs))
        for output in self.outputs:
            if output.width <= 0 or output.height <= 0:
                raise GraphError(f"{output.id}: output dimensions must be positive")
            if output.fps <= 0:
                raise GraphError(f"{output.id}: output fps must be positive")
            if output.video_crf < 0:
                raise GraphError(f"{output.id}: video_crf must be >= 0")

        if self.validation.output_width <= 0 or self.validation.output_height <= 0:
            raise GraphError("validation output dimensions must be positive")
        if self.validation.output_fps <= 0:
            raise GraphError("validation output fps must be positive")
        if self.validation.output_duration is not None and self.validation.output_duration <= 0:
            raise GraphError("validation output_duration must be positive")
        if self.validation.preserve_audio_source_id and self.validation.preserve_audio_source_id not in source_ids:
            raise GraphError("validation preserve_audio_source_id must reference a source")
        if self.validation.output_duration_source_id and self.validation.output_duration_source_id not in source_ids:
            raise GraphError("validation output_duration_source_id must reference a source")
        for point in self.validation.points:
            if point.time < 0:
                raise GraphError(f"{point.id}: validation point time must be >= 0")

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "sources": [source.to_dict() for source in self.sources],
            "tracks": [track.to_dict() for track in self.tracks],
            "outputs": [output.to_dict() for output in self.outputs],
            "validation": self.validation.to_dict(),
        }

    def to_json(self, *, indent: int | None = None) -> str:
        separators = None if indent is not None else (",", ":")
        return json.dumps(self.to_dict(), indent=indent, separators=separators, sort_keys=True)

    def stable_hash(self) -> str:
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()


def manifest_to_graph(manifest: Manifest, *, base_duration: float | None = None) -> RenderGraph:
    if base_duration is not None:
        base_duration = _seconds(base_duration)
        if base_duration <= 0:
            raise GraphError("base_duration must be positive")
        if manifest.beats and base_duration < manifest.beats[-1].end:
            raise GraphError("base_duration must cover the final cutaway beat")

    sources = [
        RenderSource(id="base", path=manifest.base, media_type="video", role="base"),
        *[
            RenderSource(
                id=_cutaway_source_id(beat),
                path=beat.asset,
                media_type="image" if beat.kind == "still" else "video",
                role="cutaway",
            )
            for beat in manifest.beats
        ],
    ]

    video_clips: list[RenderClip] = []
    last = 0.0
    base_segment = 0
    for beat in manifest.beats:
        if beat.start > last:
            video_clips.append(
                RenderClip(
                    id=f"base:{base_segment}",
                    source_id="base",
                    timeline_start=last,
                    source_start=last,
                    duration=beat.start - last,
                    operation="base",
                    fit="cover",
                    audio_policy="none",
                )
            )
            base_segment += 1
        video_clips.append(
            RenderClip(
                id=f"cutaway:{beat.id}",
                source_id=_cutaway_source_id(beat),
                timeline_start=beat.start,
                source_start=beat.source_in if beat.kind == "video" else 0.0,
                duration=beat.duration,
                operation="replace",
                fit="cover",
                audio_policy="muted",
                metadata=_beat_metadata(beat),
            )
        )
        last = beat.end

    if base_duration is None:
        video_clips.append(
            RenderClip(
                id=f"base:{base_segment}",
                source_id="base",
                timeline_start=last,
                source_start=last,
                duration=None,
                duration_mode="to_source_end",
                operation="base",
                fit="cover",
                audio_policy="none",
            )
        )
        audio_duration = None
        audio_duration_mode: ClipDurationMode = "to_source_end"
    else:
        if last < base_duration:
            video_clips.append(
                RenderClip(
                    id=f"base:{base_segment}",
                    source_id="base",
                    timeline_start=last,
                    source_start=last,
                    duration=base_duration - last,
                    operation="base",
                    fit="cover",
                    audio_policy="none",
                )
            )
        audio_duration = base_duration
        audio_duration_mode = "fixed"

    tracks = (
        RenderTrack(id="picture", media_type="video", name="Picture", clips=tuple(video_clips)),
        RenderTrack(
            id="base_audio",
            media_type="audio",
            name="Base audio",
            clips=(
                RenderClip(
                    id="audio:base",
                    source_id="base",
                    timeline_start=0.0,
                    source_start=0.0,
                    duration=audio_duration,
                    duration_mode=audio_duration_mode,
                    operation="base",
                    fit="none",
                    audio_policy="preserve",
                ),
            ),
        ),
    )

    output_width, output_height = manifest.size
    return RenderGraph(
        sources=tuple(sources),
        tracks=tracks,
        outputs=(
            RenderOutput(
                id="main",
                path=manifest.output,
                width=output_width,
                height=output_height,
                fps=manifest.fps,
            ),
        ),
        validation=ValidationExpectations(
            output_width=output_width,
            output_height=output_height,
            output_fps=manifest.fps,
            output_duration=base_duration,
            points=_validation_points(manifest.beats),
        ),
    )


graph_from_manifest = manifest_to_graph


def _validate_track_source_compatibility(track: RenderTrack, clip: RenderClip, source: RenderSource) -> None:
    if track.media_type == "video" and source.media_type not in ("video", "image"):
        raise GraphError(f"{clip.id}: video clips must reference video or image sources")
    if track.media_type == "audio" and source.media_type not in ("video", "audio"):
        raise GraphError(f"{clip.id}: audio clips must reference video or audio sources")


def _require_unique(label: str, ids: Any) -> set[str]:
    seen: set[str] = set()
    for id_ in ids:
        if id_ in seen:
            raise GraphError(f"duplicate {label} id: {id_}")
        seen.add(id_)
    return seen


def _cutaway_source_id(beat: Beat) -> str:
    return f"cutaway:{beat.id}"


def _beat_metadata(beat: Beat) -> tuple[MetadataItem, ...]:
    items = [
        MetadataItem("beat_id", beat.id),
        MetadataItem("kind", beat.kind),
        MetadataItem("line", beat.line),
        MetadataItem("interpretation", beat.interpretation),
        MetadataItem("route", beat.route),
        MetadataItem("status", beat.status),
    ]
    if beat.credit is not None:
        items.append(MetadataItem("credit", beat.credit))
    return tuple(items)


def _validation_points(beats: tuple[Beat, ...]) -> tuple[ValidationPoint, ...]:
    points: list[ValidationPoint] = []
    previous: Beat | None = None
    for beat in beats:
        points.append(ValidationPoint(id=f"{beat.id}-start", time=beat.start, kind="beat_start", beat_ids=(beat.id,)))
        points.append(
            ValidationPoint(
                id=f"{beat.id}-mid",
                time=round((beat.start + beat.end) / 2, 3),
                kind="beat_mid",
                beat_ids=(beat.id,),
            )
        )
        points.append(ValidationPoint(id=f"{beat.id}-end", time=beat.end, kind="beat_end", beat_ids=(beat.id,)))
        if previous and abs(previous.end - beat.start) < 0.05:
            points.append(
                ValidationPoint(
                    id=f"{previous.id}-{beat.id}-joint",
                    time=beat.start,
                    kind="joint",
                    beat_ids=(previous.id, beat.id),
                )
            )
        previous = beat
    return tuple(points)


def _seconds(value: float) -> float:
    return round(float(value), 6)
