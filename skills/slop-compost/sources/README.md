# Sources - how Track B reads external signals

Track B reads external signals from the user's source list. This file is the rule book; the shipped list is [defaults.md](defaults.md).
Sources are **read-only**: this skill never runs a scraper, never logs in, never bypasses robots.txt or paywalls, and keeps fetched content only in the run's work directory.

## Which list is used

1. The list that counts is `<LEDGER>/sources.md` (same format as `defaults.md`).
2. Only if it does not exist (first run, or deleted by hand), copy `<SKILL_DIR>/sources/defaults.md` to `<LEDGER>/sources.md` (step 0 does this; the `sources` subcommand does it too). Never overwrite an existing user list.
3. **New defaults after a plugin update**: if `defaults.md` has ids not present in the user's list (an entry marked `removed` still counts as present), ask once, in one line: "N new default sources (ids) - add them? (yes / no)". In a pipeline run it goes with the step 0 follow-up question, or alone if there is none; in the `sources` subcommand it is asked before handling the command. `yes` appends them; `no` appends them with `enabled: false` so the question is not repeated.
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

When the first word of the arguments is `sources` and no path named `sources` exists, SKILL.md skips the pipeline and handles the list in `<LEDGER>/sources.md`. Before the command: seed the list from defaults if it does not exist, and ask the new-defaults question if it applies (see "Which list is used").

| command | behavior |
|---|---|
| `sources list` | Table: id, category, type, enabled, removed/restored, and from `<LEDGER>/state.json` `source_stats`: cited / cited in adopted. If `state.json` does not exist, show `-` in the statistics columns. |
| `sources add [id]` | Ask once, one line: `type, how, category` (e.g. `fetch, https://example.com/rss, trend`). Validate `type` (`web`, `fetch`, `local`, comma-combined) and `category` (`trend`, `ai-trend`, `revenue`, `failure`, `community-ko`); on an invalid value, show the allowed values and ask again. If `id` is omitted, derive a kebab-case slug from `how` (host name for a URL, last path segment for a folder or git ref; add `-2`, `-3` on collision). Fill `limits` with the common default, `enabled: true`. Reject duplicate ids. Insert the new `## <id>` block right after the last existing `## ` source, before the trailing "Not included" comment block. |
| `sources remove <id>` | Do not delete. Add `removed: <YYYY-MM-DD>` and set `enabled: false`. |
| `sources edit <id>` | Show the entry, ask once for `field=value` pairs on one line, one pair per field, values may be quoted (`how="site:example.com {keyword}" limits="1 search"`). Validate enums as in `add`. The `id` cannot be changed (suggest `remove` + `add`). |
| `sources enable <id>` | Set `enabled: true`. If the entry has `removed`, clear it and add `restored: <YYYY-MM-DD>`. |
| `sources disable <id>` | Set `enabled: false`. |

An unknown verb, a missing id where one is required, or an id that does not exist: print the usage line `sources list | add [id] | remove <id> | edit <id> | enable <id> | disable <id>` and the existing ids, then stop.

After each command, show the changed entry and stop.

## Reporting

In `track-b.md`, under "Sources checked": each source id used, number of items cited, the freshest date seen, and failures (with the error). Mention lightweight mode if it applied.
