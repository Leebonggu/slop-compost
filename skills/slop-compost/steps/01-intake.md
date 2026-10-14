# Step 1 - Intake

Turn whatever the user handed over into a list of artifacts with a type, a readable working copy, and a fingerprint.

## Inputs

- `$ARGUMENTS` and the user's message: local paths, git references `<repo>@<branch>:<path>`, GitHub URLs, Notion pages, other URLs, free text. Mixed is fine.
- `<LEDGER>/state.json` (`fingerprints`, `artifacts_since_full`, `last_full_analysis`) and existing `artifacts/<id>.md`.
- Env `SLOP_COMPOST_FULL_EVERY` (default 10).

## Do

1. **Split inputs** into artifacts. One path / URL = one artifact. Free text: one artifact per distinct idea (a bullet list of ideas = several artifacts).
2. **Count.** If there are more than 10 artifacts, ask once before going further:
   "N artifacts. Analyze all now (slower, more tokens) or pick a subset? (all | list of numbers)". Wait for the answer.
3. **Assign ids**: kebab-case from the folder/repo/page name or the idea's core noun (`idea-factory`, `podcast-from-newsletter`). If the ledger already has a card with the same source, reuse its id. Ids never change.
4. **Fetch read-only working copies** (never modify the source):

   | Input | How | Fingerprint | `method` |
   |---|---|---|---|
   | Local folder (git repo) | read in place | `git -C <path> rev-parse HEAD` | `git-head` |
   | Local folder (not git) | read in place | the filtered file hash below (`method_version: 2`) | `file-hash` |
   | Git reference `<repo>@<branch>:<path>` | `git -C <repo> show <branch>:<path>` / `git -C <repo> ls-tree -r --name-only <branch> <path>` (no `fetch`; if the branch is missing, tell the user `git -C <repo> fetch origin <branch>`) | `git -C <repo> rev-parse <branch>:<path>` | `git-ref` |
   | GitHub URL | `git clone --depth 50 <url> <LEDGER>/runs/<run-id>.work/src/<id>` (private: `gh repo clone <owner/repo> <dir> -- --depth 50`); the clone is deleted in step 8 | HEAD sha of the clone | `git-head` |
   | Notion page | Notion MCP fetch tool if connected | page `last_edited_time` | `notion-edited` |
   | Other URL | WebFetch | `Last-Modified` header or page date if shown, else content hash | `url-modified` |
   | Free text | keep as given | `printf %s "<text>" \| shasum` | `text-hash` |

   **File filter** (shared with step 2; use it for both hashing and reading). Exclude directories `.git node_modules .venv venv .next dist build __pycache__ .omc .claude logs`, files `*.db* *.sqlite* *.lock package-lock.json pnpm-lock.yaml`, and **secret-bearing files** `.env* *secret* *credential* *.pem *.key id_rsa* *.p12 *.keystore` (never read these at all). Hash only source and document files:

   ```bash
   cd <abs path> && find . \( -type d \( -name .git -o -name node_modules -o -name .venv -o -name venv -o -name .next -o -name dist -o -name build -o -name __pycache__ -o -name .omc -o -name .claude -o -name logs \) -prune \) -o -type f \
     \( -name '*.py' -o -name '*.js' -o -name '*.mjs' -o -name '*.cjs' -o -name '*.ts' -o -name '*.tsx' -o -name '*.jsx' -o -name '*.go' -o -name '*.rs' -o -name '*.java' -o -name '*.kt' -o -name '*.swift' -o -name '*.rb' -o -name '*.php' -o -name '*.c' -o -name '*.h' -o -name '*.cpp' -o -name '*.cs' -o -name '*.sh' -o -name '*.sql' -o -name '*.html' -o -name '*.css' -o -name '*.scss' -o -name '*.vue' -o -name '*.svelte' -o -name '*.md' -o -name '*.mdx' -o -name '*.txt' -o -name '*.json' -o -name '*.yaml' -o -name '*.yml' -o -name '*.toml' \) \
     ! -name '*.lock' ! -name 'package-lock.json' ! -name 'pnpm-lock.yaml' \
     ! -name '.env*' ! -iname '*secret*' ! -iname '*credential*' ! -name '*.pem' ! -name '*.key' ! -name 'id_rsa*' ! -name '*.p12' ! -name '*.keystore' -print | LC_ALL=C sort | while IFS= read -r f; do shasum "$f"; done | shasum | cut -c1-12
   ```

   The hash runs from inside the folder over relative paths (`./src/app.py`), so the same folder gives the same fingerprint whether the user passed an absolute or a relative path. **Migration**: a stored `file-hash` fingerprint without `method_version: 2` was computed the old way; recompute it once with this command, store it with `method_version: 2`, and treat the artifact as `unchanged` for this run.

5. **Handle blocks without stopping.** For each failure, show only the matching one-line fix, then continue with the remaining artifacts:

   | Input | Blocked when | Tell the user |
   |---|---|---|
   | Private GitHub | auth missing (`gh auth status` fails, clone 404/403) | Run `! gh auth login` in this session, then re-run with the same URL. |
   | Notion | no Notion MCP tool available | Connect the Notion MCP server (`/mcp`), or export the page as Markdown and pass the folder path. |
   | Local folder | path missing or permission denied | Show `ls -la <parent>` output and the exact path you tried; ask for the correct path. |
   | Other URL | login wall, paywall, 401/403 | Export or save the page (Markdown/PDF) and pass the file path. |

6. **Classify** each artifact: `code` / `writing` / `idea`. If mixed, one primary type plus secondary types (`code` + `writing` for a repo with a long README essay).
7. **Incremental vs full.**
   - `full` if `first_run` (`<LEDGER>/state.json` does not exist), or `--full` is in the arguments, or `state.json.artifacts_since_full >= FULL_EVERY`. In full mode, step 2 also re-reads every artifact card in the ledger and recomputes patterns and lessons across all of them; only this run's inputs are re-read from source and re-fingerprinted.
   - Otherwise `incremental`: an artifact whose fingerprint equals the stored one is `unchanged` (reuse its card, do not re-analyze). New ids are `new`. A changed fingerprint is `changed`, handled by method:

     | stored `method` | what to analyze for a `changed` artifact |
     |---|---|
     | `git-head` | only the range `git -C <path> diff --stat <old>..HEAD` and the files it lists (if `<old>` is not in the history, e.g. shallow clone, re-analyze this artifact fully) |
     | `git-ref` | only `git -C <repo> diff --stat <old tree> <new tree>` and the files it lists |
     | `file-hash`, `url-modified`, `notion-edited`, `text-hash` | the whole artifact again (this artifact only) |
   - Tell the user the mode in one line, with the reason.
   - **Everything unchanged**: if every input artifact is `unchanged` (none `new` or `changed`) and the mode is `incremental`, say so and ask once: "Nothing changed since the last run. Re-analyze with `--full`, run the tracks on the ledger's parts only, or stop? (full / tracks / stop)".
     - `full`: switch to full mode for this run and continue with step 2.
     - `tracks`: skip steps 2-3 (reuse stored cards, parts, and lessons), run step 4, then steps 5-8 with the existing ledger data. Track A works on the input artifacts' stored cards.
     - `stop`: end the run without writing a run file; nothing in the ledger changes.
   - **Scope**: only the artifacts in this input are analyzed. Ledger artifacts that were not passed this time are not re-analyzed; their parts stay available to Track B through `parts.jsonl`.

## Output

A table passed to step 2 (also written to `<LEDGER>/runs/<run-id>.work/intake.md`):

| id | source | type (primary + secondary) | working copy | fingerprint | status (new/changed/unchanged/blocked) |

Plus `mode` (`full` | `incremental`) and the list of blocked inputs with the fix that was shown.

## Reject if

These are process checks: fix the problem before step 2. If an item had to be dropped because of them, compost it with `kind: other`.

- [`01.modified-source`] Any command would write into the user's source folder or repo. Use the working-copy directory instead.
- [`01.silent-skip`] A blocked input was dropped without showing the user a fix line.
- [`01.unasked-bulk`] More than 10 artifacts went to step 2 without the user's answer to the bulk question.
- [`01.unstable-id`] An artifact already in the ledger got a new id.
- [`01.unfiltered-hash`] The fingerprint included excluded directories or files (virtualenvs, build output, databases, locks).
- [`01.secret-read`] A file matching the secret patterns was read or hashed.
- [`01.fetched-ref`] `git fetch` was run on a git-reference input instead of reading the existing ref.
