from __future__ import annotations

import subprocess
from pathlib import Path

from kino.audio_qc import (
    detect_silence_gaps,
    inspect_audio,
    measure_max_volume,
    parse_silencedetect_output,
    parse_volumedetect_output,
    write_audio_qc_json,
    write_audio_qc_markdown,
)
from kino.probe import AudioStream, MediaProbe, VideoStream


def _probe(audio: AudioStream | None = AudioStream("aac", 48000, 2, "stereo")) -> MediaProbe:
    return MediaProbe(
        path="out.mp4",
        format_name="mov,mp4,m4a,3gp,3g2,mj2",
        format_tags={"major_brand": "isom"},
        duration=8.0,
        bit_rate=8_000_000,
        size_bytes=3_000_000,
        video=VideoStream("h264", 1080, 1920, 30.0, "1:1", "9:16", "yuv420p", "progressive"),
        audio=audio,
    )


def test_parse_volumedetect_output_extracts_max_volume():
    output = """
    [Parsed_volumedetect_0 @ 0x123] mean_volume: -21.1 dB
    [Parsed_volumedetect_0 @ 0x123] max_volume: -0.2 dB
    """

    assert parse_volumedetect_output(output) == -0.2
    assert parse_volumedetect_output("no volume here") is None


def test_parse_silencedetect_output_extracts_gaps_and_tail_gap():
    output = """
    [silencedetect @ 0x123] silence_start: 1.5
    [silencedetect @ 0x123] silence_end: 3 | silence_duration: 1.5
    [silencedetect @ 0x123] silence_start: 6.25
    """

    gaps = parse_silencedetect_output(output, media_duration=8.0)

    assert len(gaps) == 2
    assert gaps[0].start == 1.5
    assert gaps[0].end == 3.0
    assert gaps[0].duration == 1.5
    assert gaps[1].start == 6.25
    assert gaps[1].end == 8.0
    assert gaps[1].duration == 1.75


def test_measure_max_volume_reports_unavailable_when_ffmpeg_is_missing(monkeypatch):
    def missing_ffmpeg(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr("kino.audio_qc.subprocess.run", missing_ffmpeg)

    volume = measure_max_volume("out.mp4")

    assert volume.available is False
    assert volume.max_volume_db is None
    assert volume.error == "ffmpeg not found"


def test_detect_silence_gaps_builds_silencedetect_command(monkeypatch):
    commands: list[list[str]] = []

    def fake_run(command: list[str], **kwargs):
        commands.append(command)
        stderr = "[silencedetect @ 0x123] silence_start: 1\n[silencedetect @ 0x123] silence_end: 2 | silence_duration: 1\n"
        return subprocess.CompletedProcess(command, 0, "", stderr)

    monkeypatch.setattr("kino.audio_qc.subprocess.run", fake_run)

    silence = detect_silence_gaps("out.mp4", noise_db=-45, min_duration=0.75)

    assert silence.available is True
    assert len(silence.gaps) == 1
    assert commands[0][0] == "ffmpeg"
    assert commands[0][commands[0].index("-map") + 1] == "0:a:0"
    assert "silencedetect=noise=-45dB:d=0.75" in commands[0]


def test_inspect_audio_is_graceful_without_audio(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("ffmpeg should not be called without an audio stream")

    monkeypatch.setattr("kino.audio_qc.probe_media", lambda path: _probe(audio=None))
    monkeypatch.setattr("kino.audio_qc.subprocess.run", fail_if_called)

    report = inspect_audio(Path("silent.mp4"))

    assert report.has_audio is False
    assert report.overall == "warning"
    assert report.volume.available is False
    assert report.silence.available is False
    assert report.to_dict()["checks"][0]["name"] == "audio_stream"


def test_inspect_audio_reports_probe_metadata_volume_and_silence(monkeypatch):
    def fake_run(command: list[str], **kwargs):
        if "volumedetect" in command:
            return subprocess.CompletedProcess(
                command,
                0,
                "",
                "[Parsed_volumedetect_0 @ 0x123] max_volume: -0.2 dB\n",
            )
        if any(part.startswith("silencedetect=") for part in command):
            return subprocess.CompletedProcess(
                command,
                0,
                "",
                "[silencedetect @ 0x123] silence_start: 2\n"
                "[silencedetect @ 0x123] silence_end: 3.5 | silence_duration: 1.5\n",
            )
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr("kino.audio_qc.probe_media", lambda path: _probe())
    monkeypatch.setattr("kino.audio_qc.subprocess.run", fake_run)

    report = inspect_audio("out.mp4", expected_sample_rate=48000, expected_channels=2)

    assert report.has_audio is True
    assert report.sample_rate == 48000
    assert report.channels == 2
    assert report.volume.max_volume_db == -0.2
    assert report.silence.gaps[0].duration == 1.5
    assert report.overall == "warning"
    assert any(check.name == "audio_channels_expected" and check.status == "pass" for check in report.checks)


def test_inspect_audio_fails_expected_sample_rate_and_channels(monkeypatch):
    monkeypatch.setattr("kino.audio_qc.probe_media", lambda path: _probe(AudioStream("aac", 44100, 1, "mono")))
    monkeypatch.setattr(
        "kino.audio_qc.subprocess.run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 0, "", ""),
    )

    report = inspect_audio("out.mp4", expected_sample_rate=48000, expected_channels=2)

    assert report.overall == "fail"
    assert any(check.name == "audio_sample_rate_expected" and check.status == "fail" for check in report.checks)
    assert any(check.name == "audio_channels_expected" and check.status == "fail" for check in report.checks)


def test_audio_qc_writers_emit_json_and_markdown(tmp_path, monkeypatch):
    monkeypatch.setattr("kino.audio_qc.probe_media", lambda path: _probe())
    monkeypatch.setattr(
        "kino.audio_qc.subprocess.run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command,
            0,
            "",
            "[Parsed_volumedetect_0 @ 0x123] max_volume: -6.0 dB\n",
        ),
    )

    report = inspect_audio("out.mp4")

    json_out = write_audio_qc_json(report, tmp_path / "KINO-AUDIO-QC.json")
    md_out = write_audio_qc_markdown(report, tmp_path / "KINO-AUDIO-QC.md")

    assert '"overall": "pass"' in json_out.read_text()
    assert "# Kino Audio QC Report" in md_out.read_text()
