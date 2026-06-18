from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .audio_qc import inspect_audio
from .captions import KinoCaptions, load_captions
from .presets import get_preset
from .probe import MediaProbe, probe_media
from .qc import expected_frame_paths, verify_frames
from .validation import validate_export
from .video import run

KINO_REVIEW_VERSION = 1
KINO_REVIEW_SCHEMA = "kino.review.v1"

ReviewStatus = Literal["pass", "manual-review-required", "warning", "fail"]


class ReviewError(ValueError):
    pass


@dataclass(frozen=True)
class ReviewCheck:
    name: str
    category: str
    status: ReviewStatus
    expected: str
    observed: str
    message: str
    recommendation: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", _status(self.status))
        if not self.name:
            raise ReviewError("review check name must not be empty")
        if not self.category:
            raise ReviewError(f"{self.name}: category must not be empty")
        if not self.expected:
            raise ReviewError(f"{self.name}: expected must not be empty")
        if not self.observed:
            raise ReviewError(f"{self.name}: observed must not be empty")
        if not self.message:
            raise ReviewError(f"{self.name}: message must not be empty")

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> ReviewCheck:
        return cls(
            name=_required_str(data, "name"),
            category=_required_str(data, "category"),
            status=_status(_required_str(data, "status")),
            expected=_required_str(data, "expected"),
            observed=_required_str(data, "observed"),
            message=_required_str(data, "message"),
            recommendation=_optional_str(data, "recommendation"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "category": self.category,
            "status": self.status,
            "expected": self.expected,
            "observed": self.observed,
            "message": self.message,
            "recommendation": self.recommendation,
        }


@dataclass(frozen=True)
class ReviewArtifact:
    kind: str
    path: str
    summary: str

    def __post_init__(self) -> None:
        if not self.kind:
            raise ReviewError("review artifact kind must not be empty")
        if not self.path:
            raise ReviewError(f"{self.kind}: artifact path must not be empty")
        if not self.summary:
            raise ReviewError(f"{self.kind}: artifact summary must not be empty")

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> ReviewArtifact:
        return cls(
            kind=_required_str(data, "kind"),
            path=_required_str(data, "path"),
            summary=_required_str(data, "summary"),
        )

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "path": self.path, "summary": self.summary}


@dataclass(frozen=True)
class KinoReview:
    id: str
    media: str
    checks: tuple[ReviewCheck, ...]
    artifacts: tuple[ReviewArtifact, ...] = ()
    overall: ReviewStatus = "pass"
    recommendations: tuple[str, ...] = ()
    preset: str | None = None
    archetype_id: str | None = None
    version: int = KINO_REVIEW_VERSION
    schema: str = KINO_REVIEW_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(self, "checks", tuple(self.checks))
        object.__setattr__(self, "artifacts", tuple(self.artifacts))
        object.__setattr__(self, "recommendations", tuple(self.recommendations))
        validate_review(self)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> KinoReview:
        return cls(
            version=_required_int(data, "version") if "version" in data else KINO_REVIEW_VERSION,
            schema=_required_str(data, "schema") if "schema" in data else KINO_REVIEW_SCHEMA,
            id=_required_str(data, "id"),
            media=_required_str(data, "media"),
            preset=_optional_str(data, "preset"),
            archetype_id=_optional_str(data, "archetype_id"),
            overall=_status(_required_str(data, "overall")),
            recommendations=_str_tuple(data.get("recommendations", ()), "recommendations"),
            artifacts=tuple(ReviewArtifact.from_dict(_mapping(item, "review artifact")) for item in _sequence(data.get("artifacts", ()), "artifacts")),
            checks=tuple(ReviewCheck.from_dict(_mapping(item, "review check")) for item in _sequence(data.get("checks", ()), "checks")),
        )

    @classmethod
    def from_json(cls, text: str) -> KinoReview:
        return cls.from_dict(_mapping(json.loads(text), "KINO-REVIEW document"))

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "schema": self.schema,
            "id": self.id,
            "media": self.media,
            "preset": self.preset,
            "archetype_id": self.archetype_id,
            "overall": self.overall,
            "recommendations": list(self.recommendations),
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "checks": [check.to_dict() for check in self.checks],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"


def review_media(
    media_path: str | Path,
    *,
    review_id: str = "kino-review",
    preset: str | None = None,
    archetype_id: str | None = None,
    captions_path: str | Path | None = None,
    frames_dir: str | Path | None = None,
    contact_sheet_path: str | Path | None = None,
    sample_count: int = 3,
    expected_sample_rate: int | None = 48000,
    expected_channels: int | None = None,
) -> KinoReview:
    media = Path(media_path)
    probe = probe_media(media)
    checks: list[ReviewCheck] = []
    artifacts: list[ReviewArtifact] = []

    checks.extend(_probe_checks(probe))

    if preset is not None:
        export_report = validate_export(probe, get_preset(preset))
        checks.extend(_checks_from_report("export", export_report.checks))
        artifacts.append(ReviewArtifact("export-validation", str(media), f"{preset} validation overall {export_report.overall}"))

    audio_report = inspect_audio(
        media,
        expected_sample_rate=expected_sample_rate,
        expected_channels=expected_channels,
    )
    checks.extend(_checks_from_report("audio", audio_report.checks))
    artifacts.append(ReviewArtifact("audio-qc", str(media), f"audio overall {audio_report.overall}"))

    captions: KinoCaptions | None = None
    if captions_path is not None:
        captions = load_captions(captions_path)
        checks.extend(_caption_checks(captions, probe=probe, expected_archetype=archetype_id))
        artifacts.append(ReviewArtifact("captions", str(captions_path), f"{len(captions.segments)} caption segment(s) reviewed"))

    if archetype_id is not None:
        checks.extend(_archetype_checks(archetype_id, probe, captions))

    if frames_dir is not None:
        labels = sample_review_frames(media, frames_dir, duration=probe.duration, sample_count=sample_count)
        frame_report = verify_frames(
            expected_frame_paths(frames_dir, labels),
            contact_sheet_path=contact_sheet_path,
        )
        checks.extend(_checks_from_report("frames", frame_report.checks))
        artifacts.append(ReviewArtifact("frame-qc", str(frames_dir), f"{len(labels)} sampled review frame(s)"))
        if contact_sheet_path is not None:
            artifacts.append(ReviewArtifact("contact-sheet", str(contact_sheet_path), "review frame contact sheet"))

    recommendations = tuple(dict.fromkeys(check.recommendation for check in checks if check.recommendation))
    return KinoReview(
        id=review_id,
        media=str(media),
        preset=preset,
        archetype_id=archetype_id,
        checks=tuple(checks),
        artifacts=tuple(artifacts),
        overall=_overall(checks),
        recommendations=recommendations,
    )


def sample_review_frames(
    media_path: str | Path,
    frames_dir: str | Path,
    *,
    duration: float | None,
    sample_count: int = 3,
) -> tuple[str, ...]:
    if sample_count < 1:
        raise ReviewError("sample_count must be >= 1")
    media = Path(media_path)
    out_dir = Path(frames_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    labels = tuple(f"review-{index + 1:02d}" for index in range(sample_count))
    for label, when in zip(labels, _sample_times(duration, sample_count), strict=True):
        run(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-ss",
                f"{when:g}",
                "-i",
                str(media),
                "-frames:v",
                "1",
                str(out_dir / f"{label}.jpg"),
            ]
        )
    return labels


def load_review(path: str | Path) -> KinoReview:
    return KinoReview.from_json(Path(path).read_text())


def write_review_json(report: KinoReview, path: str | Path) -> Path:
    validate_review(report)
    out = Path(path)
    out.write_text(report.to_json())
    return out


def write_review_markdown(report: KinoReview, path: str | Path) -> Path:
    validate_review(report)
    out = Path(path)
    lines = [
        "# Kino Media Review",
        "",
        f"Overall: `{report.overall}`",
        f"Media: `{report.media}`",
    ]
    if report.preset is not None:
        lines.append(f"Preset: `{report.preset}`")
    if report.archetype_id is not None:
        lines.append(f"Archetype: `{report.archetype_id}`")
    lines.extend(["", "## Recommendations", ""])
    if report.recommendations:
        lines.extend(f"- {recommendation}" for recommendation in report.recommendations)
    else:
        lines.append("- No blocking recommendations.")
    lines.extend(
        [
            "",
            "## Checks",
            "",
            "| Check | Category | Status | Expected | Observed | Message |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for check in report.checks:
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_cell(check.name),
                    _md_cell(check.category),
                    f"`{check.status}`",
                    _md_cell(check.expected),
                    _md_cell(check.observed),
                    _md_cell(check.message),
                ]
            )
            + " |"
        )
    out.write_text("\n".join(lines) + "\n")
    return out


def validate_review(report: KinoReview) -> None:
    if report.version != KINO_REVIEW_VERSION:
        raise ReviewError(f"unsupported KINO-REVIEW version: {report.version}")
    if report.schema != KINO_REVIEW_SCHEMA:
        raise ReviewError(f"unsupported KINO-REVIEW schema: {report.schema}")
    if not report.id:
        raise ReviewError("review id must not be empty")
    if not report.media:
        raise ReviewError(f"{report.id}: media must not be empty")
    if not report.checks:
        raise ReviewError(f"{report.id}: at least one review check is required")
    if report.overall != _overall(report.checks):
        raise ReviewError(f"{report.id}: overall does not match checks")


def _probe_checks(probe: MediaProbe) -> tuple[ReviewCheck, ...]:
    video = probe.video
    checks = [
        ReviewCheck(
            "media_duration",
            "media",
            "pass" if probe.duration is not None and probe.duration > 0 else "fail",
            "duration > 0s",
            f"{probe.duration:g}s" if probe.duration is not None else "unknown",
            "Media duration is available." if probe.duration is not None and probe.duration > 0 else "Media duration is missing.",
            "Regenerate or re-export media before review." if probe.duration is None or probe.duration <= 0 else None,
        )
    ]
    if video is None:
        checks.append(
            ReviewCheck(
                "video_stream",
                "media",
                "fail",
                "video stream",
                "none",
                "No video stream found.",
                "Render or export a video file before review.",
            )
        )
    else:
        checks.append(
            ReviewCheck(
                "video_stream",
                "media",
                "pass",
                "video stream",
                f"{video.width}x{video.height} {video.codec_name}",
                "Video stream is present.",
            )
        )
    return tuple(checks)


def _caption_checks(captions: KinoCaptions, *, probe: MediaProbe, expected_archetype: str | None) -> tuple[ReviewCheck, ...]:
    checks: list[ReviewCheck] = []
    last_end = max(segment.end for segment in captions.segments)
    duration = probe.duration
    fits = duration is not None and last_end <= duration + 0.25
    checks.append(
        ReviewCheck(
            "caption_timing_bounds",
            "captions",
            "pass" if fits else "fail",
            "last caption <= media duration + 0.25s",
            f"last={last_end:g}s, duration={duration:g}s" if duration is not None else f"last={last_end:g}s, duration=unknown",
            "Caption timings fit within the reviewed media." if fits else "Caption timings extend past the reviewed media.",
            "Replan captions from the final transcript/media timing." if not fits else None,
        )
    )
    if expected_archetype is not None:
        matches = captions.archetype_id == expected_archetype
        checks.append(
            ReviewCheck(
                "caption_archetype_match",
                "captions",
                "pass" if matches else "warning",
                expected_archetype,
                captions.archetype_id,
                "Caption archetype matches the review target." if matches else "Caption archetype differs from the review target.",
                "Regenerate captions for the target archetype." if not matches else None,
            )
        )
    if probe.video is not None and probe.video.height:
        ratio = captions.style.font_size / probe.video.height
        legible = ratio >= 0.025
        checks.append(
            ReviewCheck(
                "caption_font_size_ratio",
                "captions",
                "pass" if legible else "warning",
                "font size >= 2.5% of video height",
                f"{ratio:.3f}",
                "Caption font size is in a legible range." if legible else "Caption font may be too small for mobile review.",
                "Increase caption font size for the target export." if not legible else None,
            )
        )
    return tuple(checks)


def _archetype_checks(archetype_id: str, probe: MediaProbe, captions: KinoCaptions | None) -> tuple[ReviewCheck, ...]:
    if archetype_id not in ("social-short", "founder-product-explainer"):
        raise ReviewError(f"unsupported archetype id: {archetype_id}")
    checks: list[ReviewCheck] = []
    video = probe.video
    if archetype_id == "social-short":
        vertical = video is not None and video.width is not None and video.height is not None and video.height > video.width
        checks.append(
            ReviewCheck(
                "social_short_vertical_frame",
                "archetype",
                "pass" if vertical else "warning",
                "vertical video",
                f"{video.width}x{video.height}" if video is not None else "no video",
                "Social short export is vertical." if vertical else "Social short review target is not vertical.",
                "Export a 9:16 social preset for short-form review." if not vertical else None,
            )
        )
        if captions is None:
            checks.append(
                ReviewCheck(
                    "social_short_captions",
                    "archetype",
                    "warning",
                    "caption artifact",
                    "missing",
                    "Short-form videos usually need burned-in captions for silent autoplay.",
                    "Run plan-captions and render-captions before final review.",
                )
            )
    else:
        landscape_or_square = video is not None and video.width is not None and video.height is not None and video.width >= video.height
        checks.append(
            ReviewCheck(
                "founder_explainer_frame_shape",
                "archetype",
                "pass" if landscape_or_square else "manual-review-required",
                "landscape or square frame",
                f"{video.width}x{video.height}" if video is not None else "no video",
                "Founder explainer frame shape is appropriate for long-form/web review."
                if landscape_or_square
                else "Founder explainer is vertical; confirm this is intentional.",
                "Use a landscape/web preset unless the target channel is vertical." if not landscape_or_square else None,
            )
        )
    return tuple(checks)


def _checks_from_report(category: str, checks: tuple[object, ...]) -> tuple[ReviewCheck, ...]:
    converted: list[ReviewCheck] = []
    for check in checks:
        converted.append(
            ReviewCheck(
                name=f"{category}_{getattr(check, 'name')}",
                category=category,
                status=_status(getattr(check, "status")),
                expected=str(getattr(check, "expected")),
                observed=str(getattr(check, "observed")),
                message=str(getattr(check, "message")),
                recommendation=_recommendation(category, _status(getattr(check, "status"))),
            )
        )
    return tuple(converted)


def _recommendation(category: str, status: ReviewStatus) -> str | None:
    if status == "pass":
        return None
    if category == "audio":
        return "Fix audio clipping, silence, sample rate, or channel issues before delivery."
    if category == "frames":
        return "Inspect sampled frames/contact sheet and rerender if frames are blank, frozen, or missing."
    if category == "export":
        return "Re-export with the requested preset before delivery."
    return f"Review {category} before delivery."


def _sample_times(duration: float | None, sample_count: int) -> tuple[float, ...]:
    if duration is None or duration <= 0:
        return tuple(0.0 for _ in range(sample_count))
    if sample_count == 1:
        return (round(min(duration / 2, max(duration - 0.05, 0)), 3),)
    end = max(duration - 0.05, 0)
    return tuple(round((index / (sample_count - 1)) * end, 3) for index in range(sample_count))


def _overall(checks: tuple[ReviewCheck, ...] | list[ReviewCheck]) -> ReviewStatus:
    statuses = {check.status for check in checks}
    if "fail" in statuses:
        return "fail"
    if "warning" in statuses:
        return "warning"
    if "manual-review-required" in statuses:
        return "manual-review-required"
    return "pass"


def _status(value: str) -> ReviewStatus:
    if value not in ("pass", "manual-review-required", "warning", "fail"):
        raise ReviewError(f"unsupported review status: {value}")
    return value  # type: ignore[return-value]


def _mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ReviewError(f"{label} must be an object")
    return value


def _sequence(value: object, key: str) -> tuple[object, ...]:
    if not isinstance(value, list | tuple):
        raise ReviewError(f"{key} must be a list")
    return tuple(value)


def _required_str(data: dict[str, object], key: str) -> str:
    if key not in data:
        raise ReviewError(f"missing required key: {key}")
    value = data[key]
    if not isinstance(value, str):
        raise ReviewError(f"{key} must be a string")
    return value


def _optional_str(data: dict[str, object], key: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ReviewError(f"{key} must be a string")
    return value


def _required_int(data: dict[str, object], key: str) -> int:
    if key not in data:
        raise ReviewError(f"missing required key: {key}")
    value = data[key]
    if not isinstance(value, int) or isinstance(value, bool):
        raise ReviewError(f"{key} must be an integer")
    return value


def _str_tuple(value: object, key: str) -> tuple[str, ...]:
    items = _sequence(value, key)
    for item in items:
        if not isinstance(item, str):
            raise ReviewError(f"{key} values must be strings")
    return tuple(items)


def _md_cell(value: object) -> str:
    return str(value).replace("|", r"\|").replace("\n", "<br>")


__all__ = [
    "KINO_REVIEW_SCHEMA",
    "KINO_REVIEW_VERSION",
    "KinoReview",
    "ReviewArtifact",
    "ReviewCheck",
    "ReviewError",
    "ReviewStatus",
    "load_review",
    "review_media",
    "sample_review_frames",
    "validate_review",
    "write_review_json",
    "write_review_markdown",
]
