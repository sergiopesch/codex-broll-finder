# Verification

Use this after rendering or formatting assets.

## Frame Grid

Extract frames at:

- each beat midpoint
- each b-roll start
- each b-roll end
- each joint where one b-roll touches another

Inspect the resulting frames before presenting the render.

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
