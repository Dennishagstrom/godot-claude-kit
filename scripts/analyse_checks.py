"""Measurements for analyse.py: file collection, GDScript parsing helpers and one
analyse_*() per report section. Read-only; each returns plain dicts/lists that
analyse.py turns into the report and the action list.
"""
import json
import os
import re
import subprocess
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
        # Comments don't count (the kit's events.gd mentions @rpc in a doc comment), nor does a bare
        # multiplayer.is_server() check (single-player-safe helpers such as VisualSmoother use it).
        if not re.search(r"^[^#\n]*(@rpc|MultiplayerPeer|MultiplayerSynchronizer|MultiplayerSpawner|\.rpc(_id)?\()", t, re.M):
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


def _kit_tool(name, rel):
    import importlib.util
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "templates", *rel.split("/"))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def kit_lint(target):
    """The kit's own lint (templates/project/tools/dev/lint.py) run on the target: findings list."""
    return _kit_tool("kit_lint", "project/tools/dev/lint.py").lint(os.path.abspath(target))[0]


def kit_assets(target):
    """The kit's model check (model-import module) on the target: (findings, notes, number of models)."""
    found, notes, models = _kit_tool("kit_assets", "modules/model-import/files/tools/dev/asset_check.py").check(
        os.path.abspath(target))
    return found, notes, len(models)
