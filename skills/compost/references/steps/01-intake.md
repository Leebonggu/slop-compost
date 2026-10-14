# Step 1 - Intake

Turn whatever the user handed over into a list of artifacts with a type, a readable working copy, and a fingerprint.

## Inputs

- `$ARGUMENTS` and the user's message: local paths (folders or files), git references `<repo>@<branch>:<path>`, GitHub URLs, Notion pages, other URLs, free text. Mixed is fine.
- `init` output: `mode_hint`, `bulk_question`.

## Do

1. **Split inputs** into artifacts: one path / URL = one artifact; free text = one artifact per distinct idea (a bullet list of ideas = several texts).
2. **Count.** If `bulk_question` is true (more than 10), ask once: "N artifacts. Analyze all now (slower, more tokens) or pick a subset? (all | list of numbers)". Wait for the answer.
3. **Fingerprint**: `<CLI> fingerprint --run <RUN> <input> [<input> ...] [--as <id> ...]`. One call for all inputs (quote each). Per input it returns `kind`, `method`, `value`, `status` (`new` | `changed` | `unchanged` | `blocked` | `pending`), `artifact_id`, `card`, `next_part`, and for local folders `files_total` and `type_hint`. It stages `<WORK>/fingerprints.json` for step 8.
   - **Ids**: the script reuses the ledger id for the same source (or same text hash) and otherwise derives a kebab-case id. For free text, give a better id with `--as <id>` in input order (`podcast-from-newsletter`). Ledger ids never change.
   - Folder hashing runs from inside the folder over relative paths with the shared filter (no `.git node_modules .venv venv .next dist build __pycache__ .omc .claude logs vendor third_party generated`, no locks, databases, minified files, or secret-bearing files). A stored `file-hash` from an older `method_version` is recomputed once and counts as `unchanged` (`migrated_from_version`).
   - **Git reference**: the script uses `git rev-parse <branch>:<path>` and never fetches. `blocked` gives the refresh command; show it.
   - **`needs_llm: true`** (GitHub URL, Notion, other URL): fetch it yourself, then record the fingerprint with `<CLI> fingerprint --run <RUN> --set <artifact_id> <method> <value>`:

     | kind | fetch read-only | `value` |
     |---|---|---|
     | `github-url` | `git clone --depth 50 <url> <WORK>/src/<id>` (private: `gh repo clone <owner/repo> <dir> -- --depth 50`); `commit` deletes the clone | `git -C <dir> rev-parse HEAD` |
     | `notion` | Notion MCP fetch tool if connected | page `last_edited_time` |
     | `url` | WebFetch | `Last-Modified` header or page date, else a short content hash |
4. **Blocks never stop the run.** For each failure show only the matching one-line fix and continue with the rest:

   | Input | Blocked when | Tell the user |
   |---|---|---|
   | Private GitHub | `gh auth status` fails, clone 404/403 | Run `! gh auth login` in this session, then re-run with the same URL. |
   | Notion | no Notion MCP tool | Connect the Notion MCP server (`/mcp`), or export the page as Markdown and pass the folder path. |
   | Local folder | path missing, permission denied | Show `ls -la <parent>` and the exact path tried; ask for the correct path. |
   | Other URL | login wall, paywall, 401/403 | Export or save the page (Markdown/PDF) and pass the file path. |
   | Git reference | `status: blocked` | The `blocked` text (a `git fetch` command for the user to run). |
5. **Classify** each artifact `code` / `writing` / `idea` (one primary, optional secondary). Start from `type_hint`; free text is `idea`.
6. **Mode.** Use `mode_hint` from `init` and tell the user the mode and reason in one line. In incremental mode a `changed` artifact is analyzed by method: `git-head`/`git-ref` only the files in `changed_files` (if `previous_missing`, re-analyze the whole artifact); all other methods the whole artifact again.
   **All unchanged** (`all_unchanged: true` in incremental mode): ask once "Nothing changed since the last run. Re-analyze with `--full`, run the tracks on the ledger's parts only, or stop? (full / tracks / stop)".
   - `full`: switch this run to full (step 8 reads the mode from the run file header) and continue with step 2.
   - `tracks`: skip steps 2-3 (stored cards, parts, lessons), run step 4, then steps 5-8.
   - `stop`: end the run; nothing is written to the ledger.
7. Write the intake table to `<WORK>/intake.md`: id, source, type, working copy, method, status; plus mode and blocked inputs with the fix shown.

## Output

- `<WORK>/intake.md`, staged `<WORK>/fingerprints.json`, `mode`, blocked inputs.

## Reject if

Process checks: fix before step 2. If an item had to be dropped, compost it with `kind: other`.

- [`01.modified-source`] Any command would write into the user's source folder or repo. Use `<WORK>` instead.
- [`01.silent-skip`] A blocked input was dropped without showing the user a fix line.
- [`01.unasked-bulk`] More than 10 artifacts went to step 2 without the user's answer to the bulk question.
- [`01.unstable-id`] An artifact already in the ledger got a new id.
- [`01.unfiltered-hash`] A fingerprint was computed by hand instead of by `fingerprint`, or included excluded files.
- [`01.secret-read`] A file matching the secret patterns was read or hashed.
- [`01.fetched-ref`] `git fetch` was run on a git-reference input instead of reading the existing ref.
