# Step 8 - Ledger

Write everything staged during the run into the ledger, update the personal profile, and propose (never apply) system changes.

## Inputs

- Everything in `<LEDGER>/runs/<run-id>.work/`: `recall.json`, `intake.md`, `artifacts/*.md`, `parts.pending.jsonl`, `lessons.md`, `intents.md`, `compost*.jsonl`, `track-a.md`, `track-b.md`.
- Judgments from step 7. Run file `runs/<run-id>.md` from step 6.
- Templates: [../templates/artifact.md](../templates/artifact.md), [../templates/lesson.md](../templates/lesson.md), [../templates/profile.md](../templates/profile.md), [../templates/export.md](../templates/export.md).

## Ledger layout

```
<LEDGER>/                      # SLOP_COMPOST_HOME, default ~/.slop-compost
├── artifacts/<id>.md         # artifact card (templates/artifact.md)
├── parts.jsonl               # parts index
├── lessons.md                # lessons, dated sections, repeat counts (templates/lesson.md)
├── intents.md                # intents: "Active" and "Ended" sections
├── decisions.jsonl           # one line per judged candidate, with followups
├── compost.jsonl             # outputs that failed a "Reject if" rule
├── profile.md                # personal profile (templates/profile.md)
├── proposals.md              # system change proposals and their status
├── overrides.md              # approved system changes, applied on top of skill files
├── sources.md                # the user's source list (seeded from sources/defaults.md)
├── runs/<run-id>.md          # direction document per run
├── runs/<run-id>.work/       # working files of the run (kept)
├── state.json                # run state and fingerprints
└── export/                   # v1: format only (templates/export.md), nothing is sent
```

## Schemas

All JSONL files: one JSON object per line, UTF-8, keys in English, `at` values are ISO 8601 with offset (`2026-10-15T21:04:00+09:00`). Append only, except the in-place updates explicitly listed below (rewrite the whole file, never drop a line).

### parts.jsonl

| field | type | example |
|---|---|---|
| `id` | string, `<artifact-id>#p<n>` | `"idea-factory#p2"` |
| `artifact_id` | string | `"idea-factory"` |
| `kind` | `module` \| `sentence` \| `problem` \| `data` \| `design` \| `other` | `"module"` |
| `location` | string | `"src/rss/parse.ts:1-88"` |
| `description` | string (user language) | `"RSS fetch + dedupe by URL hash"` |
| `why_reusable` | string (user language) | `"any feed-based product needs it; has tests"` |
| `run` | string, run id where first seen | `"2026-10-15"` |
| `at` | string | `"2026-10-15T21:04:00+09:00"` |

```json
{"id":"idea-factory#p2","artifact_id":"idea-factory","kind":"module","location":"src/rss/parse.ts:1-88","description":"RSS fetch + dedupe by URL hash","why_reusable":"any feed-based product needs it; has tests","run":"2026-10-15","at":"2026-10-15T21:04:00+09:00"}
```
In-place update allowed: none. A changed part gets a new line with a new `#p<n>`.

### decisions.jsonl

| field | type | example |
|---|---|---|
| `id` | string, `<run-id>:<label>` | `"2026-10-15:A1"` |
| `run` | string | `"2026-10-15"` |
| `track` | `A` \| `B` | `"A"` |
| `candidate` | string, one-line definition | `"Cut idea-factory to the daily digest email only"` |
| `decision` | `adopt` \| `hold` \| `reject` | `"adopt"` |
| `reason` | string, may be empty | `"landing first"` |
| `artifact_ids` | string[] | `["idea-factory"]` |
| `lesson_ids` | string[] | `["L2","L4"]` |
| `at` | string | `"2026-10-15T21:10:00+09:00"` |
| `followups` | `{at: string, touched: boolean, result: "not-started"\|"in-progress"\|"done"\|"stopped", note: string}[]` | `[]` |
| `skip_count` | integer | `0` |
| `stale` | boolean | `false` |

Optional: `reused_compost` (string, compost id) for Track B candidates built from compost. Track B lines also carry `source_ids` (string[], the `Source ids:` line of the candidate).

```json
{"id":"2026-10-15:A1","run":"2026-10-15","track":"A","candidate":"Cut idea-factory to the daily digest email only","decision":"adopt","reason":"landing first","artifact_ids":["idea-factory"],"lesson_ids":["L2"],"at":"2026-10-15T21:10:00+09:00","followups":[],"skip_count":0,"stale":false}
```
In-place updates allowed: `followups` (append an element), `skip_count`, `stale` (from step 0).

### compost.jsonl

| field | type | example |
|---|---|---|
| `id` | string, `C-<run-id>-<n>` | `"C-2026-10-15-3"` |
| `run` | string | `"2026-10-15"` |
| `step` | string, step file prefix | `"05b"` |
| `kind` | `lesson` \| `candidate` \| `part` \| `pattern` \| `other` | `"candidate"` |
| `content` | string, the full rejected text | `"B3: ..."` |
| `failed_rules` | string[], rule ids from "Reject if" lists | `["05b.ev-no-counter"]` |
| `at` | string | `"2026-10-15T21:06:00+09:00"` |
| `reused_in` | string[], run ids that revived it | `[]` |

```json
{"id":"C-2026-10-15-3","run":"2026-10-15","step":"05b","kind":"candidate","content":"B3: Slack bot that ...","failed_rules":["05b.ev-no-counter"],"at":"2026-10-15T21:06:00+09:00","reused_in":[]}
```
Rule ids containing `.ev-` are **evidence rules**. An entry whose `failed_rules` are all evidence rules is "reusable compost" for Track B.
In-place update allowed: `reused_in` (append a run id).

### state.json

```json
{
  "version": 1,
  "last_full_analysis": "2026-10-15",
  "artifacts_since_full": 0,
  "runs": ["2026-10-15"],
  "fingerprints": {
    "idea-factory": {"source": "~/playground/idea-factory", "method": "file-hash", "method_version": 2, "value": "777cab6e3903", "at": "2026-10-15T21:00:00+09:00"}
  },
  "source_stats": {
    "failory": {"runs_used": ["2026-10-15", "2026-10-15-2"], "cited": 3, "cited_in_adopted": 1, "last_cited_run": "2026-10-15-2",
                "per_run": {"2026-10-15": {"enabled": true, "cited": 2, "cited_in_adopted": 1},
                            "2026-10-15-2": {"enabled": true, "cited": 1, "cited_in_adopted": 0}}}
  }
}
```
`method`: `git-head` | `git-ref` | `file-hash` | `notion-edited` | `url-modified` | `text-hash` (see the step 1 table). `method_version` (integer, optional): `2` for `file-hash` fingerprints computed from inside the folder over relative paths; a `file-hash` without it is recomputed once (step 1 migration). The existence of `state.json` is what marks "not the first run"; it is written at the end of run 1, which is always full, so `last_full_analysis` is set from run 1 on.
`source_stats.<id>`: `runs_used` (run ids where Track B used the source), `cited` (evidence lines citing it, all candidates shown), `cited_in_adopted` (citations in candidates the user adopted), `last_cited_run`, and `per_run` (`{<run-id>: {enabled: bool, cited: int, cited_in_adopted: int}}`, one entry for every run, including runs where the source was enabled but not used).

## Do

1. `mkdir -p <LEDGER>/artifacts <LEDGER>/runs <LEDGER>/export`.
2. **Artifacts**: move draft cards into `artifacts/<id>.md`. For an existing card, append a dated "Update" section; do not rewrite history.
3. **Parts**: append the lines of `runs/<run-id>.work/parts.pending.jsonl` to `parts.jsonl` (step 2 writes only new parts there, already in the final schema).
4. **Lessons**: append a `## <YYYY-MM-DD> (run <run-id>)` section to `lessons.md` (template). For repeated lessons, add the new evidence under the same id and update its `repeat` line; mark structural habits.
5. **Intents**: apply staged changes to `intents.md` ([../templates/intents.md](../templates/intents.md); move ended ones to "Ended" with date; never delete).
6. **Decisions**: append one line per judged candidate (schema above), taking candidate text, labels, `Source ids:` and `reused_compost` from `runs/<run-id>.md` (the reference document, not the track files). Then apply `recall.json` updates (followups, skip_count, stale) by rewriting `decisions.jsonl` with every line kept.
7. **Compost**: merge `compost.pending.jsonl`, `compost.track-a.jsonl`, `compost.track-b.jsonl` (each line already has `id`, `run`, `step`, `kind`, `content`, `failed_rules`, `at`; fill any missing field), add `reused_in: []`, append to `compost.jsonl`. For each Track B candidate in `runs/<run-id>.md` with `reused_compost`, append this run id to that entry's `reused_in`.
8. **State**: update fingerprints for analyzed artifacts. If `mode == full` (always true on the first run): `last_full_analysis = today`, `artifacts_since_full = 0`. Else: `artifacts_since_full += number of new artifacts`. Append the run id to `runs`.
   **Source stats**: read the `[src:<id>]` tags and `Source ids:` lines in `runs/<run-id>.md`, join with this run's judgments, and update `state.json.source_stats`: add the run id to `runs_used` for every source used, add citation counts, add `cited_in_adopted` for adopted candidates, and write `per_run.<run-id>` = `{enabled, cited, cited_in_adopted}` for **every** source in `<LEDGER>/sources.md` (0 when unused).
   Write `state.json` (fingerprints, counters, source stats) as the last file of this step: its existence marks the ledger as initialized, so an interrupted first run stays a first run.
9. **Profile** (`profile.md`, template): rewrite the current section, keep previous ones under "History". Every statement cites decision ids, lesson ids, or followups:
   - taste: what gets adopted vs rejected (by track, by kind of candidate),
   - execution: adopted vs started vs done (from followups),
   - recurring lessons and structural habits,
   - active intents.
10. **System proposals** (`proposals.md`). Add a proposal only when evidence crosses a threshold:
    - Judgment pattern: 3+ rejections in 2+ runs sharing a reason theme (e.g. "B candidates rejected for operating burden: `2026-10-01:B2`, `2026-10-15:B1`, `2026-10-15:B3` -> require an operating-cost estimate in 05b").
    - Track statistics: one track's adopt-to-start rate is 0 across 5+ adopts.
    - **Compost hot spot**: the same rule id appears in compost entries from **3 or more runs** with **5 or more entries** total -> propose changing that step's instruction or the rubric behind it, citing the compost ids.
    - **Idle source**: over the 5 most recent run ids in `state.json.runs`, the source's `per_run` shows `enabled: true` in all 5 and `cited_in_adopted: 0` in all 5 -> propose "Disable `<id>`?" citing those run ids. Approval sets `enabled: false` in `<LEDGER>/sources.md` (not deleted) and records `applied-to: sources.md`.
    Format: `## P<n> - <title>` with `status: pending`, `evidence:` (ids), `change:` (file, section, exact edit), `why:`.
    Then ask once: "New system proposals: P3, P4. Approve? (P3 yes, P4 no | skip)".
    - `yes` -> append an override to `<LEDGER>/overrides.md` (format below) and set the proposal to `status: approved <date>` plus `applied-to: overrides.md`.
    - `no` -> `status: declined <date>`. `skip` -> stays `pending`.
    - **Never edit files under `<SKILL_DIR>`.** Overrides live in the ledger, so plugin updates do not erase them and the skill files stay identical for everyone.
11. **Overrides format** (`<LEDGER>/overrides.md`, append only; a later override for the same target and rule supersedes an earlier one, which stays in the file marked `superseded by O<n>`):

    ```markdown
    ## O1 - steps/05b-track-new.md - 05b.ev-no-counter
    - Target: `steps/05b-track-new.md` > "Do" item 5 (rule `05b.ev-no-counter`)
    - Change: Before writing counter-evidence, run at least 2 failure-case searches per candidate and list the queries.
    - Proposal: P3 (evidence: `C-2026-10-01-2`, `C-2026-10-15-1`, ...)
    - Approved: 2026-10-15
    ```
12. **Upstream export of overrides (only on request).** If the user wants to send an override back to the skill's repository, write `export/overrides-<YYYY-MM-DD>.md`: for each chosen override, the repository path (`skills/slop-compost/<target>`), the rule id, a suggested unified diff against the current file text, and a reason stated with counts only (e.g. "rule failed 6 times across 4 runs"). Strip personal data, project names, compost content, and ledger ids. The user opens the PR themselves; this skill never pushes or opens PRs.
13. **Export**: v1 does not send anything (the only thing that ever leaves the machine is short Track B search keywords, never file contents, secrets, or personal data). Only if the user asks for an export, write `export/<run-id>.md` with [../templates/export.md](../templates/export.md), stripping personal data and source code.
14. **Clean up copies** (the one explicit exception to "never delete"): remove `<LEDGER>/runs/<run-id>.work/src/` (repository clones) and any database copies made in the work directory, so the ledger does not hold a duplicate of the user's code or data. Everything else in the work directory stays.
15. Finish with a 3-line summary: ledger path, run file path, counts (adopt / hold / reject, composted).

## Output

- Updated ledger files listed above.
- Pending or decided proposals in `proposals.md`.

## Reject if

- [`08.deleted-line`] Any existing JSONL line or markdown section was removed or overwritten instead of appended/marked (clones and DB copies in Do 14 are the only allowed deletions).
- [`08.ev-profile-no-id`] A profile statement cites no decision, lesson, or followup id.
- [`08.ev-proposal-below-threshold`] A proposal was written without meeting a threshold, or without evidence ids.
- [`08.unapproved-change`] An override was written without an explicit yes.
- [`08.edited-skill-files`] Any file under `<SKILL_DIR>` was modified (approved changes belong in `overrides.md`).
- [`08.schema`] A JSONL line is missing a required field or uses a non-English key or enum value.
- [`08.sent-data`] Any ledger content left the machine (short Track B search keywords excepted).
