from __future__ import annotations

from pathlib import Path

from .presets import ExportPreset


def build_export_command(input_path: Path, output_path: Path, preset: ExportPreset, *, crf: int = 18) -> list[str]:
    if preset.container == "mp4" and output_path.suffix.lower() != ".mp4":
        raise ValueError(f"{preset.name} exports must use an .mp4 output path")

    filters = []
    if preset.min_fps is not None:
        filters.append(f"fps={int(preset.min_fps)}")
    filters.extend(
        [
            f"scale={preset.width}:{preset.height}:force_original_aspect_ratio=increase",
            f"crop={preset.width}:{preset.height}",
            "setsar=1",
            "format=yuv420p",
        ]
    )
    vf = ",".join(filters)
    return [
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-i",
        str(input_path),
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-crf",
        str(crf),
        "-preset",
        "slow",
        "-c:a",
        "aac",
        "-ar",
        str(preset.audio_sample_rate),
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
