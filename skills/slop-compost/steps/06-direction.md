# Step 6 - Direction

Merge both tracks into one side-by-side view, save it, and show it. This is the main deliverable of the run.

## Inputs

- `track-a.md`, `track-b.md`, `compost.pending.jsonl`, `compost.track-a.jsonl`, `compost.track-b.jsonl` in `<LEDGER>/runs/<run-id>.work/`.
- Step 2 parts and cross-artifact patterns, step 3 lessons, step 4 intents, step 0 recall summary.
- `mode`, `partial` flags, blocked inputs from step 1.
- Format: [../templates/direction.md](../templates/direction.md).

## Do

1. **Second check (the only one; the orchestrator does not run another).** Re-check every candidate from both tracks against the "Reject if" lists of 05a/05b and this file. Move failures to `compost.pending.jsonl` with their rule ids (process-only rules such as `05b.blocked-path` do not compost a candidate).
   **Never renumber.** Keep each surviving candidate's original label (A1, A3, B2...). Gaps are fine: if A2 was composted, the survivors are A1 and A3.
2. Fill the template in this order:
   1. Header: run id, mode (full/incremental and why), artifacts analyzed (mark `partial` ones and blocked ones).
   2. Recall summary (only if not first run).
   3. **Parts list** (this run's parts, grouped by artifact; mention how many ledger parts Track B also used) and **patterns across artifacts**. Always present, also on the first run. Patterns may include ledger artifacts marked `(ledger)`. Only if this run's artifacts plus ledger artifacts add up to 1, write "Cross-artifact patterns need 2+ artifacts" instead of inventing patterns.
   4. Lessons (structural habits first).
   5. **Two tracks side by side**: "If you revive the current idea" (A1..A3, release notes) and "If you go for a new idea" (B1..B3). Same candidate fields for both, plus external evidence and counter-evidence for B. Keep the tracks' original wording; you may shorten, not merge or reframe.
   5b. **Convergence**: if an A candidate and a B candidate reach essentially the same direction, keep both as they are and add one line under the tracks: `Convergence: A1 ≈ B2 - <what they share>`. Explain once: two independent paths reaching the same conclusion is a strong signal. Do not merge them.
   6. One compost line at the end, counts only: "Composted N (05b.ev-no-counter: 2, 03.unfalsifiable: 1)". Do not show the content unless the user asks.
3. Save the filled document to `<LEDGER>/runs/<run-id>.md` (create `runs/` if needed). If running sequentially, add `fallback: sequential` to the header.
4. Show it to the user with the labels exactly as saved, because step 7 refers to them. `runs/<run-id>.md` is the reference document for step 8 (decisions, source statistics, `reused_compost` joins); keep each candidate's `Source ids:` line and any `reused_compost` note in it.

## Output

- `<LEDGER>/runs/<run-id>.md`.
- The same content in chat (it may be lightly condensed, never with different labels).

## Reject if

- [`06.missing-parts-section`] The parts list or cross-artifact patterns section is missing (including on the first run).
- [`06.single-track`] One track is missing without an explicit "No Track X candidate survived (rules: ...)" line.
- [`06.reframed`] A candidate was merged across tracks or its claims changed during formatting (a `Convergence:` line is allowed).
- [`06.compost-shown`] Composted content shown without the user asking.
- [`06.label-mismatch`] Labels in chat differ from labels in the saved run file, or surviving candidates were renumbered.
