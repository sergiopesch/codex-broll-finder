from pathlib import Path

from codex_broll_finder.probe import parse_ffprobe_json, parse_frame_rate


def test_parse_frame_rate():
    assert parse_frame_rate("30000/1001") == 29.97
    assert parse_frame_rate("30/1") == 30.0
    assert parse_frame_rate("0/0") is None
    assert parse_frame_rate("N/A") is None


def test_parse_ffprobe_json():
    probe = parse_ffprobe_json(
        {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1080,
                    "height": 1920,
                    "avg_frame_rate": "30/1",
                    "sample_aspect_ratio": "1:1",
                    "display_aspect_ratio": "9:16",
                    "pix_fmt": "yuv420p",
                    "field_order": "progressive",
                },
                {
                    "codec_type": "audio",
                    "codec_name": "aac",
                    "sample_rate": "48000",
                    "channels": 2,
                    "channel_layout": "stereo",
                },
            ],
            "format": {
                "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
                "duration": "3.0",
                "bit_rate": "8000000",
                "tags": {"major_brand": "isom"},
            },
        },
        Path("out.mp4"),
    )

    assert probe.video is not None
    assert probe.video.height == 1920
    assert probe.audio is not None
    assert probe.audio.sample_rate == 48000
    assert probe.format_tags["major_brand"] == "isom"


def test_parse_ffprobe_json_tolerates_na_numeric_values():
    probe = parse_ffprobe_json(
        {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": "N/A",
                    "height": 1920,
                    "avg_frame_rate": "N/A",
                }
            ],
            "format": {"format_name": "mov,mp4,m4a,3gp,3g2,mj2", "duration": "N/A", "bit_rate": "N/A"},
        },
        Path("out.mp4"),
    )

    assert probe.duration is None
    assert probe.bit_rate is None
    assert probe.video is not None
    assert probe.video.width is None
    assert probe.video.avg_frame_rate is None
