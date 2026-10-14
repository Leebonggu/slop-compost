# Rubric - idea

Use for free-text ideas, idea notes, candidate JSON (e.g. from your own scraper), or pitch scraps (`idea` primary or secondary).

## Completeness checkpoints (0-100%)

| % | Checkpoint | Evidence to look for |
|---|---|---|
| 10 | One-liner | what it is in one sentence |
| 25 | Who has the problem | a specific user or buyer |
| 40 | Why now / why me | a trigger, trend, or unfair advantage |
| 55 | Who pays and how | a price or monetization model |
| 70 | Validation plan | a concrete test (landing, outreach, pre-sale) |
| 85 | Validation run | the test happened; result recorded |
| 100 | Decision with result | continued or killed based on data |

## Where parts hide

- `problem`: the pain statement and the user, even if the solution is weak.
- `data`: evidence already collected (competitor list, search volume, quotes, revenue cases).
- `sentence`: the one-liner itself if it is sharp.
- `design`: a mechanism (pricing trick, distribution hack) that could transfer to another idea.

## Stop signals

| Signal | Suggests |
|---|---|
| Never got past "who pays" | `no-revenue` (unclear payer) |
| Validation plan written, never run | `unfinished` |
| Marked rejected / dropped with a note | use the note; often `other` or `abandoned` |
| Same idea re-appears in several notes | recurring theme: raise priority (step 2) |

## Pitfalls

- For candidate JSON with `status: rejected` and a `decision_note`, the note is the stop reason evidence (cite `<id>.json:decision_note`).
- An idea without any evidence is still an artifact. Its parts are usually `problem` or `sentence`.
