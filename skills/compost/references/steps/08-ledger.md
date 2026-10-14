# Step 8 - Ledger

Write everything staged during the run into the ledger, update the personal profile, and propose (never apply) system changes.

## Inputs

- Everything in `<WORK>`, the judgments from step 7, and the run file `<LEDGER>/runs/<RUN>.md` (the reference document for decisions, source ids and `reused_compost`).
- Layout and record schemas: [../schemas.md](../schemas.md) (only if you must write a record by hand).
- Templates: [profile](../../assets/templates/profile.md), [export](../../assets/templates/export.md).

## Do

1. **Commit**: `<CLI> commit --run <RUN>` (add `--mode full` only if the run file header lacks the mode). In one pass it checks every new record against the schemas (and writes nothing if one fails), then:
   - moves draft cards to `artifacts/` (an existing card gets a dated update section; history is kept),
   - appends `parts.pending.jsonl` to `parts.jsonl`,
   - appends the lessons section, raises `Repeat` and adds evidence on repeated lessons, marks `[structural habit]` at 3,
   - replaces `intents.md` with the staged copy only if no intent id was lost,
   - appends one decision per candidate in the run file (track, candidate line, decision, reason, artifact and lesson ids, `source_ids`, `reused_compost`) and applies the staged followups / `skip_count` / `stale`,
   - merges the compost files into `compost.jsonl` (`reused_in: []`) and appends this run id to the `reused_in` of reused entries,
   - updates `state.json` last: fingerprints, `last_full_analysis` and `artifacts_since_full` (full: reset; incremental: + new artifacts), `runs`, and `source_stats` with `per_run.<RUN>` for **every** source in `sources.md`,
   - deletes `<WORK>/src/` clones and database copies (the only allowed deletion).
   Output: `saved` counts, `proposals` (threshold candidates), `ledger`, `run_file`. Fix any `error` (usually a bad pending line) and run it again.
2. **Profile** (`<LEDGER>/profile.md`, template): move the previous "Current" section under "History" unchanged, then write a new "Current" section. Every bullet cites decision ids, lesson ids, intent ids, or followups:
   - taste: what gets adopted vs rejected (by track, by kind of candidate),
   - execution: adopted vs started vs done (from followups),
   - recurring lessons and structural habits, active intents.
3. **System proposals** (`<LEDGER>/proposals.md`). Write one only when a threshold is met:
   - from `commit` `proposals` (skip any with `already_proposed: true`): `compost-hotspot` (a rule id in compost entries from 3+ runs, 5+ entries -> change that step's instruction or rubric, citing the compost ids), `idle-source` (enabled in the last 5 runs with 0 citations in adopted candidates -> "Disable `<id>`?", citing those run ids; approval runs `<CLI> sources disable <id>` and records `applied-to: sources.md`), `track-zero-start` (5+ adopts of one track, none started);
   - judgment pattern (your call): 3+ rejections in 2+ runs sharing a reason theme (e.g. "B rejected for operating burden: `2026-10-01:B2`, `2026-10-15:B1`, `2026-10-15:B3` -> require an operating-cost estimate in 05b").
   Format: `## P<n> - <title>` with `status: pending`, `evidence:` (ids), `change:` (file, section, exact edit), `why:`. Ask once: "New system proposals: P3, P4. Approve? (P3 yes, P4 no | skip)". `yes` -> append an override (below), `status: approved <date>`, `applied-to: overrides.md`. `no` -> `status: declined <date>`. `skip` -> stays `pending`. **Never edit files under `<SKILL_DIR>`.**
4. **Overrides** (`<LEDGER>/overrides.md`, append only; a later override for the same target and rule supersedes an earlier one, which stays marked `superseded by O<n>`):

   ```markdown
   ## O1 - references/steps/05b-track-new.md - 05b.ev-no-counter
   - Target: `references/steps/05b-track-new.md` > "Do" item 5 (rule `05b.ev-no-counter`)
   - Change: Before writing counter-evidence, run at least 2 failure-case searches per candidate and list the queries.
   - Proposal: P3 (evidence: `C-2026-10-01-2`, `C-2026-10-15-1`, ...)
   - Approved: 2026-10-15
   ```
5. **Upstream export of overrides (only on request)**: write `export/overrides-<YYYY-MM-DD>.md` with, per chosen override, the repository path (`skills/compost/<target>`), the rule id, a suggested unified diff, and a reason stated with counts only. Strip personal data, project names, compost content, and ledger ids. The user opens the PR; this skill never pushes.
6. **Export (only on request)**: write `export/<RUN>.md` with the export template, stripping personal data and source code. Nothing is ever sent.
7. `<CLI> validate`. Fix every `error` it reports in what you wrote (profile bullets without ids, unknown ids).
8. Finish with 3 lines: ledger path, run file path, counts (adopt / hold / reject, composted).

## Output

- Updated ledger files, `profile.md`, pending or decided proposals.

## Reject if

- [`08.deleted-line`] Any existing JSONL line or markdown section was removed or overwritten instead of appended/marked (clones and DB copies are the only allowed deletions).
- [`08.ev-profile-no-id`] A profile bullet cites no decision, lesson, intent, or followup id (`validate` reports it).
- [`08.ev-proposal-below-threshold`] A proposal was written without meeting a threshold, or without evidence ids.
- [`08.unapproved-change`] An override was written without an explicit yes.
- [`08.edited-skill-files`] Any file under `<SKILL_DIR>` was modified (approved changes belong in `overrides.md`).
- [`08.schema`] A JSONL line is missing a required field or uses a non-English key or enum value (`commit` and `validate` check this).
- [`08.sent-data`] Any ledger content left the machine (short Track B search keywords excepted).
