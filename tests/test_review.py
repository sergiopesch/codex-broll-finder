from __future__ import annotations

from types import SimpleNamespace

import pytest

from kino.audio_qc import AudioQCCheck
from kino.probe import AudioStream, MediaProbe, VideoStream
from kino.review import (
    KinoReview,
    ReviewError,
    review_media,
    sample_review_frames,
    write_review_json,
    write_review_markdown,
)
from kino.validation import ValidationCheck


def _probe(width: int = 1080, height: int = 1920, duration: float = 8.0) -> MediaProbe:
    return MediaProbe(
        path="out.mp4",
        format_name="mov,mp4,m4a,3gp,3g2,mj2",
        format_tags={"major_brand": "isom"},
        duration=duration,
        bit_rate=8_000_000,
        size_bytes=3_000_000,
        video=VideoStream("h264", width, height, 30.0, "1:1", "9:16", "yuv420p", "progressive"),
        audio=AudioStream("aac", 48000, 2, "stereo"),
    )


def test_review_media_aggregates_probe_audio_export_and_archetype(monkeypatch):
    monkeypatch.setattr("kino.review.probe_media", lambda path: _probe())
    monkeypatch.setattr(
        "kino.review.inspect_audio",
        lambda *args, **kwargs: SimpleNamespace(
            overall="pass",
            checks=(AudioQCCheck("audio_stream", "pass", "audio stream", "present", "Audio stream found."),),
        ),
    )
    monkeypatch.setattr(
        "kino.review.validate_export",
        lambda *args, **kwargs: SimpleNamespace(
            overall="pass",
            checks=(ValidationCheck("dimensions", "pass", "1080x1920", "1080x1920", "Video dimensions match preset."),),
        ),
    )

    report = review_media("out.mp4", preset="vertical-social", archetype_id="social-short")

    assert report.schema == "kino.review.v1"
    assert report.overall == "warning"
    assert any(check.name == "video_stream" and check.status == "pass" for check in report.checks)
    assert any(check.name == "social_short_captions" and check.status == "warning" for check in report.checks)
    assert any(artifact.kind == "audio-qc" for artifact in report.artifacts)
    assert any(artifact.kind == "export-validation" for artifact in report.artifacts)


def test_review_media_fails_caption_timing_past_media_duration(tmp_path, monkeypatch):
    captions = tmp_path / "KINO-CAPTIONS.json"
    captions.write_text(
        """
        {
          "version": 1,
          "schema": "kino.captions.v1",
          "id": "cap001",
          "edit_id": "edit001",
          "transcript_id": "tx001",
          "transcript_hash": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
          "archetype_id": "social-short",
          "style": {
            "preset": "social-short-bold",
            "font": "Arial",
            "font_size": 64,
            "alignment": 2,
            "margin_v": 150,
            "max_chars_per_line": 18,
            "max_lines": 2,
            "uppercase": true
          },
          "segments": [
            {
              "id": "cap:001",
              "anchor": {"token_start": 0, "token_end": 1, "word_start_id": "w001", "word_end_id": "w001"},
              "start": 0.0,
              "end": 3.0,
              "text": "HELLO",
              "emphasized_words": [],
              "confidence": 0.9,
              "reasons": ["fixture"]
            }
          ]
        }
        """
    )
    monkeypatch.setattr("kino.review.probe_media", lambda path: _probe(duration=1.0))
    monkeypatch.setattr(
        "kino.review.inspect_audio",
        lambda *args, **kwargs: SimpleNamespace(
            overall="pass",
            checks=(AudioQCCheck("audio_stream", "pass", "audio stream", "present", "Audio stream found."),),
        ),
    )

    report = review_media("out.mp4", captions_path=captions, archetype_id="social-short")

    assert report.overall == "fail"
    assert any(check.name == "caption_timing_bounds" and check.status == "fail" for check in report.checks)


def test_sample_review_frames_builds_evenly_spaced_ffmpeg_commands(tmp_path, monkeypatch):
    commands: list[list[str]] = []
    monkeypatch.setattr("kino.review.run", lambda command: commands.append(command))

    labels = sample_review_frames("out.mp4", tmp_path / "frames", duration=10.0, sample_count=3)

    assert labels == ("review-01", "review-02", "review-03")
    assert [command[command.index("-ss") + 1] for command in commands] == ["0", "4.975", "9.95"]
    assert commands[-1][-1] == str(tmp_path / "frames" / "review-03.jpg")


def test_review_writers_emit_roundtrippable_json_and_markdown(tmp_path, monkeypatch):
    monkeypatch.setattr("kino.review.probe_media", lambda path: _probe())
    monkeypatch.setattr(
        "kino.review.inspect_audio",
        lambda *args, **kwargs: SimpleNamespace(
            overall="pass",
            checks=(AudioQCCheck("audio_stream", "pass", "audio stream", "present", "Audio stream found."),),
        ),
    )

    report = review_media("out.mp4", review_id="review001")
    json_out = write_review_json(report, tmp_path / "KINO-REVIEW.json")
    md_out = write_review_markdown(report, tmp_path / "KINO-REVIEW.md")

    assert KinoReview.from_json(json_out.read_text()) == report
    assert md_out.read_text().startswith("# Kino Media Review")


def test_review_validation_rejects_mismatched_overall(monkeypatch):
    monkeypatch.setattr("kino.review.probe_media", lambda path: _probe())
    monkeypatch.setattr(
        "kino.review.inspect_audio",
        lambda *args, **kwargs: SimpleNamespace(
            overall="pass",
            checks=(AudioQCCheck("audio_stream", "pass", "audio stream", "present", "Audio stream found."),),
        ),
    )
    report = review_media("out.mp4")
    data = report.to_dict()
    data["overall"] = "fail"

    with pytest.raises(ReviewError, match="overall does not match"):
        KinoReview.from_dict(data)
