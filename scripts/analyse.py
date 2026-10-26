#!/usr/bin/env python3
"""godot-claude-kit analyser: cheap, read-only measurements of a Godot project
for working with Claude Code agents. Writes a Markdown report and prints a short
summary, so the analysis costs few tokens (Claude reads the summary, not the code).

    python3 -I analyse.py --target DIR [--out DIR/docs/claude_kit_analysis.md] [--json FILE]

Read-only on the project: the only file written is the report (--out).
"""
import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict

LARGE = 800            # lines: split before adding more
HUGE = 1500
CLAUDE_MD_GOOD = 5000  # bytes
CLAUDE_MD_BAD = 10000
BIG_DOC_BYTES = 8000
BIG_DOC_LINES = 150
BYTES_PER_TOKEN = 4.0  # rough average for English/Scandinavian prose and code
SKIP_DIRS = {".git", ".godot", ".import", "node_modules", "build", "export", ".idea", ".vscode", "__pycache__"}
TLDR_RE = re.compile(r"TL;?DR|^#+\s*(Summary|Overview|Sammendrag|Oversikt|Kort fortalt|In short)\b|^\*\*(Summary|TL;DR)",
                     re.I | re.M)
# Reference numbers measured on a real Claude-built Godot project (see STRATEGY.md).
REF = {
    "claude_md": "CLAUDE.md 16.6 KB -> 4.4 KB (-73% context on every turn of every agent)",
    "split": "splitting one big script: ~135-190k tokens with Sonnet vs ~280-390k with Opus, same result",
    "split_sizes": "4778/2563/2312-line scripts split into hub + helpers < 800 lines",
    "runner": "parallel runner: ~150 suites in ~13 min at 8 jobs; agents run only their own suites (1-3 min)",
    "audit": "a whole-project bug sweep costs ~250k tokens: do it before big playtests, not every round",
    "precommit": "pre-commit parse check takes ~2 s and stops broken scripts before they reach a branch",
}


# --- file collection -----------------------------------------------------------

def git(target, *args):
    try:
        p = subprocess.run(["git", "-C", target, *args], capture_output=True, text=True, timeout=60)
        return p.stdout if p.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def collect(target):
    files = []
    out = git(target, "ls-files", "--cached", "--others", "--exclude-standard")
    if out:
        files = [f for f in out.splitlines() if f]
    else:
        for base, dirs, names in os.walk(target):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not (d == "worktrees" and base.endswith(".claude"))]
            for n in names:
                files.append(os.path.relpath(os.path.join(base, n), target).replace(os.sep, "/"))
    keep = []
    for f in files:
        parts = f.split("/")
        if any(p in SKIP_DIRS for p in parts[:-1]) or f.startswith(".claude/worktrees/"):
            continue
        if os.path.isfile(os.path.join(target, f)):
            keep.append(f)
    return sorted(set(keep))


def read(target, rel):
    try:
        with open(os.path.join(target, rel), encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def is_test(path):
    return path.startswith(("tests/", "test/")) or "/tests/" in path or os.path.basename(path).startswith("test_")


def is_tool(path):
    return path.startswith("tools/")


def is_addon(path):
    return path.startswith("addons/")


# --- GDScript parsing helpers ----------------------------------------------------

FUNC_RE = re.compile(r"^(?:static\s+)?func\s+(\w+)\s*\(([^)]*)\)\s*(->\s*[\w\[\], .]+)?\s*:")
TOP_RE = re.compile(r"^(?:@|static\s|func\s|var\s|const\s|signal\s|class\s|class_name\s|enum\s|extends\s)")


def functions(lines):
    """Top-level functions: (name, start_index, end_index, params, has_return_type, annotations)."""
    out = []
    pending = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        m = FUNC_RE.match(line) or (FUNC_RE.match(re.sub(r"^(@\w+(\([^)]*\))?\s+)+", "", line))
                                    if line.startswith("@") else None)
        if line.startswith("@") and not m:
            pending.append(stripped)
            i += 1
            continue
        if m:
            annotations = pending + re.findall(r"@\w+(?:\([^)]*\))?", line.split("func")[0])
            pending = []
            j = i + 1
            while j < len(lines) and not TOP_RE.match(lines[j]):
                j += 1
            # Trim trailing blank lines/comments.
            end = j
            while end > i + 1 and (not lines[end - 1].strip() or lines[end - 1].startswith("#")):
                end -= 1
            out.append((m.group(1), i, end, m.group(2), bool(m.group(3)), annotations))
            i = j
            continue
        if stripped and not stripped.startswith("#"):
            pending = []
        i += 1
    return out


def strip_strings_comments(line):
    line = re.sub(r'"(?:[^"\\]|\\.)*"', '""', line)
    line = re.sub(r"'(?:[^'\\]|\\.)*'", "''", line)
    return line.split("#", 1)[0]


# --- analyses ----------------------------------------------------------------------

def analyse_scripts(target, files):
    scripts = [f for f in files if f.endswith(".gd")]
    game = [f for f in scripts if not is_test(f) and not is_addon(f)]
    tests = [f for f in scripts if is_test(f)]
    data = {}
    for f in game + tests:
        text = read(target, f)
        lines = text.splitlines()
        data[f] = {"lines": len(lines), "text": text, "list": lines, "bytes": len(text.encode("utf-8", "replace"))}
    buckets = Counter()
    for f in game:
        n = data[f]["lines"]
        buckets["< 200" if n < 200 else "200-399" if n < 400 else "400-799" if n < 800 else
                "800-1499" if n < 1500 else ">= 1500"] += 1
    top = sorted(game, key=lambda f: -data[f]["lines"])
    return scripts, game, tests, data, buckets, top


def seams(lines):
    """Split suggestions for a big script: clusters of functions by name prefix,
    #region / '# ---' sections, RPC count and string-named calls that a move can break."""
    funcs = functions(lines)
    clusters = defaultdict(lambda: [0, 0])
    handlers = [0, 0]
    rpcs = 0
    for name, s, e, _p, _r, ann in funcs:
        if any(a.startswith("@rpc") for a in ann):
            rpcs += 1
        size = e - s
        if name.startswith("_on_"):
            handlers[0] += 1
            handlers[1] += size
            continue
        if name.startswith("_") and name not in ("_ready", "_process", "_physics_process", "_input",
                                                 "_unhandled_input", "_init", "_enter_tree", "_exit_tree"):
            key = name.lstrip("_").split("_")[0]
        elif name.startswith("_"):
            key = "(engine callbacks)"
        else:
            key = name.split("_")[0]
        if key in ("get", "set", "is", "has", "can", "on", "do", "update", "apply", "make", "try"):
            parts = name.lstrip("_").split("_")
            key = parts[1] if len(parts) > 1 else key
        clusters[key][0] += 1
        clusters[key][1] += size
    sections = []
    for i, l in enumerate(lines):
        m = re.match(r"^#region\s+(.+)|^#\s*[-=]{3,}\s*(\w[^-=]*)", l)
        if m:
            sections.append((i + 1, (m.group(1) or m.group(2)).strip()))
    text = "\n".join(lines)
    dynamic = len(re.findall(r"\bcall(?:_deferred)?\(\s*&?\"|\bhas_method\(|Callable\(\s*\w+\s*,\s*&?\"|"
                             r"\brpc(?:_id)?\(\s*(?:\w+\s*,\s*)?&?\"|\bconnect\(\s*&?\"", text))
    best = sorted(((k, v) for k, v in clusters.items() if v[0] >= 3 and k != "(engine callbacks)"),
                  key=lambda kv: -kv[1][1])[:4]
    return {"funcs": len(funcs), "rpcs": rpcs, "clusters": best, "handlers": handlers,
            "sections": sections[:8], "dynamic_calls": dynamic}


def analyse_claude_md(target, files):
    always = [f for f in files if f in ("CLAUDE.md", ".claude/CLAUDE.md", "CLAUDE.local.md")]
    nested = [f for f in files if f.endswith("CLAUDE.md") and f not in always and not is_addon(f)]
    res = {"files": [], "nested": nested, "total_bytes": 0, "imports": []}
    for f in always:
        text = read(target, f)
        b = len(text.encode("utf-8", "replace"))
        imports = re.findall(r"(?:^|\s)@([\w./-]+\.md)", text)
        for imp in imports:
            ib = len(read(target, imp).encode("utf-8", "replace"))
            res["imports"].append((imp, ib))
            res["total_bytes"] += ib
        sections = []
        cur, start = "(top)", 0
        lines = text.splitlines()
        for i, l in enumerate(lines + ["## END"]):
            if l.startswith("## ") or l.startswith("# "):
                size = len("\n".join(lines[start:i]).encode("utf-8", "replace"))
                sections.append((cur, size, start + 1))
                cur, start = l.strip("# ").strip(), i
        res["files"].append({
            "path": f, "bytes": b, "lines": len(lines),
            "checkboxes": len(re.findall(r"^\s*- \[[ xX]\]", text, re.M)),
            "code_bytes": sum(len(m) for m in re.findall(r"```.*?```", text, re.S)),
            "pointers": len(re.findall(r"docs/[\w./-]+\.md", text)),
            "sections": sorted(sections, key=lambda s: -s[1])[:5],
        })
        res["total_bytes"] += b
    res["tokens"] = int(res["total_bytes"] / BYTES_PER_TOKEN)
    agents = [f for f in files if f.startswith(".claude/agents/") and f.endswith(".md")]
    skills = [f for f in files if f.startswith(".claude/skills/") and f.endswith("SKILL.md")]
    commands = [f for f in files if f.startswith(".claude/commands/") and f.endswith(".md")]
    res["agents"] = [(f, len(read(target, f))) for f in agents]
    res["skills"] = [(f, len(read(target, f))) for f in skills]
    res["commands"] = commands
    return res


def analyse_docs(target, files):
    docs = [f for f in files if f.endswith(".md") and not is_addon(f) and not is_test(f)
            and not f.startswith(".claude/") and not re.search(
                r"(^|/)(CLAUDE(\.local)?|CREDITS|LICENSE|CHANGELOG|code_?map|claude_kit_analysis)\.md$", f, re.I)]
    big, ok = [], []
    for f in docs:
        text = read(target, f)
        b = len(text.encode("utf-8", "replace"))
        n = text.count("\n")
        if b >= BIG_DOC_BYTES or n >= BIG_DOC_LINES:
            head = "\n".join(text.splitlines()[:25])
            (ok if TLDR_RE.search(head) else big).append((f, b, n))
    code_map = next((f for f in files if re.search(r"(code_?map|codemap|architecture)\.md$", f, re.I)), "")
    return {"count": len(docs), "big_without_summary": sorted(big, key=lambda x: -x[1]),
            "big_with_summary": len(ok), "code_map": code_map}


def analyse_tests(target, files, tests, data):
    res = {"test_scripts": len(tests), "frameworks": [], "runner": "", "parallel": False, "suites": 0,
           "ci": [], "durations": [], "flaky": [], "net_tests": 0, "suite_file": ""}
    if any(f.startswith("addons/gut/") for f in files):
        res["frameworks"].append("GUT")
    if any(f.lower().startswith("addons/gdunit4/") for f in files):
        res["frameworks"].append("gdUnit4")
    runners = [f for f in files if re.search(r"(test_?runner|run_?tests?|run_suites?)[\w]*\.(py|sh)$", f)
               and not f.startswith("addons/")]
    if runners:
        res["runner"] = sorted(runners, key=lambda f: (not f.startswith("tools/"), len(f)))[0]
        rt = read(target, res["runner"])
        res["parallel"] = bool(re.search(r"ThreadPoolExecutor|multiprocessing|xargs\s+-P|parallel|&\s*$", rt, re.M))
    suite_file = next((f for f in files if f.endswith("suites.txt")), "")
    if suite_file:
        res["suite_file"] = suite_file
        res["suites"] = sum(1 for l in read(target, suite_file).splitlines() if l.strip() and not l.startswith("#"))
    res["ci"] = [f for f in files if f.startswith(".github/workflows/") or f in (".gitlab-ci.yml",)]
    dur = next((f for f in files if f.endswith("durations.json")), "")
    if not dur and os.path.exists(os.path.join(target, "tests/integration/durations.json")):
        dur = "tests/integration/durations.json"
    if dur:
        try:
            d = json.loads(read(target, dur))
            res["durations"] = sorted(d.items(), key=lambda kv: -kv[1])
        except ValueError:
            pass
    flaky = []
    used = None
    if suite_file:
        refs = re.findall(r"(?:res://|sh:)(tests?/[\w/.\-]+)", read(target, suite_file))
        used = {os.path.dirname(r) + "/" for r in refs}
    for f in tests:
        if used is not None and not any(f.startswith(u) for u in used):
            continue
        t = data[f]["text"]
        frames = len(re.findall(r"\b_?(?:frame|frames|f|tick|ticks)\w*\s*(?:>|>=|==)\s*\d{2,}", t))
        timers = len(re.findall(r"await\s+[\w.()]*create_timer\(", t))
        delays = len(re.findall(r"OS\.delay_msec\(", t))
        if frames + timers + delays >= 3:
            flaky.append((f, frames, timers, delays))
        if re.search(r"create_server\(|host_game\(|join_game\(|create_client\(", t):
            res["net_tests"] += 1
    for f in files:
        if f.endswith(".sh") and is_test(f) and (used is None or any(f.startswith(u) for u in used)):
            t = read(target, f)
            sleeps = len(re.findall(r"^\s*sleep\s+\d", t, re.M))
            if sleeps >= 3:
                flaky.append((f, 0, 0, sleeps))
            if re.search(r"--host|--join|create_server", t):
                res["net_tests"] += 1
    res["flaky"] = sorted(flaky, key=lambda x: -(x[1] + x[2] + x[3]))
    return res


def analyse_workflow(target, files):
    res = {"git": bool(git(target, "rev-parse", "--is-inside-work-tree").strip())}
    if not res["git"]:
        return res
    res["branches"] = len([b for b in git(target, "branch", "--format=%(refname:short)").splitlines() if b])
    log = git(target, "log", "-300", "--format=%s%x09%p").splitlines()
    res["commits_sampled"] = len(log)
    subjects = [l.split("\t")[0] for l in log]
    res["merges"] = sum(1 for l in log if len(l.split("\t")[-1].split()) > 1)
    res["prefixed"] = sum(1 for s in subjects if re.match(r"^(\[#?\w+\]|\w+(\([\w-]+\))?!?:|#\d+)", s))
    res["hooks_path"] = git(target, "config", "core.hooksPath").strip()
    hooks_dir = os.path.join(target, ".git", "hooks")
    res["git_hooks"] = [h for h in (os.listdir(hooks_dir) if os.path.isdir(hooks_dir) else [])
                        if not h.endswith(".sample")]
    res["githooks_dir"] = [f for f in files if f.startswith(".githooks/")]
    res["worktree_scripts"] = [f for f in files if "worktree" in os.path.basename(f) and f.endswith((".sh", ".py"))]
    res["worktrees_live"] = max(0, git(target, "worktree", "list").count("\n") - 1)
    res["claude_settings"] = [f for f in files if f in (".claude/settings.json",)]
    gi = read(target, ".gitignore")
    res["gitignore_godot"] = bool(re.search(r"^/?\.godot/?\s*$", gi, re.M))
    res["dirty"] = len([l for l in git(target, "status", "--porcelain").splitlines() if l])
    return res


def analyse_network(target, files, game, data):
    tscn = [f for f in files if f.endswith(".tscn") and not is_test(f) and not is_addon(f)]
    res = {"rpcs": 0, "any_peer": 0, "unvalidated": [], "per_frame": [], "no_authority": [],
           "spawners": 0, "synchronizers": 0, "peer_connected_handlers": 0, "late_join_senders": 0,
           "uses_network": False}
    for f in tscn:
        t = read(target, f)
        res["spawners"] += t.count('type="MultiplayerSpawner"')
        res["synchronizers"] += t.count('type="MultiplayerSynchronizer"')
    for f in game:
        t, lines = data[f]["text"], data[f]["list"]
        if not re.search(r"@rpc|multiplayer\.|MultiplayerPeer|MultiplayerSynchronizer", t):
            continue
        res["uses_network"] = True
        funcs = functions(lines)
        bodies = {fn: "\n".join(lines[a:b]) for fn, a, b, _p, _r, _ann in funcs}
        # Helpers that check the sender (e.g. _from_owner()) count as validation.
        sender_helpers = {fn for fn, body in bodies.items() if "get_remote_sender_id" in body}
        file_rpcs = 0
        file_any_peer = 0
        for name, s, e, _p, _r, ann in funcs:
            rpc = next((a for a in ann if a.startswith("@rpc")), None)
            body = "\n".join(lines[s:e])
            if rpc:
                file_rpcs += 1
                res["rpcs"] += 1
                if "any_peer" in rpc:
                    res["any_peer"] += 1
                    file_any_peer += 1
                    calls = set(re.findall(r"\b(\w+)\(", body))
                    if "get_remote_sender_id" not in body and not (calls & (sender_helpers - {name})) and \
                            not re.search(r"\b_?(validate|check|guard|sender)\w*\(", body):
                        res["unvalidated"].append((f, s + 1, name, "call_local" in rpc))
            if name in ("_process", "_physics_process"):
                # Only unconditional sends (directly in the function body, not under an if/match/for).
                for k in range(s + 1, e):
                    code = strip_strings_comments(lines[k])
                    if re.match(r"^\t(?!\t)|^ {4}(?! )", lines[k]) and re.search(r"\.rpc(_id)?\(|\brpc(_id)?\(", code):
                        callee = re.search(r"(\w+)\.rpc", code)
                        ann_text = next((" ".join(a) for fn, _a, _b, _p2, _r2, a in funcs
                                         if callee and fn == callee.group(1)), "")
                        if "unreliable" not in ann_text:
                            res["per_frame"].append((f, k + 1, name))
        if file_any_peer and not re.search(r"is_server\(\)|is_multiplayer_authority\(\)|get_multiplayer_authority\(\)|"
                                       r"get_remote_sender_id\(\)", t):
            res["no_authority"].append((f, file_any_peer))
        if "peer_connected" in t:
            res["peer_connected_handlers"] += 1
            if "rpc_id(" in t:
                res["late_join_senders"] += 1
    return res


UI_TEXT_RE = re.compile(r"\.(text|tooltip_text|placeholder_text|title|dialog_text)\s*[+]?=\s*\"[^\"]*[A-Za-z]{3,}"
                        r"|\b(set_text|add_item|add_tab|set_tooltip_text|add_button)\(\s*\"[^\"]*[A-Za-z]{3,}")
MAGIC_OK = {"0", "1", "2", "-1", "0.0", "1.0", "2.0", "0.5", "-1.0", "10", "100", "180", "360", "90", "255"}


def analyse_quality(target, game, data):
    typed_vars = untyped_vars = typed_ret = untyped_ret = typed_params = untyped_params = 0
    per_file_typing = []
    magic = []
    ui_text = []
    tr_calls = 0
    for f in game:
        lines = data[f]["list"]
        tv = uv = 0
        mcount = 0
        examples = []
        for i, raw in enumerate(lines):
            line = strip_strings_comments(raw)
            s = line.strip()
            m = re.match(r"^(?:@\w+(?:\([^)]*\))?\s+)*(?:static\s+)?var\s+\w+\s*(:)?", s)
            if m and not s.startswith("for "):
                if m.group(1):
                    tv += 1
                else:
                    uv += 1
            fm = FUNC_RE.match(raw.strip()) or FUNC_RE.match(re.sub(r"^(@\w+(\([^)]*\))?\s+)+", "", raw.strip()))
            if fm:
                if fm.group(3):
                    typed_ret += 1
                else:
                    untyped_ret += 1
                for p in [p.strip() for p in fm.group(2).split(",") if p.strip()]:
                    if ":" in p:
                        typed_params += 1
                    else:
                        untyped_params += 1
            if re.match(r"^(const|@export|enum|signal|class_name|extends|var\s+\w+\s*(:\s*[\w\[\]]+)?\s*:?=\s*-?[\d.]+\s*$)", s):
                continue
            if re.match(r"^(@export|const|var)\b", s):
                continue
            for num in re.findall(r"(?<![\w.\"])(-?\d+\.\d+|-?\d+)(?![\w.])", line):
                if num not in MAGIC_OK and not re.match(r"^-?0+(\.0+)?$", num):
                    mcount += 1
                    if len(examples) < 2 and i + 1 not in examples:
                        examples.append(i + 1)
            if UI_TEXT_RE.search(raw) and "tr(" not in raw:
                ui_text.append((f, i + 1, raw.strip()[:90]))
            tr_calls += len(re.findall(r"\btr\(|\btr_n\(", raw))
        typed_vars += tv
        untyped_vars += uv
        if tv + uv >= 15:
            per_file_typing.append((f, tv / (tv + uv), tv + uv))
        if mcount:
            magic.append((f, mcount, data[f]["lines"], examples))

    def ratio(a, b):
        return round(100.0 * a / (a + b), 1) if a + b else 100.0

    return {
        "var_typed_pct": ratio(typed_vars, untyped_vars), "vars": typed_vars + untyped_vars,
        "ret_typed_pct": ratio(typed_ret, untyped_ret), "funcs": typed_ret + untyped_ret,
        "param_typed_pct": ratio(typed_params, untyped_params),
        "worst_typing": sorted(per_file_typing, key=lambda x: x[1])[:5],
        "magic_total": sum(m[1] for m in magic),
        "magic_top": sorted(magic, key=lambda x: -x[1])[:8],
        "ui_text": ui_text, "tr_calls": tr_calls,
    }


def analyse_godot(target, files, game, data):
    proj = read(target, "project.godot")
    feats = re.search(r'config/features=PackedStringArray\(([^)]*)\)', proj)
    version = re.search(r'"(\d+\.\d+)"', feats.group(1)).group(1) if feats and re.search(r'"(\d+\.\d+)"',
                                                                                      feats.group(1)) else "?"
    sec = re.search(r"^\[autoload\]\s*$(.*?)(?=^\[|\Z)", proj, re.M | re.S)
    autoloads = re.findall(r'^(\w+)="\*?res://([^"]+)"', sec.group(1) if sec else "", re.M)
    al = []
    for name, path in autoloads:
        d = data.get(path)
        cls = bool(d and re.search(r"^class_name\s", d["text"], re.M))
        al.append((name, path, d["lines"] if d else 0, cls))
    autoload_names = {n for n, _ in autoloads}
    coupling = Counter()
    examples = {}
    for f in game:
        for i, raw in enumerate(data[f]["list"]):
            line = raw.split("#", 1)[0]
            hits = 0
            for m in re.finditer(r'get_node(?:_or_null)?\(\s*"/root/(\w+)', line):
                hits += m.group(1) not in autoload_names
            hits += len(re.findall(r"\$\"?[\w.]+/[\w.]+/[\w./]+", line))       # $A/B/C (3+ levels)
            hits += len(re.findall(r'get_node(?:_or_null)?\(\s*"(?:\.\./){2,}', line))
            hits += len(re.findall(r'find_child\(\s*"|find_children\(\s*"', line))
            hits += len(re.findall(r'\.name\s*==\s*"|\.name\.begins_with\(\s*"', line))
            if hits:
                coupling[f] += hits
                examples.setdefault(f, i + 1)
    tscn = [f for f in files if f.endswith(".tscn") and not is_test(f) and not is_addon(f)]
    embedded = []
    for f in tscn:
        t = read(target, f)
        n = t.count('[sub_resource type="GDScript"')
        if n:
            embedded.append((f, n))
    return {"version": version, "autoloads": al, "coupling": coupling.most_common(8), "coupling_ex": examples,
            "coupling_total": sum(coupling.values()), "scenes": len(tscn), "embedded_scripts": embedded,
            "has_project": bool(proj)}


# --- report ------------------------------------------------------------------------

def kb(b):
    return "%.1f KB" % (b / 1000.0)


def build(target):
    files = collect(target)
    scripts, game, tests, data, buckets, top = analyse_scripts(target, files)
    cm = analyse_claude_md(target, files)
    docs = analyse_docs(target, files)
    tst = analyse_tests(target, files, tests, data)
    wf = analyse_workflow(target, files)
    net = analyse_network(target, files, game, data)
    q = analyse_quality(target, game, data)
    gd = analyse_godot(target, files, game, data)
    game_lines = sum(data[f]["lines"] for f in game)
    game_bytes = sum(data[f]["bytes"] for f in game)
    over = [f for f in top if data[f]["lines"] > LARGE]
    findings = {"files": len(files), "game_scripts": len(game), "test_scripts": len(tests), "game_lines": game_lines,
                "over_800": [(f, data[f]["lines"]) for f in over]}

    L = []  # report lines
    A = []  # actions: (impact 1-3, effort 1-3, title, why, how)
    name = os.path.basename(os.path.abspath(target))
    L += ["# Claude kit analysis: %s" % name, "",
          "TL;DR: generated by godot-claude-kit `scripts/analyse.py` (read-only measurements, no code was changed). "
          "Findings with evidence first, then a prioritised action list at the end.", "",
          "Sections: 1 Overview · 2 Script sizes · 3 CLAUDE.md and context cost · 4 Docs · 5 Tests · 6 Workflow · "
          "7 Multiplayer · 8 Code quality · 9 Godot specifics · 10 Actions", ""]

    # 1 Overview
    L += ["## 1. Overview", "",
          "- Godot %s, %d files tracked, %d game scripts (%d lines, ~%dk tokens to read them all), %d test scripts, "
          "%d scenes." % (gd["version"], len(files), len(game), game_lines, game_bytes / BYTES_PER_TOKEN / 1000,
                          len(tests), gd["scenes"]),
          "- Autoloads: %d. Git: %s." % (len(gd["autoloads"]), "yes" if wf.get("git") else "no"), ""]

    # 2 Sizes
    L += ["## 2. Script sizes", "",
          "Rule of thumb: agents must read a file before editing it, so a 2000-line script costs ~20-30k tokens "
          "every time anyone touches it, and two tasks can't work in it at once. Keep scripts < %d lines." % LARGE, "",
          "| Lines | Scripts |", "|---|---|"]
    for b in ("< 200", "200-399", "400-799", "800-1499", ">= 1500"):
        L.append("| %s | %d |" % (b, buckets.get(b, 0)))
    L += ["", "Largest game scripts:", ""]
    for f in top[:15]:
        L.append("- `%s` %d lines%s%s" % (f, data[f]["lines"], " ⚠" if data[f]["lines"] > LARGE else "",
                                          " (tool)" if is_tool(f) else ""))
    if over:
        L += ["", "Split suggestions (seams) for scripts over %d lines:" % LARGE, ""]
        for f in over[:8]:
            s = seams(data[f]["list"])
            cl = ", ".join("`%s*` %d funcs ~%d lines" % (k, v[0], v[1]) for k, v in s["clusters"]) or "no clear prefix groups"
            L.append("- `%s` (%d lines, %d funcs, %d @rpc): clusters %s%s." % (
                f, data[f]["lines"], s["funcs"], s["rpcs"], cl,
                "; %d signal handlers ~%d lines" % tuple(s["handlers"]) if s["handlers"][0] >= 5 else ""))
            if s["sections"]:
                L.append("  - Sections already marked: " + ", ".join("%s (L%d)" % (n, ln) for ln, n in s["sections"]))
            L.append("  - Move a cluster into a RefCounted helper (back-reference set in `_init`), keep the %d @rpc "
                     "functions and synced properties on the owner, keep public API as one-line forwarders.%s" % (
                         s["rpcs"], " Grep the %d string-named calls (call/has_method/Callable/rpc/connect with a "
                                    "string) before moving anything." % s["dynamic_calls"] if s["dynamic_calls"] else ""))
        over_game = [f for f in over if not is_tool(f)]
        over_tool = [f for f in over if is_tool(f)]
        how = ("Manual, one task per file with the `implementer` agent on Sonnet (round skill). Pure refactor, "
               "no behaviour change; run the file's suites before and after.")
        if over_game:
            huge = [f for f in over_game if data[f]["lines"] >= HUGE]
            A.append((3 if huge or len(over_game) > 3 else 2, 2, "Split the %d game scripts over %d lines (%s)" % (
                len(over_game), LARGE, ", ".join("`%s` %d" % (os.path.basename(f), data[f]["lines"]) for f in over_game[:4])),
                "Every agent that touches them pays to read them, and they serialise parallel work. Ref: %s; %s." % (
                    REF["split"], REF["split_sizes"]), how))
        if over_tool:
            A.append((1, 2, "Split the %d tool scripts over %d lines (%s)" % (
                len(over_tool), LARGE, ", ".join("`%s` %d" % (os.path.basename(f), data[f]["lines"]) for f in over_tool[:4])),
                "Editor/build tools are touched less often than game code, so this can wait.", how))
    L.append("")

    # 3 CLAUDE.md
    L += ["## 3. CLAUDE.md and context cost", ""]
    if not cm["files"]:
        L += ["- No CLAUDE.md. Agents start every task without the project's rules and spend tokens rediscovering "
              "them.", ""]
        A.append((3, 1, "Add a lean CLAUDE.md (< 5 KB)", "No CLAUDE.md found.", "Kit: `claude_md` (+ `docs`)."))
    else:
        for c in cm["files"]:
            L.append("- `%s`: %s, %d lines, ~%d tokens. Status checkboxes: %d. Code blocks: %s. Pointers to docs/: %d."
                     % (c["path"], kb(c["bytes"]), c["lines"], c["bytes"] / BYTES_PER_TOKEN, c["checkboxes"],
                        kb(c["code_bytes"]), c["pointers"]))
            L.append("  - Biggest sections: " + ", ".join("%s %s (L%d)" % (n[:40], kb(b), ln) for n, b, ln in c["sections"]))
        for imp, b in cm["imports"]:
            L.append("- Imported with @: `%s` %s (also loads every turn)" % (imp, kb(b)))
        if cm["nested"]:
            L.append("- Nested CLAUDE.md (load when working in that folder): " + ", ".join("`%s`" % n for n in cm["nested"][:6]))
        tok = cm["tokens"]
        L += ["- Context cost: ~%d tokens on **every turn of every agent**. 100 turns = ~%dk tokens; a round with "
              "3 agents x 150 turns + the main session = ~%dk tokens just for this file." % (tok, tok * 100 / 1000,
                                                                                         tok * 500 / 1000), ""]
        if cm["total_bytes"] > CLAUDE_MD_GOOD:
            A.append((3 if cm["total_bytes"] > CLAUDE_MD_BAD else 2, 1,
                      "Slim CLAUDE.md from %s to < 5 KB" % kb(cm["total_bytes"]),
                      "It loads on every turn (~%d tokens). Ref: %s." % (tok, REF["claude_md"]),
                      "Kit: `claude_md` + `docs`, adapted: keep rules + 'where to look' pointers; move run/test details "
                      "to docs/dev_reference.md and milestones (%d checkboxes) to docs/status.md." %
                      sum(c["checkboxes"] for c in cm["files"])))
    L.append("- Project agents: %s. Skills: %s. Commands: %d." % (
        ", ".join("`%s` (%s)" % (os.path.basename(f), kb(b)) for f, b in cm["agents"]) or "none",
        ", ".join("`%s`" % f.split("/")[-2] for f, _ in cm["skills"]) or "none", len(cm["commands"])))
    L.append("")

    # 4 Docs
    L += ["## 4. Docs", "",
          "- %d Markdown docs. Code map: %s." % (docs["count"], "`%s`" % docs["code_map"] if docs["code_map"] else
                                                 "**none** (agents search the tree instead)"),
          "- Big docs (>= %s or >= %d lines): %d with a TL;DR/summary at the top, %d without." % (
              kb(BIG_DOC_BYTES), BIG_DOC_LINES, docs["big_with_summary"], len(docs["big_without_summary"]))]
    for f, b, n in docs["big_without_summary"][:10]:
        L.append("  - `%s` %s, %d lines, no summary in the first 25 lines" % (f, kb(b), n))
    L.append("")
    if not docs["code_map"]:
        A.append((3, 1, "Add a generated code map (docs/code_map.md)",
                  "Agents grep one file to find which script owns a system instead of searching %d scripts." % len(game),
                  "Kit: `code_map` (tools/dev/code_map.py; add a one-line `##` doc comment to scripts over time)."))
    if docs["big_without_summary"]:
        A.append((2, 1, "Add a TL;DR + section index to %d big docs" % len(docs["big_without_summary"]),
                  "Agents then read 10 lines and jump to one section instead of reading the whole doc.",
                  "Manual (one Sonnet agent for all of them): 2-4 line TL;DR and a 'Sections:' line at the top."))

    # 5 Tests
    L += ["## 5. Tests", "",
          "- Test scripts: %d (game scripts: %d). Frameworks: %s. Runner: %s%s. Suites listed: %d%s." % (
              tst["test_scripts"], len(game), ", ".join(tst["frameworks"]) or "none",
              "`%s`" % tst["runner"] if tst["runner"] else "none",
              " (parallel)" if tst["parallel"] else (" (serial)" if tst["runner"] else ""), tst["suites"],
              " in `%s`" % tst["suite_file"] if tst["suite_file"] else ""),
          "- CI: %s. Network (host/client) tests: %d." % (", ".join(tst["ci"]) or "none", tst["net_tests"])]
    if tst["durations"]:
        total = sum(v for _, v in tst["durations"])
        L.append("- Last recorded durations: %d suites, %.0f s summed; slowest: %s." % (
            len(tst["durations"]), total, ", ".join("%s %.0fs" % kv for kv in tst["durations"][:5])))
    if tst["flaky"]:
        L.append("- Flaky signals (fixed frame counts / timer awaits / delays / sleeps instead of waiting on state):")
        for f, fr, ti, de in tst["flaky"][:8]:
            L.append("  - `%s`: frame-count checks %d, timer awaits %d, delays/sleeps %d" % (f, fr, ti, de))
    L.append("")
    if not tst["runner"] and not tst["frameworks"]:
        A.append((3, 2, "Add headless tests + a parallel runner",
                  "No tests found: agents can't prove a change works, so you test everything by hand. Ref: %s." % REF["runner"],
                  "Kit: `tests` (runner, suites.txt, parse check, smoke suite%s)." % (
                      ", host+client net test" if net["uses_network"] else "")))
    elif tst["runner"] and not tst["parallel"]:
        A.append((2, 2, "Make the test runner parallel with port/save-slot locks",
                  "Serial runs make agents wait; parallel runs need port locks. Ref: %s." % REF["runner"],
                  "Kit: `tests` adapted: keep existing tests, register them in suites.txt, add CHANGE_TAGS for --changed."))
    elif tst["frameworks"] and not tst["runner"]:
        A.append((2, 2, "Add a runner with --changed and tags around the existing %s tests" % "/".join(tst["frameworks"]),
                  "Agents should run only the suites their diff touches. Ref: %s." % REF["runner"],
                  "Kit: `tests` adapted: one suites.txt line per test group calling the framework's CLI."))
    if tst["flaky"]:
        A.append((2, 2, "Fix %d tests with flaky signals" % len(tst["flaky"]),
                  "A flaky test is noise everyone learns to ignore; agents re-run and burn tokens.",
                  "Manual: wait on state (signals/conditions with a timeout), not frame counts or fixed timers."))

    # 6 Workflow
    L += ["## 6. Workflow", ""]
    if not wf.get("git"):
        L += ["- **No git repository.** No branches, no review, no safe rollback.", ""]
        A.append((3, 1, "Put the project in git", "Everything else (branches, worktrees, hooks, review) needs it.",
                  "`git init`, then kit: `core` (.gitignore with .godot/)."))
    else:
        L += ["- Branches: %d. Last %d commits: %d merges, %d with a task/type prefix. Uncommitted changes: %d." % (
                  wf["branches"], wf["commits_sampled"], wf["merges"], wf["prefixed"], wf["dirty"]),
              "- Hooks: core.hooksPath=%s, .githooks/: %d files, .git/hooks active: %s." % (
                  wf["hooks_path"] or "(unset)", len(wf["githooks_dir"]), ", ".join(wf["git_hooks"]) or "none"),
              "- Worktree scripts: %s (live worktrees: %d). .gitignore covers .godot/: %s." % (
                  ", ".join("`%s`" % f for f in wf["worktree_scripts"]) or "none", wf["worktrees_live"],
                  "yes" if wf["gitignore_godot"] else "**no**"), ""]
        if not wf["hooks_path"] and not wf["git_hooks"]:
            A.append((2, 1, "Add a pre-commit hook (parse check + code map check)",
                      "Broken scripts get caught before a commit, not by the next agent. Ref: %s." % REF["precommit"],
                      "Kit: `hooks`."))
        if not wf["worktree_scripts"]:
            A.append((2, 1, "One task = one branch + worktree (scripts)",
                      "Lets 2-3 agents work at once without stepping on each other; merges stay revertable (--no-ff).",
                      "Kit: `worktrees`."))
        if not wf["gitignore_godot"]:
            A.append((2, 1, "Ignore .godot/ in git", "The import cache is machine-specific and huge.", "Kit: `core`."))
    if not cm["agents"]:
        A.append((2, 1, "Add implementer + reviewer agents and the round skill",
                  "A repeatable plan -> parallel build -> independent review -> merge loop, with short reports. "
                  "Ref: %s." % REF["audit"], "Kit: `agents` (or use the plugin's agents directly)."))

    # 7 Network
    L += ["## 7. Multiplayer", ""]
    if not net["uses_network"]:
        L += ["- No networking code found.", ""]
    else:
        L += ["- RPC functions: %d (any_peer: %d). MultiplayerSpawner nodes: %d, MultiplayerSynchronizer nodes: %d." % (
                  net["rpcs"], net["any_peer"], net["spawners"], net["synchronizers"]),
              "- Scripts handling peer_connected: %d (of which %d send something with rpc_id: likely late-join "
              "sync)." % (net["peer_connected_handlers"], net["late_join_senders"]),
              "- any_peer RPCs without a sender check (`get_remote_sender_id` or a validate/check helper): %d" %
              len(net["unvalidated"])]
        for f, ln, fn, local in net["unvalidated"][:15]:
            L.append("  - `%s:%d` %s()%s" % (f, ln, fn, " (call_local: also runs on the caller)" if local else ""))
        if net["per_frame"]:
            L.append("- Reliable RPCs sent unconditionally every frame from _process/_physics_process (use a synchronizer "
                     "or unreliable): %d" %
                     len(net["per_frame"]))
            for f, ln, fn in net["per_frame"][:8]:
                L.append("  - `%s:%d` in %s" % (f, ln, fn))
        if net["no_authority"]:
            L.append("- Scripts with any_peer RPCs but no authority check at all (is_server / is_multiplayer_authority / "
                     "sender id): " + ", ".join("`%s` (%d)" % x for x in net["no_authority"][:8]))
        L.append("- Not measurable cheaply: whether clients mutate shared state locally; review hot paths by hand "
                 "(reviewer checklist).")
        L.append("")
        if net["unvalidated"]:
            A.append((3, 2, "Validate %d any_peer RPCs on the server" % len(net["unvalidated"]),
                      "Any client can call them with any arguments (cheats, desyncs, crashes). Evidence: %s." %
                      ", ".join("%s:%d" % (os.path.basename(f), ln) for f, ln, _, _ in net["unvalidated"][:4]),
                      "Manual: check sender id, ownership, distance, cooldown, ranges at the top of each; add a "
                      "host+client test for the important ones."))
        if net["per_frame"]:
            A.append((2, 2, "Move %d unconditional per-frame RPCs to MultiplayerSynchronizer" % len(net["per_frame"]),
                      "Per-frame reliable RPCs flood the connection and lag under packet loss.",
                      "Manual: synced properties for continuous state; RPCs only for events."))
        if not tst["net_tests"]:
            A.append((2, 2, "Add a headless host + client test",
                      "Multiplayer bugs only show up with two peers; agents need a cheap way to check.",
                      "Kit: `tests` (tests/net/ example: two headless processes, roster sync)."))

    # 8 Quality
    L += ["## 8. Code quality signals", "",
          "- Static typing: vars %.0f%% typed (%d), return types %.0f%% (%d funcs), params %.0f%%." % (
              q["var_typed_pct"], q["vars"], q["ret_typed_pct"], q["funcs"], q["param_typed_pct"])]
    if q["worst_typing"] and q["worst_typing"][0][1] < 0.99:
        L.append("  - Least typed: " + ", ".join("`%s` %.0f%%" % (f, r * 100) for f, r, _ in q["worst_typing"]))
    L.append("- Number literals in logic (outside const/@export/var defaults; 0/1/2/0.5/... ignored): %d. Densest: %s." % (
        q["magic_total"], ", ".join("`%s` %d (L%s)" % (f, n, ",".join(map(str, ex))) for f, n, _, ex in q["magic_top"][:5])))
    L.append("- Player-facing text assigned in code without tr(): %d (tr() calls: %d)." % (len(q["ui_text"]), q["tr_calls"]))
    for f, ln, src in q["ui_text"][:8]:
        L.append("  - `%s:%d` `%s`" % (f, ln, src.replace("`", "'")))
    L.append("")
    if min(q["var_typed_pct"], q["ret_typed_pct"]) < 80 and q["vars"] > 50:
        A.append((2, 2, "Raise static typing (vars %.0f%%, returns %.0f%%)" % (q["var_typed_pct"], q["ret_typed_pct"]),
                  "Typed GDScript catches agent mistakes at parse time (the 2 s pre-commit check) and runs faster.",
                  "Manual: enable `debug/gdscript/warnings/untyped_declaration` (warn) and fix file by file when touched."))
    if len(q["ui_text"]) >= 10:
        A.append((2, 2, "Route %d hardcoded UI strings through tr()" % len(q["ui_text"]),
                  "Translation later is free if text goes through tr() now.",
                  "Manual (Sonnet): wrap strings in tr(); add a CLAUDE.md rule."))

    # 9 Godot
    L += ["## 9. Godot specifics", "",
          "- Autoloads (%d): %s." % (len(gd["autoloads"]), ", ".join(
              "%s %d%s" % (n, ln, " (class_name!)" if cls else "") for n, _, ln, cls in gd["autoloads"]) or "none")]
    cls_autoloads = [n for n, _, _, cls in gd["autoloads"] if cls]
    if cls_autoloads:
        L.append("  - Autoloads with class_name: %s. `-s` test scripts compile them before the autoload exists; "
                 "drop class_name on autoloads." % ", ".join(cls_autoloads))
        A.append((1, 1, "Remove class_name from %d autoload(s)" % len(cls_autoloads),
                  "Headless `-s` tests then compile cleanly.", "Manual: %s." % ", ".join(cls_autoloads)))
    big_al = [n for n, _, ln, _ in gd["autoloads"] if ln > LARGE]
    if big_al:
        L.append("  - Big autoloads are hot files (every system touches them): %s. Split into hub + modules "
                 "(`Game.<module>.func()`), autoload modules without class_name." % ", ".join(big_al))
    L.append("- Logic tied to node names/paths (deep `$A/B/C`, `/root/` non-autoload paths, `../../`, find_child, "
             "`.name ==`): %d hits. Top: %s." % (gd["coupling_total"], ", ".join(
                 "`%s` %d (L%d)" % (f, n, gd["coupling_ex"][f]) for f, n in gd["coupling"][:5]) or "none"))
    if gd["embedded_scripts"]:
        L.append("- Scenes with embedded (built-in) scripts: %d (%s). Hard to grep and review; move to .gd files." % (
            len(gd["embedded_scripts"]), ", ".join(f for f, _ in gd["embedded_scripts"][:4])))
    L.append("")
    if gd["coupling_total"] >= 30:
        A.append((1, 2, "Reduce node-name coupling (%d hits)" % gd["coupling_total"],
                  "Renaming a node or swapping a visual scene silently breaks logic.",
                  "Manual: @export node references or unique names (%Name); visuals in their own scenes."))

    # 10 Actions
    L += ["## 10. Prioritised actions", "",
          "Score = impact (3 high .. 1 low) / effort (1 small .. 3 large). `Kit: <group>` means godot-claude-kit "
          "can set it up (adapted to this project, never blind copying): ask Claude to \"apply items N, M\".", "",
          "| # | Action | Impact | Effort | Why | How |", "|---|---|---|---|---|---|"]
    A.sort(key=lambda a: (-a[0] / a[1], -a[0]))
    names = {1: "low", 2: "medium", 3: "high"}
    eff = {1: "small", 2: "medium", 3: "large"}
    actions = []
    for i, (imp, ef, title, why, how) in enumerate(A, 1):
        L.append("| %d | %s | %s | %s | %s | %s |" % (i, title, names[imp], eff[ef], why, how))
        actions.append({"n": i, "title": title, "impact": imp, "effort": ef, "why": why, "how": how})
    if not A:
        L.append("| - | Nothing urgent found | | | | |")
    L += ["", "Reference numbers (measured on a Claude-built Godot co-op game): " + "; ".join(REF.values()) + "."]
    findings.update({"claude_md_bytes": cm["total_bytes"], "claude_md_tokens": cm["tokens"],
                     "big_docs_without_summary": len(docs["big_without_summary"]), "code_map": docs["code_map"],
                     "runner": tst["runner"], "parallel": tst["parallel"], "suites": tst["suites"],
                     "hooks_path": wf.get("hooks_path", ""), "agents": [f for f, _ in cm["agents"]],
                     "skills": [f for f, _ in cm["skills"]], "unvalidated_rpcs": len(net["unvalidated"]),
                     "typed_vars_pct": q["var_typed_pct"], "ui_text_without_tr": len(q["ui_text"]),
                     "actions": actions})
    return "\n".join(L) + "\n", findings


def summary(findings, out):
    s = ["Report: %s" % out,
         "Game scripts: %d (%d lines), tests: %d. Over %d lines: %d%s" % (
             findings["game_scripts"], findings["game_lines"], findings["test_scripts"], LARGE,
             len(findings["over_800"]), (" -> " + ", ".join("%s %d" % (os.path.basename(f), n)
                                                           for f, n in findings["over_800"][:8])) if findings["over_800"] else ""),
         "CLAUDE.md: %s (~%d tokens/turn). Code map: %s. Big docs without TL;DR: %d." % (
             kb(findings["claude_md_bytes"]), findings["claude_md_tokens"], findings["code_map"] or "none",
             findings["big_docs_without_summary"]),
         "Tests: runner %s%s, %d suites. Hooks: %s. Agents: %s. Skills: %s." % (
             findings["runner"] or "none", " (parallel)" if findings["parallel"] else "", findings["suites"],
             findings["hooks_path"] or "none", ", ".join(os.path.basename(a) for a in findings["agents"]) or "none",
             ", ".join(x.split("/")[-2] for x in findings["skills"]) or "none"),
         "Unvalidated any_peer RPCs: %d. Typed vars: %.0f%%. UI text without tr(): %d." % (
             findings["unvalidated_rpcs"], findings["typed_vars_pct"], findings["ui_text_without_tr"]),
         "Actions:"]
    for a in findings["actions"]:
        s.append("  %d. [impact %d / effort %d] %s" % (a["n"], a["impact"], a["effort"], a["title"]))
    return "\n".join(s)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", default=".")
    ap.add_argument("--out", help="report path (default <target>/docs/claude_kit_analysis.md)")
    ap.add_argument("--json", help="also write the findings as JSON here")
    opts = ap.parse_args()
    target = os.path.abspath(opts.target)
    if not os.path.exists(os.path.join(target, "project.godot")):
        print("WARNING: no project.godot in %s; analysing anyway." % target)
    out = os.path.abspath(opts.out or os.path.join(target, "docs", "claude_kit_analysis.md"))
    report, findings = build(target)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(report)
    if opts.json:
        with open(opts.json, "w", encoding="utf-8") as fh:
            json.dump(findings, fh, indent=1)
    print(summary(findings, out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
