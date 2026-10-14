# Step 2 - Analyze

For each artifact: what it tried to do, how far it got, which parts are reusable, and why it stopped.
Then across artifacts: recurring themes and recurring behaviors.

## Inputs

- Intake table and `mode` from step 1.
- The rubric for each type present: [../rubrics/code.md](../rubrics/code.md), [../rubrics/writing.md](../rubrics/writing.md), [../rubrics/idea.md](../rubrics/idea.md). Read only the ones you need.
- Existing ledger cards (`<LEDGER>/artifacts/<id>.md`) and `parts.jsonl` for `unchanged`/`changed` artifacts.
- Recall summary from step 0.
- Card format: [../templates/artifact.md](../templates/artifact.md).

## Do

1. **Pick files (cost guard).** Per artifact, at most **50 core files**, chosen in this order until the cap:
   1. entry points (`main.*`, `index.*`, `app.*`, `cmd/`, `src/` roots, `package.json` `main`/`bin`, `pyproject` scripts),
   2. README / docs top level,
   3. config and manifests (`package.json`, `pyproject.toml`, `Dockerfile`, CI files; never `.env*` or other secret-bearing files),
   4. most recently changed files (`git -C <path> log --name-only --pretty=format: -n 30 | awk 'NF' | awk '!seen[$0]++'`).
   Use the **file filter** from step 1 (same excluded directories and files); also skip vendored, generated, and binary files. Never open a database in place (see SKILL.md "Read-only on inputs"). If the cap was hit, mark the artifact `partial: true` and say how many files exist in total.
   For `changed` artifacts in incremental mode, follow the step 1 table (diff range only for `git-head`/`git-ref`, whole artifact otherwise).
   **Full mode**: also read every card in `<LEDGER>/artifacts/` (not their sources) so patterns and lessons are recomputed across the whole ledger.
   **Secrets**: if a key, token, or password value appears in a file you read, do not quote it anywhere (cards, parts, lessons, queries). Refer to it as `<redacted secret at path:line>` at most.
2. **Summarize** each artifact with the rubric: goal (one sentence), how far it got (completeness 0-100% with the rubric's checkpoints), last activity date.
3. **Extract parts** (reusable pieces). Each part: `kind` (`module` | `sentence` | `problem` | `data` | `design` | `other`), `location` (`path:line-line`, paragraph number, or note line), one-line description, and why it is reusable. Aim for 2-6 strong parts per artifact; quality over count.
   Compare with `<LEDGER>/parts.jsonl` (if it exists) and mark each part `new` or `known` (same artifact and same location/description).
   Write every **new** part as one line to `<LEDGER>/runs/<run-id>.work/parts.pending.jsonl`, using the `parts.jsonl` schema in [08-ledger.md](08-ledger.md) exactly. `id` = `<artifact-id>#p<n>` where `n` = (highest existing `n` for that artifact in `parts.jsonl` and this file) + 1. Do not write `known` parts.
4. **Propose stop reasons** from the evidence, then confirm with **one batched question** for all artifacts:

   ```
   Why did each one stop? (my guess in brackets, correct in one line)
     1 idea-factory      [unfinished]         - 7 of 12 planned features half done, last commit 2026-04-11
     2 podcast-idea      [no-revenue]         - landing page live, 0 paid signups noted in README
   Values: no-revenue | unfinished | abandoned | other   (several allowed: 1 unfinished,abandoned)
   Any value can carry a note in quotes: 1 abandoned "lost interest after demo", 2 no-revenue "nobody paid"
   Answer like: 1 abandoned, 2 ok   |   empty = keep my guesses
   ```
   The user's answer wins. Parse it tolerantly (labels case-insensitive, Korean equivalents such as `미완성`, `수익 없음`, `버림`, `기타`, `그대로` accepted). Record the final reasons, any notes (`stop_reason_notes`, keyed by reason), and whether each came from the user or was accepted as guessed (`stop_reason_source: user | accepted-guess`).
5. **Across artifacts**:
   - Patterns may include artifacts already in the ledger (not in this run's input); mark them `(ledger)` and cite their stored card or part ids.
   - Recurring themes: the same problem, user, or data touched by 2+ artifacts. These raise revival priority. Cite artifact ids.
   - Recurring behaviors: patterns of how the user builds, e.g. "7 features before any user test", "backend before landing page". Cite locations in at least 2 artifacts.
6. **Parts list for the first run.** Even when the ledger is empty, produce the full parts table and the cross-artifact patterns. Step 6 must show them.
7. Write a draft card per artifact (new or changed) to `<LEDGER>/runs/<run-id>.work/artifacts/<id>.md` using the template. Step 8 moves them into `artifacts/`.

## Output

- Per artifact: summary, completeness, parts (with location), stop reasons, `partial` flag.
- Cross-artifact: themes and behaviors with evidence.
- Draft cards and draft part lines (`parts.pending.jsonl`) in the work directory.

## Reject if

Compost (see SKILL.md) each failing item with `kind: part` or `kind: pattern`; do not show it.

- [`02.ev-no-location`] A part has no concrete location (file:line, paragraph, or note line).
- [`02.generic-part`] A part's "why reusable" is generic ("clean code", "good idea") instead of naming what it saves or enables.
- [`02.ev-single-artifact-pattern`] A cross-artifact theme or behavior cites fewer than 2 artifacts.
- [`02.secret-quoted`] A key, token, or password value was quoted, stored, or used in a query.
- [`02.opened-db-in-place`] A database file was opened in place instead of a copy or `?immutable=1`.
- [`02.uncapped`] More than 50 files read for one artifact, or the cap was hit without `partial: true`.
- [`02.reason-not-confirmed`] Stop reasons were written without showing the batched confirmation question.
