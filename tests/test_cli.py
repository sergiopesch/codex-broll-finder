from kino import cli
from kino.probe import AudioStream, MediaProbe, VideoStream


def _probe() -> MediaProbe:
    return MediaProbe(
        path="missing.mp4",
        format_name="mov,mp4,m4a,3gp,3g2,mj2",
        format_tags={"major_brand": "isom"},
        duration=3.0,
        bit_rate=8_000_000,
        size_bytes=3_000_000,
        video=VideoStream("h264", 1080, 1920, 30.0, "1:1", "9:16", "yuv420p", "progressive"),
        audio=AudioStream("aac", 48000, 2, "stereo"),
    )


def test_validate_export_allows_manual_review_by_default(monkeypatch, capsys):
    from kino import probe

    monkeypatch.setattr(probe, "probe_media", lambda _: _probe())

    assert cli.main(["validate-export", "missing.mp4"]) == 0
    assert '"overall": "manual-review-required"' in capsys.readouterr().out


def test_validate_export_strict_fails_manual_review(monkeypatch):
    from kino import probe

    monkeypatch.setattr(probe, "probe_media", lambda _: _probe())

    assert cli.main(["validate-export", "missing.mp4", "--strict"]) == 1
