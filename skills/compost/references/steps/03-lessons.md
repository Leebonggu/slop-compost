# Step 3 - Lessons

Turn the analysis into falsifiable, evidence-located lessons and count how often each recurs across runs.

## Inputs

- Step 2 output (parts, stop reasons, cross-artifact behaviors).
- `lessons` and `next_lesson_id` from `<CLI> recall` (step 0). Do not open `lessons.md`.
- Format: [../../assets/templates/lesson.md](../../assets/templates/lesson.md).

## Do

1. Write candidate lessons. Each is **one sentence that could turn out false**, plus:
   - evidence locations (at least one `artifact-id:path:line`, paragraph, or note line, in backticks),
   - a falsifier: what observation would prove it wrong,
   - related stop reasons (`no-revenue` | `unfinished` | `abandoned` | `other`).
   Good: "I stop when the first external user test is more than 2 weeks away (`idea-factory:README.md:12`, `podcast-idea:notes.md:3`)." Bad: "Need better UX."
2. Compare with the past `lessons`. Same behavior and same trigger = a repeat: keep the old id and write a `### L2 - (repeat, see <date>)` entry with only the new evidence; `commit` raises the repeat count, adds the evidence to the original, and marks `[structural habit]` at 3.
   Not a duplicate: a **cause** lesson and a **reaction** lesson about the same failure. Link them with `Related:`.
3. Structural habits (repeat >= 3) go first.
4. At most 7 lessons. Zero new lessons is valid; never invent one to reach a count. Prefer lessons tied to a stop reason.
5. New ids start at `next_lesson_id`.
6. Write the lessons to `<WORK>/lessons.md` (template entries, no section heading needed), then `<CLI> lint <WORK>/lessons.md --kind lessons --compost`. Remove every lesson listed in `violations` from the file (it is now in `compost.pending.jsonl`), then check the meaning rules below yourself.

## Output

- `<WORK>/lessons.md`: lessons with id, sentence, evidence, falsifier, stop reasons, repeat, habit flag.

## Reject if

Compost each failing lesson with `kind: lesson`; do not show it. The script checks structure (marked *); you check meaning.

- [`03.ev-no-location`] *No evidence location, or the location does not exist in the analyzed material (unknown artifact, missing file, line past the end).
- [`03.unfalsifiable`] *No falsifier; or the sentence cannot be wrong ("quality matters", "UX needs work").
- [`03.multi-claim`] More than one claim in one lesson. Split it or compost it.
- [`03.duplicate`] *Restates an existing lesson under a new id instead of a repeat (the script catches identical wording; you catch paraphrases).
