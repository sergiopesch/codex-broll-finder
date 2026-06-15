from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from .manifest import load_manifest
from .presets import PRESETS, get_preset


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="broll-tool")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate-manifest", help="Parse and validate BROLL-MANIFEST.json")
    validate.add_argument("manifest")

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


if __name__ == "__main__":
    raise SystemExit(main())
