# Step 3 - Lessons

Turn the analysis into falsifiable, evidence-located lessons and count how often each recurs across runs.

## Inputs

- Step 2 output (parts, stop reasons, cross-artifact behaviors).
- `<LEDGER>/lessons.md` (all past lessons with ids and repeat counts).
- Format: [../templates/lesson.md](../templates/lesson.md).

## Do

1. Write candidate lessons. Each lesson is **one sentence that could turn out false**, plus:
   - evidence locations (at least one `artifact-id:path:line`, paragraph, or note line),
   - a falsifier: what observation would prove it wrong,
   - related stop reasons (`no-revenue` | `unfinished` | `abandoned` | `other`).
   Good: "I stop when the first external user test is more than 2 weeks away (`idea-factory:README.md:12`, `podcast-idea:notes.md:3`)."
   Bad: "Need better UX." / "Should validate more."
2. Compare with past lessons in `lessons.md`. If a new lesson says the same thing (same behavior and same trigger), do not create a duplicate: reuse the old id and increment `repeat`, adding the new evidence.
   Not a duplicate: a **cause** lesson and a **reaction** lesson about the same failure. Example: "Without my own context in the prompt, the output is generic and I lose interest" (cause) vs "When LLM output disappoints, I quit before revising the prompt or adding review" (reaction) are two lessons; link them with a `Related:` line.
3. Lessons with `repeat >= 3` are promoted to **structural habit**. Mark them and put them first.
4. At most 7 lessons per run. Never invent a lesson without evidence just to reach a count: zero new lessons is a valid result. Prefer lessons that connect to a stop reason.
5. Assign ids `L<n>` continuing the highest id in `lessons.md` (start at `L1`).

## Output

- Lesson list (id, sentence, evidence, falsifier, stop reasons, repeat, habit flag) staged in `<LEDGER>/runs/<run-id>.work/lessons.md`.

## Reject if

Compost (see SKILL.md) each failing lesson with `kind: lesson`; do not show it.

- [`03.ev-no-location`] No evidence location, or the location does not exist in the analyzed material.
- [`03.unfalsifiable`] No falsifier, or the sentence cannot be wrong ("quality matters", "UX needs work").
- [`03.multi-claim`] More than one claim in one lesson. Split it or compost it.
- [`03.duplicate`] Restates an existing lesson under a new id instead of incrementing `repeat`.
