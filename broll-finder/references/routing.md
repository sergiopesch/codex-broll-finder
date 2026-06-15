# Routing And Sourcing

Use this reference while planning and sourcing b-roll.

## Classification

| Route | Trigger | Preferred source |
| --- | --- | --- |
| `receipt` | current claim, discourse, quote, stat, controversy, review | tweet embed, article headline, search result, original post |
| `entity` | named person, physical product, company moment, historical event | official or authoritative channel/page |
| `product-ui` | software/tool workflow or feature | own recording first, then official demo, then current docs/screenshots |
| `concept` | abstract process, model, comparison, stat with no literal footage | user's motion graphics project or simple on-brand generated card |
| `evocative` | story action, place, mood, physical setting | reputable stock/library source checked for watermark and AI artifacts |
| `taste` | meme, reaction, creator clip, joke timing | user library or explicit user approval |

## Interpretation Rules

- Source the meaning, not the nearest keyword.
- For people, query the person plus the mention context, never the bare name.
- A quote or claim usually wants the artifact containing it, not the speaker's face.
- Cards do not replace real footage of literal, filmable things.
- Motion beats static when relevance is equal, except when reading a receipt is the point.

## Phrase Map

| Narration | Source |
| --- | --- |
| people are saying | posts, headlines, search results |
| number or stat | pricing page, dashboard, chart, stat card |
| went viral | viral post with visible metrics or growth graph |
| decline/tanking | graph down, error state, failing artifact |
| research shows | paper headline or expert clip |
| direct quote | authentic post/blog/article screenshot |
| back in the day | archival footage or period image |
| place | establishing shot of the place |
| X vs Y | sequential full-bleed singles |
| how it works | screen recording or motion graphic |
| emotion/reaction | propose the beat; user supplies taste asset |

## Search Rules

- For YouTube entity beats, search inside official/trusted channels first:
  `yt-dlp "https://www.youtube.com/@handle/search?query=query" --flat-playlist --print "%(title).75s ||| %(duration_string)s ||| %(id)s"`
- Use metadata search before download.
- Download only the selected source, preferably `-f "bv*[height<=1080]+ba/b"`.
- Open YouTube search is a flagged fallback, not a default.
- For tweets, prefer platform embeds for clean screenshots when possible.
- For product UI, check recency because interfaces change quickly.

## Scoring

Score every candidate 1-5:

1. Recency fit
2. Source authority
3. Relevance to the interpretation
4. Recognizability/readability
5. Format fit: silent-able, full-bleed-able, 2-6s usable, at least 720p

Drop candidates below 4 on relevance or source authority for objective beats.

## Escalation

Try at most two distinct methods for a beat:

1. Local artifacts and project files
2. Web/search identity resolution
3. Plain public source via `yt-dlp` or browser capture
4. User browser cookies or logged-in browser capture
5. Flag as user-source-required or drop

Do not retry the same failing method with small flag changes.
