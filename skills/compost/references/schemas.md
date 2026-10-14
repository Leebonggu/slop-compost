# Ledger layout and record schemas

Read this only when you must write or inspect a record by hand: `ledger.py` (`commit`, `validate`) writes and checks every record below.

## Ledger layout

```
<LEDGER>/                      # SLOP_COMPOST_HOME, default ~/.slop-compost
├── artifacts/<id>.md         # artifact card (assets/templates/artifact.md)
├── parts.jsonl               # parts index
├── lessons.md                # lessons, dated sections, repeat counts (assets/templates/lesson.md)
├── intents.md                # intents: "Active" and "Ended" sections
├── decisions.jsonl           # one line per judged candidate, with followups
├── compost.jsonl             # outputs that failed a "Reject if" rule
├── profile.md                # personal profile (assets/templates/profile.md)
├── proposals.md              # system change proposals and their status
├── overrides.md              # approved system changes, applied on top of skill files
├── sources.md                # the user's source list (seeded from assets/default-sources.md)
├── runs/<run-id>.md          # direction document per run
├── runs/<run-id>.work/       # working files of the run (kept)
├── state.json                # run state and fingerprints
└── export/                   # v1: format only (assets/templates/export.md), nothing is sent
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
    "idea-factory": {"source": "~/playground/idea-factory", "method": "file-hash", "method_version": 3, "value": "777cab6e3903", "at": "2026-10-15T21:00:00+09:00"}
  },
  "source_stats": {
    "failory": {"runs_used": ["2026-10-15", "2026-10-15-2"], "cited": 3, "cited_in_adopted": 1, "last_cited_run": "2026-10-15-2",
                "per_run": {"2026-10-15": {"enabled": true, "cited": 2, "cited_in_adopted": 1},
                            "2026-10-15-2": {"enabled": true, "cited": 1, "cited_in_adopted": 0}}}
  }
}
```
`method`: `git-head` | `git-ref` | `file-hash` | `notion-edited` | `url-modified` | `text-hash` (see step 1). `method_version` (integer, `file-hash` only): `3` = computed by `ledger.py fingerprint` from inside the folder over relative paths with the current filter (v0.1.1 wrote `2`, earlier runs none). An older or missing version is recomputed once and treated as `unchanged` (migration). The existence of `state.json` is what marks "not the first run"; it is written at the end of run 1, which is always full, so `last_full_analysis` is set from run 1 on.
`source_stats.<id>`: `runs_used` (run ids where Track B used the source), `cited` (evidence lines citing it, all candidates shown), `cited_in_adopted` (citations in candidates the user adopted), `last_cited_run`, and `per_run` (`{<run-id>: {enabled: bool, cited: int, cited_in_adopted: int}}`, one entry for every run, including runs where the source was enabled but not used).

## Work directory (`runs/<run-id>.work/`)

Staged by the script or the steps during a run; `commit` reads them. Kept after the run except `src/` and database copies.

| file | written by | content |
|---|---|---|
| `run.json` | `init` | run id, `mode_hint`, `first_run` |
| `fingerprints.json` | `fingerprint` | per artifact id: input, kind, method, `method_version`, value, status, source, at |
| `recall.json` | `apply-recall` | `updates` per decision id: `followup` and/or `skip_count`, `stale` |
| `intake.md`, `artifacts/<id>.md` | steps 1-2 | intake table, draft cards |
| `parts.pending.jsonl` | step 2 | new parts (`run`, `at` may be omitted) |
| `lessons.md`, `intents.md` | steps 3-4 | lesson entries, full intents copy |
| `input-a.md`, `input-b.md` | `bundle` | track inputs |
| `track-a.md`, `track-b.md` | step 5 | track outputs |
| `compost.pending.jsonl`, `compost.track-a.jsonl`, `compost.track-b.jsonl` | `lint --compost`, steps | composted items (`reused_in` added by `commit`) |
| `judgments.json` | `judge` | per label: track, decision, reason |
