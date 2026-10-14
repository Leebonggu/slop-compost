# Rubric - code

Use for artifacts whose primary or secondary type is `code` (repos, folders with source files).

## Completeness checkpoints (0-100%)

Score by the furthest checkpoint with evidence, not by line count.

| % | Checkpoint | Evidence to look for |
|---|---|---|
| 10 | Intent stated | README / first commit message / TODO says what it is for |
| 25 | Skeleton runs | entry point, dependency manifest, a run script |
| 40 | Core path works | the main feature has a code path end to end (input -> output) |
| 60 | Usable by the author | config, sample data, or a CLI/UI to trigger the core path |
| 75 | Usable by a stranger | setup docs, env example, error handling on the core path |
| 90 | Reachable | deployed URL, published package, landing page, or distribution channel |
| 100 | Used | analytics, users, payments, issues from other people |

## Where parts hide

- `module`: self-contained logic with a clear input/output (parsers, scrapers, auth wrappers, prompt chains, data transforms). Stronger if it has tests or is imported from 2+ places.
- `data`: seed data, curated lists, schemas, scraped datasets, prompt libraries.
- `design`: UI components, design tokens, flows in Figma links, landing page copy blocks.
- `problem`: the problem statement in the README or issue list, especially if it names a user.
- Infra snippets (CI, Docker, deploy scripts) count as `module` only if non-trivial.

## Stop signals

| Signal | Suggests |
|---|---|
| Many half-done features, no deploy config | `unfinished` (scope creep) |
| Deployed + payment code, no usage evidence | `no-revenue` |
| Last commits are refactors / dependency bumps, then silence | `abandoned` (motivation faded) |
| TODO list longer than the done list | `unfinished` |
| README pivots or rewrites the goal mid-history | `other` (direction changed) |

Use `git log --format='%ad %s' --date=short -n 40` to read the story; cite commit hashes as evidence locations when useful (`<artifact-id>@<sha>`).

## Pitfalls

- Do not judge code quality as a lesson ("messy code"). Judge what it did to the outcome.
- A big dependency list is not a part. A small function that solved a hard problem is.
- Databases (`*.db`, `*.sqlite`, `*.sqlite3`): never open them in place. Copy the file (and its `-wal`/`-shm`) into the run's work directory and query the copy, or open `file:<path>?immutable=1` (e.g. `sqlite3 'file:/abs/path/app.db?immutable=1' '.tables'`). Even `-readonly` can create or touch the `-shm` file next to the original. Schema and row counts are usually enough; do not dump user data.
