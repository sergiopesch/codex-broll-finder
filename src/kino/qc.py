from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal

from PIL import Image, ImageChops, ImageDraw, ImageOps, ImageStat, UnidentifiedImageError

FrameQCStatus = Literal["pass", "warning", "fail"]


@dataclass(frozen=True)
class FrameExpectation:
    label: str
    path: Path

    def to_dict(self) -> dict[str, str]:
        return {"label": self.label, "path": str(self.path)}


@dataclass(frozen=True)
class FrameQCCheck:
    name: str
    status: FrameQCStatus
    label: str | None
    path: Path | None
    expected: str
    observed: str
    message: str

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "status": self.status,
            "label": self.label,
            "path": str(self.path) if self.path is not None else None,
            "expected": self.expected,
            "observed": self.observed,
            "message": self.message,
        }


@dataclass(frozen=True)
class FrameQCReport:
    frames: tuple[FrameExpectation, ...]
    checks: tuple[FrameQCCheck, ...]
    overall: FrameQCStatus
    contact_sheet: Path | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "overall": self.overall,
            "contact_sheet": str(self.contact_sheet) if self.contact_sheet is not None else None,
            "frames": [frame.to_dict() for frame in self.frames],
            "checks": [check.to_dict() for check in self.checks],
        }


@dataclass(frozen=True)
class _FrameAnalysis:
    frame: FrameExpectation
    mean_luma: float
    comparison_image: Image.Image


def expected_frame_paths(frame_dir: str | Path, labels: Iterable[str], *, suffix: str = ".jpg") -> tuple[FrameExpectation, ...]:
    root = Path(frame_dir)
    normalized_suffix = suffix if suffix.startswith(".") else f".{suffix}"
    return tuple(FrameExpectation(label, root / f"{label}{normalized_suffix}") for label in labels)


def frame_expectations_from_dir(
    frame_dir: str | Path,
    *,
    suffixes: tuple[str, ...] = (".jpg", ".jpeg", ".png"),
) -> tuple[FrameExpectation, ...]:
    root = Path(frame_dir)
    normalized = {suffix.lower() if suffix.startswith(".") else f".{suffix.lower()}" for suffix in suffixes}
    return tuple(FrameExpectation(path.stem, path) for path in sorted(root.iterdir()) if path.suffix.lower() in normalized)


def verify_frames(
    frames: Iterable[FrameExpectation | tuple[str, str | Path] | str | Path],
    *,
    min_bytes: int = 512,
    black_luma_threshold: float = 8.0,
    near_identical_rms_threshold: float = 1.5,
    comparison_size: tuple[int, int] = (64, 64),
    contact_sheet_path: str | Path | None = None,
) -> FrameQCReport:
    if min_bytes < 0:
        raise ValueError("min_bytes must be >= 0")
    if black_luma_threshold < 0:
        raise ValueError("black_luma_threshold must be >= 0")
    if near_identical_rms_threshold < 0:
        raise ValueError("near_identical_rms_threshold must be >= 0")
    if comparison_size[0] <= 0 or comparison_size[1] <= 0:
        raise ValueError("comparison_size dimensions must be positive")

    expected = _coerce_frames(frames)
    checks: list[FrameQCCheck] = []
    analyses: list[_FrameAnalysis] = []

    for frame in expected:
        analysis = _inspect_frame(
            frame,
            min_bytes=min_bytes,
            black_luma_threshold=black_luma_threshold,
            comparison_size=comparison_size,
        )
        checks.extend(analysis[0])
        if analysis[1] is not None:
            analyses.append(analysis[1])

    checks.extend(_near_identical_checks(analyses, threshold=near_identical_rms_threshold))

    sheet_path = Path(contact_sheet_path) if contact_sheet_path is not None else None
    if sheet_path is not None:
        generate_contact_sheet(expected, sheet_path)

    return FrameQCReport(
        frames=expected,
        checks=tuple(checks),
        overall=_overall_status(checks),
        contact_sheet=sheet_path,
    )


def generate_contact_sheet(
    frames: Iterable[FrameExpectation | tuple[str, str | Path] | str | Path],
    out_path: str | Path,
    *,
    columns: int = 4,
    thumb_size: tuple[int, int] = (320, 180),
    padding: int = 12,
    label_height: int = 24,
    background: tuple[int, int, int] = (26, 26, 26),
    tile_background: tuple[int, int, int] = (42, 42, 42),
) -> Path:
    expected = _coerce_frames(frames)
    if columns <= 0:
        raise ValueError("columns must be positive")
    if thumb_size[0] <= 0 or thumb_size[1] <= 0:
        raise ValueError("thumb_size dimensions must be positive")
    if padding < 0:
        raise ValueError("padding must be >= 0")
    if label_height < 0:
        raise ValueError("label_height must be >= 0")

    rows = max(1, math.ceil(len(expected) / columns))
    tile_w, tile_h = thumb_size[0], thumb_size[1] + label_height
    sheet_w = padding + columns * (tile_w + padding)
    sheet_h = padding + rows * (tile_h + padding)
    sheet = Image.new("RGB", (sheet_w, sheet_h), background)
    draw = ImageDraw.Draw(sheet)

    for index, frame in enumerate(expected):
        col = index % columns
        row = index // columns
        x = padding + col * (tile_w + padding)
        y = padding + row * (tile_h + padding)
        sheet.paste(_contact_sheet_tile(frame, thumb_size, tile_background), (x, y))
        if label_height:
            label = _truncate_label(frame.label, tile_w)
            draw.text((x + 6, y + thumb_size[1] + 5), label, fill=(235, 235, 235))

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    return out


def write_frame_qc_json(report: FrameQCReport, path: str | Path) -> Path:
    out = Path(path)
    out.write_text(json.dumps(report.to_dict(), indent=2) + "\n")
    return out


def write_frame_qc_markdown(report: FrameQCReport, path: str | Path) -> Path:
    out = Path(path)
    lines = [
        "# Kino Frame QC Report",
        "",
        f"Overall: `{report.overall}`",
        f"Frames: `{len(report.frames)}`",
    ]
    if report.contact_sheet is not None:
        lines.append(f"Contact sheet: `{report.contact_sheet}`")
    lines.extend(
        [
            "",
            "| Check | Status | Frame | Expected | Observed | Message |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for check in report.checks:
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_cell(check.name),
                    f"`{check.status}`",
                    _md_cell(check.label or ""),
                    _md_cell(check.expected),
                    _md_cell(check.observed),
                    _md_cell(check.message),
                ]
            )
            + " |"
        )
    out.write_text("\n".join(lines) + "\n")
    return out


def _coerce_frames(
    frames: Iterable[FrameExpectation | tuple[str, str | Path] | str | Path],
) -> tuple[FrameExpectation, ...]:
    coerced: list[FrameExpectation] = []
    for item in frames:
        if isinstance(item, FrameExpectation):
            coerced.append(item)
        elif isinstance(item, tuple):
            label, path = item
            coerced.append(FrameExpectation(str(label), Path(path)))
        else:
            path = Path(item)
            coerced.append(FrameExpectation(path.stem, path))
    return tuple(coerced)


def _inspect_frame(
    frame: FrameExpectation,
    *,
    min_bytes: int,
    black_luma_threshold: float,
    comparison_size: tuple[int, int],
) -> tuple[list[FrameQCCheck], _FrameAnalysis | None]:
    checks: list[FrameQCCheck] = []
    if not frame.path.exists():
        return [
            FrameQCCheck(
                "missing_frame",
                "fail",
                frame.label,
                frame.path,
                "expected verification frame file",
                "missing",
                "Expected verification frame was not found.",
            )
        ], None

    size = frame.path.stat().st_size
    if size < min_bytes:
        return [
            FrameQCCheck(
                "tiny_frame_file",
                "fail",
                frame.label,
                frame.path,
                f">= {min_bytes} bytes",
                f"{size} bytes",
                "Verification frame file is empty or too small to trust.",
            )
        ], None

    try:
        with Image.open(frame.path) as image:
            rgb = image.convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        return [
            FrameQCCheck(
                "unreadable_frame",
                "fail",
                frame.label,
                frame.path,
                "readable image file",
                type(exc).__name__,
                "Verification frame could not be decoded as an image.",
            )
        ], None

    luma = ImageOps.grayscale(rgb)
    mean_luma = float(ImageStat.Stat(luma).mean[0])
    checks.append(
        FrameQCCheck(
            "frame_file",
            "pass",
            frame.label,
            frame.path,
            f"readable image >= {min_bytes} bytes",
            f"{size} bytes, {rgb.width}x{rgb.height}",
            "Verification frame exists and can be decoded.",
        )
    )
    if mean_luma <= black_luma_threshold:
        checks.append(
            FrameQCCheck(
                "near_black_frame",
                "warning",
                frame.label,
                frame.path,
                f"mean luma > {black_luma_threshold:g}",
                f"mean luma {mean_luma:.2f}",
                "Verification frame is black or near-black; review for missing visual content.",
            )
        )

    comparison = luma.resize(comparison_size, Image.Resampling.BILINEAR)
    return checks, _FrameAnalysis(frame=frame, mean_luma=mean_luma, comparison_image=comparison)


def _near_identical_checks(analyses: list[_FrameAnalysis], *, threshold: float) -> list[FrameQCCheck]:
    checks: list[FrameQCCheck] = []
    for previous, current in zip(analyses, analyses[1:]):
        rms = _rms_difference(previous.comparison_image, current.comparison_image)
        if rms <= threshold:
            checks.append(
                FrameQCCheck(
                    "near_identical_adjacent_frames",
                    "warning",
                    f"{previous.frame.label},{current.frame.label}",
                    current.frame.path,
                    f"RMS difference > {threshold:g}",
                    f"RMS difference {rms:.2f}",
                    "Adjacent verification frames are nearly identical; review for frozen frames or missed edits.",
                )
            )
    return checks


def _rms_difference(left: Image.Image, right: Image.Image) -> float:
    diff = ImageChops.difference(left, right)
    histogram = diff.histogram()
    squares = (value * ((index % 256) ** 2) for index, value in enumerate(histogram))
    return math.sqrt(sum(squares) / float(left.size[0] * left.size[1]))


def _overall_status(checks: list[FrameQCCheck]) -> FrameQCStatus:
    statuses = {check.status for check in checks}
    if "fail" in statuses:
        return "fail"
    if "warning" in statuses:
        return "warning"
    return "pass"


def _contact_sheet_tile(
    frame: FrameExpectation,
    thumb_size: tuple[int, int],
    tile_background: tuple[int, int, int],
) -> Image.Image:
    tile = Image.new("RGB", thumb_size, tile_background)
    try:
        with Image.open(frame.path) as image:
            thumb = ImageOps.contain(image.convert("RGB"), thumb_size, Image.Resampling.LANCZOS)
    except (FileNotFoundError, UnidentifiedImageError, OSError):
        draw = ImageDraw.Draw(tile)
        draw.text((12, 12), "missing/unreadable", fill=(235, 235, 235))
        return tile

    x = (thumb_size[0] - thumb.width) // 2
    y = (thumb_size[1] - thumb.height) // 2
    tile.paste(thumb, (x, y))
    return tile


def _truncate_label(label: str, width: int) -> str:
    max_chars = max(4, width // 8)
    if len(label) <= max_chars:
        return label
    return label[: max_chars - 1] + "..."


def _md_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
