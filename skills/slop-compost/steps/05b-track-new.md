# Step 5B - Track B: go for a new idea

You are the Track B writer. Question: **"If the user leaves the originals behind, what new idea do these parts and lessons point to, given what is happening outside?"**
You work alone. Do not read Track A's files (`input-a.md`, `track-a.md`, `compost.track-a.jsonl`) even if you can see them.

## Inputs

- `input-b.md` (path in your brief): lessons, all parts (with source artifact id), active intents, profile excerpt, past rejected Track B candidates with reasons, reusable compost entries.
- Source list: the `$LEDGER/sources.md` path in your brief. Rules for reading it: [../sources/README.md](../sources/README.md). Lightweight flag (yes/no) in your brief.
- Output language (given in your brief). Enum values and ids stay in English.
- Candidate shape: the "Candidate" block in [../templates/direction.md](../templates/direction.md).

## Do

1. **Gather external signals** from the enabled entries of the source list, within each entry's `limits`. Every item gets a source (URL or local path), a date, and the source id `[src:<id>]`. Always use at least one `failure`-category source per candidate. For Korean domains prefer the `fetch` URL (RSS, list page) over `site:` searches. If lightweight is `yes`, use one source per category.
2. **Recombine.** Look for combinations of 2+ parts (ideally from different artifacts) that meet an external signal. Lessons constrain the shape: a lesson like "I stop when user contact is >2 weeks away" means the candidate must put a user in front of it in week 1.
3. **Reuse compost (optional).** A reusable compost entry is a past candidate that failed only for missing evidence. You may revive one, but only if you **fill in exactly what was missing** (dated source, counter-evidence, or lesson link) with new research. If you do, add `"reused_compost": "<compost id>"` to the candidate so the orchestrator can append this run id to its `reused_in`.
4. **Avoid repeats.** Do not re-propose a past rejected Track B candidate unless an external signal changed since then; if you do, cite the old decision id and what changed.
5. Write **1-3 candidates** `B1..B3`. Each must contain:
   - one-line definition, who pays and roughly how much,
   - parts used (`artifact-id` + location), lessons applied (ids, and the change each causes),
   - **external evidence**: 1-3 items, each `claim - source - date (YYYY-MM-DD) [src:<source id>]`,
   - **counter-evidence** (mandatory, both):
     - why this could fail (specific mechanism, not "competition"),
     - a similar attempt that failed or shut down, with source and date (from failory detail pages, quote the Cause field and the Closed year). If you searched and found none, write the queries used and "none found" (this counts only if the queries are shown),
   - **first experiment** within 7 days + **success criterion with a number** + kill criterion,
   - respected intents (ids) and any intent it bends.
6. Write the result to the `track-b.md` path from your brief, plus a "Sources checked" list (source id, items cited, freshest date, failures, lightweight or not), plus one line with the composted **count** per rule id. Never put composted candidate text in `track-b.md`. At the end of each candidate add `Source ids: <id>, <id>` (all sources it cites).
7. Apply "Reject if". Write each failing candidate as one JSON line to `compost.track-b.jsonl`:
   `{"step":"05b","kind":"candidate","content":"<full text>","failed_rules":["05b.ev-no-counter"]}`.

## Output

- `track-b.md` (1-3 candidates + sources checked). If none survived, say so with the failed rule ids.
- `compost.track-b.jsonl` (possibly empty).
- Reply to the orchestrator with only: candidates kept, composted, compost ids reused.

## Reject if

- [`05b.ev-no-source`] An external evidence item has no source (URL or ledger path).
- [`05b.ev-no-date`] An external evidence item or failure case has no date.
- [`05b.ev-no-counter`] Missing either counter-evidence part (failure mechanism, or a similar failure case / shown "none found" queries).
- [`05b.ev-no-part`] Uses no part from the input.
- [`05b.no-experiment`] No first experiment, or it cannot finish within 7 days.
- [`05b.no-number`] The success criterion has no observable number.
- [`05b.compost-unfixed`] Reuses a compost entry without filling the evidence that was missing.
- [`05b.ev-no-src-id`] An external evidence item has no `[src:<id>]`, or the id is not in the source list.
- [`05b.blocked-path`] A fetch hit a path the source's limits forbid (e.g. robots-disallowed paths) or exceeded the request cap.
- [`05b.saw-track-a`] Anything in it came from Track A files.
- [`05b.compost-in-output`] `track-b.md` contains the text of a composted candidate (counts only).
