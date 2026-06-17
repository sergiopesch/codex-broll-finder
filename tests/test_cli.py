import json

import pytest

from kino import cli
from kino.manifest import load_manifest
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


def test_help_exposes_phase_1_commands(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])

    assert exc.value.code == 0
    out = capsys.readouterr().out
    for command in (
        "init-edit",
        "propose-beat",
        "approve-beat",
        "reject-beat",
        "compile-manifest",
        "validate-manifest",
        "render-cutaways",
        "verify-frames",
        "make-contact-sheet",
        "check-frames",
        "list-presets",
        "list-archetypes",
        "plan-replica",
        "plan-edit",
        "validate-plan",
        "apply-plan",
        "probe-media",
        "analyze-audio",
        "validate-export",
        "export-variant",
    ):
        assert command in out


def test_help_exposes_kino_plan_contract(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])

    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "validate-plan" in out
    assert "apply-plan" in out


def test_plan_edit_writes_reviewable_plan_and_validates_it(tmp_path, capsys):
    transcript = tmp_path / "transcript.json"
    edit = tmp_path / "KINO-EDIT.json"
    plan = tmp_path / "KINO-PLAN.json"
    transcript.write_text(
        json.dumps(
            {
                "id": "tx001",
                "language": "en",
                "source": "input.mp4",
                "words": [
                    {"id": "w001", "text": "This", "start": 0.0, "end": 0.2},
                    {"id": "w002", "text": "mistake", "start": 0.2, "end": 0.5},
                    {"id": "w003", "text": "cost", "start": 0.5, "end": 0.8},
                    {"id": "w004", "text": "a", "start": 0.8, "end": 0.9},
                    {"id": "w005", "text": "week", "start": 0.9, "end": 1.2},
                    {"id": "w006", "text": "watch", "start": 1.2, "end": 1.5},
                    {"id": "w007", "text": "the", "start": 1.5, "end": 1.6},
                    {"id": "w008", "text": "demo", "start": 1.6, "end": 2.0},
                    {"id": "w009", "text": "and", "start": 2.0, "end": 2.1},
                    {"id": "w010", "text": "try", "start": 2.1, "end": 2.3},
                    {"id": "w011", "text": "Kino", "start": 2.3, "end": 2.6},
                ],
            }
        )
    )

    assert cli.main(["init-edit", str(transcript), str(edit), "--id", "edit001"]) == 0
    assert cli.main(["add-source", str(edit), "src001", "generated", "fixture://ui-proof", "--title", "UI proof"]) == 0
    assert (
        cli.main(
            [
                "add-asset",
                str(edit),
                "asset001",
                "src001",
                "image",
                "assets/ui-proof.png",
                "--score",
                "0.9",
                "--notes",
                "product UI demo proof",
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert cli.main(["plan-edit", str(edit), str(plan), "--archetype", "social-short"]) == 0
    data = json.loads(capsys.readouterr().out)

    assert data["schema"] == "kino.plan.v1"
    assert data["version"] == 1
    assert data["edit_id"] == "edit001"
    assert data["archetype_id"] == "social-short"
    assert data["transcript_hash"].startswith("sha256:")
    assert data["summary"]["beat_count"] == len(data["beats"])
    assert "duration" not in json.dumps(data)
    assert data["beats"][0]["anchor"]["quote"]
    assert data["beats"][0]["confidence"] > 0
    assert data["beats"][0]["reasons"]
    assert data["beats"][0]["asset_fits"]
    assert json.loads(plan.read_text()) == data

    assert cli.main(["validate-plan", str(plan)]) == 0
    assert "ok:" in capsys.readouterr().out


def test_apply_plan_imports_proposed_beats_into_edit(tmp_path):
    transcript = tmp_path / "transcript.json"
    edit = tmp_path / "KINO-EDIT.json"
    plan = tmp_path / "KINO-PLAN.json"
    transcript.write_text(
        json.dumps(
            {
                "id": "tx001",
                "language": "en",
                "source": "input.mp4",
                "words": [
                    {"id": "w001", "text": "Kino", "start": 0.0, "end": 0.25},
                    {"id": "w002", "text": "plans", "start": 0.25, "end": 0.6},
                    {"id": "w003", "text": "better", "start": 0.6, "end": 0.9},
                    {"id": "w004", "text": "proof", "start": 0.9, "end": 1.2},
                    {"id": "w005", "text": "beats", "start": 1.2, "end": 1.5},
                ],
            }
        )
    )

    assert cli.main(["init-edit", str(transcript), str(edit), "--id", "edit001"]) == 0
    assert cli.main(["plan-edit", str(edit), str(plan), "--archetype", "founder-product-explainer"]) == 0
    assert cli.main(["apply-plan", str(plan), str(edit)]) == 0

    data = json.loads(edit.read_text())
    assert data["beats"]
    assert all(beat["status"] == "proposed" for beat in data["beats"])
    assert all(beat["selected_asset_id"] is None for beat in data["beats"])
    assert all(beat["plan_id"] == "edit001:founder-product-explainer:plan" for beat in data["beats"])
    assert all(beat["confidence"] > 0 for beat in data["beats"])
    assert all(beat["reasons"] for beat in data["beats"])


def test_edit_planning_cli_flow_compiles_manifest(tmp_path):
    transcript = tmp_path / "transcript.json"
    edit = tmp_path / "KINO-EDIT.json"
    manifest_path = tmp_path / "KINO-MANIFEST.json"
    transcript.write_text(
        """
        {
          "id": "tx001",
          "language": "en",
          "source": "input.mp4",
          "words": [
            {"id": "w001", "text": "Kino", "start": 0.0, "end": 0.25},
            {"id": "w002", "text": "plans", "start": 0.25, "end": 0.6}
          ]
        }
        """
    )

    assert cli.main(["init-edit", str(transcript), str(edit), "--id", "edit001"]) == 0
    assert cli.main(["add-source", str(edit), "src001", "url", "https://example.com", "--title", "Example"]) == 0
    assert cli.main(["add-asset", str(edit), "asset001", "src001", "web", "assets/source.png", "--credit", "Kino"]) == 0
    assert (
        cli.main(
            [
                "propose-beat",
                str(edit),
                "beat001",
                "0",
                "2",
                "--route",
                "receipt",
                "--interpretation",
                "Show the source.",
                "--source-plan",
                "Capture the source page.",
                "--source-id",
                "src001",
                "--asset-id",
                "asset001",
            ]
        )
        == 0
    )
    assert cli.main(["approve-beat", str(edit), "beat001", "asset001"]) == 0
    assert (
        cli.main(
            [
                "compile-manifest",
                str(edit),
                str(manifest_path),
                "--base",
                "input.mp4",
                "--output",
                "out.mp4",
                "--size",
                "1080x1920",
                "--fps",
                "24",
            ]
        )
        == 0
    )

    manifest = load_manifest(manifest_path)
    assert manifest.base == tmp_path / "input.mp4"
    assert manifest.output == tmp_path / "out.mp4"
    assert manifest.size == (1080, 1920)
    assert manifest.fps == 24
    assert manifest.beats[0].id == "beat001"
    assert manifest.beats[0].line == "Kino plans"
    assert manifest.beats[0].kind == "still"


def test_list_archetypes_outputs_builtin_definitions(capsys):
    assert cli.main(["list-archetypes"]) == 0
    out = capsys.readouterr().out

    assert "social-short" in out
    assert "founder-product-explainer" in out


def test_plan_replica_outputs_intent_level_beat_plan(tmp_path, capsys):
    analysis = tmp_path / "analysis.json"
    analysis.write_text(
        json.dumps(
            {
                "id": "ref-social",
                "duration": 28.0,
                "platforms": ["YouTube Shorts"],
                "aspect_ratio": "9:16",
                "pacing": "fast",
                "primary_spine": "talking head",
                "visual_signals": ["bold burned-in captions", "hard cuts"],
                "proof_signals": ["product UI"],
                "transcript_cues": [
                    {
                        "id": "cue.hook",
                        "token_start": 0,
                        "token_end": 4,
                        "text": "This is the hook.",
                        "kind": "hook",
                    },
                    {
                        "id": "cue.proof",
                        "token_start": 4,
                        "token_end": 8,
                        "text": "Here is the proof.",
                        "kind": "proof",
                    },
                ],
            }
        )
    )
    out = tmp_path / "KINO-REPLICA-PLAN.json"

    assert cli.main(["plan-replica", str(analysis), "--json-out", str(out)]) == 0
    data = json.loads(capsys.readouterr().out)

    assert data["archetype_id"] == "social-short"
    assert data["beats"][0]["role"] == "hook"
    assert json.loads(out.read_text()) == data
