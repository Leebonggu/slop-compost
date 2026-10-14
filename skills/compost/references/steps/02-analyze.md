# Step 2 - Analyze

For each artifact: what it tried to do, how far it got, which parts are reusable, and why it stopped.
Then across artifacts: recurring themes and recurring behaviors.

## Inputs

- Step 1 output (ids, types, status, `changed_files`, `next_part`, `card`) and `mode`.
- The rubric for each type present: [../rubrics/code.md](../rubrics/code.md), [../rubrics/writing.md](../rubrics/writing.md), [../rubrics/idea.md](../rubrics/idea.md). Read only the ones you need.
- For artifacts with `card: true`: `<LEDGER>/artifacts/<id>.md` (it lists the known parts).
- Recall summary from step 0. Card format: [../../assets/templates/artifact.md](../../assets/templates/artifact.md).

## Do

1. **Pick files.** Local folders: `<CLI> select-files <folder> --max 50`. Read only the listed files (top or relevant range for long ones). `partial: true` means the cap was hit: mark the card `partial: true` and say how many files exist (`total`). `databases` lists database files: never open them in place (SKILL.md). Changed artifacts in incremental mode: read only `changed_files` for `git-head`/`git-ref`.
   **Full mode**: also read every card in `<LEDGER>/artifacts/` (not their sources) so patterns and lessons are recomputed across the ledger.
   **Secrets**: if a key, token, or password value appears in a file you read, never quote it; at most write `<redacted secret at path:line>`.
2. **Summarize** each artifact with its rubric: goal (one sentence), how far it got (0-100% by the rubric's checkpoints), last activity date.
3. **Extract parts**: `kind` (`module` | `sentence` | `problem` | `data` | `design` | `other`), `location` (`path:line-line`, paragraph, or note line), one-line description, why it is reusable. 2-6 strong parts per artifact.
   Compare with the known parts in the card; skip `known` ones (same location/description). Append each **new** part as one JSON line to `<WORK>/parts.pending.jsonl` with `id`, `artifact_id`, `kind`, `location`, `description`, `why_reusable` (`run` and `at` are filled by `commit`). Number ids from `next_part` upward (`proj#p3`, `proj#p4`, ...).
4. **Stop reasons**: propose them from the evidence and confirm with **one batched question** for all artifacts:

   ```
   Why did each one stop? (my guess in brackets, correct in one line)
     1 idea-factory      [unfinished]         - 7 of 12 planned features half done, last commit 2026-04-11
     2 podcast-idea      [no-revenue]         - landing page live, 0 paid signups noted in README
   Values: no-revenue | unfinished | abandoned | other   (several allowed: 1 unfinished,abandoned)
   Any value can carry a note in quotes: 1 abandoned "lost interest after demo", 2 no-revenue "nobody paid"
   Answer like: 1 abandoned, 2 ok   |   empty = keep my guesses
   ```
   The user's answer wins (Korean equivalents such as `미완성`, `수익 없음`, `버림`, `기타`, `그대로` are fine). Record the reasons, notes (`stop_reason_notes`), and `stop_reason_source: user | accepted-guess`.
5. **Across artifacts** (also on the first run): themes (same problem, user, or data in 2+ artifacts; they raise revival priority) and behaviors (how the user builds, e.g. "7 features before any user test"), each citing 2+ artifacts. Ledger artifacts may be cited, marked `(ledger)`.
6. **Draft cards** in `<WORK>/artifacts/<id>.md`. New artifact: the full card from the template. Existing card: only what changed (new parts, new stop reasons, notes) plus any front-matter keys to update (`fingerprint`, `stop_reasons`, `partial`, ...); `commit` appends it as a dated update section and never rewrites history.

## Output

- Per artifact: summary, completeness, parts, stop reasons, `partial`. Cross-artifact themes and behaviors with evidence.
- `<WORK>/artifacts/*.md`, `<WORK>/parts.pending.jsonl`.

## Reject if

Compost each failing item (`kind: part` or `kind: pattern`, write the line to `<WORK>/compost.pending.jsonl` with `step: "02"`); do not show it.

- [`02.ev-no-location`] A part has no concrete location (file:line, paragraph, or note line).
- [`02.generic-part`] A part's "why reusable" is generic ("clean code", "good idea") instead of naming what it saves or enables.
- [`02.ev-single-artifact-pattern`] A cross-artifact theme or behavior cites fewer than 2 artifacts.
- [`02.secret-quoted`] A key, token, or password value was quoted, stored, or used in a query.
- [`02.opened-db-in-place`] A database file was opened in place instead of a copy or `?immutable=1`.
- [`02.uncapped`] More than 50 files read for one artifact, or the cap was hit without `partial: true`.
- [`02.reason-not-confirmed`] Stop reasons were written without showing the batched confirmation question.
