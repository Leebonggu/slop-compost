# Step 7 - Judge

The user judges every candidate in **one line**. No per-candidate questions, no "pick a track" question.

## Inputs

- The candidate labels shown in step 6 (A1..A3, B1..B3).

## Do

1. Ask once (translate):

   ```
   Your call on each candidate, one line:
     adopt (a) / hold (h) / reject (r), optional reason after it
   Example: A1 adopt landing first, A2 hold, B1 reject too much ops   |   A1 a, B2 r
   Anything you leave out = hold. Empty answer = everything hold.
   ```
2. Parse tolerantly:
   - Split on commas or semicolons into items. Each item: `<label> <decision> [reason]`.
   - Labels are case-insensitive (`a1` = `A1`). Decisions: `adopt|a`, `hold|h`, `reject|r`, and the user's language equivalents (e.g. Korean `채택`, `보류`, `기각`).
   - Reason = the rest of the item, trimmed. Empty is allowed.
   - Unknown labels or decisions: list them back in one line and ask only about those. Everything else is kept as parsed.
   - Missing labels default to `hold` with an empty reason.
3. Echo the parsed result as a compact table (label, decision, reason) and continue to step 8 without asking for confirmation, unless something was unparseable.
4. Do not ask the user to choose a track. The track tag is attached automatically in step 8.
5. Convergent pairs (`A1 ≈ B2`) are judged independently. Do not ask the user to pick one of the pair; adopting both is valid.

## Output

- A list of `{label, track, decision, reason}` for every candidate shown in step 6.

## Reject if

- [`07.per-candidate-questions`] More than one question was asked for judgments that parsed cleanly.
- [`07.invented-reason`] A reason was filled in that the user did not write.
- [`07.track-question`] The user was asked to pick a track, or to pick one of a convergent pair.
- [`07.missing-candidate`] A shown candidate has no judgment record (it must default to `hold`).
