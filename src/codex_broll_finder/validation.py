from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from .presets import ExportPreset
from .probe import MediaProbe

CheckStatus = Literal["pass", "warning", "fail", "manual-review-required"]


@dataclass(frozen=True)
class ValidationCheck:
    name: str
    status: CheckStatus
    expected: str
    observed: str
    message: str


@dataclass(frozen=True)
class ValidationReport:
    preset: dict[str, object]
    media: dict[str, object]
    checks: tuple[ValidationCheck, ...]
    overall: CheckStatus

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["checks"] = [asdict(check) for check in self.checks]
        return data


def validate_export(probe: MediaProbe, preset: ExportPreset) -> ValidationReport:
    checks = tuple(_checks(probe, preset))
    overall = _overall_status(checks)
    return ValidationReport(preset=preset.to_dict(), media=probe.to_dict(), checks=checks, overall=overall)


def write_json_report(report: ValidationReport, path: str | Path) -> Path:
    out = Path(path)
    out.write_text(json.dumps(report.to_dict(), indent=2) + "\n")
    return out


def write_markdown_report(report: ValidationReport, path: str | Path) -> Path:
    out = Path(path)
    lines = [
        "# B-Roll Validation Report",
        "",
        f"Overall: `{report.overall}`",
        f"Preset: `{report.preset['name']}`",
        f"Media: `{report.media['path']}`",
        "",
        "| Check | Status | Expected | Observed | Message |",
        "| --- | --- | --- | --- | --- |",
    ]
    for check in report.checks:
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_cell(check.name),
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


def _checks(probe: MediaProbe, preset: ExportPreset) -> list[ValidationCheck]:
    checks: list[ValidationCheck] = []
    video = probe.video
    audio = probe.audio

    if video is None:
        checks.append(_fail("video_stream", "one video stream", "none", "Export has no video stream."))
        return checks

    checks.append(
        _status(
            "container",
            _format_matches(probe.format_name, preset.container, path=probe.path, tags=probe.format_tags),
            preset.container,
            str(probe.format_name),
            "Container matches preset.",
            "Export container should be MP4 for social/web delivery.",
        )
    )
    checks.append(
        _status(
            "dimensions",
            (video.width, video.height) == preset.dimensions,
            f"{preset.width}x{preset.height}",
            f"{video.width}x{video.height}",
            "Video dimensions match preset.",
            "Video dimensions do not match preset.",
        )
    )
    checks.append(
        _status(
            "video_codec",
            video.codec_name == preset.video_codec,
            preset.video_codec,
            str(video.codec_name),
            "Video codec matches preset.",
            "Video codec should be H.264 for social MP4 exports.",
        )
    )
    checks.append(_pixel_format_check(video.pix_fmt))
    checks.append(_progressive_check(video.field_order))
    checks.append(_sar_check(video.sample_aspect_ratio))
    if preset.min_fps is not None:
        fps = video.avg_frame_rate or 0
        checks.append(
            _status(
                "frame_rate",
                fps >= preset.min_fps,
                f">= {preset.min_fps:g} fps",
                f"{fps:g} fps" if fps else "unknown",
                "Frame rate meets preset floor.",
                "Frame rate is below the social preset floor.",
            )
        )

    if audio is None:
        checks.append(
            ValidationCheck(
                name="audio_stream",
                status="warning",
                expected="AAC audio stream at 48 kHz",
                observed="none",
                message="No audio stream found; this may be intentional for silent exports.",
            )
        )
    else:
        checks.append(
            _status(
                "audio_codec",
                audio.codec_name == preset.audio_codec,
                preset.audio_codec,
                str(audio.codec_name),
                "Audio codec matches preset.",
                "Audio codec should be AAC for MP4 social exports.",
            )
        )
        checks.append(
            _status(
                "audio_sample_rate",
                audio.sample_rate == preset.audio_sample_rate,
                f"{preset.audio_sample_rate} Hz",
                f"{audio.sample_rate} Hz",
                "Audio sample rate matches preset.",
                "Audio sample rate should be 48 kHz.",
            )
        )

    checks.append(_faststart_check(probe.path))
    return checks


def _overall_status(checks: tuple[ValidationCheck, ...]) -> CheckStatus:
    statuses = {check.status for check in checks}
    if "fail" in statuses:
        return "fail"
    if "warning" in statuses:
        return "warning"
    if "manual-review-required" in statuses:
        return "manual-review-required"
    return "pass"


def _status(
    name: str,
    passed: bool,
    expected: str,
    observed: str,
    pass_message: str,
    fail_message: str,
    *,
    warning: bool = False,
) -> ValidationCheck:
    if passed:
        return ValidationCheck(name, "pass", expected, observed, pass_message)
    return ValidationCheck(name, "warning" if warning else "fail", expected, observed, fail_message)


def _fail(name: str, expected: str, observed: str, message: str) -> ValidationCheck:
    return ValidationCheck(name, "fail", expected, observed, message)


def _progressive_check(field_order: str | None) -> ValidationCheck:
    if field_order in (None, "unknown", "progressive"):
        return ValidationCheck(
            "progressive_scan",
            "pass",
            "progressive or unknown",
            str(field_order),
            "No interlaced field order reported.",
        )
    return ValidationCheck(
        "progressive_scan",
        "fail",
        "progressive",
        field_order,
        "Interlaced exports are not acceptable for social/web delivery.",
    )


def _sar_check(sample_aspect_ratio: str | None) -> ValidationCheck:
    if sample_aspect_ratio in ("1:1", "1/1"):
        return ValidationCheck("square_pixels", "pass", "1:1", str(sample_aspect_ratio), "Sample aspect ratio is square.")
    if sample_aspect_ratio in (None, "0:1"):
        return ValidationCheck(
            "square_pixels",
            "warning",
            "1:1",
            str(sample_aspect_ratio),
            "Sample aspect ratio is missing or unknown; verify before release.",
        )
    return ValidationCheck(
        "square_pixels",
        "fail",
        "1:1",
        sample_aspect_ratio,
        "Non-square pixels are not acceptable for social/web delivery.",
    )


def _pixel_format_check(pix_fmt: str | None) -> ValidationCheck:
    if pix_fmt == "yuv420p":
        return ValidationCheck(
            "pixel_format",
            "pass",
            "yuv420p",
            pix_fmt,
            "Pixel format is broadly compatible for social/web delivery.",
        )
    if pix_fmt is None:
        return ValidationCheck(
            "pixel_format",
            "warning",
            "yuv420p",
            "unknown",
            "Pixel format is unknown; verify 4:2:0 compatibility before release.",
        )
    return ValidationCheck(
        "pixel_format",
        "fail",
        "yuv420p",
        pix_fmt,
        "Use yuv420p for broad social/web compatibility.",
    )


def _format_matches(
    format_name: str | None,
    expected: str,
    *,
    path: str,
    tags: dict[str, str],
) -> bool:
    if not format_name:
        return False
    aliases = {part.strip().lower() for part in format_name.split(",")}
    if expected == "mp4":
        major_brand = tags.get("major_brand", "").strip().lower()
        has_mp4_demuxer = bool({"mp4", "mov", "m4a", "3gp", "3g2", "mj2"} & aliases)
        has_mp4_extension = Path(path).suffix.lower() == ".mp4"
        is_quicktime = major_brand in {"qt", "qt  "}
        return has_mp4_demuxer and has_mp4_extension and not is_quicktime
    return expected in aliases


def _faststart_check(path: str) -> ValidationCheck:
    media_path = Path(path)
    if not media_path.exists():
        return ValidationCheck(
            "faststart",
            "manual-review-required",
            "moov atom before mdat",
            "file not available",
            "MP4 atom order could not be inspected because the file is not available.",
        )

    head = media_path.read_bytes()[:2_000_000]
    moov_at = head.find(b"moov")
    mdat_at = head.find(b"mdat")
    if moov_at == -1 or mdat_at == -1:
        return ValidationCheck(
            "faststart",
            "manual-review-required",
            "moov atom before mdat",
            "moov or mdat atom not found in first 2 MB",
            "MP4 atom order could not be determined from the file header.",
        )
    if moov_at < mdat_at:
        return ValidationCheck(
            "faststart",
            "pass",
            "moov atom before mdat",
            f"moov@{moov_at}, mdat@{mdat_at}",
            "MP4 appears to be fast-start optimized.",
        )
    return ValidationCheck(
        "faststart",
        "warning",
        "moov atom before mdat",
        f"moov@{moov_at}, mdat@{mdat_at}",
        "MP4 may not start playback quickly on social/web platforms; export with -movflags +faststart.",
    )


def _md_cell(value: str) -> str:
    return value.replace("\\", "\\\\").replace("|", "\\|").replace("\n", "<br>")
