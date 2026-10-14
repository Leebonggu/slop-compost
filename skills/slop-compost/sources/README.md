# Sources - how Track B reads external signals

Track B reads external signals from the user's source list. This file is the rule book; the shipped list is [defaults.md](defaults.md).
Sources are **read-only**: this skill never runs a scraper, never logs in, never bypasses robots.txt or paywalls, and keeps fetched content only in the run's work directory.

## Which list is used

1. The list that counts is `$LEDGER/sources.md` (same format as `defaults.md`).
2. If it does not exist (first run, or deleted by hand), copy `${CLAUDE_SKILL_DIR}/sources/defaults.md` to `$LEDGER/sources.md` before Track B starts (step 0 does this).
3. **New defaults after a plugin update**: if `defaults.md` has ids that are not in the user's list (including entries marked `removed`), say once, in one line: "N new default sources (ids) - add them? (yes / no)". `yes` appends them; `no` appends them with `enabled: false` so the question is not repeated.
4. Use only entries with `enabled: true` and no `removed` date.

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

If the run is `incremental` and the only new artifact is a single `idea` or `writing` artifact, Track B uses **one source per category** (the first enabled entry of each category; `failure` always included). Say so in "Sources checked".

## `sources` subcommand (CRUD)

When the first word of the arguments is `sources`, SKILL.md skips the pipeline and handles the list in `$LEDGER/sources.md` (seed it from defaults first if missing):

| command | behavior |
|---|---|
| `sources list` | Table: id, category, type, enabled, removed, and from `state.json.source_stats`: cited / cited in adopted. |
| `sources add [id]` | Ask once, one line: `type, how, category` (e.g. `fetch, https://example.com/rss, trend`). Fill `limits` with the common default, `enabled: true`. Reject duplicate ids. |
| `sources remove <id>` | Do not delete. Add `removed: <YYYY-MM-DD>` and `enabled: false`. |
| `sources edit <id>` | Show the entry, ask once for `field=value` pairs on one line, apply. |
| `sources enable <id>` / `sources disable <id>` | Set `enabled`. |

After each command, show the changed entry and stop.

## Reporting

In `track-b.md`, under "Sources checked": each source id used, number of items cited, the freshest date seen, and failures (with the error). Mention lightweight mode if it applied.
