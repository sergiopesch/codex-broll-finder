from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .probe import probe_media

AudioQCStatus = Literal["pass", "warning", "fail"]

_MAX_VOLUME_RE = re.compile(r"max_volume:\s*(?P<value>[-+]?(?:\d+(?:\.\d+)?|\.\d+))\s*dB")
_SILENCE_START_RE = re.compile(r"silence_start:\s*(?P<value>[-+]?(?:\d+(?:\.\d+)?|\.\d+))")
_SILENCE_END_RE = re.compile(r"silence_end:\s*(?P<end>[-+]?(?:\d+(?:\.\d+)?|\.\d+))")
_SILENCE_DURATION_RE = re.compile(r"silence_duration:\s*(?P<duration>[-+]?(?:\d+(?:\.\d+)?|\.\d+))")


@dataclass(frozen=True)
class AudioQCCheck:
    name: str
    status: AudioQCStatus
    expected: str
    observed: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "status": self.status,
            "expected": self.expected,
            "observed": self.observed,
            "message": self.message,
        }


@dataclass(frozen=True)
class VolumeStats:
    max_volume_db: float | None
    available: bool
    error: str | None = None


@dataclass(frozen=True)
class SilenceGap:
    start: float
    end: float
    duration: float


@dataclass(frozen=True)
class SilenceAnalysis:
    gaps: tuple[SilenceGap, ...]
    available: bool
    error: str | None = None


@dataclass(frozen=True)
class AudioQCReport:
    path: str
    has_audio: bool
    sample_rate: int | None
    channels: int | None
    channel_layout: str | None
    volume: VolumeStats
    silence: SilenceAnalysis
    checks: tuple[AudioQCCheck, ...]
    overall: AudioQCStatus

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "has_audio": self.has_audio,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "channel_layout": self.channel_layout,
            "volume": {
                "max_volume_db": self.volume.max_volume_db,
                "available": self.volume.available,
                "error": self.volume.error,
            },
            "silence": {
                "gaps": [
                    {"start": gap.start, "end": gap.end, "duration": gap.duration} for gap in self.silence.gaps
                ],
                "available": self.silence.available,
                "error": self.silence.error,
            },
            "checks": [
                check.to_dict() for check in self.checks
            ],
            "overall": self.overall,
        }


def inspect_audio(
    path: str | Path,
    *,
    expected_sample_rate: int | None = 48000,
    expected_channels: int | None = None,
    clipping_threshold_db: float = -0.1,
    silence_noise_db: float = -50.0,
    silence_min_duration: float = 1.0,
) -> AudioQCReport:
    media_path = Path(path)
    probe = probe_media(media_path)
    audio = probe.audio
    if audio is None:
        checks = (
            AudioQCCheck(
                "audio_stream",
                "warning",
                "audio stream",
                "none",
                "No audio stream found; this may be intentional for silent exports.",
            ),
        )
        return AudioQCReport(
            path=str(media_path),
            has_audio=False,
            sample_rate=None,
            channels=None,
            channel_layout=None,
            volume=VolumeStats(None, available=False, error="no audio stream"),
            silence=SilenceAnalysis((), available=False, error="no audio stream"),
            checks=checks,
            overall=_overall_status(checks),
        )

    volume = measure_max_volume(media_path)
    silence = detect_silence_gaps(
        media_path,
        noise_db=silence_noise_db,
        min_duration=silence_min_duration,
        media_duration=probe.duration,
    )
    checks = tuple(
        _build_checks(
            sample_rate=audio.sample_rate,
            channels=audio.channels,
            expected_sample_rate=expected_sample_rate,
            expected_channels=expected_channels,
            volume=volume,
            clipping_threshold_db=clipping_threshold_db,
            silence=silence,
            silence_min_duration=silence_min_duration,
        )
    )
    return AudioQCReport(
        path=str(media_path),
        has_audio=True,
        sample_rate=audio.sample_rate,
        channels=audio.channels,
        channel_layout=audio.channel_layout,
        volume=volume,
        silence=silence,
        checks=checks,
        overall=_overall_status(checks),
    )


def measure_max_volume(path: str | Path) -> VolumeStats:
    result = _run_ffmpeg_audio_filter(Path(path), "volumedetect")
    if result.returncode is None:
        return VolumeStats(None, available=False, error=result.error)
    if result.returncode:
        return VolumeStats(None, available=False, error=_tool_error(result))
    max_volume = parse_volumedetect_output(result.stderr)
    if max_volume is None:
        return VolumeStats(None, available=False, error="ffmpeg volumedetect did not report max_volume")
    return VolumeStats(max_volume, available=True)


def detect_silence_gaps(
    path: str | Path,
    *,
    noise_db: float = -50.0,
    min_duration: float = 1.0,
    media_duration: float | None = None,
) -> SilenceAnalysis:
    result = _run_ffmpeg_audio_filter(
        Path(path),
        f"silencedetect=noise={_format_db(noise_db)}:d={min_duration:g}",
    )
    if result.returncode is None:
        return SilenceAnalysis((), available=False, error=result.error)
    if result.returncode:
        return SilenceAnalysis((), available=False, error=_tool_error(result))
    return SilenceAnalysis(parse_silencedetect_output(result.stderr, media_duration=media_duration), available=True)


def parse_volumedetect_output(output: str) -> float | None:
    match = _MAX_VOLUME_RE.search(output)
    if match is None:
        return None
    return float(match.group("value"))


def parse_silencedetect_output(output: str, *, media_duration: float | None = None) -> tuple[SilenceGap, ...]:
    gaps: list[SilenceGap] = []
    current_start: float | None = None
    for line in output.splitlines():
        start_match = _SILENCE_START_RE.search(line)
        if start_match:
            current_start = float(start_match.group("value"))
            continue

        end_match = _SILENCE_END_RE.search(line)
        if end_match is None:
            continue
        end = float(end_match.group("end"))
        duration_match = _SILENCE_DURATION_RE.search(line)
        duration = float(duration_match.group("duration")) if duration_match else None
        start = current_start if current_start is not None else end - (duration or 0.0)
        gaps.append(_silence_gap(start, end, duration))
        current_start = None

    if current_start is not None and media_duration is not None and media_duration > current_start:
        gaps.append(_silence_gap(current_start, media_duration, media_duration - current_start))
    return tuple(gaps)


def write_audio_qc_json(report: AudioQCReport, path: str | Path) -> Path:
    out = Path(path)
    out.write_text(json.dumps(report.to_dict(), indent=2) + "\n")
    return out


def write_audio_qc_markdown(report: AudioQCReport, path: str | Path) -> Path:
    out = Path(path)
    lines = [
        "# Kino Audio QC Report",
        "",
        f"Overall: `{report.overall}`",
        f"Media: `{report.path}`",
        f"Audio stream: `{'present' if report.has_audio else 'missing'}`",
        f"Sample rate: `{report.sample_rate}`",
        f"Channels: `{report.channels}`",
        f"Max volume: `{report.volume.max_volume_db}`",
        f"Silence gaps: `{len(report.silence.gaps)}`",
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


@dataclass(frozen=True)
class _FFmpegResult:
    returncode: int | None
    stdout: str
    stderr: str
    error: str | None = None


def _run_ffmpeg_audio_filter(path: Path, audio_filter: str) -> _FFmpegResult:
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-nostats",
                "-i",
                str(path),
                "-map",
                "0:a:0",
                "-af",
                audio_filter,
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return _FFmpegResult(None, "", "", "ffmpeg not found")
    return _FFmpegResult(result.returncode, result.stdout, result.stderr)


def _build_checks(
    *,
    sample_rate: int | None,
    channels: int | None,
    expected_sample_rate: int | None,
    expected_channels: int | None,
    volume: VolumeStats,
    clipping_threshold_db: float,
    silence: SilenceAnalysis,
    silence_min_duration: float,
) -> list[AudioQCCheck]:
    checks = [
        AudioQCCheck("audio_stream", "pass", "audio stream", "present", "Audio stream found."),
        _presence_check("audio_sample_rate", sample_rate, "sample rate"),
        _presence_check("audio_channels", channels, "channel count"),
    ]
    if expected_sample_rate is not None:
        checks.append(
            _status(
                "audio_sample_rate_expected",
                sample_rate == expected_sample_rate,
                f"{expected_sample_rate} Hz",
                f"{sample_rate} Hz" if sample_rate is not None else "unknown",
                "Audio sample rate matches expected rate.",
                "Audio sample rate does not match expected rate.",
            )
        )
    if expected_channels is not None:
        checks.append(
            _status(
                "audio_channels_expected",
                channels == expected_channels,
                str(expected_channels),
                str(channels) if channels is not None else "unknown",
                "Audio channel count matches expected count.",
                "Audio channel count does not match expected count.",
            )
        )
    checks.append(_volume_check(volume, clipping_threshold_db))
    checks.append(_silence_check(silence, silence_min_duration))
    return checks


def _presence_check(name: str, value: int | None, label: str) -> AudioQCCheck:
    return _status(
        name,
        value is not None,
        label,
        str(value) if value is not None else "unknown",
        f"Audio {label} is available.",
        f"Audio {label} is missing from probe metadata.",
    )


def _volume_check(volume: VolumeStats, clipping_threshold_db: float) -> AudioQCCheck:
    if not volume.available:
        return AudioQCCheck(
            "audio_max_volume",
            "warning",
            f"< {clipping_threshold_db:g} dB",
            "unavailable",
            f"Could not measure max volume: {volume.error}",
        )
    observed = f"{volume.max_volume_db:g} dB"
    return _status(
        "audio_max_volume",
        volume.max_volume_db is not None and volume.max_volume_db < clipping_threshold_db,
        f"< {clipping_threshold_db:g} dB",
        observed,
        "Max volume is below the clipping-risk threshold.",
        "Max volume is at or above the clipping-risk threshold.",
        warning=True,
    )


def _silence_check(silence: SilenceAnalysis, silence_min_duration: float) -> AudioQCCheck:
    if not silence.available:
        return AudioQCCheck(
            "audio_silence_gaps",
            "warning",
            f"no gaps >= {silence_min_duration:g}s",
            "unavailable",
            f"Could not run silence detection: {silence.error}",
        )
    if not silence.gaps:
        return AudioQCCheck(
            "audio_silence_gaps",
            "pass",
            f"no gaps >= {silence_min_duration:g}s",
            "none",
            "No silence gaps detected.",
        )
    return AudioQCCheck(
        "audio_silence_gaps",
        "warning",
        f"no gaps >= {silence_min_duration:g}s",
        str(len(silence.gaps)),
        "Silence gaps detected; review whether they are intentional.",
    )


def _status(
    name: str,
    passed: bool,
    expected: str,
    observed: str,
    pass_message: str,
    fail_message: str,
    *,
    warning: bool = False,
) -> AudioQCCheck:
    if passed:
        return AudioQCCheck(name, "pass", expected, observed, pass_message)
    return AudioQCCheck(name, "warning" if warning else "fail", expected, observed, fail_message)


def _overall_status(checks: tuple[AudioQCCheck, ...]) -> AudioQCStatus:
    statuses = {check.status for check in checks}
    if "fail" in statuses:
        return "fail"
    if "warning" in statuses:
        return "warning"
    return "pass"


def _tool_error(result: _FFmpegResult) -> str:
    return (result.stderr.strip() or result.stdout.strip() or "ffmpeg audio analysis failed")[-1600:]


def _format_db(value: float) -> str:
    return f"{value:g}dB"


def _silence_gap(start: float, end: float, duration: float | None) -> SilenceGap:
    resolved_duration = duration if duration is not None else end - start
    return SilenceGap(round(start, 6), round(end, 6), round(resolved_duration, 6))


def _md_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
