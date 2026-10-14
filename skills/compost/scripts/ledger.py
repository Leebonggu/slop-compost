#!/usr/bin/env python3
"""slop-compost ledger tool.

Deterministic work for the compost pipeline: run ids, fingerprints, file
selection, recall/judge parsing, input bundles, structural lint, the step 8
commit, source list CRUD and ledger validation.

Every command prints exactly one compact JSON object. Errors print
{"error": ...} and exit 1. Python 3.9+ standard library only. No network.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
DEFAULT_SOURCES = SKILL_DIR / "assets" / "default-sources.md"

FILE_HASH_VERSION = 3
PART_KINDS = {"module", "sentence", "problem", "data", "design", "other"}
DECISIONS = {"adopt", "hold", "reject"}
RESULTS = {"not-started", "in-progress", "done", "stopped"}
COMPOST_KINDS = {"lesson", "candidate", "part", "pattern", "other"}
SOURCE_TYPES = {"web", "fetch", "local"}
SOURCE_CATEGORIES = {"trend", "ai-trend", "revenue", "failure", "community-ko"}
SOURCE_FIELDS = ["category", "type", "how", "limits", "notes", "enabled"]
DEFAULT_LIMITS = "1-2 requests per run"
SOURCES_USAGE = "sources list | add [id] | remove <id> | edit <id> | enable <id> | disable <id>"
AT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?([+-]\d{2}:\d{2}|Z)$")


class LedgerError(Exception):
    pass


# ---------------------------------------------------------------- basics

def now() -> datetime:
    fixed = os.environ.get("SLOP_COMPOST_NOW")  # test hook only
    if fixed:
        return datetime.fromisoformat(fixed)
    return datetime.now().astimezone()


def now_iso() -> str:
    return now().isoformat(timespec="seconds")


def today() -> str:
    return now().strftime("%Y-%m-%d")


def out(obj) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n")


def ledger_path(arg) -> Path:
    raw = arg or os.environ.get("SLOP_COMPOST_HOME") or "~/.slop-compost"
    return Path(os.path.expanduser(raw)).resolve()


def env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix="." + path.name + ".")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LedgerError(f"{path}: invalid JSON ({exc})")


def write_json(path: Path, obj) -> None:
    write_atomic(path, json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def read_jsonl(path: Path) -> list:
    rows = []
    for n, line in enumerate(read_text(path).splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise LedgerError(f"{path}:{n}: invalid JSON ({exc})")
    return rows


def jsonl_text(rows) -> str:
    return "".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n" for r in rows)


def run_git(args, cwd=None):
    try:
        res = subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return res.stdout.strip() if res.returncode == 0 else None


def slug(text: str) -> str:
    s = re.sub(r"[^0-9A-Za-z]+", "-", text.lower()).strip("-")
    return re.sub(r"-{2,}", "-", s)


def work_dir(ledger: Path, run: str) -> Path:
    if not run or not re.match(r"^\d{4}-\d{2}-\d{2}(-\d+)?$", run):
        raise LedgerError(f"invalid run id: {run!r}")
    return ledger / "runs" / f"{run}.work"


def require_work(ledger: Path, run: str) -> Path:
    wd = work_dir(ledger, run)
    if not wd.is_dir():
        raise LedgerError(f"work directory not found: {wd} (run init first)")
    return wd


# ---------------------------------------------------------------- file filter

BASE_PRUNE = {".git", "node_modules", ".venv", "venv", ".next", "dist", "build", "__pycache__",
              ".omc", ".claude", "logs"}
V3_PRUNE = {"vendor", "third_party", "generated"}
SOURCE_EXT = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".kt",
              ".swift", ".rb", ".php", ".c", ".h", ".cpp", ".cs", ".sh", ".sql", ".html", ".css",
              ".scss", ".vue", ".svelte", ".md", ".mdx", ".txt", ".json", ".yaml", ".yml", ".toml"}
CODE_EXT = SOURCE_EXT - {".md", ".mdx", ".txt", ".json", ".yaml", ".yml", ".toml"}
LOCK_NAMES = {"package-lock.json", "pnpm-lock.yaml"}
SECRET_CASE = [".env*", "*.pem", "*.key", "id_rsa*", "*.p12", "*.keystore"]
SECRET_ICASE = ["*secret*", "*credential*"]
DB_PATTERNS = ["*.db*", "*.sqlite*"]
GENERATED_FILES = ["*.min.js", "*.min.css"]
SPECIAL_NAMES = {"Dockerfile", "Makefile", "go.mod", "Procfile"}  # selection only, never hashed


def is_secret(name: str) -> bool:
    if any(fnmatch.fnmatchcase(name, p) for p in SECRET_CASE):
        return True
    low = name.lower()
    return any(fnmatch.fnmatchcase(low, p) for p in SECRET_ICASE)


def is_db(name: str) -> bool:
    return any(fnmatch.fnmatchcase(name, p) for p in DB_PATTERNS)


def keep_file(name: str, version: int = FILE_HASH_VERSION, special: bool = False) -> bool:
    if is_secret(name) or name.endswith(".lock") or name in LOCK_NAMES:
        return False
    if version >= 3 and (is_db(name) or any(fnmatch.fnmatchcase(name, p) for p in GENERATED_FILES)):
        return False
    if special and name in SPECIAL_NAMES:
        return True
    return os.path.splitext(name)[1] in SOURCE_EXT


def walk_files(root: Path, version: int = FILE_HASH_VERSION, special: bool = False):
    """Yield (relpath with ./ prefix, abs path) like `find . ... -type f`, plus counters."""
    prune = BASE_PRUNE | (V3_PRUNE if version >= 3 else set())
    stats = {"secrets_skipped": 0, "databases": []}
    files = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in prune and not os.path.islink(os.path.join(dirpath, d))]
        for name in filenames:
            full = os.path.join(dirpath, name)
            if os.path.islink(full) or not os.path.isfile(full):
                continue
            rel = "./" + os.path.relpath(full, root).replace(os.sep, "/")
            if is_secret(name):
                stats["secrets_skipped"] += 1
                continue
            if is_db(name):
                stats["databases"].append(rel[2:])
            if keep_file(name, version, special):
                files.append((rel, full))
    return files, stats


def sha1_file(path: str) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def folder_hash(root: Path, version: int = FILE_HASH_VERSION) -> str:
    """Same as `cd <root> && find ... | LC_ALL=C sort | while read f; do shasum "$f"; done | shasum | cut -c1-12`."""
    files, _ = walk_files(root, version)
    files.sort(key=lambda x: os.fsencode(x[0]))
    outer = hashlib.sha1()
    for rel, full in files:
        outer.update(f"{sha1_file(full)}  {rel}\n".encode("utf-8", "surrogateescape"))
    return outer.hexdigest()[:12]


def single_file_hash(path: Path) -> str:
    rel = "./" + path.name
    return hashlib.sha1(f"{sha1_file(str(path))}  {rel}\n".encode()).hexdigest()[:12]


# ---------------------------------------------------------------- ledger readers

def state_of(ledger: Path) -> dict:
    return read_json(ledger / "state.json", None) or {}


def front_matter(text: str) -> dict:
    m = re.match(r"^---\n(.*?)\n---\n?", text, re.S)
    data = {}
    if not m:
        return data
    for line in m.group(1).splitlines():
        mm = re.match(r"^([A-Za-z_][\w-]*):\s*(.*?)\s*(#.*)?$", line)
        if mm:
            data[mm.group(1)] = mm.group(2)
    return data


def strip_front_matter(text: str) -> str:
    return re.sub(r"^---\n.*?\n---\n?", "", text, count=1, flags=re.S)


def card_paths(ledger: Path) -> dict:
    d = ledger / "artifacts"
    return {p.stem: p for p in sorted(d.glob("*.md"))} if d.is_dir() else {}


def norm_source(src: str) -> str:
    if not src:
        return ""
    src = src.strip()
    if re.match(r"^https?://", src):
        return src.rstrip("/")
    m = re.match(r"^(.+?)@([^:@/]+):(.*)$", src)
    if m and not src.startswith("text"):
        repo = os.path.realpath(os.path.expanduser(m.group(1)))
        return f"{repo}@{m.group(2)}:{m.group(3).strip('/')}"
    if src.startswith(("~", "/", ".")):
        return os.path.realpath(os.path.expanduser(src)).rstrip("/")
    return src


def known_artifacts(ledger: Path) -> dict:
    """artifact id -> normalized source (from state fingerprints and cards)."""
    res = {}
    for aid, fp in (state_of(ledger).get("fingerprints") or {}).items():
        res[aid] = norm_source(fp.get("source", ""))
    for aid, p in card_paths(ledger).items():
        src = front_matter(read_text(p)).get("source", "")
        if aid not in res or not res[aid]:
            res[aid] = norm_source(src)
    return res


LESSON_HEAD = re.compile(r"^(#{2,5})\s*\**\s*(L\d+)\b\s*[-–—:.]?\s*(.*)$")
CAND_HEAD = re.compile(r"^(#{2,5})\s*\**\s*([AB])(\d+)\b\**\s*[-–—:.)]?\s*(.*)$")
REPEAT_RE = re.compile(r"^(\s*[-*]\s*(?:Repeat|반복)[^:：]*[:：]\s*)(\d+)(.*)$", re.I)
HABIT_RE = re.compile(r"\[(structural habit|구조적 습관)\]", re.I)


def blocks(text: str, head_re):
    """Split markdown into blocks starting at headings matching head_re.
    Returns list of (match, start_line, end_line, block_text)."""
    lines = text.splitlines()
    found = []
    for i, line in enumerate(lines):
        m = head_re.match(line)
        if m:
            found.append((i, m))
    res = []
    for i, m in found:
        level = len(m.group(1))
        j = i + 1
        while j < len(lines):
            h = re.match(r"^(#{1,6})\s", lines[j])
            if h and len(h.group(1)) <= level:
                break
            j += 1
        res.append((m, i, j, "\n".join(lines[i:j])))
    return res


def parse_lessons(text: str) -> dict:
    """lesson id -> {sentence, repeat, habit, first_run}."""
    res = {}
    all_lines = text.splitlines()
    for m, start, end, body in blocks(text, LESSON_HEAD):
        lid, rest = m.group(2), m.group(3)
        head_run = None
        for line in all_lines[:start][::-1]:
            sec = re.match(r"^##\s+.*?\(run\s+([\w-]+)\)", line)
            if sec:
                head_run = sec.group(1)
                break
        entry = res.setdefault(lid, {"sentence": "", "repeat": 1, "habit": False, "first_run": head_run})
        sentence = HABIT_RE.sub("", rest).strip()
        if sentence and not re.match(r"^\((repeat|반복)", sentence, re.I) and not entry["sentence"]:
            entry["sentence"] = sentence
            entry["first_run"] = head_run
        if HABIT_RE.search(rest):
            entry["habit"] = True
        for line in body.splitlines():
            rm = REPEAT_RE.match(line)
            if rm:
                entry["repeat"] = max(entry["repeat"], int(rm.group(2)))
        if entry["repeat"] >= 3:
            entry["habit"] = True
    return res


def parse_intents(text: str) -> dict:
    active, ended, section = [], [], None
    for line in text.splitlines():
        h = re.match(r"^##\s+(.*)$", line)
        if h:
            t = h.group(1).strip().lower()
            if t.startswith(("active", "활성", "현재")):
                section = "active"
            elif t.startswith(("ended", "종료", "끝")):
                section = "ended"
            else:
                section = "active" if section is None else "ended"
            continue
        m = re.match(r'^\s*[-*]\s*(I\d+)\s*["“](.*?)["”]', line) or re.match(r"^\s*[-*]\s*(I\d+)\b\s*[-:]?\s*(.*)$", line)
        if m and section:
            (active if section == "active" else ended).append({"id": m.group(1), "text": m.group(2).strip()})
    return {"active": active, "ended": ended}


def profile_current(text: str) -> str:
    """The first `## ` section (Current), without History."""
    keep, res = False, []
    for line in text.splitlines():
        if re.match(r"^##\s", line):
            if keep:
                break
            low = line.lower()
            if "history" in low or "이력" in low:
                break
            keep = True
            continue
        if keep:
            res.append(line)
    return "\n".join(res).strip()


# ---------------------------------------------------------------- sources.md

def parse_sources(text: str) -> dict:
    lines = text.splitlines()
    header, entries, tail = [], [], []
    i = 0
    while i < len(lines) and not lines[i].startswith("## "):
        header.append(lines[i])
        i += 1
    cur = None
    while i < len(lines):
        line = lines[i]
        if line.startswith("## "):
            cur = {"id": line[3:].strip(), "lines": [line]}
            entries.append(cur)
        elif line.startswith("<!--"):
            tail = lines[i:]
            break
        else:
            cur["lines"].append(line)
        i += 1
    for e in entries:
        e["fields"] = {}
        for line in e["lines"][1:]:
            m = re.match(r"^-\s*([a-z_]+):\s*(.*)$", line)
            if m:
                e["fields"][m.group(1)] = m.group(2).strip()
    return {"header": header, "entries": entries, "tail": tail}


def render_sources(doc: dict) -> str:
    parts = list(doc["header"])
    for e in doc["entries"]:
        body = list(e["lines"])
        while body and not body[-1].strip():
            body.pop()
        parts.extend(body)
        parts.append("")
    parts.extend(doc["tail"])
    text = "\n".join(parts)
    return text if text.endswith("\n") else text + "\n"


def set_field(entry: dict, field: str, value) -> None:
    value = "" if value is None else str(value)
    for idx, line in enumerate(entry["lines"]):
        if re.match(rf"^-\s*{re.escape(field)}:", line):
            if value == "":
                del entry["lines"][idx]
            else:
                entry["lines"][idx] = f"- {field}: {value}"
            break
    else:
        if value != "":
            last = len(entry["lines"])
            while last > 1 and not entry["lines"][last - 1].strip():
                last -= 1
            entry["lines"].insert(last, f"- {field}: {value}")
    if value == "":
        entry["fields"].pop(field, None)
    else:
        entry["fields"][field] = value


def entry_enabled(e) -> bool:
    return e["fields"].get("enabled", "true").lower() == "true" and not e["fields"].get("removed")


def source_domains(entry: dict) -> list:
    how = entry["fields"].get("how", "")
    doms = set()
    for m in re.finditer(r"https?://([^/\s`'\")]+)", how):
        doms.add(m.group(1).lower())
    for m in re.finditer(r"site:([\w.-]+)", how):
        doms.add(m.group(1).lower())
    return sorted(d[4:] if d.startswith("www.") else d for d in doms)


def seed_sources(ledger: Path, defaults: Path) -> bool:
    target = ledger / "sources.md"
    if target.exists():
        return False
    if not defaults.exists():
        raise LedgerError(f"default sources not found: {defaults}")
    write_atomic(target, read_text(defaults))
    return True


def new_default_ids(ledger: Path, defaults: Path) -> list:
    user = {e["id"] for e in parse_sources(read_text(ledger / "sources.md"))["entries"]}
    return [e["id"] for e in parse_sources(read_text(defaults))["entries"] if e["id"] not in user]


# ---------------------------------------------------------------- init

def cmd_init(a, ledger: Path):
    skill_dir = Path(a.skill_dir).expanduser().resolve() if a.skill_dir else SKILL_DIR
    defaults = skill_dir / "assets" / "default-sources.md"
    ledger.mkdir(parents=True, exist_ok=True)
    (ledger / "runs").mkdir(exist_ok=True)
    state_file = ledger / "state.json"
    first_run = not state_file.exists()
    state = state_of(ledger)
    seeded = seed_sources(ledger, defaults)
    base, n, run_id = today(), 1, today()
    while (ledger / "runs" / f"{run_id}.md").exists() or (ledger / "runs" / f"{run_id}.work").exists():
        n += 1
        run_id = f"{base}-{n}"
    wd = ledger / "runs" / f"{run_id}.work"
    wd.mkdir(parents=True)
    full_every = env_int("SLOP_COMPOST_FULL_EVERY", 10)
    since = int(state.get("artifacts_since_full", 0) or 0)
    if first_run:
        mode, reason = "full", "first run"
    elif a.full:
        mode, reason = "full", "--full"
    elif since >= full_every:
        mode, reason = "full", f"artifacts_since_full {since} >= {full_every}"
    else:
        mode, reason = "incremental", f"artifacts_since_full {since} < {full_every}"
    res = {
        "ledger": str(ledger), "run_id": run_id, "work_dir": str(wd), "first_run": first_run,
        "mode_hint": mode, "mode_reason": reason,
        "lang": os.environ.get("SLOP_COMPOST_LANG", "auto") or "auto",
        "full_every": full_every,
        "track_model": os.environ.get("SLOP_COMPOST_TRACK_MODEL", "sonnet") or "sonnet",
        "overrides_present": (ledger / "overrides.md").exists(),
        "sources_seeded": seeded,
    }
    if a.inputs is not None:
        res["bulk_question"] = a.inputs > 10
    nd = new_default_ids(ledger, defaults)
    if nd:
        res["new_default_sources"] = nd
    write_json(wd / "run.json", {"run_id": run_id, "mode_hint": mode, "mode_reason": reason,
                                 "first_run": first_run, "created_at": now_iso()})
    out(res)


# ---------------------------------------------------------------- fingerprint

def classify_input(raw: str) -> str:
    s = raw.strip()
    if re.match(r"^https?://", s):
        host = urlparse(s).netloc.lower()
        if host.endswith("notion.so") or host.endswith("notion.site"):
            return "notion"
        if host in ("github.com", "www.github.com") and len([p for p in urlparse(s).path.split("/") if p]) >= 2:
            return "github-url"
        return "url"
    m = re.match(r"^(.+?)@([^:@/\s]+):(.*)$", s)
    if m and os.path.isdir(os.path.expanduser(m.group(1))):
        return "git-ref"
    p = os.path.expanduser(s)
    if "\n" not in s and os.path.isdir(p):
        return "git-repo" if os.path.exists(os.path.join(p, ".git")) else "folder"
    if "\n" not in s and os.path.isfile(p):
        return "file"
    return "text"


def default_id(raw: str, kind: str) -> str:
    s = raw.strip()
    if kind in ("folder", "git-repo"):
        return slug(os.path.basename(os.path.abspath(os.path.expanduser(s)))) or "artifact"
    if kind == "file":
        return slug(os.path.splitext(os.path.basename(s))[0]) or "artifact"
    if kind == "git-ref":
        m = re.match(r"^(.+?)@([^:@/\s]+):(.*)$", s)
        repo = os.path.basename(os.path.abspath(os.path.expanduser(m.group(1))))
        last = [p for p in m.group(3).split("/") if p]
        return slug(repo + ("-" + last[-1] if last else "")) or "artifact"
    if kind == "github-url":
        return slug([p for p in urlparse(s).path.split("/") if p][1].replace(".git", ""))
    if kind == "notion":
        last = [p for p in urlparse(s).path.split("/") if p]
        name = re.sub(r"-?[0-9a-f]{32}$", "", last[-1]) if last else ""
        return slug(name) or "notion-page"
    if kind == "url":
        u = urlparse(s)
        last = [p for p in u.path.split("/") if p]
        host = u.netloc.lower().replace("www.", "")
        return slug(last[-1] if last else host.split(".")[0]) or "page"
    words = re.findall(r"[A-Za-z0-9]+", s)[:4]
    return slug("-".join(words)) or "idea-" + hashlib.sha1(s.encode()).hexdigest()[:6]


def text_hash(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def same_value(method: str, stored: str, new: str) -> bool:
    stored = (stored or "").split()[0] if stored else ""
    if not stored or not new:
        return False
    if method in ("git-head", "git-ref", "text-hash"):
        k = min(len(stored), len(new))
        return k >= 7 and stored[:k] == new[:k]
    return stored == new


def fingerprint_one(raw: str, kind: str):
    """-> dict(method, method_version?, value, source, needs_llm?, blocked?, files_total?)."""
    s = raw.strip()
    if kind in ("folder", "file"):
        p = Path(os.path.expanduser(s)).resolve()
        if kind == "file":
            return {"method": "file-hash", "method_version": FILE_HASH_VERSION, "value": single_file_hash(p), "source": str(p)}
        files, stats = walk_files(p)
        return {"method": "file-hash", "method_version": FILE_HASH_VERSION, "value": folder_hash(p), "source": str(p),
                "files_total": len(files), "type_hint": type_hint(files)}
    if kind == "git-repo":
        p = Path(os.path.expanduser(s)).resolve()
        head = run_git(["-C", str(p), "rev-parse", "HEAD"])
        files, _ = walk_files(p)
        res = {"method": "git-head", "value": head, "source": str(p), "files_total": len(files), "type_hint": type_hint(files)}
        if not head:
            res["blocked"] = f"git -C {p} rev-parse HEAD failed (empty repository?)"
        return res
    if kind == "git-ref":
        m = re.match(r"^(.+?)@([^:@/\s]+):(.*)$", s)
        repo = os.path.realpath(os.path.expanduser(m.group(1)))
        branch, sub = m.group(2), m.group(3).strip("/")
        val = run_git(["-C", repo, "rev-parse", f"{branch}:{sub}"])
        res = {"method": "git-ref", "value": val, "source": f"{repo}@{branch}:{sub}"}
        if not val:
            res["blocked"] = f"ref not found; refresh with: git -C {repo} fetch origin {branch}"
        return res
    if kind == "github-url":
        return {"method": "git-head", "value": None, "source": s.rstrip("/"), "needs_llm": True}
    if kind == "notion":
        return {"method": "notion-edited", "value": None, "source": s.rstrip("/"), "needs_llm": True}
    if kind == "url":
        return {"method": "url-modified", "value": None, "source": s.rstrip("/"), "needs_llm": True}
    return {"method": "text-hash", "value": text_hash(s), "source": "text", "type_hint": "idea"}


def type_hint(files) -> str:
    exts = [os.path.splitext(r)[1] for r, _ in files]
    if any(e in CODE_EXT for e in exts):
        return "code"
    return "writing" if exts else "idea"


def resolve_id(raw, kind, info, ledger, taken):
    known = known_artifacts(ledger)
    state_fp = state_of(ledger).get("fingerprints") or {}
    src = norm_source(info.get("source", ""))
    if kind == "text":
        for aid, fp in state_fp.items():
            if fp.get("method") == "text-hash" and same_value("text-hash", fp.get("value"), info["value"]):
                return aid
    elif src:
        for aid, ksrc in known.items():
            if ksrc and ksrc == src:
                return aid
    base = default_id(raw, kind)
    cand, n = base, 1
    while cand in known or cand in taken:
        n += 1
        cand = f"{base}-{n}"
    return cand


def status_for(ledger, aid, info):
    fp = (state_of(ledger).get("fingerprints") or {}).get(aid)
    res = {}
    if info.get("blocked"):
        return "blocked", res
    if info.get("value") is None:
        return "pending", res
    if not fp:
        return "new", res
    method = info["method"]
    if fp.get("method") == "file-hash" and method == "file-hash" and int(fp.get("method_version") or 1) < FILE_HASH_VERSION:
        res["migrated_from_version"] = int(fp.get("method_version") or 1)
        return "unchanged", res
    if fp.get("method") == method and same_value(method, fp.get("value"), info["value"]):
        return "unchanged", res
    res["previous"] = fp.get("value")
    return "changed", res


def changed_files(info, previous):
    if info["method"] == "git-head":
        repo = info["source"]
        if not previous or run_git(["-C", repo, "cat-file", "-t", previous]) != "commit":
            return None
        listing = run_git(["-C", repo, "diff", "--name-only", f"{previous}..HEAD"])
        return [l for l in (listing or "").splitlines() if l and not is_secret(os.path.basename(l))]
    if info["method"] == "git-ref":
        repo = info["source"].split("@")[0]
        listing = run_git(["-C", repo, "diff", "--name-only", previous, info["value"]])
        if listing is None:
            return None
        return [l for l in listing.splitlines() if l and not is_secret(os.path.basename(l))]
    return None


def cmd_fingerprint(a, ledger: Path):
    staged_path = None
    staged = {}
    if a.run:
        staged_path = require_work(ledger, a.run) / "fingerprints.json"
        staged = read_json(staged_path, {}) or {}
    results = []
    if a.set:
        aid, method, value = a.set
        if method not in ("git-head", "git-ref", "file-hash", "notion-edited", "url-modified", "text-hash"):
            raise LedgerError(f"unknown method: {method}")
        if not a.run:
            raise LedgerError("--set requires --run")
        prev = staged.get(aid, {})
        info = {"method": method, "value": value, "source": prev.get("source") or (a.source or "")}
        if not info["source"]:
            raise LedgerError(f"{aid}: no staged source; pass --source")
        st, extra = status_for(ledger, aid, info)
        rec = {"input": prev.get("input", info["source"]), "kind": prev.get("kind", "url"), "method": method,
               "value": value, "status": st, "artifact_id": aid, "source": info["source"]}
        rec.update(extra)
        staged[aid] = dict(rec, at=now_iso())
        results.append(rec)
    taken = set(staged)
    as_ids = a.as_ids or []
    part_max = {}
    for p in all_parts(ledger, a.run if staged_path is not None else None):
        m = re.match(r"^(.+)#p(\d+)$", p.get("id", ""))
        if m:
            part_max[m.group(1)] = max(part_max.get(m.group(1), 0), int(m.group(2)))
    cards = card_paths(ledger)
    for idx, raw in enumerate(a.inputs or []):
        kind = classify_input(raw)
        info = fingerprint_one(raw, kind)
        if idx < len(as_ids) and as_ids[idx]:
            aid = as_ids[idx]
        else:
            aid = resolve_id(raw, kind, info, ledger, taken)
        taken.add(aid)
        st, extra = status_for(ledger, aid, info)
        rec = {"input": raw if kind != "text" else (raw[:60] + ("..." if len(raw) > 60 else "")), "kind": kind,
               "method": info["method"], "value": info["value"], "status": st, "artifact_id": aid}
        if "method_version" in info:
            rec["method_version"] = info["method_version"]
        for k in ("needs_llm", "blocked", "files_total", "type_hint"):
            if k in info:
                rec[k] = info[k]
        rec.update(extra)
        rec["card"] = aid in cards
        rec["next_part"] = f"{aid}#p{part_max.get(aid, 0) + 1}"
        if st == "changed" and info["method"] in ("git-head", "git-ref"):
            files = changed_files(info, extra.get("previous"))
            if files is None:
                rec["previous_missing"] = True
            else:
                rec["changed_files"] = files[:200]
        results.append(rec)
        if staged_path is not None:
            keep = {k: v for k, v in rec.items() if k not in ("changed_files",)}
            keep["source"] = info["source"]
            keep["at"] = now_iso()
            staged[aid] = keep
    if staged_path is not None:
        write_json(staged_path, staged)
    statuses = [r["status"] for r in results if r["status"] not in ("blocked",)]
    res = {"inputs": results, "all_unchanged": bool(statuses) and all(s == "unchanged" for s in statuses)}
    out(res)


# ---------------------------------------------------------------- select-files

ENTRY_STEMS = {"main", "index", "app", "server", "cli", "__main__", "manage", "run"}
CONFIG_NAMES = {"package.json", "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "Dockerfile",
                "Makefile", "go.mod", "Cargo.toml", "tsconfig.json", "Procfile", "docker-compose.yml",
                "docker-compose.yaml", "vite.config.ts", "next.config.js", "manage.py"}


def count_lines(path: str) -> int:
    n = 0
    try:
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                n += chunk.count(b"\n")
    except OSError:
        return 0
    return n


def cmd_select_files(a, ledger: Path):
    root = Path(os.path.expanduser(a.folder)).resolve()
    if not root.is_dir():
        raise LedgerError(f"not a folder: {root}")
    files, stats = walk_files(root, special=True)
    rels = [r[2:] for r, _ in files]
    relset = set(rels)
    chosen, reasons = [], {}

    def add(path, reason):
        if path in relset and path not in reasons:
            chosen.append(path)
            reasons[path] = reason

    pkg = root / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
            for key in ("main", "module"):
                if isinstance(data.get(key), str):
                    add(os.path.normpath(data[key]), "entry: package.json " + key)
            b = data.get("bin")
            for v in (b.values() if isinstance(b, dict) else [b] if isinstance(b, str) else []):
                add(os.path.normpath(v), "entry: package.json bin")
        except (json.JSONDecodeError, OSError):
            pass
    pyproject = read_text(root / "pyproject.toml")
    for m in re.finditer(r'^\s*[\w-]+\s*=\s*"([\w.]+):\w+"', pyproject, re.M):
        mod = m.group(1).replace(".", "/")
        for cand in (mod + ".py", mod + "/__init__.py", "src/" + mod + ".py"):
            add(cand, "entry: pyproject script")
    for r in sorted(rels, key=lambda x: (x.count("/"), x)):
        parts = r.split("/")
        stem, ext = os.path.splitext(parts[-1])
        shallow = len(parts) <= 2 or (len(parts) == 3 and parts[0] in ("src", "cmd", "app"))
        if stem in ENTRY_STEMS and ext in CODE_EXT and shallow:
            add(r, "entry point")
        elif parts[0] == "cmd" and ext in CODE_EXT and len(parts) <= 3:
            add(r, "entry point (cmd/)")
    for r in sorted(rels):
        parts = r.split("/")
        if len(parts) == 1 and parts[0].lower().startswith("readme"):
            add(r, "readme")
    for r in sorted(rels):
        parts = r.split("/")
        if len(parts) == 2 and parts[0].lower() in ("docs", "doc") and os.path.splitext(r)[1] in (".md", ".mdx", ".txt"):
            add(r, "docs (top level)")
        elif len(parts) == 1 and os.path.splitext(r)[1] in (".md", ".mdx") and not parts[0].lower().startswith("readme"):
            add(r, "docs (top level)")
    for r in sorted(rels):
        parts = r.split("/")
        if (len(parts) == 1 and parts[-1] in CONFIG_NAMES) or (len(parts) == 3 and parts[0] == ".github" and parts[1] == "workflows"):
            add(r, "config")
    recent = []
    if run_git(["-C", str(root), "rev-parse", "--is-inside-work-tree"]) == "true":
        prefix = run_git(["-C", str(root), "rev-parse", "--show-prefix"]) or ""
        log = run_git(["-C", str(root), "log", "--name-only", "--pretty=format:", "-n", "30", "--", "."]) or ""
        for line in log.splitlines():
            line = line.strip()
            if line and line.startswith(prefix):
                rel = line[len(prefix):]
                if rel not in recent:
                    recent.append(rel)
        reason = "recently changed (git log)"
    else:
        reason = "recently changed (mtime)"
    by_mtime = sorted(rels, key=lambda r: -os.path.getmtime(root / r))
    for r in recent + by_mtime:
        add(r, reason if r in recent or not recent else "recently changed (mtime)")
    total = len(rels)
    selected = chosen[: a.max]
    res = {"folder": str(root), "total": total, "selected": len(selected), "partial": total > a.max,
           "files": [{"path": p, "lines": count_lines(str(root / p)), "reason": reasons[p]} for p in selected]}
    if stats["secrets_skipped"]:
        res["secrets_skipped"] = stats["secrets_skipped"]
    if stats["databases"]:
        res["databases"] = stats["databases"][:20]
    out(res)


# ---------------------------------------------------------------- recall

def followup_list(decisions):
    items = []
    for d in decisions:
        if d.get("decision") != "adopt" or d.get("stale") is True:
            continue
        fus = d.get("followups") or []
        if fus and (fus[-1].get("result") in ("done", "stopped")):
            continue
        items.append(d)
    return [{"label": f"F{i}", "id": d["id"], "run": d.get("run"), "track": d.get("track"),
             "candidate": d.get("candidate", ""), "skip_count": int(d.get("skip_count") or 0)}
            for i, d in enumerate(items, 1)]


def cmd_recall(a, ledger: Path):
    first = not (ledger / "state.json").exists()
    decisions = read_jsonl(ledger / "decisions.jsonl")
    fl = followup_list(decisions)
    adopted = [d for d in decisions if d.get("decision") == "adopt"]
    by_track = {}
    for d in adopted:
        t = by_track.setdefault(d.get("track", "?"), {"adopted": 0, "started": 0, "done": 0, "ids_started": []})
        t["adopted"] += 1
        fus = d.get("followups") or []
        if any(f.get("touched") for f in fus):
            t["started"] += 1
            t["ids_started"].append(d["id"])
        if any(f.get("result") == "done" for f in fus):
            t["done"] += 1
    lessons = parse_lessons(read_text(ledger / "lessons.md"))
    habits = [{"id": k, "sentence": v["sentence"], "repeat": v["repeat"]} for k, v in lessons.items() if v["repeat"] >= 3]
    intents = parse_intents(read_text(ledger / "intents.md"))["active"]
    compost = read_jsonl(ledger / "compost.jsonl")
    rule_runs = {}
    for c in compost:
        for r in c.get("failed_rules") or []:
            rule_runs.setdefault(r, {"runs": set(), "ids": []})
            rule_runs[r]["runs"].add(c.get("run"))
            rule_runs[r]["ids"].append(c.get("id"))
    hotspots = [{"rule": r, "runs": len(v["runs"]), "count": len(v["ids"]), "ids": v["ids"][:5]}
                for r, v in sorted(rule_runs.items()) if len(v["runs"]) >= 3]
    nums = [int(k[1:]) for k in lessons]
    out({"first_run": first, "followups": fl,
         "summary": {"adoption": by_track, "habits": habits, "active_intents": intents,
                     "compost_hotspots": hotspots, "profile_present": (ledger / "profile.md").exists()},
         "lessons": [{"id": k, "sentence": v["sentence"], "repeat": v["repeat"]} for k, v in lessons.items()],
         "next_lesson_id": f"L{max(nums or [0]) + 1}"})


SKIP_WORDS = ["skip", "s", "pass", "스킵", "건너뜀", "패스"]
TOUCH_WORDS = {"yes": True, "y": True, "손댔음": True, "했음": True, "함": True,
               "no": False, "n": False, "안 함": False, "안함": False, "못 함": False, "못함": False}
RESULT_WORDS = {"not-started": "not-started", "not started": "not-started", "시작 안 함": "not-started",
                "시작안함": "not-started", "시작 안함": "not-started", "미착수": "not-started",
                "in-progress": "in-progress", "in progress": "in-progress", "진행중": "in-progress",
                "진행 중": "in-progress", "done": "done", "완료": "done", "stopped": "stopped",
                "stop": "stopped", "중단": "stopped", "그만둠": "stopped"}


def split_items(line: str) -> list:
    items, buf, quote = [], "", None
    pairs = {'"': '"', "“": "”", "'": "'"}
    for ch in line:
        if quote:
            buf += ch
            if ch == quote:
                quote = None
        elif ch in pairs and (ch != "'" or not buf or buf[-1] in " \t"):
            quote = pairs[ch]
            buf += ch
        elif ch in ",;":
            items.append(buf.strip())
            buf = ""
        else:
            buf += ch
    if buf.strip():
        items.append(buf.strip())
    return [i for i in items if i]


def extract_quote(text: str):
    m = re.search(r'"([^"]*)"|“([^”]*)”|\'([^\']*)\'', text)
    if not m:
        return text, None
    note = next(g for g in m.groups() if g is not None)
    return (text[:m.start()] + " " + text[m.end():]).strip(), note


def match_phrases(tokens, table):
    """Greedy longest-phrase match. Returns (matches list of (value), leftover tokens)."""
    phrases = sorted(table.keys(), key=lambda p: -len(p.split()))
    found, rest, i = [], [], 0
    while i < len(tokens):
        for p in phrases:
            pt = p.split()
            if [t.lower() for t in tokens[i:i + len(pt)]] == pt:
                found.append(table[p])
                i += len(pt)
                break
        else:
            rest.append(tokens[i])
            i += 1
    return found, rest


def parse_followup_item(body: str):
    text, note = extract_quote(body)
    tokens = text.split()
    if len(tokens) == 1 and tokens[0].lower() in SKIP_WORDS:
        return {"skip": True}
    table = {}
    table.update({k: ("result", v) for k, v in RESULT_WORDS.items()})
    table.update({k: ("touched", v) for k, v in TOUCH_WORDS.items()})
    table.update({k: ("skip", True) for k in SKIP_WORDS if k != "s"})
    found, rest = match_phrases(tokens, table)
    touched = result = None
    skip = False
    for kind, val in found:
        if kind == "result" and result is None:
            result = val
        elif kind == "touched" and touched is None:
            touched = val
        elif kind == "skip":
            skip = True
    if skip and touched is None and result is None:
        return {"skip": True}
    if touched is None and result is None:
        return None
    if result is None:
        result = "in-progress" if touched else "not-started"
    if touched is None:
        touched = result != "not-started"
    if note is None:
        note = " ".join(rest).strip()
    return {"touched": touched, "result": result, "note": note}


def cmd_apply_recall(a, ledger: Path):
    wd = require_work(ledger, a.run)
    decisions = read_jsonl(ledger / "decisions.jsonl")
    dmap = {d["id"]: d for d in decisions}
    fl = followup_list(decisions)
    path = wd / "recall.json"
    staged = read_json(path, None) or {"updates": {}, "resolved": {}, "pending": []}
    by_f = {f["label"].upper(): f for f in fl}
    applied, skipped, unparsed, ambiguous, stale_now = [], [], [], [], []
    mentioned = set()
    line = (a.answer or "").strip()
    if line.lower() in SKIP_WORDS or line == "":
        items = []
        global_skip = True
    else:
        items = split_items(line)
        global_skip = False
    for item in items:
        m = re.match(r"^\s*(\S+)\s*(.*)$", item)
        label, body = m.group(1), m.group(2)
        label = label.rstrip(":")
        target = None
        if label.upper() in by_f:
            target = by_f[label.upper()]
        else:
            exact = [f for f in fl if f["id"].lower() == label.lower()]
            short = [f for f in fl if f["id"].split(":")[-1].lower() == label.lower()]
            if exact:
                target = exact[0]
            elif len(short) == 1:
                target = short[0]
            elif len(short) > 1:
                ambiguous.append({"item": item, "matches": [f["id"] for f in short]})
                for f in short:
                    mentioned.add(f["id"])
                continue
        if target is None:
            if label.lower() in SKIP_WORDS and not body:
                global_skip = True
                continue
            unparsed.append({"item": item, "reason": "unknown label"})
            continue
        mentioned.add(target["id"])
        parsed = parse_followup_item(body)
        if parsed is None:
            unparsed.append({"item": item, "reason": "no touched/result/skip word"})
            continue
        if parsed.get("skip"):
            staged["resolved"][target["id"]] = "skip"
        else:
            staged["resolved"][target["id"]] = {"at": now_iso(), "touched": parsed["touched"],
                                                "result": parsed["result"], "note": parsed["note"]}
    # mentioned but not parsed -> ask again; everything else left unresolved counts as a skip
    pending = set()
    for f in fl:
        fid = f["id"]
        if fid in staged["resolved"]:
            continue
        if fid in mentioned:
            pending.add(fid)
        else:
            staged["resolved"][fid] = "skip"
    updates = {}
    for f in fl:
        fid = f["id"]
        d = dmap[fid]
        r = staged["resolved"].get(fid)
        if r is None:
            continue
        if r == "skip":
            sc = int(d.get("skip_count") or 0) + 1
            upd = {"skip_count": sc}
            if sc >= 3:
                upd["stale"] = True
                stale_now.append(f["label"])
            updates[fid] = upd
            skipped.append(f["label"])
        else:
            updates[fid] = {"followup": r, "skip_count": 0}
            applied.append(f["label"])
    staged["updates"] = updates
    staged["pending"] = sorted(pending)
    write_json(path, staged)
    out({"applied": applied, "skipped": skipped, "stale": stale_now, "unparsed": unparsed, "ambiguous": ambiguous})


# ---------------------------------------------------------------- bundles

PART_REF = re.compile(r"\b([A-Za-z0-9][\w.-]*#p\d+)\b")
A_REF = re.compile(r"`?\b\d{4}-\d{2}-\d{2}(?:-\d+)?:A\d+\b`?|\bA\d+\b|\b[Tt]rack A\b|트랙 ?A")


def all_parts(ledger: Path, run: str = None) -> list:
    parts = read_jsonl(ledger / "parts.jsonl")
    if run:
        parts += read_jsonl(work_dir(ledger, run) / "parts.pending.jsonl")
    return parts


def run_scope(ledger: Path, wd: Path) -> list:
    fps = read_json(wd / "fingerprints.json", {}) or {}
    ids = [k for k, v in fps.items() if v.get("status") != "blocked"]
    if not ids and (wd / "artifacts").is_dir():
        ids = [p.stem for p in sorted((wd / "artifacts").glob("*.md"))]
    return ids


def card_text(ledger: Path, wd: Path, aid: str) -> str:
    draft = wd / "artifacts" / f"{aid}.md"
    base = read_text(ledger / "artifacts" / f"{aid}.md")
    if draft.exists():
        d = read_text(draft)
        return (base + "\n\n<!-- update draft -->\n" + strip_front_matter(d)) if base and not d.startswith("---") else d
    return base


def card_goal(text: str) -> str:
    for line in text.splitlines():
        m = re.match(r"^\s*[-*]\s*(Goal|목표)\s*[:：]\s*(.+)$", line, re.I)
        if m:
            return m.group(2).strip()
    body = [l.strip() for l in strip_front_matter(text).splitlines() if l.strip() and not l.startswith("#")]
    return body[0][:160] if body else ""


def lessons_for_bundle(ledger: Path, wd: Path) -> str:
    work = read_text(wd / "lessons.md").strip()
    if work:
        return work
    lessons = parse_lessons(read_text(ledger / "lessons.md"))
    return "\n".join(f"- **{k}**{' [structural habit]' if v['habit'] else ''} {v['sentence']} (repeat {v['repeat']})"
                     for k, v in lessons.items())


def intents_for_bundle(ledger: Path, wd: Path) -> list:
    src = wd / "intents.md" if (wd / "intents.md").exists() else ledger / "intents.md"
    return parse_intents(read_text(src))["active"]


def part_line(p) -> str:
    return f"- `{p.get('id')}` ({p.get('kind')}) `{p.get('location')}` - {p.get('description')} - why: {p.get('why_reusable')}"


def scrub(text: str):
    new, n = A_REF.subn("another candidate", text)
    return new, n


def cmd_bundle(a, ledger: Path):
    wd = require_work(ledger, a.run)
    scope = run_scope(ledger, wd)
    pending = read_jsonl(wd / "parts.pending.jsonl")
    ledger_parts = read_jsonl(ledger / "parts.jsonl")
    intents = intents_for_bundle(ledger, wd)
    profile = profile_current(read_text(ledger / "profile.md"))
    lessons = lessons_for_bundle(ledger, wd)
    items = {}
    if a.track == "a":
        lines = [f"# Track A input (run {a.run})", "", "## Artifacts (run scope)"]
        for aid in scope:
            lines += ["", f"### {aid}", card_text(ledger, wd, aid).strip() or "(no card)"]
        parts = [p for p in ledger_parts + pending if p.get("artifact_id") in scope]
        lines += ["", "## Parts"] + [part_line(p) for p in parts]
        lines += ["", "## Lessons", lessons or "(none)"]
        lines += ["", "## Active intents"] + [f'- {i["id"]} "{i["text"]}"' for i in intents]
        lines += ["", "## Profile excerpt", profile or "(none)"]
        items = {"artifacts": len(scope), "parts": len(parts), "intents": len(intents)}
        path = wd / "input-a.md"
    else:
        known = known_artifacts(ledger)
        ids = list(dict.fromkeys(scope + list(known)))
        lines = [f"# Track B input (run {a.run})", "", "## Artifacts (one line each)"]
        for aid in ids:
            t = card_text(ledger, wd, aid)
            fm = front_matter(t)
            lines.append(f"- `{aid}` ({fm.get('type', '?')}): {card_goal(t)}")
        parts = ledger_parts + pending
        lines += ["", "## Parts (all)"] + [part_line(p) for p in parts]
        lines += ["", "## Lessons", lessons or "(none)"]
        lines += ["", "## Active intents"] + [f'- {i["id"]} "{i["text"]}"' for i in intents]
        scrubbed = 0
        kept = []
        for line in profile.splitlines():
            if A_REF.search(line):
                scrubbed += 1
                continue
            kept.append(line)
        lines += ["", "## Profile excerpt (Track A references removed)", "\n".join(kept).strip() or "(none)"]
        rejected = []
        for d in read_jsonl(ledger / "decisions.jsonl"):
            if d.get("track") == "B" and d.get("decision") == "reject":
                cand, n1 = scrub(d.get("candidate", ""))
                reason, n2 = scrub(d.get("reason", ""))
                scrubbed += n1 + n2
                rejected.append(f"- `{d['id']}`: {cand} - reason: {reason or '(none)'}")
        lines += ["", "## Past rejected Track B candidates"] + (rejected or ["(none)"])
        reusable = []
        for c in read_jsonl(ledger / "compost.jsonl"):
            rules = c.get("failed_rules") or []
            if c.get("step") == "05b" and c.get("kind") == "candidate" and rules and all(".ev-" in r for r in rules):
                content, n = scrub(c.get("content", ""))
                scrubbed += n
                reusable.append(f"### {c['id']} (failed: {', '.join(rules)})\n{content}")
        lines += ["", "## Reusable compost"] + (reusable or ["(none)"])
        items = {"artifacts": len(ids), "parts": len(parts), "intents": len(intents),
                 "rejected_b": len(rejected), "reusable_compost": len(reusable), "scrubbed": scrubbed}
        path = wd / "input-b.md"
    text = "\n".join(lines) + "\n"
    write_atomic(path, text)
    out({"path": str(path), "bytes": len(text.encode("utf-8")), "items": items})


# ---------------------------------------------------------------- markdown candidate parsing

FIELD_KEYS = [
    ("counter", ["counter-evidence", "counter evidence", "반대 증거", "반대 근거", "반증 근거"]),
    ("evidence", ["external evidence", "외부 근거", "외부 증거"]),
    ("experiment", ["first experiment", "experiment", "첫 실험", "실험"]),
    ("success", ["success", "성공"]),
    ("kill", ["kill", "중단 기준", "중단", "stop"]),
    ("parts", ["parts", "부품"]),
    ("lessons", ["lessons", "lesson", "교훈"]),
    ("source_ids", ["source ids"]),
    ("who_pays", ["who pays", "누가 돈", "지불"]),
    ("intents", ["intents", "의도"]),
    ("falsifier", ["falsifier", "반증"]),
    ("loc_evidence", ["evidence", "근거"]),
]


def field_kind(key: str):
    k = key.strip().strip("*").strip().lower()
    for kind, words in FIELD_KEYS:
        if any(k.startswith(w) for w in words):
            return kind
    return None


def parse_fields(block: str) -> dict:
    """field kind -> text (value plus indented continuation lines)."""
    fields, cur = {}, None
    for line in block.splitlines()[1:]:
        m = re.match(r"^ {0,1}[-*]\s+(.*)$", line)
        if m:
            cur = None
            for seg in m.group(1).split("|"):
                mm = re.match(r"^\s*\**([^:：]{1,40}?)\**\s*[:：]\s*(.*)$", seg)
                if mm:
                    kind = field_kind(mm.group(1))
                    if kind:
                        fields[kind] = (fields.get(kind, "") + "\n" + mm.group(2)).strip()
                        cur = kind
            continue
        if cur and (line.startswith("  ") or line.startswith("\t")) and line.strip():
            fields[cur] = (fields[cur] + "\n" + line.strip()).strip()
        elif not line.strip():
            continue
        else:
            cur = None
    return fields


def evidence_items(text: str) -> list:
    items = []
    for line in text.splitlines():
        line = re.sub(r"^\s*[-*]\s*", "", line).strip()
        if not line:
            continue
        items += [s.strip() for s in re.split(r";\s+", line) if s.strip()]
    return items


def too_long(experiment: str) -> bool:
    t = experiment.lower()
    for m in re.finditer(r"(\d+)\s*-?\s*(days?|일)", t):
        if int(m.group(1)) > 7:
            return True
    for m in re.finditer(r"(\d+)\s*-?\s*(weeks?|주)", t):
        if int(m.group(1)) >= 2:
            return True
    return bool(re.search(r"\d+\s*-?\s*(months?|개월|달)\b", t))


class LintCtx:
    def __init__(self, ledger: Path, run: str = None):
        self.ledger, self.run = ledger, run
        self.wd = work_dir(ledger, run) if run else None
        self.parts = {p.get("id") for p in all_parts(ledger, run if run and self.wd.exists() else None)}
        self.artifacts = dict(known_artifacts(ledger))
        if self.wd and self.wd.exists():
            for aid, v in (read_json(self.wd / "fingerprints.json", {}) or {}).items():
                self.artifacts[aid] = norm_source(v.get("source", ""))
        for p in self.parts:
            self.artifacts.setdefault(p.split("#")[0], "")
        src_doc = parse_sources(read_text(ledger / "sources.md"))
        self.sources = {e["id"]: e for e in src_doc["entries"]}


def check_candidate(track: str, block: str, ctx: LintCtx):
    rules, warnings = set(), []
    pre = "05a" if track == "A" else "05b"
    f = parse_fields(block)
    exp = f.get("experiment", "")
    if not exp.strip() or too_long(exp):
        rules.add(f"{pre}.no-experiment")
    if not re.search(r"\d", f.get("success", "")):
        rules.add(f"{pre}.no-number")
    if not re.search(r"\d", f.get("kill", "")):
        warnings.append("kill criterion missing or without a number")
    refs = PART_REF.findall(f.get("parts", ""))
    if not refs or any(r not in ctx.parts for r in refs):
        rules.add(f"{pre}.ev-no-part")
    if track == "A":
        lt = f.get("lessons", "")
        ids = re.findall(r"\bL\d+\b", lt)
        if not ids:
            rules.add("05a.ev-no-lesson-link")
        else:
            for seg in re.split(r"[,;\n]", lt):
                if re.search(r"\bL\d+\b", seg) and not re.search(r"->|→|=>", seg):
                    rules.add("05a.ev-no-lesson-link")
    else:
        ev_items = evidence_items(f.get("evidence", ""))
        if not ev_items:
            rules.add("05b.ev-no-source")
        for it in ev_items:
            rules |= check_evidence_item(it, ctx)
        counter = f.get("counter", "")
        c_items = evidence_items(counter)
        case_items = [i for i in c_items if re.search(r"https?://|\[src:|\d{4}-\d{2}-\d{2}", i)]
        none_found = [i for i in c_items if re.search(r"none found|찾지 못|없음", i, re.I) and re.search(r"[\"“'`]", i)]
        mech = [i for i in c_items if i not in case_items and i not in none_found and len(i) >= 10]
        if not counter.strip() or not mech or not (case_items or none_found):
            rules.add("05b.ev-no-counter")
        for it in case_items:
            rules |= check_evidence_item(it, ctx)
        if "source_ids" not in f:
            warnings.append("missing 'Source ids:' line")
    return sorted(rules), warnings


def check_evidence_item(item: str, ctx: LintCtx) -> set:
    rules = set()
    if re.search(r"cap reached", item, re.I):
        return rules
    tags = re.findall(r"\[src:([\w.-]+)\]", item)
    urls = re.findall(r"https?://[^\s)\]>`'\"]+", item)
    local = [t for t in tags if t in ctx.sources and "local" in ctx.sources[t]["fields"].get("type", "")]
    if not urls and not (local and re.search(r"\b[\w.-]+:[\w./-]+", item)):
        rules.add("05b.ev-no-source")
    if not re.search(r"\b\d{4}-\d{2}-\d{2}\b", item):
        rules.add("05b.ev-no-date")
    if not tags or any(t not in ctx.sources for t in tags):
        rules.add("05b.ev-no-src-id")
    for t in tags:
        if t not in ctx.sources:
            continue
        doms = source_domains(ctx.sources[t])
        if not doms or "local" in ctx.sources[t]["fields"].get("type", ""):
            continue
        for u in urls:
            host = urlparse(u).netloc.lower()
            host = host[4:] if host.startswith("www.") else host
            if not any(host == d.split("/")[0] or host.endswith("." + d.split("/")[0]) for d in doms):
                rules.add("05b.ev-no-source")
    return rules


def location_exists(loc: str, ctx: LintCtx) -> bool:
    loc = loc.strip("`").strip()
    m = re.match(r"^([A-Za-z0-9][\w.-]*)(?:([:@#])(.*))?$", loc)
    if not m:
        return False
    aid, sep, rest = m.group(1), m.group(2), m.group(3) or ""
    if aid not in ctx.artifacts:
        return False
    if sep == "#":
        return loc in ctx.parts
    if sep != ":" or not rest:
        return sep == "@" and bool(rest)
    src = ctx.artifacts.get(aid) or ""
    pm = re.match(r"^([^:]+?)(?::(¶?\d+)(?:-(\d+))?)?$", rest)
    if not pm:
        return True
    base = Path(src) if src and os.path.isdir(src) else None
    if base is None:
        return True  # text, url or notion artifact: path cannot be checked here
    target = base / pm.group(1)
    if not target.is_file():
        return False
    line = pm.group(2)
    if line and not line.startswith("¶"):
        last = int(pm.group(3) or line)
        return count_lines(str(target)) + 1 >= last
    return True


def lint_lessons(text: str, ctx: LintCtx):
    existing = parse_lessons(read_text(ctx.ledger / "lessons.md"))
    norm = {re.sub(r"\W+", " ", v["sentence"].lower()).strip(): k for k, v in existing.items() if v["sentence"]}
    res = []
    for m, s, e, body in blocks(text, LESSON_HEAD):
        lid = m.group(2)
        rules = set()
        f = parse_fields(body)
        locs = re.findall(r"`([^`]+)`", f.get("loc_evidence", ""))
        if not locs or not any(location_exists(l, ctx) for l in locs):
            rules.add("03.ev-no-location")
        if lid not in existing and not f.get("falsifier", "").strip():
            rules.add("03.unfalsifiable")  # a repeat entry carries only new evidence
        sentence = HABIT_RE.sub("", m.group(3)).strip()
        key = re.sub(r"\W+", " ", sentence.lower()).strip()
        if lid not in existing and key and key in norm:
            rules.add("03.duplicate")
        res.append((lid, body, sorted(rules), []))
    return res


def candidate_blocks(text: str):
    return [(m.group(2) + m.group(3), m.group(2), m.group(4).strip(), body) for m, s, e, body in blocks(text, CAND_HEAD)]


def compost_labels(rows) -> set:
    labels = set()
    for c in rows:
        m = re.search(r"(?m)^\s*#{0,5}\s*\**\s*([AB]\d+)\b", c.get("content", "")) or re.match(r"^\s*([AB]\d+)\b", c.get("content", ""))
        if m:
            labels.add(m.group(1))
    return labels


def similarity(a: str, b: str) -> float:
    ta, tb = set(re.findall(r"\w+", a.lower())), set(re.findall(r"\w+", b.lower()))
    return len(ta & tb) / max(1, len(ta | tb))


def lint_tracks(text: str, ctx: LintCtx, only: str = None):
    res = []
    for label, track, definition, body in candidate_blocks(text):
        if only and track != only:
            continue
        rules, warns = check_candidate(track, body, ctx)
        res.append((label, body, rules, warns))
    return res


def lint_direction(text: str, ctx: LintCtx):
    res = lint_tracks(text, ctx)
    extra = {}
    file_rules = []
    if not (re.search(r"(?m)^\|.*#p\d+", text) and re.search(r"(?im)^#{2,4}.*(pattern|패턴)", text)):
        file_rules.append("06.missing-parts-section")
    labels = candidate_blocks(text)
    for t in ("A", "B"):
        if not any(l[1] == t for l in labels) and not re.search(
                rf"(?i)no track {t} candidate|트랙 ?{t}.*(없|살아남지)", text):
            file_rules.append("06.single-track")
    if ctx.wd and ctx.wd.exists():
        composted = read_jsonl(ctx.wd / "compost.pending.jsonl") + read_jsonl(ctx.wd / "compost.track-a.jsonl") + \
            read_jsonl(ctx.wd / "compost.track-b.jsonl")
        clabels = compost_labels(composted)
        for t, fname in (("A", "track-a.md"), ("B", "track-b.md")):
            track_text = read_text(ctx.wd / fname)
            if not track_text:
                continue
            tdefs = {l: d for l, tr, d, b in candidate_blocks(track_text)}
            for label, tr, d, b in labels:
                if tr != t:
                    continue
                if label in clabels:
                    extra.setdefault(label, set()).add("06.compost-shown")
                if label not in tdefs:
                    extra.setdefault(label, set()).add("06.label-mismatch")
                    continue
                own = similarity(d, tdefs[label])
                if any(similarity(d, od) > own + 0.2 for ol, od in tdefs.items() if ol != label):
                    extra.setdefault(label, set()).add("06.label-mismatch")
    out_rows = []
    for label, body, rules, warns in res:
        out_rows.append((label, body, sorted(set(rules) | extra.pop(label, set())), warns))
    for label, rules in extra.items():
        out_rows.append((label, "", sorted(rules), []))
    if file_rules:
        out_rows.append(("(file)", "", sorted(set(file_rules)), []))
    return out_rows


def infer_run(path: Path):
    if path.parent.name.endswith(".work"):
        return path.parent.name[:-5]
    if path.parent.name == "runs" and re.match(r"^\d{4}-\d{2}-\d{2}(-\d+)?$", path.stem):
        return path.stem
    return None


LLM_CHECKS = {
    "lessons": ["03.unfalsifiable (meaning)", "03.multi-claim", "03.duplicate (paraphrase)"],
    "track-a": ["05a.same-as-before", "05a.saw-track-b", "05a.no-number (observable?)"],
    "track-b": ["05b.ev-no-counter (mechanism is specific)", "05b.compost-unfixed", "05b.saw-track-a", "05b.blocked-path"],
    "direction": ["06.reframed", "05a/05b semantic rules"],
}


def cmd_lint(a, ledger: Path):
    path = Path(a.file).expanduser().resolve()
    if not path.exists():
        raise LedgerError(f"file not found: {path}")
    run = a.run or infer_run(path)
    ctx = LintCtx(ledger, run)
    text = read_text(path)
    if a.kind == "lessons":
        rows = lint_lessons(text, ctx)
    elif a.kind == "track-a":
        rows = lint_tracks(text, ctx, "A")
    elif a.kind == "track-b":
        rows = lint_tracks(text, ctx, "B")
    else:
        rows = lint_direction(text, ctx)
    if a.kind in ("track-a", "track-b") and ctx.wd and ctx.wd.exists():
        cfile = ctx.wd / ("compost.track-a.jsonl" if a.kind == "track-a" else "compost.track-b.jsonl")
        clabels = compost_labels(read_jsonl(cfile))
        rule = "05a.compost-in-output" if a.kind == "track-a" else "05b.compost-in-output"
        rows = [(l, b, sorted(set(r) | ({rule} if l in clabels else set())), w) for l, b, r, w in rows]
    violations = [{"label": l, "rule_ids": r} for l, b, r, w in rows if r]
    warnings = [{"label": l, "warnings": w} for l, b, r, w in rows if w]
    res = {"file": str(path), "kind": a.kind, "checked": len([r for r in rows if r[0] != "(file)"]),
           "violations": violations, "llm_checks": LLM_CHECKS[a.kind]}
    if warnings:
        res["warnings"] = warnings
    if a.compost:
        if not run:
            raise LedgerError("--compost needs --run")
        res["composted"] = compost_rows(ledger, run, a.kind, a.step, rows)
    out(res)


def compost_rows(ledger: Path, run: str, kind: str, step: str, rows) -> list:
    wd = require_work(ledger, run)
    fname = {"track-a": "compost.track-a.jsonl", "track-b": "compost.track-b.jsonl"}.get(kind, "compost.pending.jsonl")
    target = wd / fname
    existing = read_jsonl(target)
    have = {(c.get("step"), first_label(c.get("content", ""))) for c in existing}
    prefix = {"track-a": "a", "track-b": "b"}.get(kind, "")
    used = set()
    for c in existing:
        m = re.match(rf"^C-{re.escape(run)}-{prefix}(\d+)$", c.get("id", ""))
        if m:
            used.add(int(m.group(1)))
    if not prefix:
        for f in ("compost.pending.jsonl",):
            for c in read_jsonl(wd / f):
                m = re.match(rf"^C-{re.escape(run)}-(\d+)$", c.get("id", ""))
                if m:
                    used.add(int(m.group(1)))
    new_rows, ids = [], []
    n = max(used or {0})
    for label, body, rules, warns in rows:
        rules = [r for r in rules if not r.startswith("06.") and r != "05b.blocked-path"]
        if not rules or not body:
            continue
        st = step or {"lessons": "03", "track-a": "05a", "track-b": "05b"}.get(kind) or rules[0].split(".")[0]
        if (st, label) in have:
            continue
        n += 1
        cid = f"C-{run}-{prefix}{n}"
        new_rows.append({"id": cid, "run": run, "step": st, "kind": "lesson" if kind == "lessons" else "candidate",
                         "content": body, "failed_rules": rules, "at": now_iso()})
        ids.append(cid)
    if new_rows:
        write_atomic(target, read_text(target) + jsonl_text(new_rows))
    return ids


def first_label(content: str):
    m = re.search(r"(?m)^\s*#{0,5}\s*\**\s*([ABL]\d+)\b", content)
    return m.group(1) if m else None


# ---------------------------------------------------------------- judge

DECISION_WORDS = {"adopt": "adopt", "a": "adopt", "채택": "adopt", "hold": "hold", "h": "hold", "보류": "hold",
                  "reject": "reject", "r": "reject", "기각": "reject"}


def direction_labels(ledger: Path, run: str) -> list:
    path = ledger / "runs" / f"{run}.md"
    if not path.exists():
        raise LedgerError(f"run file not found: {path}")
    return [l for l, t, d, b in candidate_blocks(read_text(path))]


def cmd_judge(a, ledger: Path):
    wd = require_work(ledger, a.run)
    labels = direction_labels(ledger, a.run)
    path = wd / "judgments.json"
    staged = read_json(path, None) or {}
    unparsed = []
    line = (a.answer or "").strip()
    for item in split_items(line):
        m = re.match(r"^\s*([A-Za-z]\d+(?:\s*[+&/≈=]\s*[A-Za-z]\d+)*)\s*[:：]?\s*(\S+)?\s*(.*)$", item)
        if not m:
            unparsed.append({"item": item, "reason": "no label"})
            continue
        group = [g.strip().upper() for g in re.split(r"[+&/≈=]", m.group(1))]
        word = (m.group(2) or "").lower()
        reason = m.group(3).strip()
        if word not in DECISION_WORDS:
            for w in sorted(DECISION_WORDS, key=len, reverse=True):
                if len(w) > 1 and word.startswith(w):
                    reason = (word[len(w):] + " " + reason).strip()
                    word = w
                    break
        if word not in DECISION_WORDS:
            unparsed.append({"item": item, "reason": "unknown decision"})
            continue
        bad = [g for g in group if g not in labels]
        if bad:
            unparsed.append({"item": item, "reason": "unknown label " + ",".join(bad)})
            continue
        reason = reason.strip().strip('"“”').strip()
        for g in group:
            staged[g] = {"label": g, "track": g[0], "decision": DECISION_WORDS[word], "reason": reason}
    decisions = []
    for l in labels:
        d = staged.get(l) or {"label": l, "track": l[0], "decision": "hold", "reason": "", "defaulted": True}
        decisions.append(d)
    write_json(path, {d["label"]: d for d in decisions})
    out({"decisions": decisions, "unparsed": unparsed})


# ---------------------------------------------------------------- schemas

def check_row(kind: str, row: dict) -> list:
    errs = []
    req = {
        "parts": {"id": str, "artifact_id": str, "kind": str, "location": str, "description": str,
                  "why_reusable": str, "run": str, "at": str},
        "decisions": {"id": str, "run": str, "track": str, "candidate": str, "decision": str, "reason": str,
                      "artifact_ids": list, "lesson_ids": list, "at": str, "followups": list,
                      "skip_count": int, "stale": bool},
        "compost": {"id": str, "run": str, "step": str, "kind": str, "content": str, "failed_rules": list,
                    "at": str, "reused_in": list},
    }[kind]
    if not isinstance(row, dict):
        return ["not an object"]
    for k in row:
        if not re.match(r"^[a-z][a-z0-9_]*$", k):
            errs.append(f"non-English key {k!r}")
    for k, t in req.items():
        if k not in row:
            errs.append(f"missing {k}")
        elif not isinstance(row[k], t) or (t is int and isinstance(row[k], bool)):
            errs.append(f"{k} must be {t.__name__}")
    if errs:
        return errs
    if not AT_RE.match(row["at"]):
        errs.append("at must be ISO 8601 with offset")
    if kind == "parts":
        if row["kind"] not in PART_KINDS:
            errs.append(f"kind {row['kind']!r} not in enum")
        if not re.match(r"^.+#p\d+$", row["id"]) or not row["id"].startswith(row["artifact_id"] + "#"):
            errs.append("id must be <artifact_id>#p<n>")
    elif kind == "decisions":
        if row["track"] not in ("A", "B"):
            errs.append("track must be A|B")
        if row["decision"] not in DECISIONS:
            errs.append("decision not in enum")
        for f in row["followups"]:
            if not isinstance(f, dict) or not isinstance(f.get("touched"), bool) or f.get("result") not in RESULTS \
                    or not isinstance(f.get("at"), str) or not isinstance(f.get("note", ""), str):
                errs.append("bad followup")
        for k in ("source_ids",):
            if k in row and not isinstance(row[k], list):
                errs.append(f"{k} must be list")
    elif kind == "compost":
        if row["kind"] not in COMPOST_KINDS:
            errs.append("kind not in enum")
    return errs


def validate_ledger(ledger: Path) -> dict:
    errors, warnings, counts = [], [], {}
    ids = {}
    for kind, fname in (("parts", "parts.jsonl"), ("decisions", "decisions.jsonl"), ("compost", "compost.jsonl")):
        try:
            rows = read_jsonl(ledger / fname)
        except LedgerError as exc:
            errors.append(str(exc))
            rows = []
        counts[kind] = len(rows)
        seen = set()
        for n, r in enumerate(rows, 1):
            for e in check_row(kind, r):
                errors.append(f"{fname}:{n}: {e}")
            rid = r.get("id") if isinstance(r, dict) else None
            if rid in seen:
                errors.append(f"{fname}:{n}: duplicate id {rid}")
            seen.add(rid)
        ids[kind] = rows
    state = {}
    try:
        state = read_json(ledger / "state.json", {}) or {}
    except LedgerError as exc:
        errors.append(str(exc))
    if state:
        for k in ("runs", "fingerprints"):
            if k not in state:
                errors.append(f"state.json: missing {k}")
    lessons = parse_lessons(read_text(ledger / "lessons.md"))
    arts = known_artifacts(ledger)
    compost_ids = {c.get("id") for c in ids["compost"]}
    decision_ids = {d.get("id") for d in ids["decisions"]}
    runs = set(state.get("runs") or [])
    for d in ids["decisions"]:
        for l in d.get("lesson_ids") or []:
            if l not in lessons:
                errors.append(f"decisions {d.get('id')}: unknown lesson {l}")
        for aid in d.get("artifact_ids") or []:
            if aid not in arts:
                errors.append(f"decisions {d.get('id')}: unknown artifact {aid}")
        rc = d.get("reused_compost")
        if rc and rc not in compost_ids:
            errors.append(f"decisions {d.get('id')}: unknown reused_compost {rc}")
    for p in ids["parts"]:
        if p.get("artifact_id") not in arts:
            warnings.append(f"parts {p.get('id')}: artifact has no card or fingerprint")
    for c in ids["compost"]:
        for r in c.get("reused_in") or []:
            if runs and r not in runs:
                warnings.append(f"compost {c.get('id')}: reused_in run {r} not in state.runs")
    errors += profile_errors(read_text(ledger / "profile.md"), decision_ids, set(lessons), compost_ids,
                             {i["id"] for s in parse_intents(read_text(ledger / "intents.md")).values() for i in s})
    return {"ok": not errors, "errors": errors[:100], "warnings": warnings[:50], "counts": counts}


ID_PATTERNS = re.compile(r"\d{4}-\d{2}-\d{2}(?:-\d+)?:[AB]\d+|\bL\d+\b|\bI\d+\b|\bC-[\w-]+")


def profile_errors(text, decision_ids, lesson_ids, compost_ids, intent_ids) -> list:
    errs = []
    cur = profile_current(text)
    for line in cur.splitlines():
        if not re.match(r"^\s*[-*]\s+\S", line):
            continue
        found = ID_PATTERNS.findall(line)
        if not found:
            errs.append(f"profile.md: 08.ev-profile-no-id: {line.strip()[:80]}")
            continue
        for i in found:
            if re.match(r"^\d{4}", i) and i not in decision_ids:
                errs.append(f"profile.md: unknown decision id {i}")
            elif i.startswith("L") and i not in lesson_ids:
                errs.append(f"profile.md: unknown lesson id {i}")
            elif i.startswith("C-") and i not in compost_ids:
                errs.append(f"profile.md: unknown compost id {i}")
            elif re.match(r"^I\d+$", i) and i not in intent_ids:
                errs.append(f"profile.md: unknown intent id {i}")
    return errs


def cmd_validate(a, ledger: Path):
    out(validate_ledger(ledger))


# ---------------------------------------------------------------- commit

def apply_card(ledger: Path, draft: Path, run: str):
    aid = draft.stem
    target = ledger / "artifacts" / f"{aid}.md"
    d = read_text(draft)
    if not target.exists():
        return target, d, "new"
    base = read_text(target)
    dfm = front_matter(d)
    if dfm:
        m = re.match(r"^---\n(.*?)\n---\n?", base, re.S)
        if m:
            fm_lines = m.group(1).splitlines()
            for key in ("fingerprint", "stop_reasons", "stop_reason_notes", "stop_reason_source", "partial",
                        "last_run", "secondary_types", "type"):
                if key not in dfm:
                    continue
                for i, line in enumerate(fm_lines):
                    if re.match(rf"^{re.escape(key)}:", line):
                        fm_lines[i] = f"{key}: {dfm[key]}"
                        break
                else:
                    fm_lines.append(f"{key}: {dfm[key]}")
            base = "---\n" + "\n".join(fm_lines) + "\n---\n" + base[m.end():]
    base = re.sub(r"(?m)^last_run:.*$", f"last_run: {run[:10]}", base, count=1)
    body = strip_front_matter(d).strip()
    body = re.sub(r"^#\s+.*\n?", "", body, count=1).strip()
    text = base.rstrip("\n") + f"\n\n### {today()} (run {run})\n" + body + "\n"
    return target, text, "updated"


def merge_lessons(ledger_text: str, work_text: str, run: str):
    existing = parse_lessons(ledger_text)
    work = work_text.strip()
    if not work:
        return ledger_text, 0, 0
    if not re.match(r"^##\s", work):
        work = f"## {today()} (run {run})\n\n" + work
    new_ids, repeats = [], []
    lines = ledger_text.splitlines() if ledger_text else ["# Lessons"]
    for m, s, e, body in blocks(work, LESSON_HEAD):
        lid = m.group(2)
        if lid not in existing:
            new_ids.append(lid)
            continue
        repeats.append(lid)
        evid = re.findall(r"`[^`]+`", parse_fields(body).get("loc_evidence", ""))
        orig = None
        for om, os_, oe, ob in blocks("\n".join(lines), LESSON_HEAD):
            if om.group(2) == lid and not re.match(r"^\((repeat|반복)", om.group(3).strip(), re.I):
                orig = (os_, oe)
                break
        if orig is None:
            continue
        os_, oe = orig
        rep_done = False
        for i in range(os_, oe):
            rm = REPEAT_RE.match(lines[i])
            if rm and not rep_done:
                n = int(rm.group(2)) + 1
                tail = rm.group(3)
                if re.search(r"\(runs?\s", tail):
                    tail = re.sub(r"\)\s*$", f", {run})", tail.rstrip())
                else:
                    first = existing[lid].get("first_run") or "?"
                    tail = f" (runs {first}, {run})"
                lines[i] = f"{rm.group(1)}{n}{tail}"
                rep_done = True
                if n >= 3 and not HABIT_RE.search(lines[os_]):
                    lines[os_] = lines[os_].rstrip() + "   [structural habit]"
            elif re.match(r"^\s*[-*]\s*(Evidence|근거)\s*[:：]", lines[i], re.I) and evid:
                have = set(re.findall(r"`[^`]+`", lines[i]))
                add = [x for x in evid if x not in have]
                if add:
                    lines[i] = lines[i].rstrip() + ", " + ", ".join(add)
        if not rep_done:
            lines.insert(oe, f"- Repeat: 2 (runs {existing[lid].get('first_run') or '?'}, {run})")
    text = "\n".join(lines).rstrip("\n") + "\n\n" + work + "\n"
    return text, len(new_ids), len(repeats)


def decision_from_block(run, label, definition, body, judgment, arts):
    parts = PART_REF.findall(body)
    aids = []
    for p in parts:
        a_ = p.split("#")[0]
        if a_ not in aids:
            aids.append(a_)
    for tok in re.findall(r"`([^`]+)`", body):
        t = tok.split(":")[0].split("#")[0]
        if t in arts and t not in aids:
            aids.append(t)
    lids = list(dict.fromkeys(re.findall(r"\bL\d+\b", body)))
    row = {"id": f"{run}:{label}", "run": run, "track": label[0], "candidate": definition.strip("* "),
           "decision": judgment["decision"], "reason": judgment.get("reason", ""), "artifact_ids": aids,
           "lesson_ids": lids, "at": now_iso(), "followups": [], "skip_count": 0, "stale": False}
    if label[0] == "B":
        m = re.search(r"(?mi)^\s*[-*]?\s*Source ids\s*:\s*(.+)$", body)
        row["source_ids"] = [s.strip(" `") for s in m.group(1).split(",") if s.strip(" `")] if m else []
    rc = re.search(r"reused_compost[\"'`]?\s*[:=]?\s*[\"'`]?(C-[\w-]+)", body)
    if rc:
        row["reused_compost"] = rc.group(1)
    return row


def detect_mode(run_text: str, wd: Path, override):
    if override:
        return override
    head = run_text.split("\n## ", 1)[0]
    m = re.search(r"\b(full|incremental)\b", head)
    if m:
        return m.group(1)
    return (read_json(wd / "run.json", {}) or {}).get("mode_hint", "incremental")


def cmd_commit(a, ledger: Path):
    run = a.run
    wd = require_work(ledger, run)
    run_file = ledger / "runs" / f"{run}.md"
    if not run_file.exists():
        raise LedgerError(f"run file not found: {run_file} (step 6 writes it)")
    state = state_of(ledger)
    if run in (state.get("runs") or []):
        raise LedgerError(f"run {run} already committed")
    run_text = read_text(run_file)
    writes = {}  # path -> text, written at the end; state.json last
    saved = {}

    # artifacts
    arts = known_artifacts(ledger)
    new_cards = upd_cards = 0
    if (wd / "artifacts").is_dir():
        for draft in sorted((wd / "artifacts").glob("*.md")):
            target, text, kind = apply_card(ledger, draft, run)
            writes[target] = text
            arts.setdefault(draft.stem, "")
            if kind == "new":
                new_cards += 1
            else:
                upd_cards += 1
    saved["artifacts_new"], saved["artifacts_updated"] = new_cards, upd_cards

    # parts
    old_parts = read_jsonl(ledger / "parts.jsonl")
    pend = read_jsonl(wd / "parts.pending.jsonl")
    ids = {p.get("id") for p in old_parts}
    errs = []
    for n, p in enumerate(pend, 1):
        p.setdefault("run", run)
        p.setdefault("at", now_iso())
        for e in check_row("parts", p):
            errs.append(f"parts.pending.jsonl:{n}: {e}")
        if p.get("id") in ids:
            errs.append(f"parts.pending.jsonl:{n}: duplicate id {p.get('id')}")
        ids.add(p.get("id"))
    if pend:
        writes[ledger / "parts.jsonl"] = read_text(ledger / "parts.jsonl") + jsonl_text(pend)
    saved["parts"] = len(pend)

    # lessons
    ltext, n_new, n_rep = merge_lessons(read_text(ledger / "lessons.md"), read_text(wd / "lessons.md"), run)
    if n_new or n_rep or read_text(wd / "lessons.md").strip():
        writes[ledger / "lessons.md"] = ltext
    saved["lessons_new"], saved["lessons_repeated"] = n_new, n_rep

    # intents
    wi = read_text(wd / "intents.md")
    if wi.strip():
        old = parse_intents(read_text(ledger / "intents.md"))
        new = parse_intents(wi)
        old_ids = {i["id"] for s in old.values() for i in s}
        new_ids = {i["id"] for s in new.values() for i in s}
        lost = sorted(old_ids - new_ids)
        if lost:
            errs.append(f"intents.md: intents removed instead of ended: {', '.join(lost)}")
        writes[ledger / "intents.md"] = wi if wi.endswith("\n") else wi + "\n"
        saved["intents_active"] = len(new["active"])

    # decisions
    judg = read_json(wd / "judgments.json", {}) or {}
    old_dec = read_jsonl(ledger / "decisions.jsonl")
    old_ids = {d.get("id") for d in old_dec}
    new_dec = []
    for m, s, e, body in blocks(run_text, CAND_HEAD):
        label = m.group(2) + m.group(3)
        j = judg.get(label) or {"decision": "hold", "reason": ""}
        row = decision_from_block(run, label, m.group(4).strip(), body, j, arts)
        if row["id"] in old_ids or any(row["id"] == d["id"] for d in new_dec):
            errs.append(f"decision {row['id']} already exists")
        for e2 in check_row("decisions", row):
            errs.append(f"decision {row['id']}: {e2}")
        new_dec.append(row)
    recall = read_json(wd / "recall.json", {}) or {}
    applied_fu = 0
    for d in old_dec:
        u = (recall.get("updates") or {}).get(d.get("id"))
        if not u:
            continue
        if "followup" in u:
            d.setdefault("followups", []).append(u["followup"])
            applied_fu += 1
        if "skip_count" in u:
            d["skip_count"] = u["skip_count"]
        if u.get("stale"):
            d["stale"] = True
    all_dec = old_dec + new_dec
    if new_dec or applied_fu or recall.get("updates"):
        writes[ledger / "decisions.jsonl"] = jsonl_text(all_dec)
    counts = {"adopt": 0, "hold": 0, "reject": 0}
    for d in new_dec:
        counts[d["decision"]] += 1
    saved["decisions"] = counts
    saved["followups_applied"] = applied_fu

    # compost
    old_c = read_jsonl(ledger / "compost.jsonl")
    cids = {c.get("id") for c in old_c}
    new_c = []
    seq = 0
    for fname in ("compost.pending.jsonl", "compost.track-a.jsonl", "compost.track-b.jsonl"):
        for c in read_jsonl(wd / fname):
            seq += 1
            c.setdefault("run", run)
            c.setdefault("at", now_iso())
            c.setdefault("kind", "candidate" if "track" in fname else "other")
            c.setdefault("step", {"compost.track-a.jsonl": "05a", "compost.track-b.jsonl": "05b"}.get(fname, "other"))
            c.setdefault("content", "")
            c.setdefault("failed_rules", [])
            if not c.get("id"):
                c["id"] = f"C-{run}-x{seq}"
            c.setdefault("reused_in", [])
            if c["id"] in cids:
                errs.append(f"compost id {c['id']} already exists")
            cids.add(c["id"])
            for e2 in check_row("compost", c):
                errs.append(f"{fname}: {c['id']}: {e2}")
            new_c.append(c)
    reused = 0
    for d in new_dec:
        rc = d.get("reused_compost")
        if not rc:
            continue
        for c in old_c:
            if c.get("id") == rc:
                if run not in c.setdefault("reused_in", []):
                    c["reused_in"].append(run)
                    reused += 1
                break
        else:
            errs.append(f"{d['id']}: reused_compost {rc} not in compost.jsonl")
    if new_c or reused:
        writes[ledger / "compost.jsonl"] = jsonl_text(old_c + new_c)
    saved["compost"] = len(new_c)
    saved["compost_reused"] = reused

    if errs:
        raise LedgerError("schema check failed; nothing written: " + " | ".join(errs[:20]))

    # state
    mode = detect_mode(run_text, wd, a.mode)
    fps_staged = read_json(wd / "fingerprints.json", {}) or {}
    fps = state.setdefault("fingerprints", {})
    n_new_art = 0
    for aid, v in fps_staged.items():
        if v.get("status") == "blocked" or not v.get("value"):
            continue
        rec = {"source": v.get("source", ""), "method": v["method"], "value": v["value"], "at": v.get("at") or now_iso()}
        if v["method"] == "file-hash":
            rec["method_version"] = v.get("method_version", FILE_HASH_VERSION)
        fps[aid] = rec
        if v.get("status") == "new":
            n_new_art += 1
    state.setdefault("version", 1)
    if mode == "full":
        state["last_full_analysis"] = run[:10]
        state["artifacts_since_full"] = 0
    else:
        state["artifacts_since_full"] = int(state.get("artifacts_since_full", 0) or 0) + n_new_art
        state.setdefault("last_full_analysis", None)
    state.setdefault("runs", []).append(run)
    stats = state.setdefault("source_stats", {})
    src_entries = parse_sources(read_text(ledger / "sources.md"))["entries"]
    per = {e["id"]: {"enabled": entry_enabled(e), "cited": 0, "cited_in_adopted": 0} for e in src_entries}
    used = set()
    judged = {d["id"].split(":")[1]: d["decision"] for d in new_dec}
    for m, s, e, body in blocks(run_text, CAND_HEAD):
        label = m.group(2) + m.group(3)
        if m.group(2) != "B":
            continue
        for line in body.splitlines():
            for sid in set(re.findall(r"\[src:([\w.-]+)\]", line)):
                per.setdefault(sid, {"enabled": False, "cited": 0, "cited_in_adopted": 0})
                per[sid]["cited"] += 1
                used.add(sid)
                if judged.get(label) == "adopt":
                    per[sid]["cited_in_adopted"] += 1
        sm = re.search(r"(?mi)^\s*[-*]?\s*Source ids\s*:\s*(.+)$", body)
        if sm:
            for sid in [x.strip(" `") for x in sm.group(1).split(",") if x.strip(" `")]:
                used.add(sid)
                per.setdefault(sid, {"enabled": False, "cited": 0, "cited_in_adopted": 0})
    for sid, pr in per.items():
        st = stats.setdefault(sid, {"runs_used": [], "cited": 0, "cited_in_adopted": 0, "last_cited_run": None, "per_run": {}})
        st.setdefault("per_run", {})[run] = pr
        if sid in used and run not in st.setdefault("runs_used", []):
            st["runs_used"].append(run)
        st["cited"] = int(st.get("cited", 0)) + pr["cited"]
        st["cited_in_adopted"] = int(st.get("cited_in_adopted", 0)) + pr["cited_in_adopted"]
        if pr["cited"]:
            st["last_cited_run"] = run

    proposals = proposal_candidates(state, old_c + new_c, all_dec, read_text(ledger / "proposals.md"))

    # write: everything else first, state.json last
    for d in ("artifacts", "runs", "export"):
        (ledger / d).mkdir(parents=True, exist_ok=True)
    for path, text in writes.items():
        write_atomic(path, text)
    cleaned = cleanup_work(wd)
    write_json(ledger / "state.json", state)
    out({"saved": saved, "proposals": proposals, "ledger": str(ledger), "run_file": str(run_file),
         "mode": mode, "cleaned": cleaned})


def proposal_candidates(state, compost, decisions, proposals_text) -> list:
    res = []
    rule_map = {}
    for c in compost:
        for r in c.get("failed_rules") or []:
            v = rule_map.setdefault(r, {"runs": set(), "ids": []})
            v["runs"].add(c.get("run"))
            v["ids"].append(c.get("id"))
    for r, v in sorted(rule_map.items()):
        if len(v["runs"]) >= 3 and len(v["ids"]) >= 5:
            res.append({"type": "compost-hotspot", "rule": r, "runs": sorted(v["runs"]), "compost_ids": v["ids"],
                        "already_proposed": r in proposals_text})
    recent = (state.get("runs") or [])[-5:]
    if len(recent) == 5:
        for sid, st in sorted((state.get("source_stats") or {}).items()):
            pr = st.get("per_run") or {}
            if all(pr.get(r, {}).get("enabled") is True and pr.get(r, {}).get("cited_in_adopted", 1) == 0 for r in recent):
                res.append({"type": "idle-source", "source": sid, "runs": recent,
                            "already_proposed": f"`{sid}`" in proposals_text or f"Disable {sid}" in proposals_text})
    for t in ("A", "B"):
        adopts = [d for d in decisions if d.get("track") == t and d.get("decision") == "adopt"]
        if len(adopts) >= 5 and not any(any(f.get("touched") for f in d.get("followups") or []) for d in adopts):
            res.append({"type": "track-zero-start", "track": t, "decision_ids": [d["id"] for d in adopts]})
    return res


def cleanup_work(wd: Path) -> list:
    cleaned = []
    src = wd / "src"
    if src.exists():
        shutil.rmtree(src)
        cleaned.append(str(src))
    for p in sorted(wd.rglob("*")):
        if p.is_file() and (is_db(p.name)):
            p.unlink()
            cleaned.append(str(p))
    return cleaned


# ---------------------------------------------------------------- sources

def sources_doc(ledger: Path):
    ledger.mkdir(parents=True, exist_ok=True)
    seed_sources(ledger, DEFAULT_SOURCES)
    return parse_sources(read_text(ledger / "sources.md"))


def usage_error(doc, msg):
    ids = [e["id"] for e in doc["entries"]]
    raise LedgerError(f"{msg}. usage: {SOURCES_USAGE}. ids: {', '.join(ids)}")


def norm_types(value: str) -> str:
    types = [t.strip() for t in re.split(r"[,\s]+", value or "") if t.strip()]
    bad = [t for t in types if t not in SOURCE_TYPES]
    if not types or bad:
        raise LedgerError(f"invalid type {value!r}; allowed: {', '.join(sorted(SOURCE_TYPES))} (comma-combined)")
    return ", ".join(types)


def check_category(value: str) -> str:
    if value not in SOURCE_CATEGORIES:
        raise LedgerError(f"invalid category {value!r}; allowed: {', '.join(sorted(SOURCE_CATEGORIES))}")
    return value


def derive_source_id(how: str, taken) -> str:
    m = re.search(r"https?://([^/\s`'\"]+)", how)
    if m:
        host = m.group(1).lower()
        base = slug(host[4:] if host.startswith("www.") else host)
    else:
        gm = re.match(r"^\s*`?(.+?)@([^:@/\s]+):(.*?)`?\s*$", how)
        path = gm.group(3) if gm else how.strip().strip("`")
        last = [p for p in re.split(r"[/\\]", path) if p]
        base = slug(last[-1] if last else "") or slug(how) or "source"
    cand, n = base, 1
    while cand in taken:
        n += 1
        cand = f"{base}-{n}"
    return cand


def entry_json(e, stats=None):
    f = e["fields"]
    res = {"id": e["id"], "category": f.get("category"), "type": f.get("type"),
           "enabled": f.get("enabled", "true").lower() == "true"}
    for k in ("removed", "restored"):
        if f.get(k):
            res[k] = f[k]
    if stats is not None:
        st = stats.get(e["id"])
        res["cited"] = st.get("cited", 0) if st else "-"
        res["cited_in_adopted"] = st.get("cited_in_adopted", 0) if st else "-"
    return res


def cmd_sources(a, ledger: Path):
    doc = sources_doc(ledger)
    path = ledger / "sources.md"
    by_id = {e["id"]: e for e in doc["entries"]}
    verb = a.verb
    nd = new_default_ids(ledger, DEFAULT_SOURCES)

    def save(e, extra=None):
        write_atomic(path, render_sources(doc))
        res = {"changed": entry_json(e), "path": str(path)}
        res.update(extra or {})
        out(res)

    if verb == "list":
        state_file = ledger / "state.json"
        stats = (state_of(ledger).get("source_stats") or {}) if state_file.exists() else {}
        rows = [entry_json(e, stats if state_file.exists() else {}) for e in doc["entries"]]
        if not state_file.exists():
            for r in rows:
                r["cited"] = r["cited_in_adopted"] = "-"
        res = {"sources": rows, "path": str(path)}
        if nd:
            res["new_default_sources"] = nd
        out(res)
        return
    if verb == "sync-defaults":
        if a.id not in ("yes", "no"):
            raise LedgerError("sync-defaults needs yes|no")
        defaults = {e["id"]: e for e in parse_sources(read_text(DEFAULT_SOURCES))["entries"]}
        added = []
        for sid in nd:
            e = defaults[sid]
            e = {"id": sid, "lines": list(e["lines"]), "fields": dict(e["fields"])}
            if a.id == "no":
                set_field(e, "enabled", "false")
            doc["entries"].append(e)
            added.append(sid)
        write_atomic(path, render_sources(doc))
        out({"added": added, "enabled": a.id == "yes", "path": str(path)})
        return
    if verb == "add":
        if not (a.type and a.how and a.category):
            raise LedgerError("add needs --type, --how and --category (ask the user once: type, how, category)")
        types = norm_types(a.type)
        cat = check_category(a.category)
        sid = a.id or derive_source_id(a.how, by_id)
        if not re.match(r"^[a-z0-9][a-z0-9-]*$", sid):
            raise LedgerError(f"id must be kebab-case: {sid!r}")
        if sid in by_id:
            raise LedgerError(f"duplicate id: {sid}")
        lines = [f"## {sid}", f"- category: {cat}", f"- type: {types}", f"- how: {a.how}",
                 f"- limits: {a.limits or DEFAULT_LIMITS}"]
        if a.notes:
            lines.append(f"- notes: {a.notes}")
        lines.append("- enabled: true")
        e = {"id": sid, "lines": lines, "fields": {}}
        e["fields"] = {k: v for k, v in (re.match(r"^-\s*([a-z_]+):\s*(.*)$", l).groups() for l in lines[1:])}
        doc["entries"].append(e)
        save(e)
        return
    if verb not in ("remove", "edit", "enable", "disable"):
        usage_error(doc, f"unknown verb {verb!r}")
    if not a.id:
        usage_error(doc, f"{verb} needs an id")
    e = by_id.get(a.id)
    if not e:
        usage_error(doc, f"no source {a.id!r}")
    if verb == "remove":
        set_field(e, "enabled", "false")
        if not e["fields"].get("removed"):
            set_field(e, "removed", today())
        save(e)
    elif verb == "disable":
        set_field(e, "enabled", "false")
        save(e)
    elif verb == "enable":
        set_field(e, "enabled", "true")
        if e["fields"].get("removed"):
            set_field(e, "removed", "")
            set_field(e, "restored", today())
        save(e)
    else:
        pairs = a.pairs or []
        if not pairs:
            out({"entry": entry_json(e), "fields": e["fields"], "hint": "pass field=value pairs"})
            return
        seen = set()
        for pair in pairs:
            if "=" not in pair:
                raise LedgerError(f"expected field=value, got {pair!r}")
            k, v = pair.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k == "id":
                raise LedgerError("id cannot be changed; use remove + add")
            if k not in SOURCE_FIELDS:
                raise LedgerError(f"unknown field {k!r}; allowed: {', '.join(SOURCE_FIELDS)}")
            if k in seen:
                raise LedgerError(f"field given twice: {k}")
            seen.add(k)
            if k == "type":
                v = norm_types(v)
            elif k == "category":
                v = check_category(v)
            elif k == "enabled" and v not in ("true", "false"):
                raise LedgerError("enabled must be true|false")
            set_field(e, k, v)
        save(e)


# ---------------------------------------------------------------- main

def build_parser():
    p = argparse.ArgumentParser(prog="ledger.py", description="slop-compost ledger tool")
    p.add_argument("--ledger", help="ledger root (default: $SLOP_COMPOST_HOME or ~/.slop-compost)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init")
    s.add_argument("--skill-dir")
    s.add_argument("--full", action="store_true")
    s.add_argument("--inputs", type=int)

    s = sub.add_parser("fingerprint")
    s.add_argument("inputs", nargs="*")
    s.add_argument("--run")
    s.add_argument("--as", dest="as_ids", action="append", help="artifact id for the input at the same position")
    s.add_argument("--set", nargs=3, metavar=("ARTIFACT_ID", "METHOD", "VALUE"))
    s.add_argument("--source", help="source for --set when nothing is staged")

    s = sub.add_parser("select-files")
    s.add_argument("folder")
    s.add_argument("--max", type=int, default=50)

    sub.add_parser("recall")

    s = sub.add_parser("apply-recall")
    s.add_argument("--run", required=True)
    s.add_argument("answer", nargs="?", default="")

    s = sub.add_parser("bundle")
    s.add_argument("track", choices=["a", "b"])
    s.add_argument("--run", required=True)

    s = sub.add_parser("lint")
    s.add_argument("file")
    s.add_argument("--kind", required=True, choices=["lessons", "track-a", "track-b", "direction"])
    s.add_argument("--compost", action="store_true")
    s.add_argument("--run")
    s.add_argument("--step")

    s = sub.add_parser("judge")
    s.add_argument("--run", required=True)
    s.add_argument("answer", nargs="?", default="")

    s = sub.add_parser("commit")
    s.add_argument("--run", required=True)
    s.add_argument("--mode", choices=["full", "incremental"])

    sub.add_parser("validate")

    s = sub.add_parser("sources")
    s.add_argument("verb")
    s.add_argument("id", nargs="?")
    s.add_argument("pairs", nargs="*")
    s.add_argument("--type")
    s.add_argument("--how")
    s.add_argument("--category")
    s.add_argument("--limits")
    s.add_argument("--notes")
    return p


COMMANDS = {"init": cmd_init, "fingerprint": cmd_fingerprint, "select-files": cmd_select_files,
            "recall": cmd_recall, "apply-recall": cmd_apply_recall, "bundle": cmd_bundle, "lint": cmd_lint,
            "judge": cmd_judge, "commit": cmd_commit, "validate": cmd_validate, "sources": cmd_sources}


def main(argv=None) -> int:
    parser = build_parser()
    try:
        a = parser.parse_args(argv)
    except SystemExit as exc:
        if exc.code not in (0, None):
            out({"error": "invalid arguments (see stderr)"})
            return 1
        return 0
    try:
        COMMANDS[a.cmd](a, ledger_path(a.ledger))
        return 0
    except LedgerError as exc:
        out({"error": str(exc)})
        return 1
    except Exception as exc:  # keep the one-JSON-object contract
        out({"error": f"{type(exc).__name__}: {exc}"})
        return 1


if __name__ == "__main__":
    sys.exit(main())
