from pathlib import Path

from kino.presets import get_preset
from kino.probe import AudioStream, MediaProbe, VideoStream
from kino.validation import validate_export


def valid_probe() -> MediaProbe:
    return MediaProbe(
        path="out.mp4",
        format_name="mov,mp4,m4a,3gp,3g2,mj2",
        format_tags={"major_brand": "isom"},
        duration=3.0,
        bit_rate=8_000_000,
        size_bytes=3_000_000,
        video=VideoStream("h264", 1080, 1920, 30.0, "1:1", "9:16", "yuv420p", "progressive"),
        audio=AudioStream("aac", 48000, 2, "stereo"),
    )


def test_valid_export_needs_only_faststart_manual_review():
    report = validate_export(valid_probe(), get_preset("vertical-social"))

    assert report.overall == "manual-review-required"
    assert all(check.status != "fail" for check in report.checks)


def test_dimension_mismatch_fails():
    probe = valid_probe()
    bad_probe = MediaProbe(
        path=probe.path,
        format_name=probe.format_name,
        format_tags=probe.format_tags,
        duration=probe.duration,
        bit_rate=probe.bit_rate,
        size_bytes=probe.size_bytes,
        video=VideoStream("h264", 1920, 1080, 30.0, "1:1", "16:9", "yuv420p", "progressive"),
        audio=probe.audio,
    )

    report = validate_export(bad_probe, get_preset("vertical-social"))

    assert report.overall == "fail"
    assert any(check.name == "dimensions" and check.status == "fail" for check in report.checks)


def test_container_mismatch_fails():
    probe = valid_probe()
    bad_probe = MediaProbe(
        path=probe.path,
        format_name="matroska,webm",
        format_tags={},
        duration=probe.duration,
        bit_rate=probe.bit_rate,
        size_bytes=probe.size_bytes,
        video=probe.video,
        audio=probe.audio,
    )

    report = validate_export(bad_probe, get_preset("vertical-social"))

    assert report.overall == "fail"
    assert any(check.name == "container" and check.status == "fail" for check in report.checks)


def test_mov_extension_does_not_pass_mp4_container():
    probe = valid_probe()
    bad_probe = MediaProbe(
        path="out.mov",
        format_name=probe.format_name,
        format_tags=probe.format_tags,
        duration=probe.duration,
        bit_rate=probe.bit_rate,
        size_bytes=probe.size_bytes,
        video=probe.video,
        audio=probe.audio,
    )

    report = validate_export(bad_probe, get_preset("vertical-social"))

    assert report.overall == "fail"
    assert any(check.name == "container" and check.status == "fail" for check in report.checks)


def test_below_minimum_social_frame_rate_fails():
    probe = valid_probe()
    bad_probe = MediaProbe(
        path=probe.path,
        format_name=probe.format_name,
        format_tags=probe.format_tags,
        duration=probe.duration,
        bit_rate=probe.bit_rate,
        size_bytes=probe.size_bytes,
        video=VideoStream("h264", 1080, 1920, 24.0, "1:1", "9:16", "yuv420p", "progressive"),
        audio=probe.audio,
    )

    report = validate_export(bad_probe, get_preset("vertical-social"))

    assert report.overall == "fail"
    assert any(check.name == "frame_rate" and check.status == "fail" for check in report.checks)


def test_non_420_pixel_format_fails():
    probe = valid_probe()
    bad_probe = MediaProbe(
        path=probe.path,
        format_name=probe.format_name,
        format_tags=probe.format_tags,
        duration=probe.duration,
        bit_rate=probe.bit_rate,
        size_bytes=probe.size_bytes,
        video=VideoStream("h264", 1080, 1920, 30.0, "1:1", "9:16", "yuv444p", "progressive"),
        audio=probe.audio,
    )

    report = validate_export(bad_probe, get_preset("vertical-social"))

    assert report.overall == "fail"
    assert any(check.name == "pixel_format" and check.status == "fail" for check in report.checks)


def test_audio_codec_mismatch_fails():
    probe = valid_probe()
    bad_probe = MediaProbe(
        path=probe.path,
        format_name=probe.format_name,
        format_tags=probe.format_tags,
        duration=probe.duration,
        bit_rate=probe.bit_rate,
        size_bytes=probe.size_bytes,
        video=probe.video,
        audio=AudioStream("mp3", 48000, 2, "stereo"),
    )

    report = validate_export(bad_probe, get_preset("vertical-social"))

    assert report.overall == "fail"
    assert any(check.name == "audio_codec" and check.status == "fail" for check in report.checks)


def test_audio_sample_rate_mismatch_fails():
    probe = valid_probe()
    bad_probe = MediaProbe(
        path=probe.path,
        format_name=probe.format_name,
        format_tags=probe.format_tags,
        duration=probe.duration,
        bit_rate=probe.bit_rate,
        size_bytes=probe.size_bytes,
        video=probe.video,
        audio=AudioStream("aac", 44100, 2, "stereo"),
    )

    report = validate_export(bad_probe, get_preset("vertical-social"))

    assert report.overall == "fail"
    assert any(check.name == "audio_sample_rate" and check.status == "fail" for check in report.checks)


def test_markdown_report_shape(tmp_path):
    from kino.validation import write_markdown_report

    out = write_markdown_report(validate_export(valid_probe(), get_preset("vertical-social")), tmp_path / "report.md")

    assert Path(out).read_text().startswith("# Kino Validation Report")


def test_markdown_report_escapes_table_cells(tmp_path):
    from kino.validation import ValidationCheck, ValidationReport, write_markdown_report

    report = ValidationReport(
        preset={"name": "vertical-social"},
        media={"path": "out.mp4"},
        checks=(ValidationCheck("pipe|check", "pass", "a|b", "c\nd", "ok|fine"),),
        overall="pass",
    )

    out = write_markdown_report(report, tmp_path / "report.md")
    text = Path(out).read_text()

    assert "pipe\\|check" in text
    assert "c<br>d" in text


def test_faststart_passes_when_moov_precedes_mdat(tmp_path):
    media = tmp_path / "faststart.mp4"
    media.write_bytes(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x08moov\x00\x00\x00\x08mdat")
    probe = valid_probe()
    report = validate_export(
        MediaProbe(
            path=str(media),
            format_name=probe.format_name,
            format_tags=probe.format_tags,
            duration=probe.duration,
            bit_rate=probe.bit_rate,
            size_bytes=probe.size_bytes,
            video=probe.video,
            audio=probe.audio,
        ),
        get_preset("vertical-social"),
    )

    assert report.overall == "pass"
    assert any(check.name == "faststart" and check.status == "pass" for check in report.checks)


def test_faststart_warns_when_mdat_precedes_moov(tmp_path):
    media = tmp_path / "slowstart.mp4"
    media.write_bytes(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x08mdat\x00\x00\x00\x08moov")
    probe = valid_probe()
    report = validate_export(
        MediaProbe(
            path=str(media),
            format_name=probe.format_name,
            format_tags=probe.format_tags,
            duration=probe.duration,
            bit_rate=probe.bit_rate,
            size_bytes=probe.size_bytes,
            video=probe.video,
            audio=probe.audio,
        ),
        get_preset("vertical-social"),
    )

    assert report.overall == "warning"
    assert any(check.name == "faststart" and check.status == "warning" for check in report.checks)
