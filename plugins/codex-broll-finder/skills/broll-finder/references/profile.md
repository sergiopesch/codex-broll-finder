# B-Roll Profile

Create `BROLL-PROFILE.md` in the user's project when no profile exists. Keep it short and update it when the user states a preference or ban.

## Required Fields

```markdown
# B-Roll Profile

Confirmed-by: <name> (<YYYY-MM-DD>)

## Defaults
- Format:
- Topic:
- Resolution:
- Cadence:
- Audio:
- Stills motion:
- Source attribution:
- Motion graphics:
- AI-generated b-roll:

## Trusted Sources
- <source> [tags] - why it is trusted

## Guardrails
- <ban or preference>

## Reference Library
- <meme/show/recurring source>, if user supplied
```

## Onboarding Questions

Ask only what is needed to make the first run safe:

1. Should b-roll audio always be stripped, or can source audio ever be used?
2. Should static images get subtle sub-pixel zoom, or stay fully static?
3. Should source credits appear on screen: off, white, black, or auto?
4. Should concept/stat beats use an existing motion graphics project? If yes, record the path.
5. Is AI-generated b-roll allowed? Default is off.

## Persistence

When a user bans a category, source, or style, write it to `Guardrails` immediately. Do not propose or source that category again in the session.
