from __future__ import annotations

import subprocess
from pathlib import Path

from .manifest import Beat, Manifest
from .receipt import beat_asset_timing_hash, build_render_receipt, write_render_receipt


class ToolError(RuntimeError):
    pass


def run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode:
        detail = result.stderr[-1600:] or result.stdout[-1600:]
        raise ToolError(detail.strip() or f"command failed: {' '.join(cmd)}")


def ffprobe_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise ToolError(result.stderr.strip())
    return float(result.stdout.strip())


def video_filter(width: int, height: int, fps: int) -> str:
    return (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},setsar=1,fps={fps},format=yuv420p"
    )


def format_clip_args(beat: Beat, out: Path, vf: str) -> list[str]:
    if beat.kind == "still":
        return [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-loop",
            "1",
            "-t",
            str(beat.duration),
            "-i",
            str(beat.asset),
            "-vf",
            vf,
            "-an",
            "-c:v",
            "libx264",
            "-crf",
            "18",
            "-preset",
            "fast",
            str(out),
        ]
    return [
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-ss",
        str(beat.source_in),
        "-t",
        str(beat.duration),
        "-i",
        str(beat.asset),
        "-vf",
        vf,
        "-an",
        "-c:v",
        "libx264",
        "-crf",
        "18",
        "-preset",
        "fast",
        str(out),
    ]


def build_render_command(manifest: Manifest, formatted: list[Path], end: float) -> list[str]:
    vf = video_filter(*manifest.size, manifest.fps)
    inputs = ["-i", str(manifest.base)]
    for path in formatted:
        inputs.extend(["-i", str(path)])

    graph: list[str] = []
    parts: list[str] = []
    last = 0.0
    segment = 0
    for index, beat in enumerate(manifest.beats):
        if beat.start > last:
            graph.append(f"[0:v]trim=start={last}:end={beat.start},setpts=PTS-STARTPTS,{vf}[g{segment}]")
            parts.append(f"[g{segment}]")
            segment += 1
        graph.append(f"[{index + 1}:v]setpts=PTS-STARTPTS[c{index}]")
        parts.append(f"[c{index}]")
        last = beat.end

    if last < end:
        graph.append(f"[0:v]trim=start={last}:end={end},setpts=PTS-STARTPTS,{vf}[g{segment}]")
        parts.append(f"[g{segment}]")

    graph.append("".join(parts) + f"concat=n={len(parts)}:v=1:a=0[v]")
    graph.append(f"[0:a]atrim=start=0:end={end},asetpts=PTS-STARTPTS[a]")

    return [
        "ffmpeg",
        "-y",
        "-v",
        "error",
        *inputs,
        "-filter_complex",
        ";".join(graph),
        "-map",
        "[v]",
        "-map",
        "[a]",
        "-c:v",
        "libx264",
        "-crf",
        "18",
        "-preset",
        "fast",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(manifest.output),
    ]


def formatted_clip_path(beat: Beat, fmt_dir: Path, vf: str) -> Path:
    return fmt_dir / f"{beat.id}-{beat_asset_timing_hash(beat, vf)}.mp4"


def render_cutaways(manifest: Manifest, fmt_dir: Path | None = None) -> Path:
    fmt_dir = fmt_dir or manifest.path.parent / "assets" / "fmt"
    fmt_dir.mkdir(parents=True, exist_ok=True)
    vf = video_filter(*manifest.size, manifest.fps)

    formatted: list[Path] = []
    formatted_commands: list[list[str]] = []
    for beat in manifest.beats:
        out = formatted_clip_path(beat, fmt_dir, vf)
        formatted.append(out)
        if not out.exists():
            command = format_clip_args(beat, out, vf)
            formatted_commands.append(command)
            run(command)

    end = ffprobe_duration(manifest.base)
    command = build_render_command(manifest, formatted, end)
    run(command)
    write_render_receipt(
        build_render_receipt(
            manifest,
            command,
            formatted,
            base_duration=end,
            formatted_commands=formatted_commands,
        ),
        manifest.path.parent,
    )
    return manifest.output


def verification_times(manifest: Manifest) -> list[tuple[str, float]]:
    times: list[tuple[str, float]] = []
    previous: Beat | None = None
    for beat in manifest.beats:
        times.append((f"{beat.id}-start", beat.start))
        times.append((f"{beat.id}-mid", round((beat.start + beat.end) / 2, 3)))
        times.append((f"{beat.id}-end", beat.end))
        if previous and abs(previous.end - beat.start) < 0.05:
            times.append((f"{previous.id}-{beat.id}-joint", beat.start))
        previous = beat
    return times


def extract_verify_frames(manifest: Manifest, source: Path | None = None, out_dir: Path | None = None) -> Path:
    source = source or manifest.output
    out_dir = out_dir or manifest.path.parent / "verify_frames"
    out_dir.mkdir(parents=True, exist_ok=True)
    for label, when in verification_times(manifest):
        run(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-ss",
                str(when),
                "-i",
                str(source),
                "-frames:v",
                "1",
                str(out_dir / f"{label}.jpg"),
            ]
        )
    return out_dir
