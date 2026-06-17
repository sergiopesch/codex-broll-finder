# Verification

Use this after rendering or formatting assets.

## Frame Grid

Extract frames at:

- each beat midpoint
- each b-roll start
- each b-roll end
- each joint where one b-roll touches another

Inspect the resulting frames before presenting the render.

## Contact Sheet And Frame QC

After `verify-frames`, generate a labeled sheet and machine-readable QC report:

```bash
python3 kino/scripts/kino_tool.py make-contact-sheet verify_frames KINO-CONTACT-SHEET.jpg
python3 kino/scripts/kino_tool.py check-frames verify_frames \
  --manifest KINO-MANIFEST.json \
  --json-out KINO-FRAME-QC.json \
  --md-out KINO-FRAME-QC.md \
  --contact-sheet KINO-CONTACT-SHEET.jpg
```

Treat `fail` as blocking. Treat `warning` as a visible review item; intentional still cutaways can legitimately produce near-identical-frame warnings.

Current automated checks:

- expected verification frame files from the manifest
- tiny or empty frame files
- unreadable image files
- black or near-black frames
- near-identical adjacent verification frames

## Auto-Reject

Reject and fix any frame with:

1. burned-in captions or subtitles from the source
2. unrelated lower thirds or name tags
3. watermarks, stock previews, or channel bugs that are not explicitly accepted
4. the speaker's own face/tile used as b-roll in the same video
5. generated cards replacing literal footage
6. letterboxing, tiny floating content, or bad crop/blur-fill framing
7. a sub-1s flash of talking head between adjacent cutaways
8. unreadable receipt text

## Timing

- Anchor on or just after the spoken word, typically +0.2 to +0.5s.
- Late usually reads intentional; early reads wrong.
- Connect adjacent b-rolls by extending the earlier beat to the next beat start.
