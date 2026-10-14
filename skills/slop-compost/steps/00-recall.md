# Step 0 - Recall

Load what past runs left behind, and close the loop on past adopted candidates with **one batched question**.

## Inputs

- `$LEDGER` (resolved in SKILL.md).
- Ledger files if present: `state.json`, `decisions.jsonl`, `lessons.md`, `intents.md`, `profile.md`, `compost.jsonl`, `sources.md`.
- Shipped source list: [../sources/defaults.md](../sources/defaults.md) (rules in [../sources/README.md](../sources/README.md)).
- Record schemas: [08-ledger.md](08-ledger.md) (read only the "Schemas" section if you need field details).

## Do

1. Check the ledger: `ls -la "$LEDGER" 2>/dev/null`.
   - Missing or empty: set `first_run = true` (this forces `mode = full` in step 1), create `$LEDGER`, seed `$LEDGER/sources.md` from `${CLAUDE_SKILL_DIR}/sources/defaults.md`, tell the user in one line ("First run: ledger created at `<path>`, full analysis"), skip to Output.
   - **Sources** (every run): if `$LEDGER/sources.md` is missing, seed it from defaults. If `defaults.md` has ids not present in the user's list (removed entries count as present), add one line to this step's question: "N new default sources (ids) - add them? (yes / no)". `yes` appends them; `no` appends them with `enabled: false`.
2. Read `state.json`, `profile.md`, the latest dated section of `lessons.md`, and the active section of `intents.md`.
3. Build the **follow-up list** from `decisions.jsonl`: lines where `decision == "adopt"` and `stale != true`, and either
   - `followups` is empty, or
   - the last followup has `touched == true` and its `result` is not a final state (`done` or `stopped`).
4. If the list is non-empty, show it numbered, **all at once**, and ask one question. Example (translate to the user's language):

   ```
   Follow-up on what you adopted before (one line, any order):
     F1  [2026-10-01 A1] Cut idea-factory to the daily digest only
     F2  [2026-10-01 B2] Newsletter-to-podcast for niche B2B
   Answer format: F1 yes in-progress "landing is up", F2 no "no time"   |   F1 done, F2 stopped "no demand"   |   skip
   - yes/no = did you touch it   - result: not-started | in-progress | done | stopped   - "note" optional
   - Leave an item out, or say skip, to be asked again next time.
   ```

5. Parse the answer tolerantly (same rules as step 7):
   - Split on commas or semicolons; each item is `<label> [touched] [result] [note]`. Labels are case-insensitive (`f1` = `F1`).
   - touched: `yes|y|no|n` and equivalents in the user's language (Korean: `손댔음`, `했음`, `함` = yes; `안 함`, `안함`, `못 함` = no).
   - result: `not-started|in-progress|done|stopped` and equivalents (Korean: `시작 안 함`, `진행중`/`진행 중`, `완료`, `중단`/`그만둠`). A result alone implies touched (`not-started` implies `no`).
   - note: quoted text, or the rest of the item after the recognized words.
   - skip: `skip`, `s`, `pass`, or Korean `스킵`, `건너뜀`, `패스` (for one item or for all).
   - Unparseable items: list them back in one line and ask only about those.
6. Apply the parsed answers. For every item answered, append a followup object `{at, touched, result, note}` to that decision (schema in 08-ledger.md).
   For every item skipped (left out, or global `skip`): `skip_count += 1`. If `skip_count >= 3`, set `stale = true` and tell the user it will not be asked again.
   Stage these changes in `$LEDGER/runs/<run-id>.work/recall.json`; step 8 writes them to `decisions.jsonl`.
7. Summarize recurring patterns for later steps (keep to 3-5 bullets, each with ids):
   - adoption-to-start rate: "adopted 5, started 1 (`2026-10-01:A1`)".
   - lessons with `repeat >= 3` ("structural habits").
   - compost hot spots: rule ids that failed in 3+ past runs (count from `compost.jsonl`).

## Output

- `first_run` flag.
- `recall.json` staged followups (may be empty).
- A short "Recall summary" block (patterns with evidence ids) passed to steps 2-6. Show it to the user only if it has content.

## Reject if

Compost (see SKILL.md) any summary bullet that fails these, rule ids in brackets:

- [`00.ev-no-id`] A pattern bullet does not cite at least one decision id, lesson id, or compost id.
- [`00.invented-followup`] A followup was recorded for an item the user did not answer (skips must stay skips).
- [`00.asked-stale`] A `stale` decision was included in the follow-up list.
