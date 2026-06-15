from __future__ import annotations

from dataclasses import asdict, dataclass
from fractions import Fraction


@dataclass(frozen=True)
class ExportPreset:
    name: str
    width: int
    height: int
    ratio: str
    container: str
    video_codec: str
    audio_codec: str
    audio_sample_rate: int
    min_fps: float | None
    notes: str

    @property
    def dimensions(self) -> tuple[int, int]:
        return self.width, self.height

    @property
    def aspect_fraction(self) -> Fraction:
        left, right = self.ratio.split(":")
        return Fraction(int(left), int(right))

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


PRESETS: dict[str, ExportPreset] = {
    "vertical-social": ExportPreset(
        name="vertical-social",
        width=1080,
        height=1920,
        ratio="9:16",
        container="mp4",
        video_codec="h264",
        audio_codec="aac",
        audio_sample_rate=48000,
        min_fps=30.0,
        notes="Default vertical export for Shorts, Reels, and TikTok-style delivery.",
    ),
    "square-social": ExportPreset(
        name="square-social",
        width=1080,
        height=1080,
        ratio="1:1",
        container="mp4",
        video_codec="h264",
        audio_codec="aac",
        audio_sample_rate=48000,
        min_fps=30.0,
        notes="Square feed-compatible export.",
    ),
    "portrait-feed": ExportPreset(
        name="portrait-feed",
        width=1080,
        height=1350,
        ratio="4:5",
        container="mp4",
        video_codec="h264",
        audio_codec="aac",
        audio_sample_rate=48000,
        min_fps=30.0,
        notes="Tall feed export for LinkedIn and Meta-style feeds.",
    ),
    "landscape-web": ExportPreset(
        name="landscape-web",
        width=1920,
        height=1080,
        ratio="16:9",
        container="mp4",
        video_codec="h264",
        audio_codec="aac",
        audio_sample_rate=48000,
        min_fps=None,
        notes="Standard 16:9 web and YouTube-style export.",
    ),
}


def get_preset(name: str) -> ExportPreset:
    try:
        return PRESETS[name]
    except KeyError as exc:
        available = ", ".join(sorted(PRESETS))
        raise KeyError(f"unknown export preset {name!r}; available: {available}") from exc


def preset_names() -> list[str]:
    return sorted(PRESETS)
