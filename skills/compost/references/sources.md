# Sources - how Track B reads external signals

Track B reads external signals from the user's source list. This file is the rule book; the shipped list is [default-sources.md](../assets/default-sources.md).
Sources are **read-only**: this skill never runs a scraper, never logs in, never bypasses robots.txt or paywalls, and keeps fetched content only in the run's work directory.

## Which list is used

1. The list that counts is `<LEDGER>/sources.md` (same format as the shipped list).
2. Only if it does not exist (first run, or deleted by hand), `ledger.py` copies the shipped list to `<LEDGER>/sources.md` (`init` and every `sources` command do this). It never overwrites an existing user list.
3. **New defaults after a plugin update**: `init` and `sources list` report `new_default_sources` (default ids not in the user's list; an entry marked `removed` still counts as present). Ask once, in one line: "N new default sources (ids) - add them? (yes / no)". In a pipeline run it goes with the step 0 follow-up question, or alone if there is none; in the `sources` skill it is asked before handling the command. Then `ledger.py sources sync-defaults yes|no`: `yes` appends them; `no` appends them with `enabled: false` so the question is not repeated.
4. **Parsing**: each `## <id>` heading is one source; field lines are `- <field>: <value>`.
5. Use only entries with `enabled: true` and no `removed` date.

## Source types

| type | how to read |
|---|---|
| `web` | WebSearch with the query template, `{keyword}` replaced by a keyword from the parts and lessons. |
| `fetch` | WebFetch the URL. Respect the entry's `limits` and any robots notes. |
| `local` | A folder path, or a git reference `<repo>@<branch>:<path>` on this machine. See below. |

**Korean (and other non-English) domains**: WebSearch results for Korean sites are often thin. When an entry offers both, prefer the `fetch` URL (RSS, list page) over `site:` searches.

### `local` sources

- Folder: read `*.md`, `*.txt`, and `*.json` (cap 50 files, newest first by mtime).
- Git reference `<repo>@<branch>:<path>` (example `~/my-scraper@data:items`):
  - Do **not** run `git fetch`. Read the ref that already exists:
    `git -C <repo> ls-tree --name-only <branch> <path>/` and `git -C <repo> show <branch>:<path>/<file>`.
  - If the branch is missing or looks stale (newest item date older than 14 days), tell the user the command to refresh it (`git -C <repo> fetch origin <branch>`) and continue with what exists.
- JSON items need at least these fields (a file may hold one object or an array); items missing one are skipped and counted:

  | field | type |
  |---|---|
  | `title` | string |
  | `summary` | string |
  | `source_url` | string (URL) |
  | `date` | string `YYYY-MM-DD` |

  Optional: `tags` (string[]), `outcome` (`success` \| `failure` \| `unknown`, helps counter-evidence).
- Markdown files are allowed; the date is the front-matter `date`, a date in the file name, or the mtime marked `mtime`.
- Cite as `<source id>:<relative path>[:line]`.

This is how a user plugs in their own scraper: point a `local` source at its output folder or data branch.

## Reading rules

- Every cited item needs a **source** (URL, or local path) and a **date** `YYYY-MM-DD` (publication date; if none, the access date marked `accessed`).
- Every cited item also records the **source id** it came from, as `[src:<id>]` at the end of the evidence line. Step 8 uses this for source statistics.
- Prefer items from the last 18 months. Older items may be used for failure cases, marked `(old)`.
- Run at least one `failure`-category source for every Track B candidate. Trend and revenue evidence alone is survivorship bias.
- Stay within each entry's `limits`. If a request fails (403, timeout, empty), record it and move on; do not retry more than once.

## Lightweight mode

Applies when the run is `incremental` AND there is exactly 1 `new` artifact AND 0 `changed` artifacts AND that artifact is `idea` or `writing`. Track B then uses **one source per category** (the first enabled entry of each category), with one exception: the `failure` category keeps **both** `failory` and `failure-search` (if enabled). Say so in "Sources checked".

## Request caps

Stay within each entry's `limits`. When a cap is reached, skip the request and write `cap reached (<source id>)` where that evidence would go. Reaching a cap never composts a candidate.

## `sources` subcommand (CRUD)

Used by the `sources` skill, and by the compost skill when its first argument is `sources` and no path named `sources` exists. Every verb is one `ledger.py sources ...` call against `<LEDGER>/sources.md`; the script seeds the list if needed, validates, writes atomically, and prints the changed entry.

| command | script call | behavior |
|---|---|---|
| `sources list` | `sources list` | id, category, type, enabled, removed/restored, and from `state.json` `source_stats`: cited / cited in adopted (`-` when there is no `state.json`). Show it as a table. |
| `sources add [id]` | `sources add [id] --type <t> --how <how> --category <c> [--limits ..] [--notes ..]` | Ask once, one line: `type, how, category` (e.g. `fetch, https://example.com/rss, trend`) and map the answer to the flags. `type`: `web`, `fetch`, `local` (comma-combined). `category`: `trend`, `ai-trend`, `revenue`, `failure`, `community-ko`. On an `error` with allowed values, show them and ask again. Without `id` the script derives a kebab-case slug from `how` (host name for a URL, last path segment for a folder or git ref; `-2`, `-3` on collision). `limits` defaults to the common limit, `enabled: true`. Duplicate ids are rejected. The block goes after the last source, before the trailing "Not included" comment. |
| `sources remove <id>` | `sources remove <id>` | Never deletes: adds `removed: <YYYY-MM-DD>` and sets `enabled: false`. |
| `sources edit <id>` | `sources edit <id>` then `sources edit <id> field=value ...` | The first call shows the entry; ask once for `field=value` pairs on one line (values may be quoted) and pass each pair as one argument. Enums are validated as in `add`. `id` cannot be changed (suggest `remove` + `add`). |
| `sources enable <id>` | `sources enable <id>` | `enabled: true`; a removed entry loses `removed` and gets `restored: <YYYY-MM-DD>`. |
| `sources disable <id>` | `sources disable <id>` | `enabled: false`. |

An unknown verb, a missing id, or an unknown id returns an `error` with the usage line `sources list | add [id] | remove <id> | edit <id> | enable <id> | disable <id>` and the existing ids: show it and stop. After each command, show the changed entry and stop.

## Reporting

In `track-b.md`, under "Sources checked": each source id used, number of items cited, the freshest date seen, and failures (with the error). Mention lightweight mode if it applied.
