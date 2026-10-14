---
name: slop-compost
description: Turn abandoned side projects and AI slop (code repos, drafts, half-baked ideas) into compost for the next idea - reusable parts and evidence-backed lessons - then propose two independent directions - revive the original (Track A) or grow a new idea from the parts, backed by external signals and counter-evidence (Track B). The user's adopt/hold/reject judgments accumulate in a local ledger so later runs fit them better. Use when the user wants to revive, post-mortem, compost, or salvage an abandoned project or idea - e.g. "revive this", "abandoned project", "side project post-mortem", "compost my slop", "what can I salvage", "슬롭 부활", "버린 프로젝트", "만들다 만 거", "아이디어 되살려", "퇴비", "실패작", "실패는 성공의 어머니".
argument-hint: "<paths|urls|repo@branch:path|text...> [--full] | sources list|add|remove|edit|enable|disable [id]"
---

# slop-compost (orchestrator)

Failure is the mother of success: abandoned work is compost, not trash.

You run a 9-step pipeline (0-8) over abandoned artifacts. This file only sets the order, shared rules, and paths.
**Read each step file only when you enter that step** (not before) to save context.

Skill directory: `${CLAUDE_SKILL_DIR}`. Every relative path in the step, rubric, source and template files
resolves against this directory. When you hand a file to a subagent, give it the absolute path
(`${CLAUDE_SKILL_DIR}/...`), because subagents do not see this file.

Arguments given by the user: `$ARGUMENTS`

## Subcommand: `sources`

If the first word of the arguments is `sources`, do **not** run the pipeline. Resolve `$LEDGER` (below), read
`${CLAUDE_SKILL_DIR}/sources/README.md` section "`sources` subcommand (CRUD)", handle the command against `$LEDGER/sources.md`, and stop.

## Language (applies to every step)

1. If env `SLOP_COMPOST_LANG` is `ko` or `en`, use it. Otherwise detect the language of the user's messages and arguments.
2. Write **all** user-facing output, questions, and ledger prose (artifact cards, lessons, intents, profile, runs, proposals) in that language. Translate template headings.
3. Keep these in English no matter what: JSON/JSONL keys, file names, ids, and enum values
   (`adopt|hold|reject`, `no-revenue|unfinished|abandoned|other`, track `A|B`, part kinds, `partial`, `stale`).
4. Check the language with: `printenv SLOP_COMPOST_LANG`.

## Ledger and settings

Resolve once at the start with Bash and reuse the values:

| Setting | Env var | Default |
|---|---|---|
| Ledger root (`$LEDGER` below) | `SLOP_COMPOST_HOME` | `~/.slop-compost` |
| Output language | `SLOP_COMPOST_LANG` | auto-detect |
| Full re-analysis threshold | `SLOP_COMPOST_FULL_EVERY` | `10` |

```bash
echo "LEDGER=${SLOP_COMPOST_HOME:-$HOME/.slop-compost}"; echo "LANG=${SLOP_COMPOST_LANG:-auto}"; echo "FULL_EVERY=${SLOP_COMPOST_FULL_EVERY:-10}"
```

Ledger layout and every record schema: [steps/08-ledger.md](steps/08-ledger.md) (read it at step 8, or earlier only if a step tells you to).
The ledger is local only. Never send ledger content anywhere.

**Sources**: Track B reads the user's list `$LEDGER/sources.md`, seeded from [sources/defaults.md](sources/defaults.md). Rules: [sources/README.md](sources/README.md).

**Overrides**: if `$LEDGER/overrides.md` exists, read it once at the start. It holds system changes the user approved (step 8). Each time you read a step, rubric, source or template file, apply the overrides whose target is that file **on top of it; an override wins over the file's text**. Pass the relevant overrides to the track subagents inside their briefs. Never edit files under `${CLAUDE_SKILL_DIR}`.

**Run id**: `YYYY-MM-DD` (today). If `$LEDGER/runs/<that>.md` exists, append `-2`, `-3`, ... Working files for this run go in `$LEDGER/runs/<run-id>.work/`.

**Arguments**: `--full` forces full re-analysis. Everything else is an input artifact (path, URL, `<repo>@<branch>:<path>`, or text).

**Mode**: `full` if this is the first run (no ledger), or `--full` is in the arguments, or `state.json.artifacts_since_full >= FULL_EVERY`; otherwise `incremental`. Step 1 decides this.

**Scope** (what each step looks at):
- The **run scope** is the artifacts given in this run's input. Steps 2-3 analyze only these (and only their changes in incremental mode).
- Cross-artifact patterns may also cite artifacts already in the ledger; mark those `(ledger)`.
- Track A works on run-scope artifacts. Track B gets **all** parts in `parts.jsonl` plus this run's new parts.

## Global rules

- **The user decides.** Stop at proposing directions. Never start building, never edit the user's projects.
- **Read-only on inputs.** Do not modify the analyzed repos, folders, or pages. Do not run their code.
  Databases (SQLite and similar): never open them in place. Copy the file (with its `-wal`/`-shm` if present) into the work directory and query the copy, or open it as `file:<path>?immutable=1`. Warning: even `-readonly` mode can create or touch the `-shm` file next to the original.
- **No unsupported claims.** A lesson without an evidence location is composted. A direction without a 7-day first experiment and a numeric success criterion is composted. A Track B candidate without dated external evidence and counter-evidence is composted. Each step file ends with a "Reject if" checklist: apply it before you show output.
- **Compost, don't discard.** Output that fails a "Reject if" rule is removed from what the user sees but kept: collect it in `$LEDGER/runs/<run-id>.work/compost.pending.jsonl` (one JSON line per item, with `kind` and the failed rule ids; the track subagents write `compost.track-a.jsonl` / `compost.track-b.jsonl` instead, to avoid parallel writes) and step 8 appends it to `$LEDGER/compost.jsonl`. Even this skill's own slop is material for system fixes (step 8) and for Track B (step 5b).
- **Never delete.** Rejected candidates, old lessons, old intents, removed sources stay in the ledger. Append or mark, never remove.
- **System rules change only with approval.** You may *propose* changes to rubrics/steps/sources (step 8). Approved changes go to `$LEDGER/overrides.md` (or `$LEDGER/sources.md` for source switches), never into the skill files.
- **Batch questions.** Ask each step's questions in one message and accept one-line answers. Do not ask candidate by candidate.
- **Permission blocks do not stop the run.** Show the one-line fix for what failed, continue with the rest.
- **Cost guard.** Max 50 core files per artifact (step 2). If more than 10 artifacts arrive, ask whether to analyze all at once before step 2.

## Pipeline

| Step | File | Ask user? | Writes |
|---|---|---|---|
| 0 Recall | [steps/00-recall.md](steps/00-recall.md) | one batched follow-up question (if past adopts exist) | `decisions.jsonl` followups, seeds `sources.md` |
| 1 Intake | [steps/01-intake.md](steps/01-intake.md) | only if inputs missing, blocked, or >10 artifacts | working copies list |
| 2 Analyze | [steps/02-analyze.md](steps/02-analyze.md) + [rubrics/code.md](rubrics/code.md), [rubrics/writing.md](rubrics/writing.md), [rubrics/idea.md](rubrics/idea.md) | one batched stop-reason confirmation | artifact drafts |
| 3 Lessons | [steps/03-lessons.md](steps/03-lessons.md) | no | lesson drafts |
| 4 Intent | [steps/04-intent.md](steps/04-intent.md) | one optional question | intent draft |
| 5 Tracks | [steps/05a-track-revive.md](steps/05a-track-revive.md), [steps/05b-track-new.md](steps/05b-track-new.md), [sources/README.md](sources/README.md) | no | `track-a.md`, `track-b.md` |
| 6 Direction | [steps/06-direction.md](steps/06-direction.md) | no | `runs/<run-id>.md` |
| 7 Judge | [steps/07-judge.md](steps/07-judge.md) | one batched judgment line | judgments |
| 8 Ledger | [steps/08-ledger.md](steps/08-ledger.md) | approval only for system proposals | all ledger files incl. `compost.jsonl`, `overrides.md` |

Templates: [templates/artifact.md](templates/artifact.md), [templates/lesson.md](templates/lesson.md), [templates/direction.md](templates/direction.md), [templates/profile.md](templates/profile.md), [templates/export.md](templates/export.md).

### Step flow

1. **Step 0** - Read `${CLAUDE_SKILL_DIR}/steps/00-recall.md`. If the ledger does not exist, mark `first_run` (mode will be `full`) and continue.
2. **Step 1** - Read `${CLAUDE_SKILL_DIR}/steps/01-intake.md`. If `$ARGUMENTS` is empty, ask once what to analyze (paths, URLs, or a sentence about the idea).
3. **Step 2** - Read `${CLAUDE_SKILL_DIR}/steps/02-analyze.md`, then only the rubric(s) for the artifact types present.
4. **Step 3** - Read `${CLAUDE_SKILL_DIR}/steps/03-lessons.md`.
5. **Step 4** - Read `${CLAUDE_SKILL_DIR}/steps/04-intent.md`. The user may skip.
6. **Step 5** - Write the two input bundles described in step 5 below, show the size line, then launch both tracks.
7. **Step 6** - Read `${CLAUDE_SKILL_DIR}/steps/06-direction.md`. Put both tracks side by side. Show it to the user.
8. **Step 7** - Read `${CLAUDE_SKILL_DIR}/steps/07-judge.md`. One batched judgment line.
9. **Step 8** - Read `${CLAUDE_SKILL_DIR}/steps/08-ledger.md`. Write everything. End with a short summary of what was saved and where.

### Step 5: two independent tracks

Purpose: Track B must not be anchored on Track A's framing, and vice versa (confirmation-bias guard).

1. Write `$LEDGER/runs/<run-id>.work/input-a.md`: run-scope artifact summaries, their parts, stop reasons, lessons, active intents, profile excerpt.
2. Write `$LEDGER/runs/<run-id>.work/input-b.md`: lessons, **all** parts (`parts.jsonl` + this run's new parts, with source artifact id), active intents, profile excerpt, past rejected Track B candidates with reasons, and **reusable compost**: entries of `$LEDGER/compost.jsonl` with `kind: candidate` whose `failed_rules` are all evidence rules (rule ids containing `.ev-`). No artifact summaries beyond one line each.
   **Scrub Track A from input-b**: any profile sentence or rejection reason that names a Track A label or describes a Track A candidate is generalized or dropped (e.g. "overlaps with A1" -> "duplicate of another candidate").
3. **Size line**: before launching, show one line, e.g. "Tracks: 2 (parallel) - Track B sources: 9 (lightweight: 5)". Lightweight mode (one source per category) applies when the mode is `incremental` and the only new artifact is a single `idea` or `writing` artifact; see [sources/README.md](sources/README.md).
4. **If the Agent tool is available**: launch **two subagents in the same message** (parallel, `general-purpose`):
   - Track A brief: "Read `${CLAUDE_SKILL_DIR}/steps/05a-track-revive.md` and follow it. Input: `<abs path to input-a.md>`. Write your result to `<abs path>/track-a.md`. Output language: `<lang>`. Overrides for 05a: `<text or none>`. Do not read track-b.md or input-b.md."
   - Track B brief: "Read `${CLAUDE_SKILL_DIR}/steps/05b-track-new.md` and `${CLAUDE_SKILL_DIR}/sources/README.md` and follow them. Input: `<abs path to input-b.md>`. Source list: `<abs path to $LEDGER/sources.md>`. Lightweight: `<yes|no>`. Write your result to `<abs path>/track-b.md`. Output language: `<lang>`. Overrides for 05b/sources: `<text or none>`. Do not read track-a.md or input-a.md."
   - Never paste one track's output into the other's brief.
5. **Fallback (no subagents)**: read `05a`, write Track A, save `track-a.md`, and treat it as frozen. Then read `05b` + `sources/README.md` and write Track B **from input-b.md only**, without re-reading or referring to Track A. Do not edit `track-a.md` after Track B starts. Note `fallback: sequential` in the run file.
6. After both finish, apply each track file's "Reject if" list yourself as a second check. Move failing candidates to `compost.pending.jsonl` (subagents already wrote their own composted items to `compost.track-*.jsonl`).

## Output to the user

- Keep chat output short: the direction (step 6) is the main deliverable. Everything else is saved to the ledger.
- Always end the run with: ledger path, run file path, and how many candidates were adopted / held / rejected.
