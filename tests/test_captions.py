from dataclasses import replace
from pathlib import Path

import pytest

from kino.captions import (
    CaptionError,
    KinoCaptions,
    build_render_captions_command,
    captions_to_ass,
    default_caption_style,
    plan_captions,
    render_captions,
    validate_captions_for_edit,
    wrap_caption_text,
)
from kino.edit import KinoEdit, Transcript, WordToken


def token(id_, text, start, end, confidence=None):
    return WordToken(id=id_, text=text, start=start, end=end, confidence=confidence)


def edit():
    return KinoEdit(
        id="edit001",
        transcript=Transcript(
            id="tx001",
            words=(
                token("w001", "This", 0.0, 0.2, 0.9),
                token("w002", "mistake", 0.2, 0.5, 0.8),
                token("w003", "cost", 0.5, 0.8, 0.95),
                token("w004", "a", 0.8, 0.95, 0.9),
                token("w005", "week", 0.95, 1.2, 0.9),
                token("w006", "watch", 1.2, 1.5, 0.85),
                token("w007", "the", 1.5, 1.6, 0.9),
                token("w008", "demo", 1.6, 2.0, 0.9),
                token("w009", "proof", 2.0, 2.35, 0.9),
                token("w010", "now", 2.35, 2.6, 0.9),
            ),
        ),
    )


def test_plan_captions_creates_valid_reviewable_contract():
    captions = plan_captions(edit(), archetype_id="social-short")
    data = captions.to_dict()

    assert data["schema"] == "kino.captions.v1"
    assert data["version"] == 1
    assert data["id"] == "edit001:social-short:captions"
    assert data["transcript_hash"].startswith("sha256:")
    assert data["style"]["preset"] == "social-short-bold"
    assert data["segments"]
    assert data["segments"][0]["text"] == "THIS MISTAKE COST A WEEK"
    assert data["segments"][0]["emphasized_words"] == ["mistake"]
    assert all(segment["reasons"] for segment in data["segments"])
    assert all(0 <= segment["confidence"] <= 1 for segment in data["segments"])

    loaded = KinoCaptions.from_json(captions.to_json())
    assert loaded == captions


def test_founder_caption_style_uses_longer_clean_segments():
    captions = plan_captions(edit(), archetype_id="founder-product-explainer")

    assert captions.style.preset == "founder-explainer-clean"
    assert captions.segments[0].text == "This mistake cost a week watch the demo"
    assert captions.segments[0].duration <= 4.5


def test_validate_captions_for_edit_rejects_transcript_drift():
    base = edit()
    captions = plan_captions(base, archetype_id="social-short")
    drifted = replace(
        base,
        transcript=replace(
            base.transcript,
            words=(*base.transcript.words[:-1], token("w010", "later", 2.35, 2.6)),
        ),
    )

    with pytest.raises(CaptionError, match="transcript_hash"):
        validate_captions_for_edit(captions, drifted)


def test_caption_validation_rejects_unreadable_segments():
    captions = plan_captions(edit(), archetype_id="social-short")
    bad_segment = replace(captions.segments[0], end=captions.segments[0].start + 0.05)

    with pytest.raises(CaptionError, match="too short"):
        KinoCaptions.from_dict({**captions.to_dict(), "segments": [bad_segment.to_dict()]})


def test_wrap_caption_text_respects_style_limits():
    style = default_caption_style("social-short")

    assert wrap_caption_text("THIS MISTAKE COST A WEEK", style) == ("THIS MISTAKE COST", "A WEEK")


def test_captions_to_ass_outputs_dialogue_lines():
    captions = plan_captions(edit(), archetype_id="social-short")
    ass = captions_to_ass(captions, size=(1080, 1920))

    assert "PlayResX: 1080" in ass
    assert "Style: Default" in ass
    assert "Dialogue: 0,0:00:00.00,0:00:01.20" in ass
    assert r"THIS MISTAKE COST\NA WEEK" in ass


def test_render_command_burns_ass_subtitles_and_copies_audio():
    cmd = build_render_captions_command(Path("input.mp4"), Path("captions.ass"), Path("out.mp4"))

    assert cmd[:5] == ["ffmpeg", "-y", "-v", "error", "-i"]
    assert any(part.startswith("subtitles=") for part in cmd)
    assert "-c:a" in cmd
    assert "copy" in cmd
    assert cmd[-1] == "out.mp4"


def test_render_captions_writes_ass_and_runs_ffmpeg(tmp_path, monkeypatch):
    commands = []

    def fake_run(command):
        commands.append(command)
        Path(command[-1]).write_bytes(b"video")

    monkeypatch.setattr("kino.captions.run", fake_run)
    output = render_captions(
        tmp_path / "input.mp4",
        plan_captions(edit(), archetype_id="social-short"),
        tmp_path / "captioned.mp4",
        size=(1080, 1920),
    )

    assert output == tmp_path / "captioned.mp4"
    assert (tmp_path / "captioned.ass").read_text().startswith("[Script Info]")
    assert commands
    assert commands[0][-1] == str(tmp_path / "captioned.mp4")
