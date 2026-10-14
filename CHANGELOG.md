# Changelog

All notable changes to slop-compost. Versions follow `.claude-plugin/plugin.json`.

## 0.2.0 - 2026-10-15

Structure and token rework. Pipeline behavior, rules, and ledger format are unchanged; v0.1.1 ledgers are read as they are.

### Changed
- Skills split and renamed: the pipeline is `compost` (`/slop-compost:compost`), source-list management is `sources` (`/slop-compost:sources`). Manual install links both `skills/compost` and `skills/sources` into `~/.claude/skills/` as siblings.
- Standard skill layout: `scripts/` (code), `references/` (step guides, rubrics, source rules, schemas; read on demand), `assets/` (templates, shipped source list).
- `SKILL.md` is a short orchestrator; each step guide replaces mechanical procedures with one script call. Record schemas moved to `references/schemas.md`, read only when a record is written by hand.
- Track subagents run on `SLOP_COMPOST_TRACK_MODEL` (default `sonnet`) and get only absolute paths in their briefs.
- Folder fingerprints use `method_version: 3` (also excludes `vendor/`, `third_party/`, `generated/`, minified files, databases). Older `file-hash` fingerprints are recomputed once and count as unchanged.

### Added
- `scripts/ledger.py` (Python 3.9+, standard library only, no network): `init`, `fingerprint`, `select-files`, `recall`, `apply-recall`, `bundle`, `lint`, `judge`, `commit`, `validate`, `sources`. Each prints one compact JSON line, so the model reads summaries instead of ledger files. Writes are atomic and schema-checked; `commit` writes nothing if any new record fails.
- `allowed-tools` in both skills pre-approves the script call for the turn that invokes the skill.
- `sources sync-defaults yes|no` applies the answer to the "new default sources" question.
- Unit tests (`tests/test_ledger.py`, v0.1.1 ledger fixture) and a GitHub Actions workflow on Python 3.9 and 3.12.
- Env var `SLOP_COMPOST_TRACK_MODEL`.

## 0.1.1 - 2026-10-15

- Follow-up loop no longer stops after a "not touched" answer; skip count resets on any answer.
- Track A compost no longer leaks into Track B input.
- Absolute path literals instead of shell variables in step files.
- `first_run` = no `state.json`; `sources.md` seeded only when missing.
- Secrets excluded and never quoted; untrusted-content rule; clones and database copies cleaned at the end of a run.
- Path-normalized fingerprints, changed-artifact handling, all-unchanged flow.
- Source request caps, per-run source stats, `sources` CRUD gaps.
- Korean answer parsing for recall and intent; at most 7 lessons per run (0 allowed).

## 0.1.0 - 2026-10-15

- First release: 9-step pipeline (recall, intake, analyze, lessons, intent, two independent tracks, direction, judge, ledger), local ledger, compost for rejected output, 9 default external sources with `sources` CRUD, incremental and full analysis.
