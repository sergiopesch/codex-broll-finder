from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from .manifest import load_manifest
from .presets import PRESETS, get_preset


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kino")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate-manifest", help="Parse and validate KINO-MANIFEST.json")
    validate.add_argument("manifest")

    init_edit = sub.add_parser("init-edit", help="Create KINO-EDIT.json from transcript JSON")
    init_edit.add_argument("transcript")
    init_edit.add_argument("output")
    init_edit.add_argument("--id", dest="edit_id")

    add_source = sub.add_parser("add-source", help="Add a source receipt entry to KINO-EDIT.json")
    add_source.add_argument("edit")
    add_source.add_argument("id")
    add_source.add_argument("kind", choices=["url", "file", "capture", "user", "generated", "other"])
    add_source.add_argument("locator")
    add_source.add_argument("--title")
    add_source.add_argument("--author")
    add_source.add_argument("--publisher")
    add_source.add_argument("--license")
    add_source.add_argument("--captured-at")
    add_source.add_argument("--notes")
    add_source.add_argument("--out")

    add_asset = sub.add_parser("add-asset", help="Add an asset candidate entry to KINO-EDIT.json")
    add_asset.add_argument("edit")
    add_asset.add_argument("id")
    add_asset.add_argument("source_id")
    add_asset.add_argument("kind", choices=["video", "still", "image", "web", "audio", "document", "other"])
    add_asset.add_argument("uri")
    add_asset.add_argument("--start", type=float)
    add_asset.add_argument("--end", type=float)
    add_asset.add_argument("--width", type=int)
    add_asset.add_argument("--height", type=int)
    add_asset.add_argument("--score", type=float)
    add_asset.add_argument("--credit")
    add_asset.add_argument("--notes")
    add_asset.add_argument("--out")

    propose = sub.add_parser("propose-beat", help="Add a proposed beat candidate to KINO-EDIT.json")
    propose.add_argument("edit")
    propose.add_argument("id")
    propose.add_argument("token_start", type=int)
    propose.add_argument("token_end", type=int)
    propose.add_argument("--route", required=True)
    propose.add_argument("--interpretation", required=True)
    propose.add_argument("--source-plan", required=True)
    propose.add_argument("--fallback")
    propose.add_argument("--source-id", action="append", default=[])
    propose.add_argument("--asset-id", action="append", default=[])
    propose.add_argument("--out")

    approve = sub.add_parser("approve-beat", help="Approve a proposed beat with a selected asset")
    approve.add_argument("edit")
    approve.add_argument("beat_id")
    approve.add_argument("asset_id")
    approve.add_argument("--out")

    reject = sub.add_parser("reject-beat", help="Reject a proposed beat while preserving the reason")
    reject.add_argument("edit")
    reject.add_argument("beat_id")
    reject.add_argument("reason")
    reject.add_argument("--out")

    compile_manifest = sub.add_parser("compile-manifest", help="Compile approved KINO-EDIT beats to KINO-MANIFEST.json")
    compile_manifest.add_argument("edit")
    compile_manifest.add_argument("manifest")
    compile_manifest.add_argument("--base", required=True)
    compile_manifest.add_argument("--output", default="output_with_kino.mp4")
    compile_manifest.add_argument("--size", default="1920x1080")
    compile_manifest.add_argument("--fps", type=int, default=30)

    zoom = sub.add_parser("zoom-still", help="Render a smooth sub-pixel still zoom")
    zoom.add_argument("input")
    zoom.add_argument("output")
    zoom.add_argument("duration", type=float)
    zoom.add_argument("--rate", type=float, default=0.015)
    zoom.add_argument("--fps", type=int, default=30)
    zoom.add_argument("--size", default="1920x1080")
    zoom.add_argument("--blurfill", action="store_true")

    capture = sub.add_parser("capture-page", help="Capture a page with headless Chrome/Chromium")
    capture.add_argument("url")
    capture.add_argument("output")
    capture.add_argument("--chrome")
    capture.add_argument("--wait", type=float, default=7.0)
    capture.add_argument("--scale", type=int, default=1)
    capture.add_argument("--size", default="1920x1080")

    render = sub.add_parser("render-cutaways", help="Render b-roll over a base video using a manifest")
    render.add_argument("manifest")

    frames = sub.add_parser("verify-frames", help="Extract midpoint and joint frames for visual inspection")
    frames.add_argument("manifest")
    frames.add_argument("--source")
    frames.add_argument("--out-dir")

    presets = sub.add_parser("list-presets", help="List built-in social export presets")
    presets.add_argument("--json", action="store_true")

    probe = sub.add_parser("probe-media", help="Probe media streams with ffprobe and print JSON")
    probe.add_argument("input")

    validate_export = sub.add_parser("validate-export", help="Validate an export against a preset")
    validate_export.add_argument("input")
    validate_export.add_argument("--preset", default="vertical-social", choices=sorted(PRESETS))
    validate_export.add_argument("--json-out")
    validate_export.add_argument("--md-out")
    validate_export.add_argument("--strict", action="store_true", help="Return nonzero unless every check passes")

    export = sub.add_parser("export-variant", help="Export a platform variant with ffmpeg")
    export.add_argument("input")
    export.add_argument("output")
    export.add_argument("--preset", default="vertical-social", choices=sorted(PRESETS))
    export.add_argument("--crf", type=int, default=18)

    args = parser.parse_args(argv)

    if args.command == "validate-manifest":
        manifest = load_manifest(args.manifest)
        print(f"ok: {len(manifest.beats)} beats")
        return 0

    if args.command == "init-edit":
        from .edit import write_edit_json
        from .planning import load_edit_from_transcript_json

        edit = load_edit_from_transcript_json(args.transcript, edit_id=args.edit_id)
        out = write_edit_json(edit, args.output)
        print(f"done: {out}")
        return 0

    if args.command == "add-source":
        from dataclasses import replace

        from .edit import SourceReceipt, load_edit, validate_edit, write_edit_json

        edit = load_edit(args.edit)
        updated = replace(
            edit,
            sources=(
                *edit.sources,
                SourceReceipt(
                    id=args.id,
                    kind=args.kind,
                    locator=args.locator,
                    title=args.title,
                    author=args.author,
                    publisher=args.publisher,
                    license=args.license,
                    captured_at=args.captured_at,
                    notes=args.notes,
                ),
            ),
        )
        validate_edit(updated)
        out = write_edit_json(updated, _edit_out_path(args.edit, args.out))
        print(f"done: {out}")
        return 0

    if args.command == "add-asset":
        from dataclasses import replace

        from .edit import AssetCandidate, load_edit, validate_edit, write_edit_json

        edit = load_edit(args.edit)
        updated = replace(
            edit,
            assets=(
                *edit.assets,
                AssetCandidate(
                    id=args.id,
                    source_id=args.source_id,
                    kind=args.kind,
                    uri=args.uri,
                    start=args.start,
                    end=args.end,
                    width=args.width,
                    height=args.height,
                    score=args.score,
                    credit=args.credit,
                    notes=args.notes,
                ),
            ),
        )
        validate_edit(updated)
        out = write_edit_json(updated, _edit_out_path(args.edit, args.out))
        print(f"done: {out}")
        return 0

    if args.command == "propose-beat":
        from .edit import BeatCandidate, load_edit, write_edit_json
        from .planning import add_beat_candidates

        edit = load_edit(args.edit)
        updated = add_beat_candidates(
            edit,
            BeatCandidate(
                id=args.id,
                token_start=args.token_start,
                token_end=args.token_end,
                route=args.route,
                interpretation=args.interpretation,
                source_plan=args.source_plan,
                fallback=args.fallback,
                source_ids=tuple(args.source_id),
                asset_ids=tuple(args.asset_id),
            ),
        )
        out = write_edit_json(updated, _edit_out_path(args.edit, args.out))
        print(f"done: {out}")
        return 0

    if args.command == "approve-beat":
        from .edit import load_edit, write_edit_json
        from .planning import approve_beat

        updated = approve_beat(load_edit(args.edit), args.beat_id, args.asset_id)
        out = write_edit_json(updated, _edit_out_path(args.edit, args.out))
        print(f"done: {out}")
        return 0

    if args.command == "reject-beat":
        from .edit import load_edit, write_edit_json
        from .planning import reject_beat

        updated = reject_beat(load_edit(args.edit), args.beat_id, args.reason)
        out = write_edit_json(updated, _edit_out_path(args.edit, args.out))
        print(f"done: {out}")
        return 0

    if args.command == "compile-manifest":
        from .compile import compile_edit_to_manifest, write_manifest_json
        from .edit import load_edit

        manifest = compile_edit_to_manifest(
            load_edit(args.edit),
            args.base,
            args.output,
            size=_parse_size(args.size),
            fps=args.fps,
        )
        out = write_manifest_json(manifest, args.manifest)
        print(f"done: {out}")
        return 0

    if args.command == "zoom-still":
        from .stills import render_zoom_still

        size = _parse_size(args.size)
        render_zoom_still(
            Path(args.input),
            Path(args.output),
            args.duration,
            rate=args.rate,
            fps=args.fps,
            size=size,
            blurfill=args.blurfill,
        )
        print(f"done: {args.output}")
        return 0

    if args.command == "capture-page":
        from .capture import capture_page

        width, height = _parse_size(args.size)
        asyncio.run(
            capture_page(
                args.url,
                Path(args.output),
                chrome=args.chrome,
                wait=args.wait,
                width=width,
                height=height,
                scale=args.scale,
            )
        )
        print(f"done: {args.output}")
        return 0

    if args.command == "render-cutaways":
        from .video import render_cutaways

        output = render_cutaways(load_manifest(args.manifest))
        print(f"done: {output}")
        return 0

    if args.command == "verify-frames":
        from .video import extract_verify_frames

        manifest = load_manifest(args.manifest)
        out_dir = extract_verify_frames(
            manifest,
            source=Path(args.source) if args.source else None,
            out_dir=Path(args.out_dir) if args.out_dir else None,
        )
        print(f"done: {out_dir}")
        return 0

    if args.command == "list-presets":
        import json

        if args.json:
            print(json.dumps({name: preset.to_dict() for name, preset in PRESETS.items()}, indent=2))
        else:
            for preset in PRESETS.values():
                print(f"{preset.name}: {preset.width}x{preset.height} {preset.ratio} {preset.video_codec}/{preset.audio_codec}")
        return 0

    if args.command == "probe-media":
        import json

        from .probe import probe_media

        probe = probe_media(args.input)
        print(json.dumps(probe.to_dict(), indent=2))
        return 0

    if args.command == "validate-export":
        import json

        from .probe import probe_media
        from .validation import validate_export, write_json_report, write_markdown_report

        report = validate_export(probe_media(args.input), get_preset(args.preset))
        if args.json_out:
            write_json_report(report, args.json_out)
        if args.md_out:
            write_markdown_report(report, args.md_out)
        print(json.dumps(report.to_dict(), indent=2))
        if args.strict:
            return 0 if report.overall == "pass" else 1
        return 1 if report.overall == "fail" else 0

    if args.command == "export-variant":
        from .export import build_export_command
        from .video import run

        run(build_export_command(Path(args.input), Path(args.output), get_preset(args.preset), crf=args.crf))
        print(f"done: {args.output}")
        return 0

    return 2


def _parse_size(value: str) -> tuple[int, int]:
    raw = value.lower().split("x")
    if len(raw) != 2:
        raise argparse.ArgumentTypeError("size must be WIDTHxHEIGHT")
    return int(raw[0]), int(raw[1])


def _edit_out_path(edit_path: str, out_path: str | None) -> Path:
    return Path(out_path) if out_path else Path(edit_path)


if __name__ == "__main__":
    raise SystemExit(main())
