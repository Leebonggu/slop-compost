"""Tests for skills/compost/scripts/ledger.py (stdlib unittest, temporary ledgers only)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "compost" / "scripts" / "ledger.py"
FIXTURE = ROOT / "tests" / "fixtures" / "v011-ledger"
NOW = "2026-10-15T21:00:00+09:00"
RUN = "2026-10-15"

sys.path.insert(0, str(SCRIPT.parent))
import ledger  # noqa: E402


def sh(*args, cwd=None):
    subprocess.run(list(args), cwd=cwd, check=True, capture_output=True)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="slop-test-"))
        self.L = self.tmp / "ledger"
        self.env = dict(os.environ, SLOP_COMPOST_NOW=NOW)
        for k in ("SLOP_COMPOST_HOME", "SLOP_COMPOST_LANG", "SLOP_COMPOST_FULL_EVERY", "SLOP_COMPOST_TRACK_MODEL"):
            self.env.pop(k, None)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_cli(self, *args, ok=True, cwd=None):
        res = subprocess.run([sys.executable, str(SCRIPT), "--ledger", str(self.L)] + [str(a) for a in args],
                             capture_output=True, text=True, env=self.env, cwd=cwd)
        lines = [l for l in res.stdout.splitlines() if l.strip()]
        self.assertEqual(len(lines), 1, f"expected one JSON line, got: {res.stdout!r} {res.stderr!r}")
        data = json.loads(lines[0])
        if ok:
            self.assertEqual(res.returncode, 0, data)
            self.assertNotIn("error", data)
        else:
            self.assertEqual(res.returncode, 1)
            self.assertIn("error", data)
        return data

    def init(self, *extra):
        return self.run_cli("init", *extra)

    def wd(self, run=RUN):
        return self.L / "runs" / f"{run}.work"

    def write(self, path, text):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def jsonl(self, path, rows):
        return self.write(path, "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))

    def read_jsonl(self, path):
        return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]

    def use_fixture(self):
        shutil.copytree(FIXTURE, self.L)


def decision(did, decision="adopt", track=None, followups=None, stale=False, skip=0, **kw):
    run, label = did.split(":")
    row = {"id": did, "run": run, "track": track or label[0], "candidate": f"cand {did}", "decision": decision,
           "reason": "", "artifact_ids": [], "lesson_ids": [], "at": "2026-10-01T21:00:00+09:00",
           "followups": followups or [], "skip_count": skip, "stale": stale}
    row.update(kw)
    return row


def fu(result, touched=True):
    return {"at": "2026-10-02T10:00:00+09:00", "touched": touched, "result": result, "note": ""}


# ------------------------------------------------------------------ init

class InitTests(Base):
    def test_first_run_seeds_sources_and_reserves_run_id(self):
        r = self.init()
        self.assertTrue(r["first_run"])
        self.assertEqual(r["run_id"], RUN)
        self.assertEqual(r["mode_hint"], "full")
        self.assertEqual(r["track_model"], "sonnet")
        self.assertTrue((self.L / "sources.md").exists())
        self.assertTrue(self.wd().is_dir())
        r2 = self.init()
        self.assertEqual(r2["run_id"], RUN + "-2")

    def test_run_file_also_blocks_id_and_env(self):
        self.write(self.L / "runs" / f"{RUN}.md", "x")
        self.env.update(SLOP_COMPOST_TRACK_MODEL="haiku", SLOP_COMPOST_LANG="ko", SLOP_COMPOST_FULL_EVERY="3")
        r = self.init("--inputs", "12")
        self.assertEqual(r["run_id"], RUN + "-2")
        self.assertEqual((r["track_model"], r["lang"], r["full_every"]), ("haiku", "ko", 3))
        self.assertTrue(r["bulk_question"])

    def test_new_default_sources_reported(self):
        self.write(self.L / "sources.md", "# Sources\n\n## hn-show\n- category: trend\n- type: fetch\n- how: x\n- enabled: true\n")
        r = self.init()
        self.assertIn("failory", r["new_default_sources"])
        self.assertNotIn("hn-show", r["new_default_sources"])

    def test_mode_incremental_and_threshold(self):
        self.write(self.L / "state.json", json.dumps({"version": 1, "runs": ["2026-10-01"], "fingerprints": {},
                                                     "artifacts_since_full": 9}))
        self.assertEqual(self.init()["mode_hint"], "incremental")
        self.write(self.L / "state.json", json.dumps({"version": 1, "runs": ["2026-10-01"], "fingerprints": {},
                                                     "artifacts_since_full": 10}))
        self.assertEqual(self.init()["mode_hint"], "full")
        self.assertEqual(self.init("--full")["mode_reason"], "--full")


# ------------------------------------------------------------------ fingerprint

class FingerprintTests(Base):
    def make_folder(self):
        f = self.tmp / "proj"
        self.write(f / "src" / "app.py", "print('hi')\n")
        self.write(f / "README.md", "# proj\n")
        return f

    def test_absolute_and_relative_paths_match(self):
        f = self.make_folder()
        a = self.run_cli("fingerprint", str(f))["inputs"][0]
        b = self.run_cli("fingerprint", "proj", cwd=str(self.tmp))["inputs"][0]
        self.assertEqual(a["value"], b["value"])
        self.assertEqual(a["artifact_id"], "proj")
        self.assertEqual(a["method_version"], ledger.FILE_HASH_VERSION)
        self.assertEqual((a["next_part"], a["card"]), ("proj#p1", False))

    def test_excluded_and_secret_files_do_not_change_hash(self):
        f = self.make_folder()
        before = ledger.folder_hash(f)
        for rel in ("node_modules/x/index.js", ".venv/lib.py", "dist/out.js", "build/b.js", "__pycache__/a.py",
                    ".omc/s.json", ".claude/c.md", "logs/l.txt", "vendor/v.js", "yarn.lock", "package-lock.json",
                    "app.db.json", "data.sqlite3", ".env", ".env.local", "my_secret.txt", "AWS_Credentials.json",
                    "server.pem", "api.key", "id_rsa", "cert.p12", "app.keystore", "bundle.min.js", "image.png"):
            self.write(f / rel, "x\n")
        self.assertEqual(ledger.folder_hash(f), before)
        self.write(f / "src" / "new.py", "x\n")
        self.assertNotEqual(ledger.folder_hash(f), before)

    def test_v2_hash_matches_v011_shell_command(self):
        if not shutil.which("shasum"):
            self.skipTest("shasum not available")
        f = self.make_folder()
        self.write(f / "docs" / "a b.md", "space\n")
        cmd = (r"""find . \( -type d \( -name .git -o -name node_modules -o -name .venv -o -name venv -o -name .next -o -name dist -o -name build -o -name __pycache__ -o -name .omc -o -name .claude -o -name logs \) -prune \) -o -type f """
               r"""\( -name '*.py' -o -name '*.md' -o -name '*.json' \) ! -name '*.lock' ! -name 'package-lock.json' ! -name 'pnpm-lock.yaml' """
               r"""! -name '.env*' ! -iname '*secret*' ! -iname '*credential*' ! -name '*.pem' ! -name '*.key' ! -name 'id_rsa*' ! -name '*.p12' ! -name '*.keystore' -print """
               r"""| LC_ALL=C sort | while IFS= read -r f; do shasum "$f"; done | shasum | cut -c1-12""")
        expected = subprocess.run(["bash", "-c", cmd], cwd=str(f), capture_output=True, text=True).stdout.strip()
        self.assertEqual(ledger.folder_hash(f, 2), expected)

    def test_unchanged_changed_and_all_unchanged(self):
        f = self.make_folder()
        value = ledger.folder_hash(f)
        text = "a newsletter to podcast idea"
        self.write(self.L / "state.json", json.dumps({"version": 1, "runs": ["2026-10-01"], "fingerprints": {
            "proj": {"source": str(f), "method": "file-hash", "method_version": 3, "value": value, "at": NOW},
            "pod": {"source": "text", "method": "text-hash", "value": ledger.text_hash(text) + "  -", "at": NOW}}}))
        r = self.run_cli("fingerprint", str(f), text)
        self.assertEqual([i["status"] for i in r["inputs"]], ["unchanged", "unchanged"])
        self.assertEqual(r["inputs"][1]["artifact_id"], "pod")
        self.assertTrue(r["all_unchanged"])
        self.write(f / "src" / "app.py", "print('changed')\n")
        r = self.run_cli("fingerprint", str(f))
        self.assertEqual(r["inputs"][0]["status"], "changed")
        self.assertEqual(r["inputs"][0]["previous"], value)
        self.assertFalse(r["all_unchanged"])

    def test_method_version_migration_counts_as_unchanged(self):
        f = self.make_folder()
        self.write(self.L / "state.json", json.dumps({"version": 1, "runs": ["x"], "fingerprints": {
            "proj": {"source": str(f), "method": "file-hash", "method_version": 2, "value": "000000000000", "at": NOW}}}))
        r = self.run_cli("fingerprint", str(f))["inputs"][0]
        self.assertEqual(r["status"], "unchanged")
        self.assertEqual(r["migrated_from_version"], 2)

    def test_git_repo_and_git_ref(self):
        if not shutil.which("git"):
            self.skipTest("git not available")
        repo = self.tmp / "repo"
        self.write(repo / "items" / "a.json", "{}\n")
        sh("git", "init", "-q", "-b", "main", cwd=repo)
        sh("git", "-c", "user.email=t@t", "-c", "user.name=t", "add", ".", cwd=repo)
        sh("git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init", cwd=repo)
        r = self.run_cli("fingerprint", str(repo), f"{repo}@main:items", f"{repo}@nope:items")["inputs"]
        self.assertEqual((r[0]["kind"], r[0]["method"]), ("git-repo", "git-head"))
        self.assertEqual(len(r[0]["value"]), 40)
        self.assertEqual((r[1]["kind"], r[1]["method"], r[1]["artifact_id"]), ("git-ref", "git-ref", "repo-items"))
        self.assertEqual(r[2]["status"], "blocked")
        self.assertIn("fetch origin nope", r[2]["blocked"])

    def test_network_inputs_need_llm_and_set(self):
        self.init()
        r = self.run_cli("fingerprint", "--run", RUN, "https://github.com/me/old-app", "https://www.notion.so/My-Page-0123456789abcdef0123456789abcdef", "https://example.com/post/idea")["inputs"]
        self.assertEqual([i["kind"] for i in r], ["github-url", "notion", "url"])
        self.assertTrue(all(i["needs_llm"] for i in r))
        self.assertEqual(r[1]["artifact_id"], "my-page")
        s = self.run_cli("fingerprint", "--run", RUN, "--set", "old-app", "git-head", "abc1234def")["inputs"][0]
        self.assertEqual(s["status"], "new")
        staged = json.loads((self.wd() / "fingerprints.json").read_text())
        self.assertEqual(staged["old-app"]["value"], "abc1234def")
        self.assertEqual(staged["old-app"]["source"], "https://github.com/me/old-app")


class SelectFilesTests(Base):
    def test_ranking_partial_and_secrets(self):
        f = self.tmp / "app"
        self.write(f / "README.md", "r\n")
        self.write(f / "package.json", json.dumps({"main": "lib/start.js"}))
        self.write(f / "lib" / "start.js", "x\n")
        self.write(f / "src" / "index.ts", "x\ny\n")
        self.write(f / ".env", "TOKEN=1\n")
        self.write(f / "secrets.json", "{}")
        self.write(f / "app.db", "x")
        for i in range(10):
            self.write(f / "src" / f"m{i}.ts", "x\n")
        r = self.run_cli("select-files", f, "--max", "5")
        paths = [x["path"] for x in r["files"]]
        self.assertEqual(paths[0], "lib/start.js")
        self.assertIn("src/index.ts", paths)
        self.assertIn("README.md", paths)
        self.assertIn("package.json", paths)
        self.assertTrue(r["partial"])
        self.assertEqual(r["selected"], 5)
        self.assertEqual(r["secrets_skipped"], 2)
        self.assertEqual(r["databases"], ["app.db"])
        self.assertNotIn(".env", json.dumps(r))
        self.assertEqual([x["lines"] for x in r["files"] if x["path"] == "src/index.ts"], [2])


# ------------------------------------------------------------------ recall

class RecallTests(Base):
    def seed(self):
        self.jsonl(self.L / "decisions.jsonl", [
            decision("2026-10-01:A1"),                                   # F1: no followups
            decision("2026-10-01:B1", followups=[fu("in-progress")]),     # F2: last not done
            decision("2026-10-01:A2", followups=[fu("done")]),           # excluded: done
            decision("2026-10-01:A3", followups=[fu("stopped")]),        # excluded: stopped
            decision("2026-10-01:B2", stale=True),                       # excluded: stale
            decision("2026-10-01:B3", decision="hold"),                  # excluded: not adopt
            decision("2026-10-08:A1", followups=[fu("not-started", touched=False)], skip=2),  # F3
        ])
        self.write(self.L / "state.json", json.dumps({"version": 1, "runs": ["2026-10-01", "2026-10-08"], "fingerprints": {}}))
        self.init()

    def test_h1_followup_list(self):
        self.seed()
        r = self.run_cli("recall")
        ids = [f["id"] for f in r["followups"]]
        self.assertEqual(ids, ["2026-10-01:A1", "2026-10-01:B1", "2026-10-08:A1"])
        self.assertEqual([f["label"] for f in r["followups"]], ["F1", "F2", "F3"])
        self.assertFalse(r["first_run"])

    def test_apply_korean_skip_stale_and_reset(self):
        self.seed()
        r = self.run_cli("apply-recall", "--run", RUN, 'F1 손댔음 진행 중 "랜딩 올림"')
        self.assertEqual(r["applied"], ["F1"])
        self.assertEqual(sorted(r["skipped"]), ["F2", "F3"])
        self.assertEqual(r["stale"], ["F3"])
        staged = json.loads((self.wd() / "recall.json").read_text())["updates"]
        self.assertEqual(staged["2026-10-01:A1"]["followup"]["result"], "in-progress")
        self.assertTrue(staged["2026-10-01:A1"]["followup"]["touched"])
        self.assertEqual(staged["2026-10-01:A1"]["followup"]["note"], "랜딩 올림")
        self.assertEqual(staged["2026-10-01:A1"]["skip_count"], 0)
        self.assertEqual(staged["2026-10-01:B1"], {"skip_count": 1})
        self.assertEqual(staged["2026-10-08:A1"], {"skip_count": 3, "stale": True})

    def test_answer_resets_skip_count_and_no_means_not_started(self):
        self.seed()
        r = self.run_cli("apply-recall", "--run", RUN, "F3 no, F2 완료, F1 안 함")
        self.assertEqual(sorted(r["applied"]), ["F1", "F2", "F3"])
        up = json.loads((self.wd() / "recall.json").read_text())["updates"]
        self.assertEqual(up["2026-10-08:A1"]["followup"]["result"], "not-started")
        self.assertFalse(up["2026-10-08:A1"]["followup"]["touched"])
        self.assertEqual(up["2026-10-08:A1"]["skip_count"], 0)
        self.assertEqual(up["2026-10-01:B1"]["followup"]["result"], "done")
        self.assertTrue(up["2026-10-01:B1"]["followup"]["touched"])
        self.assertEqual(up["2026-10-01:A1"]["followup"]["result"], "not-started")

    def test_global_skip(self):
        self.seed()
        r = self.run_cli("apply-recall", "--run", RUN, "스킵")
        self.assertEqual(r["applied"], [])
        self.assertEqual(len(r["skipped"]), 3)

    def test_original_labels_ambiguous_and_unparsed(self):
        self.seed()
        r = self.run_cli("apply-recall", "--run", RUN, "B1 stopped \"no demand\", A1 done, F9 yes, 2026-10-08:A1 blah")
        self.assertEqual(r["applied"], ["F2"])
        self.assertEqual(r["ambiguous"][0]["matches"], ["2026-10-01:A1", "2026-10-08:A1"])
        self.assertEqual({u["item"] for u in r["unparsed"]}, {"F9 yes", "2026-10-08:A1 blah"})
        self.assertEqual(r["skipped"], [])  # ambiguous/unparsed items wait for a second answer
        r2 = self.run_cli("apply-recall", "--run", RUN, "2026-10-01:A1 yes, 2026-10-08:A1 skip")
        self.assertEqual(sorted(r2["applied"]), ["F1", "F2"])
        self.assertEqual(r2["skipped"], ["F3"])


# ------------------------------------------------------------------ judge

DIRECTION = """# slop-compost run 2026-10-15

- Mode: incremental (1 new)
- Artifacts: proj

## Parts
| id | kind | location | what |
|---|---|---|---|
| proj#p1 | module | src/app.py:1 | printer |

## Patterns across artifacts
- Cross-artifact patterns need 2+ artifacts

## Two tracks

### If you revive the current idea (Track A)
#### A1 - Ship the printer as a CLI
- Parts: `proj#p1`
- Lessons -> changes: L1 -> user test in week 1
- First experiment (<= 7 days): post the CLI to 20 users in 3 days
- Success: 5 of 20 reply   |   Kill: 0 replies
- Intents: respects I1

#### A3 - Printer as a web page
- Parts: `proj#p1`
- Lessons -> changes: L1 -> landing first
- First experiment (<= 7 days): landing page for 5 days
- Success: 30 signups   |   Kill: under 5 signups

### If you go for a new idea (Track B)
#### B1 - Printer API for newsletters
- Who pays: newsletter authors, $9/month
- Parts: `proj#p1`
- Lessons -> changes: L1 -> pre-sell first
- External evidence:
  - Show HN printer tool got 300 points - https://news.ycombinator.com/item?id=1 - 2026-09-01 [src:hn-show]
- Counter-evidence: why it could fail: authors already get printing from their platform; similar failure: PrintCo (Cause: no demand, Closed: 2021) - https://www.failory.com/cemetery/printco - 2024-03-01 [src:failory]
- First experiment (<= 7 days): email 40 authors in 5 days
- Success: 3 paid pre-orders at $9   |   Kill: 0 pre-orders
- Source ids: hn-show, failory

Convergence: A1 ≈ B1 - both ship the printer

Composted 1 (05a.no-number: 1)
"""


class JudgeTests(Base):
    def setUp(self):
        super().setUp()
        self.init()
        self.write(self.L / "runs" / f"{RUN}.md", DIRECTION)

    def test_parse_mixed_line(self):
        r = self.run_cli("judge", "--run", RUN, "A1 a 랜딩 먼저, b1 기각 운영 부담")
        d = {x["label"]: x for x in r["decisions"]}
        self.assertEqual((d["A1"]["decision"], d["A1"]["reason"]), ("adopt", "랜딩 먼저"))
        self.assertEqual((d["B1"]["decision"], d["B1"]["reason"], d["B1"]["track"]), ("reject", "운영 부담", "B"))
        self.assertEqual((d["A3"]["decision"], d["A3"]["reason"]), ("hold", ""))
        self.assertEqual(r["unparsed"], [])

    def test_empty_means_all_hold_and_unknowns(self):
        r = self.run_cli("judge", "--run", RUN, "")
        self.assertEqual({x["decision"] for x in r["decisions"]}, {"hold"})
        r = self.run_cli("judge", "--run", RUN, "A2 a, A1 maybe, A3 채택")
        self.assertEqual(len(r["unparsed"]), 2)
        self.assertEqual({x["label"]: x["decision"] for x in r["decisions"]}["A3"], "adopt")

    def test_convergent_pair_both_adopted(self):
        r = self.run_cli("judge", "--run", RUN, "A1+B1 adopt same direction")
        d = {x["label"]: x["decision"] for x in r["decisions"]}
        self.assertEqual((d["A1"], d["B1"]), ("adopt", "adopt"))


# ------------------------------------------------------------------ bundle

class BundleTests(Base):
    def test_bundle_b_scrubs_track_a_and_filters_compost(self):
        self.use_fixture()
        self.init()
        self.jsonl(self.L / "compost.jsonl", [
            {"id": "C-1-b1", "run": "2026-10-01", "step": "05b", "kind": "candidate", "content": "B2: reusable",
             "failed_rules": ["05b.ev-no-counter", "05b.ev-no-date"], "at": NOW, "reused_in": []},
            {"id": "C-1-b2", "run": "2026-10-01", "step": "05b", "kind": "candidate", "content": "B3: mixed",
             "failed_rules": ["05b.ev-no-counter", "05b.no-number"], "at": NOW, "reused_in": []},
            {"id": "C-1-a1", "run": "2026-10-01", "step": "05a", "kind": "candidate", "content": "A2: track a",
             "failed_rules": ["05a.ev-no-part"], "at": NOW, "reused_in": []},
            {"id": "C-1-3", "run": "2026-10-01", "step": "05b", "kind": "lesson", "content": "lesson",
             "failed_rules": ["03.ev-no-location"], "at": NOW, "reused_in": []},
        ])
        r = self.run_cli("bundle", "b", "--run", RUN)
        text = Path(r["path"]).read_text()
        self.assertEqual(r["items"]["reusable_compost"], 1)
        self.assertIn("C-1-b1", text)
        self.assertNotIn("C-1-b2", text)
        self.assertNotIn("C-1-a1", text)
        self.assertIn("another candidate", text)  # "overlaps with A1" was generalized
        self.assertNotRegex(text, r"\bA1\b")
        self.assertNotIn("2026-10-01:A1", text)
        self.assertNotIn("A adopted", text)       # profile line about Track A dropped
        self.assertGreaterEqual(r["items"]["scrubbed"], 2)
        self.assertIn("idea-factory#p1", text)

    def test_bundle_a_contains_run_scope_only(self):
        self.use_fixture()
        self.init()
        self.write(self.wd() / "fingerprints.json", json.dumps({"idea-factory": {"status": "changed", "method": "file-hash", "value": "x", "source": "~/x"}}))
        self.write(self.wd() / "lessons.md", "### L3 - new lesson\n- Evidence: `idea-factory:README.md:1`\n")
        r = self.run_cli("bundle", "a", "--run", RUN)
        text = Path(r["path"]).read_text()
        self.assertIn("idea-factory#p1", text)
        self.assertNotIn("podcast-idea#p1", text)
        self.assertIn("L3 - new lesson", text)
        self.assertIn('I1 "B2B only"', text)
        self.assertEqual(r["items"]["artifacts"], 1)


# ------------------------------------------------------------------ lint

class LintTests(Base):
    def setUp(self):
        super().setUp()
        self.init()
        self.proj = self.tmp / "proj"
        self.write(self.proj / "src" / "app.py", "a\nb\nc\n")
        self.write(self.wd() / "fingerprints.json", json.dumps({"proj": {"status": "new", "method": "file-hash", "value": "x", "source": str(self.proj)}}))
        self.jsonl(self.wd() / "parts.pending.jsonl", [{"id": "proj#p1", "artifact_id": "proj", "kind": "module", "location": "src/app.py:1",
                                                         "description": "d", "why_reusable": "w", "run": RUN, "at": NOW}])

    def lint(self, name, text, kind, *extra):
        p = self.write(self.wd() / name, text)
        return self.run_cli("lint", p, "--kind", kind, *extra)

    def rules(self, r):
        return {v["label"]: set(v["rule_ids"]) for v in r["violations"]}

    def test_lessons(self):
        text = """## 2026-10-15 (run 2026-10-15)

### L1 - I quit when the demo has no audience
- Evidence: `proj:src/app.py:2`
- Falsifier: a project with an early test that stopped anyway

### L2 - No location here
- Evidence: none
- Falsifier: x

### L3 - Missing file
- Evidence: `proj:src/nope.py:1`
- Falsifier: x

### L4 - Line out of range
- Evidence: `proj:src/app.py:99`

### L5 - I stop before user tests
- Evidence: `proj:src/app.py:1`
- Falsifier: y

### L9 - (repeat, see 2026-10-01)
- Evidence: `proj:src/app.py:3`
"""
        self.write(self.L / "lessons.md", "# Lessons\n\n## 2026-10-01 (run 2026-10-01)\n\n### L9 - I stop before user tests!\n- Repeat: 1\n")
        r = self.rules(self.lint("lessons.md", text, "lessons"))
        self.assertNotIn("L1", r)
        self.assertEqual(r["L2"], {"03.ev-no-location"})
        self.assertEqual(r["L3"], {"03.ev-no-location"})
        self.assertEqual(r["L4"], {"03.ev-no-location", "03.unfalsifiable"})
        self.assertIn("03.duplicate", r["L5"])
        self.assertNotIn("L9", r)  # repeat entry: evidence only

    def test_track_a(self):
        text = DIRECTION.split("### If you go")[0] + """
#### A4 - No number
- Parts: `proj#p1`
- Lessons -> changes: L1 -> x
- First experiment (<= 7 days): 2 weeks of interviews
- Success: many users

#### A5 - Bad links
- Parts: `ghost#p9`
- Lessons -> changes: L1, L2 -> x
- First experiment (<= 7 days): 3 days
- Success: 3 replies | Kill: 0
"""
        r = self.rules(self.lint("track-a.md", text, "track-a"))
        self.assertNotIn("A1", r)
        self.assertNotIn("A3", r)
        self.assertEqual(r["A4"], {"05a.no-experiment", "05a.no-number"})
        self.assertEqual(r["A5"], {"05a.ev-no-part", "05a.ev-no-lesson-link"})

    def test_track_b_evidence_rules(self):
        src = """## hn-show
- category: trend
- type: fetch, web
- how: fetch `https://hn.algolia.com/api`; search `site:news.ycombinator.com {keyword}`
- enabled: true

## failory
- category: failure
- type: fetch
- how: `https://www.failory.com/cemetery`
- enabled: true

## failure-search
- category: failure
- type: web
- how: `{keyword} startup shut down`
- enabled: true
"""
        self.write(self.L / "sources.md", "# Sources\n\n" + src)
        good = DIRECTION.split("### If you go for a new idea (Track B)")[1].split("Convergence")[0]
        bad = """
#### B2 - Bad evidence
- Parts: `proj#p1`
- External evidence:
  - claim without anything
  - claim - https://evil.example.com/x - 2026-01-01 [src:hn-show]
  - claim - https://anything.example.org/y - 2026-01-02 [src:failure-search]
  - claim - https://news.ycombinator.com/z [src:unknown-src]
- Counter-evidence: it could fail because nobody cares at all
- First experiment (<= 7 days): 5 days
- Success: 3 paid

#### B3 - Cap and none-found are fine
- Parts: `proj#p1`
- External evidence:
  - cap reached (hn-show)
- Counter-evidence: why it could fail: platforms bundle this already; similar failure: none found for "printer api shut down", "프린터 서비스 종료"
- First experiment (<= 7 days): 5 days
- Success: 3 paid | Kill: 0
- Source ids: hn-show, failure-search
"""
        r = self.lint("track-b.md", good + bad, "track-b")
        rules = self.rules(r)
        self.assertNotIn("B1", rules)
        self.assertEqual(rules["B2"], {"05b.ev-no-source", "05b.ev-no-date", "05b.ev-no-src-id", "05b.ev-no-counter"})
        self.assertNotIn("B3", rules)
        self.assertTrue(any(w["label"] == "B2" for w in r["warnings"]))

    def test_domain_mismatch_only(self):
        self.write(self.L / "sources.md", "# S\n\n## hn-show\n- type: web\n- how: `site:news.ycombinator.com {keyword}`\n- enabled: true\n\n## failory\n- type: fetch\n- how: `https://www.failory.com/cemetery`\n- enabled: true\n")
        text = DIRECTION.split("### If you go for a new idea (Track B)")[1].split("Convergence")[0].replace(
            "https://news.ycombinator.com/item?id=1", "https://techcrunch.com/a")
        self.assertEqual(self.rules(self.lint("track-b.md", text, "track-b"))["B1"], {"05b.ev-no-source"})

    def test_compost_in_output_and_compost_flag(self):
        text = DIRECTION.split("### If you go")[0] + "\n#### A4 - x\n- Parts: `proj#p1`\n- Success: none\n"
        r = self.lint("track-a.md", text, "track-a", "--compost")
        self.assertEqual(len(r["composted"]), 1)
        rows = self.read_jsonl(self.wd() / "compost.track-a.jsonl")
        self.assertEqual(rows[0]["id"], f"C-{RUN}-a1")
        self.assertEqual((rows[0]["step"], rows[0]["kind"], rows[0]["run"]), ("05a", "candidate", RUN))
        self.assertTrue(rows[0]["content"].startswith("#### A4"))
        r2 = self.lint("track-a.md", text, "track-a", "--compost")
        self.assertEqual(r2["composted"], [])  # idempotent
        self.assertIn("05a.compost-in-output", self.rules(r2)["A4"])

    def test_direction_rules(self):
        track_a = DIRECTION.split("### If you go")[0]
        self.write(self.wd() / "track-a.md", track_a)
        self.write(self.wd() / "track-b.md", "#### B1 - Printer API for newsletters\n")
        self.write(self.L / "sources.md", ledger.DEFAULT_SOURCES.read_text())
        renumbered = DIRECTION.replace("#### A3 - Printer as a web page", "#### A2 - Printer as a web page")
        p = self.write(self.L / "runs" / f"{RUN}.md", renumbered)
        r = self.run_cli("lint", p, "--kind", "direction")
        self.assertIn("06.label-mismatch", self.rules(r)["A2"])
        no_parts = DIRECTION.replace("| proj#p1 | module | src/app.py:1 | printer |\n", "").split("### If you go")[0]
        p = self.write(self.L / "runs" / f"{RUN}.md", no_parts)
        r = self.rules(self.run_cli("lint", p, "--kind", "direction"))
        self.assertEqual(r["(file)"], {"06.missing-parts-section", "06.single-track"})
        ok = self.run_cli("lint", self.write(self.L / "runs" / f"{RUN}.md", DIRECTION), "--kind", "direction")
        self.assertEqual(ok["violations"], [])


# ------------------------------------------------------------------ commit

class CommitTests(Base):
    def prepare(self, fixture=True):
        if fixture:
            self.use_fixture()
        r = self.init()
        wd = self.wd()
        proj = self.tmp / "proj"
        self.write(proj / "src" / "app.py", "a\n")
        self.write(wd / "fingerprints.json", json.dumps({"proj": {"status": "new", "method": "file-hash", "method_version": 3,
                                                                  "value": "abc123abc123", "source": str(proj), "at": NOW}}))
        self.jsonl(wd / "parts.pending.jsonl", [{"id": "proj#p1", "artifact_id": "proj", "kind": "module", "location": "src/app.py:1",
                                                 "description": "printer", "why_reusable": "prints"}])
        self.write(wd / "artifacts" / "proj.md", "---\nid: proj\nsource: x\ntype: code\n---\n\n# proj\n\n## Summary\n- Goal: print\n")
        self.write(wd / "src" / "clone" / "file.py", "x")
        self.write(wd / "copy.db", "x")
        self.write(wd / "copy.db-wal", "x")
        self.jsonl(wd / "compost.track-a.jsonl", [{"id": f"C-{RUN}-a1", "run": RUN, "step": "05a", "kind": "candidate",
                                                   "content": "#### A2 - x", "failed_rules": ["05a.no-number"], "at": NOW}])
        self.jsonl(wd / "compost.pending.jsonl", [{"id": f"C-{RUN}-1", "step": "03", "kind": "lesson", "content": "L9",
                                                   "failed_rules": ["03.unfalsifiable"]}])
        self.write(self.L / "runs" / f"{RUN}.md", DIRECTION.replace("- Source ids: hn-show, failory",
                                                                    "- Source ids: hn-show, failory\n- reused_compost: C-2026-10-01-b1"))
        return r

    def test_commit_merges_everything(self):
        self.prepare()
        self.run_cli("apply-recall", "--run", RUN, "F1 done")
        self.run_cli("judge", "--run", RUN, "A1 a, B1 adopt")
        self.write(self.wd() / "lessons.md", "### L1 - (repeat, see 2026-10-01)\n- Evidence: `proj:src/app.py:1`\n\n### L3 - new one\n- Evidence: `proj:src/app.py:1`\n- Falsifier: f\n- Repeat: 1\n")
        r = self.run_cli("commit", "--run", RUN)
        s = r["saved"]
        self.assertEqual(s["parts"], 1)
        self.assertEqual(s["decisions"], {"adopt": 2, "hold": 1, "reject": 0})
        self.assertEqual((s["lessons_new"], s["lessons_repeated"]), (1, 1))
        self.assertEqual((s["compost"], s["compost_reused"], s["followups_applied"]), (2, 1, 1))
        self.assertEqual((s["artifacts_new"], r["mode"]), (1, "incremental"))
        dec = {d["id"]: d for d in self.read_jsonl(self.L / "decisions.jsonl")}
        self.assertEqual(len(dec), 6)
        self.assertEqual(dec["2026-10-01:A1"]["followups"][-1]["result"], "done")
        self.assertEqual(dec[f"{RUN}:B1"]["source_ids"], ["hn-show", "failory"])
        self.assertEqual(dec[f"{RUN}:B1"]["reused_compost"], "C-2026-10-01-b1")
        self.assertEqual(dec[f"{RUN}:A1"]["artifact_ids"], ["proj"])
        self.assertEqual(dec[f"{RUN}:A1"]["lesson_ids"], ["L1"])
        self.assertEqual(dec[f"{RUN}:A3"]["decision"], "hold")
        comp = {c["id"]: c for c in self.read_jsonl(self.L / "compost.jsonl")}
        self.assertEqual(comp["C-2026-10-01-b1"]["reused_in"], [RUN])
        self.assertEqual(comp[f"C-{RUN}-1"]["run"], RUN)
        self.assertEqual(comp[f"C-{RUN}-1"]["reused_in"], [])
        state = json.loads((self.L / "state.json").read_text())
        self.assertEqual(state["runs"][-1], RUN)
        self.assertEqual(state["artifacts_since_full"], 2)
        self.assertEqual(state["fingerprints"]["proj"]["method_version"], 3)
        self.assertIn("idea-factory", state["fingerprints"])
        st = state["source_stats"]
        self.assertEqual(st["hn-show"]["per_run"][RUN], {"enabled": True, "cited": 1, "cited_in_adopted": 1})
        self.assertEqual(st["failory"]["cited"], 2)
        self.assertEqual(st["failory"]["runs_used"], ["2026-10-01", RUN])
        self.assertEqual(st["geeknews"]["per_run"][RUN], {"enabled": True, "cited": 0, "cited_in_adopted": 0})
        lessons = (self.L / "lessons.md").read_text()
        self.assertIn("- Repeat: 2 (runs 2026-10-01, 2026-10-15)", lessons)
        self.assertIn("`idea-factory:README.md:12`, `proj:src/app.py:1`", lessons)
        self.assertIn("### L3 - new one", lessons)
        self.assertTrue((self.L / "artifacts" / "proj.md").exists())
        self.assertFalse((self.wd() / "src").exists())
        self.assertFalse((self.wd() / "copy.db").exists())
        self.assertFalse((self.wd() / "copy.db-wal").exists())
        self.assertTrue((self.wd() / "fingerprints.json").exists())
        self.assertTrue(self.run_cli("validate")["ok"])
        self.run_cli("commit", "--run", RUN, ok=False)  # already committed

    def test_full_mode_resets_counter(self):
        self.prepare(fixture=False)
        self.write(self.L / "runs" / f"{RUN}.md", DIRECTION.replace("Mode: incremental", "Mode: full"))
        r = self.run_cli("commit", "--run", RUN)
        state = json.loads((self.L / "state.json").read_text())
        self.assertEqual((r["mode"], state["artifacts_since_full"], state["last_full_analysis"]), ("full", 0, RUN))

    def test_schema_failure_writes_nothing(self):
        self.prepare()
        before = (self.L / "decisions.jsonl").read_text()
        self.jsonl(self.wd() / "parts.pending.jsonl", [{"id": "proj#p1", "artifact_id": "proj", "kind": "widget",
                                                         "location": "x", "description": "d", "why_reusable": "w"}])
        r = self.run_cli("commit", "--run", RUN, ok=False)
        self.assertIn("kind 'widget' not in enum", r["error"])
        self.assertEqual((self.L / "decisions.jsonl").read_text(), before)
        self.assertNotIn(RUN, json.loads((self.L / "state.json").read_text())["runs"])
        self.assertTrue((self.wd() / "src").exists())

    def test_intent_removal_rejected(self):
        self.prepare()
        self.write(self.wd() / "intents.md", "# Intents\n\n## Active\n- I3 \"new\"\n\n## Ended\n- I2 \"x\"\n")
        r = self.run_cli("commit", "--run", RUN, ok=False)
        self.assertIn("I1", r["error"])

    def test_hotspot_idle_source_and_track_proposals(self):
        self.prepare()
        rows = [{"id": f"C-r{i}-{j}", "run": f"2026-09-0{i}", "step": "05b", "kind": "candidate", "content": "c",
                 "failed_rules": ["05b.ev-no-counter"], "at": NOW, "reused_in": []} for i in (1, 2, 3) for j in (1, 2)]
        self.jsonl(self.L / "compost.jsonl", self.read_jsonl(self.L / "compost.jsonl") + rows)
        state = json.loads((self.L / "state.json").read_text())
        state["runs"] = ["2026-09-01", "2026-09-02", "2026-09-03", "2026-09-04"]
        for sid in ("geeknews", "failory"):
            state["source_stats"][sid] = {"runs_used": [], "cited": 0, "cited_in_adopted": 0, "last_cited_run": None,
                                          "per_run": {r: {"enabled": True, "cited": 1, "cited_in_adopted": 0} for r in state["runs"]}}
        state["source_stats"]["failory"]["per_run"]["2026-09-02"]["cited_in_adopted"] = 1
        self.write(self.L / "state.json", json.dumps(state))
        dec = [decision(f"2026-09-0{i}:B1") for i in range(1, 6)]
        self.jsonl(self.L / "decisions.jsonl", dec)
        r = self.run_cli("commit", "--run", RUN)
        kinds = {(p["type"], p.get("rule") or p.get("source") or p.get("track")) for p in r["proposals"]}
        self.assertIn(("compost-hotspot", "05b.ev-no-counter"), kinds)
        self.assertIn(("idle-source", "geeknews"), kinds)
        self.assertNotIn(("idle-source", "failory"), kinds)
        self.assertNotIn(("idle-source", "hn-show"), kinds)  # cited in adopted this run
        self.assertIn(("track-zero-start", "B"), kinds)


# ------------------------------------------------------------------ sources

class SourcesTests(Base):
    def test_crud(self):
        listing = self.run_cli("sources", "list")
        self.assertEqual(listing["sources"][0]["cited"], "-")
        r = self.run_cli("sources", "add", "--type", "fetch", "--how", "https://www.example.com/rss", "--category", "trend")
        self.assertEqual(r["changed"]["id"], "example-com")
        r = self.run_cli("sources", "add", "--type", "fetch, web", "--how", "https://example.com/feed", "--category", "trend")
        self.assertEqual(r["changed"]["id"], "example-com-2")
        self.run_cli("sources", "add", "--type", "local", "--how", "~/scraper@data:items", "--category", "failure")
        text = (self.L / "sources.md").read_text()
        self.assertLess(text.index("## items"), text.index("<!--"))
        self.assertLess(text.index("## exploding-topics"), text.index("## example-com"))
        self.assertIn("- limits: 1-2 requests per run", text)
        e = self.run_cli("sources", "add", "--type", "rss", "--how", "x", "--category", "trend", ok=False)
        self.assertIn("allowed", e["error"])
        self.run_cli("sources", "add", "example-com", "--type", "web", "--how", "x", "--category", "trend", ok=False)
        self.run_cli("sources", "add", "x", "--type", "web", "--how", "x", "--category", "news", ok=False)
        r = self.run_cli("sources", "remove", "geeknews")
        self.assertEqual((r["changed"]["enabled"], r["changed"]["removed"]), (False, RUN))
        self.assertIn("## geeknews", (self.L / "sources.md").read_text())
        r = self.run_cli("sources", "enable", "geeknews")
        self.assertEqual((r["changed"]["enabled"], r["changed"].get("removed"), r["changed"]["restored"]), (True, None, RUN))
        self.assertFalse(self.run_cli("sources", "disable", "hn-show")["changed"]["enabled"])
        r = self.run_cli("sources", "edit", "failory", 'how=site:failory.com {keyword}', "limits=1 search", "category=revenue")
        self.assertEqual(r["changed"]["category"], "revenue")
        self.assertIn("- how: site:failory.com {keyword}", (self.L / "sources.md").read_text())
        self.run_cli("sources", "edit", "failory", "id=new", ok=False)
        self.run_cli("sources", "edit", "failory", "category=bogus", ok=False)
        e = self.run_cli("sources", "frobnicate", ok=False)
        self.assertIn("usage: sources list", e["error"])
        self.assertIn("hn-show", e["error"])
        self.run_cli("sources", "remove", ok=False)
        self.run_cli("sources", "remove", "nope", ok=False)

    def test_sync_defaults(self):
        self.write(self.L / "sources.md", "# Sources\n\n## hn-show\n- category: trend\n- type: fetch\n- how: x\n- enabled: true\n")
        self.assertIn("failory", self.run_cli("sources", "list")["new_default_sources"])
        r = self.run_cli("sources", "sync-defaults", "no")
        self.assertIn("failory", r["added"])
        listing = {s["id"]: s for s in self.run_cli("sources", "list")["sources"]}
        self.assertFalse(listing["failory"]["enabled"])
        self.assertNotIn("new_default_sources", self.run_cli("sources", "list"))


# ------------------------------------------------------------------ v0.1.1 compatibility

class CompatTests(Base):
    def test_fixture_reads_and_validates(self):
        self.use_fixture()
        v = self.run_cli("validate")
        self.assertTrue(v["ok"], v["errors"])
        r = self.run_cli("recall")
        self.assertEqual([f["id"] for f in r["followups"]], ["2026-10-01:A1", "2026-10-08:A1"])
        self.assertEqual([h["id"] for h in r["summary"]["habits"]], ["L2"])
        self.assertEqual(r["next_lesson_id"], "L3")
        self.assertEqual(r["lessons"][0]["sentence"], "I stop when the first external user test is more than 2 weeks away")
        self.assertEqual(r["summary"]["active_intents"], [{"id": "I1", "text": "B2B only"}])
        self.assertEqual(r["summary"]["adoption"]["A"], {"adopted": 2, "started": 1, "done": 0, "ids_started": ["2026-10-08:A1"]})
        listing = {s["id"]: s for s in self.run_cli("sources", "list")["sources"]}
        self.assertEqual(listing["failory"]["cited"], 1)
        i = self.init()
        self.assertFalse(i["first_run"])
        self.assertEqual(i["mode_hint"], "incremental")
        self.assertNotIn("new_default_sources", i)

    def test_v011_text_and_card_source_reuse_ids(self):
        self.use_fixture()
        home = self.tmp / "home"
        folder = home / "playground" / "old-notes"
        self.write(folder / "notes.md", "n\n")
        self.env["HOME"] = str(home)
        r = self.run_cli("fingerprint", str(folder))["inputs"][0]
        self.assertEqual(r["artifact_id"], "old-notes")
        self.assertEqual(r["status"], "unchanged")       # stored without method_version -> migrated once
        self.assertTrue(r["card"])
        self.assertEqual(r["migrated_from_version"], 1)

    def test_validate_detects_problems(self):
        self.use_fixture()
        rows = self.read_jsonl(self.L / "decisions.jsonl")
        rows[0]["decision"] = "maybe"
        rows[1]["lesson_ids"] = ["L77"]
        rows[2]["결정"] = "x"
        self.jsonl(self.L / "decisions.jsonl", rows)
        self.write(self.L / "profile.md", "# Profile\n\n## Current\n- No ids in this line.\n- Cites `2026-01-01:A9`.\n")
        errs = " ".join(self.run_cli("validate")["errors"])
        for needle in ("decision not in enum", "unknown lesson L77", "non-English key", "08.ev-profile-no-id",
                       "unknown decision id 2026-01-01:A9"):
            self.assertIn(needle, errs)


if __name__ == "__main__":
    unittest.main()
