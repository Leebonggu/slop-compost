# Step 7 - Judge

The user judges every candidate in **one line**. No per-candidate questions, no "pick a track" question.

## Inputs

- The labels in `<LEDGER>/runs/<RUN>.md` (A1..A3, B1..B3).

## Do

1. Ask once (translate):

   ```
   Your call on each candidate, one line:
     adopt (a) / hold (h) / reject (r), optional reason after it
   Example: A1 adopt landing first, A2 hold, B1 reject too much ops   |   A1 a, B2 r
   Anything you leave out = hold. Empty answer = everything hold.
   ```
2. Pass the answer unchanged: `<CLI> judge --run <RUN> '<answer line>'`. The script splits on commas/semicolons, accepts case-insensitive labels, `adopt|a|hold|h|reject|r` and Korean `채택|보류|기각`, takes the rest of the item as the reason, defaults missing labels to `hold`, accepts a convergent pair written together (`A1+B2 adopt`), and stages `<WORK>/judgments.json`.
3. `unparsed` non-empty: list those items back in one line and ask only about them, then call `judge` again with the new line (earlier answers are kept).
4. Echo `decisions` as a compact table (label, decision, reason) and continue to step 8 without asking for confirmation.
5. Never ask the user to choose a track or one of a convergent pair; adopting both is valid. The track tag is attached in step 8.

## Output

- `<WORK>/judgments.json`: one `{label, track, decision, reason}` per candidate in the run file.

## Reject if

- [`07.per-candidate-questions`] More than one question was asked for judgments that parsed cleanly.
- [`07.invented-reason`] A reason was filled in that the user did not write (pass the user's line unchanged).
- [`07.track-question`] The user was asked to pick a track, or one of a convergent pair.
- [`07.missing-candidate`] A shown candidate has no judgment record (the script defaults it to `hold`).
