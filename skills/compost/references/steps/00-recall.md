# Step 0 - Recall

Load what past runs left behind and close the loop on past adopted candidates with **one batched question**.

## Inputs

- `init` output (SKILL.md runs it first): `first_run`, `new_default_sources`, `overrides_present`.
- `<CLI> recall` output: `followups`, `summary` (adoption by track, structural habits, active intents, compost hot spots), `lessons`, `next_lesson_id`. Do not open `decisions.jsonl`, `lessons.md`, `intents.md` or `compost.jsonl`: the JSON covers them.

## Do

1. **First run** (`first_run: true`): tell the user in one line ("First run: ledger at `<LEDGER>`, full analysis"). Only Do 4 can apply; then go to Output.
2. Run `<CLI> recall`. `followups` is already the H1 list: `decision == adopt` AND not `stale` AND (no followups OR the last `result` is not `done`/`stopped`). `touched` plays no part.
3. If `followups` is non-empty, show it numbered, all at once, and ask one question (translate):

   ```
   Follow-up on what you adopted before (one line, any order):
     F1  [2026-10-01 A1] Cut idea-factory to the daily digest only
     F2  [2026-10-01 B2] Newsletter-to-podcast for niche B2B
   Answer format: F1 yes in-progress "landing is up", F2 no "no time"   |   F1 done, F2 stopped "no demand"   |   skip
   - yes/no = did you touch it   - result: not-started | in-progress | done | stopped   - "note" optional
   - Leave an item out, or say skip, to be asked again next time.
   ```

   Pass the answer unchanged: `<CLI> apply-recall --run <RUN> '<answer line>'`. The script parses tolerantly (F labels or original labels such as `B1` / `2026-10-15:A1`; yes/no and results with Korean equivalents such as `손댔음`, `안 함`, `진행 중`, `완료`, `중단`; quoted notes; `skip`/`스킵`), applies the defaults (a result implies touched; `no` alone = `not-started`; `yes` alone = `in-progress`), resets `skip_count` for answered items, adds 1 for skipped items, marks `stale` at 3, and stages `<WORK>/recall.json` for step 8.
   - `unparsed` or `ambiguous` non-empty: ask once about only those (show full ids for ambiguous labels), then call `apply-recall` again with the new line. Earlier answers are kept.
   - `stale` non-empty: tell the user those items will not be asked again.
4. **New default sources** (`new_default_sources` in the `init` output): ask in the same message as Do 3, or alone as one line: "N new default sources (ids) - add them? (yes / no)". Then `<CLI> sources sync-defaults yes|no` (`no` adds them disabled so the question is not repeated).
5. Write a 3-5 bullet **recall summary** for later steps from `summary`, each bullet with ids: adoption-to-start rate per track, structural habits (repeat >= 3), compost hot spots (rule ids failing in 3+ runs).

## Output

- `first_run` flag, `<WORK>/recall.json` (may be absent), the recall summary (show it only if it has content). Keep `lessons` and `next_lesson_id` for step 3.

## Reject if

Compost any summary bullet that fails these:

- [`00.ev-no-id`] A pattern bullet does not cite at least one decision id, lesson id, or compost id.
- [`00.invented-followup`] A followup was recorded for an item the user did not answer (skips must stay skips; pass the user's words unchanged to `apply-recall`).
- [`00.asked-stale`] A `stale` decision was included in the follow-up list.
