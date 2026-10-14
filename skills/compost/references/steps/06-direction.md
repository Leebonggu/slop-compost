# Step 6 - Direction

Merge both tracks into one side-by-side view, save it, and show it. This is the main deliverable of the run.

## Inputs

- `<WORK>/track-a.md`, `<WORK>/track-b.md` (the composted items are already in the `compost*.jsonl` files).
- Step 2 parts and patterns, step 3 lessons, step 4 intents, step 0 recall summary, `mode`, `partial` flags, blocked inputs.
- Format: [../../assets/templates/direction.md](../../assets/templates/direction.md).

## Do

1. Fill the template in this order:
   1. Header: run id, `Mode: full|incremental` with the reason (step 8 reads this word), artifacts (mark `partial` and blocked ones), `fallback: sequential` if the tracks ran without subagents.
   2. Recall summary (not on the first run).
   3. **Parts** table (this run's parts by artifact, with ids; mention how many ledger parts Track B used) and **patterns across artifacts**. Always present, also on the first run. Only if this run's plus ledger artifacts add up to 1, write "Cross-artifact patterns need 2+ artifacts" under the patterns heading.
   4. Lessons (structural habits first).
   5. **Two tracks side by side**: "If you revive the current idea" (A candidates, release notes) and "If you go for a new idea" (B candidates). Copy each candidate block with its **original label** and field lines (you may shorten wording, never merge or reframe). Keep every `Source ids:` line, `[src:<id>]` tag and `reused_compost` line: step 8 reads them from this file.
   6. **Convergence**: if an A and a B candidate reach essentially the same direction, keep both and add `Convergence: A1 ≈ B2 - <what they share>` under the tracks, with one sentence: two independent paths reaching the same conclusion is a strong signal.
   7. One compost line at the end, counts only: "Composted N (05b.ev-no-counter: 2, 03.unfalsifiable: 1)".
2. Save it to `<LEDGER>/runs/<RUN>.md`.
3. **Second check (the only one)**: `<CLI> lint <LEDGER>/runs/<RUN>.md --kind direction --compost`. It re-runs the 05a/05b structural rules on every candidate, compares labels and definitions with the track files, and checks the sections below. For each violation: remove a failing candidate (it is now in `compost.pending.jsonl`; never renumber the rest) or fix a file-level problem (`(file)` label), save again, and lint again until `violations` is empty. Then apply the meaning rules of 05a/05b and this file yourself.
4. Show the saved document to the user with the labels exactly as saved (step 7 refers to them; light condensing is fine).

## Output

- `<LEDGER>/runs/<RUN>.md` and the same content in chat.

## Reject if

- [`06.missing-parts-section`] *The parts table or the patterns section is missing (including on the first run).
- [`06.single-track`] *One track is missing without an explicit "No Track X candidate survived (rules: ...)" line.
- [`06.reframed`] A candidate was merged across tracks or its claims changed during formatting (a `Convergence:` line is allowed).
- [`06.compost-shown`] *Composted content is shown without the user asking.
- [`06.label-mismatch`] *Labels differ from the track files or surviving candidates were renumbered; or chat labels differ from the saved file.

(* = checked by `lint --kind direction`.)
