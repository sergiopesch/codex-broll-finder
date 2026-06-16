# Manifest Format

Use `KINO-MANIFEST.json` as the executable source of truth.

```json
{
  "version": 1,
  "base": "input.mp4",
  "output": "output_with_kino.mp4",
  "size": [1920, 1080],
  "fps": 30,
  "beats": [
    {
      "id": "b001",
      "start": 2.2,
      "end": 5.1,
      "line": "Today we are using Codex to build this.",
      "interpretation": "The line introduces Codex as the tool being used.",
      "route": "product-ui",
      "asset": "assets/fmt/b001.mp4",
      "kind": "video",
      "source_in": 0.0,
      "status": "approved",
      "credit": "OpenAI / YouTube"
    }
  ],
  "removed": []
}
```

## Rules

- Beat ids are stable across renders.
- `start` and `end` are seconds in the base video.
- `kind` is `video` or `still`.
- Beats must be sorted and non-overlapping before rendering.
- Approved beats cannot be removed unless their id appears in `removed` with a reason.
- Keep raw downloads in `assets/raw/` and formatted render inputs in `assets/fmt/`.
