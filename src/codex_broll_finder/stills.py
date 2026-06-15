from __future__ import annotations

import subprocess
from pathlib import Path

from PIL import Image, ImageFilter


def render_zoom_still(
    src_path: Path,
    out_path: Path,
    duration: float,
    *,
    rate: float = 0.015,
    fps: int = 30,
    size: tuple[int, int] = (1920, 1080),
    blurfill: bool = False,
) -> None:
    width, height = size
    source = Image.open(src_path).convert("RGB")
    base = _blurfill(source, width, height) if blurfill else _cover(source, width, height)
    frame_count = round(duration * fps)
    ffmpeg = subprocess.Popen(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{width}x{height}",
            "-r",
            str(fps),
            "-i",
            "-",
            "-an",
            "-c:v",
            "libx264",
            "-crf",
            "18",
            "-preset",
            "fast",
            "-pix_fmt",
            "yuv420p",
            str(out_path),
        ],
        stdin=subprocess.PIPE,
    )
    assert ffmpeg.stdin is not None
    for frame in range(frame_count):
        scale = 1.0 + rate * (frame / fps)
        box_w, box_h = width / scale, height / scale
        x0, y0 = (width - box_w) / 2, (height - box_h) / 2
        frame_image = base.resize((width, height), Image.Resampling.LANCZOS, box=(x0, y0, x0 + box_w, y0 + box_h))
        ffmpeg.stdin.write(frame_image.tobytes())
    ffmpeg.stdin.close()
    code = ffmpeg.wait()
    if code:
        raise RuntimeError(f"ffmpeg failed with exit code {code}")


def _cover(image: Image.Image, width: int, height: int) -> Image.Image:
    scale = max(width / image.width, height / image.height)
    resized = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
    x0 = (resized.width - width) // 2
    y0 = (resized.height - height) // 2
    return resized.crop((x0, y0, x0 + width, y0 + height))


def _blurfill(image: Image.Image, width: int, height: int) -> Image.Image:
    background = _cover(image, width, height).filter(ImageFilter.GaussianBlur(45))
    scale = min(width * 0.88 / image.width, height * 0.88 / image.height)
    foreground = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
    background.paste(foreground, ((width - foreground.width) // 2, (height - foreground.height) // 2))
    return background
