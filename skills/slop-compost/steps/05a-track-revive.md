# Step 5A - Track A: revive the current idea

You are the Track A writer. Question: **"If the user revives what they already built, what is the smallest path that could work?"**
You work alone. Do not read Track B's files (`input-b.md`, `track-b.md`, `compost.track-b.jsonl`) even if you can see them.

## Inputs

- `input-a.md` (path given in your brief): artifact summaries, parts with locations, stop reasons, lessons with ids, active intents, profile excerpt.
- Output language (given in your brief). Enum values and ids stay in English.
- Candidate shape: the "Candidate" block in [../templates/direction.md](../templates/direction.md).

## Do

1. Rank artifacts by revival priority: recurring theme across artifacts (+), parts marked must-keep by an intent (+), recent activity (+), stop reason `abandoned` with no stated motivation (-).
2. For the top artifacts, apply the default prescription per stop reason (an artifact with several reasons gets several):
   - `unfinished` -> **cut scope.** "If only one of the remaining things got finished, which one?" Name the one thing; everything else is out.
   - `no-revenue` -> **change who pays, the price, or the channel.** Change one variable at a time, and say which.
   - `abandoned` -> **check motivation.** If the profile, intents, or notes show motivation, propose a revival. If not, do not propose a revival: write a **Release note** instead ("let it go; hand parts X, Y to the parts list") and produce no candidate for it.
   - `other` -> derive the prescription from the user's own words for the reason.
3. Write **1-3 candidates** `A1..A3`. Each must contain:
   - one-line definition (what changes vs the original),
   - parts used (`artifact-id` + location),
   - lessons applied: for **each** cited lesson id, the concrete change it causes ("L2 -> landing page before any new feature"),
   - **first experiment** that fits in 7 days or less (what, by when, cost),
   - **success criterion with a number** ("10 of 40 emailed users reply", "3 paid pre-orders at $9"),
   - kill criterion: what result means stop,
   - respected intents (ids) and any intent it bends (say so explicitly).
4. Respect intents. A candidate that violates an active intent must say which one and why it is still worth showing, or be composted.
5. Write the result to the `track-a.md` path from your brief: candidates, then release notes, then one line with the composted **count** per rule id. Never put composted candidate text in `track-a.md`.
6. Apply "Reject if" below. Write each failing candidate as one JSON line to `compost.track-a.jsonl` (same directory):
   `{"step":"05a","kind":"candidate","content":"<the full candidate text>","failed_rules":["05a.no-number"]}`. The orchestrator adds `id`, `run`, `at`, `reused_in`.

## Output

- `track-a.md` (1-3 candidates + release notes). If every candidate failed, write "No Track A candidate survived" and the rule ids that failed.
- `compost.track-a.jsonl` (possibly empty).
- Reply to the orchestrator with only: number of candidates kept, number composted.

## Reject if

- [`05a.no-experiment`] No first experiment, or it cannot finish within 7 days.
- [`05a.no-number`] The success criterion has no number, or the number is not observable within the experiment.
- [`05a.ev-no-lesson-link`] Cites a lesson without saying which concrete change it causes, or cites no lesson at all.
- [`05a.ev-no-part`] Uses no part from the input, or cites a part location that is not in the input.
- [`05a.same-as-before`] It repeats what the artifact already did without changing the variable named by its stop reason.
- [`05a.saw-track-b`] Anything in it came from Track B files.
- [`05a.compost-in-output`] `track-a.md` contains the text of a composted candidate (counts only).
