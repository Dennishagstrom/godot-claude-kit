#!/usr/bin/env python3
"""godot-claude-kit scaffolder: renders the kit's templates into a Godot project.

Never overwrites a file that differs unless it is named with --overwrite (or
--overwrite-all). Files that are already identical are skipped, so running it
twice is safe (idempotent). Answers are saved in <target>/.claude/godot-kit.json
and reused on the next run, together with a hash of every file the kit wrote:
a file whose content still matches that hash was not edited by the user, so a
newer template replaces it (state UPDATE) without asking.

    python3 -I scaffold.py detect --target DIR
    python3 -I scaffold.py plan   --target DIR --answers '{"game_name": "X", ...}' [--only tests,hooks]
    python3 -I scaffold.py apply  --target DIR [--answers ...] [--only ...] [--overwrite CLAUDE.md,docs/status.md]
                                  [--overwrite-all] [--create-project] [--git-init]
    python3 -I scaffold.py groups
    python3 -I scaffold.py recommend --target DIR --answers '{...}'   # modules for this game, with reasons

Answer keys: game_name, dimension ("2D"/"3D"), multiplayer (bool), max_players (int),
text_language (e.g. "English"), default_port (int, default 7777), modules (list of module
names; default: the ones `recommend` turns on), and the frame from the godot-start interview
(pitch, camera, platforms, input, art, scope, ...; see kit_frame.py).
`--only` takes groups and/or module names; modules named there are added to the saved list.
"""
import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import doctor  # noqa: E402  (python3 -I does not add the script folder to sys.path)
import kit_frame  # noqa: E402
import kit_modules  # noqa: E402

KIT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TPL = os.path.join(KIT_ROOT, "templates", "project")
KIT_VERSION = json.load(open(os.path.join(KIT_ROOT, ".claude-plugin", "plugin.json"))).get("version", "0")
ANSWERS_FILE = ".claude/godot-kit.json"

GROUPS = {
    "core": "Godot path helper, .gitignore lines, saved answers (always included)",
    "claude_md": "Lean CLAUDE.md (< 5 KB) with rules and 'where to look' pointers",
    "docs": "docs/dev_reference.md, status.md, dev_workflow.md, rounds/",
    "code_map": "tools/dev/code_map.py + generated docs/code_map.md",
    "tests": "tools/test_runner.py (parallel), tests/ skeleton, smoke + real-time main + lint suites, Rng "
             "(+ host/client net and late-join tests, RPC parity check)",
    "worktrees": "tools/dev/new_worktree.sh / finish_worktree.sh, .claude/.gdignore",
    "hooks": ".githooks/pre-commit (parse check + code map) and core.hooksPath",
    "agents": ".claude/agents implementer + reviewer, .claude/skills/round",
    "autoloads": "autoload/events.gd (+ autoload/network.gd if multiplayer), registered in project.godot",
    "basics": "README.md, docs/design.md, .editorconfig (written when missing, then the project's own)",
    "permissions": ".claude/settings.json: allow the test runner, code map, worktree scripts, read-only git",
}

# (source relative to the kit root, target relative to the project, group, condition)
MANIFEST = [
    ("templates/project/tools/dev/godot_env.sh", "tools/dev/godot_env.sh", "core", None),
    ("templates/project/CLAUDE.md", "CLAUDE.md", "claude_md", None),
    ("templates/project/docs/dev_reference.md", "docs/dev_reference.md", "docs", None),
    ("templates/project/docs/status.md", "docs/status.md", "docs", None),
    ("templates/project/docs/dev_workflow.md", "docs/dev_workflow.md", "docs", None),
    ("templates/project/docs/rounds/README.md", "docs/rounds/README.md", "docs", None),
    ("templates/project/tools/dev/code_map.py", "tools/dev/code_map.py", "code_map", None),
    ("templates/project/tools/test_runner.py", "tools/test_runner.py", "tests", None),
    ("templates/project/tests/.gdignore", "tests/.gdignore", "tests", None),
    ("templates/project/tests/.gitignore", "tests/.gitignore", "tests", None),
    ("templates/project/tests/integration/suites.txt", "tests/integration/suites.txt", "tests", None),
    ("templates/project/tests/parse_check.gd", "tests/parse_check.gd", "tests", None),
    ("templates/project/tests/smoke/test_smoke.gd", "tests/smoke/test_smoke.gd", "tests", None),
    ("templates/project/tests/net/run_net.sh", "tests/net/run_net.sh", "tests", "multiplayer"),
    ("templates/project/tests/net/net_host.gd", "tests/net/net_host.gd", "tests", "multiplayer"),
    ("templates/project/tests/net/net_client.gd", "tests/net/net_client.gd", "tests", "multiplayer"),
    ("templates/project/tests/net/late_join_fixture.gd", "tests/net/late_join_fixture.gd", "tests", "multiplayer"),
    ("templates/project/tests/net/late_join_host.gd", "tests/net/late_join_host.gd", "tests", "multiplayer"),
    ("templates/project/tests/net/late_join_client.gd", "tests/net/late_join_client.gd", "tests", "multiplayer"),
    ("templates/project/tests/smoke/run_main.sh", "tests/smoke/run_main.sh", "tests", None),
    ("templates/project/tests/lint/run_lint.sh", "tests/lint/run_lint.sh", "tests", None),
    ("templates/project/tests/core/test_rng.gd", "tests/core/test_rng.gd", "tests", None),
    ("templates/project/tools/dev/lint.py", "tools/dev/lint.py", "tests", None),
    ("templates/project/tools/dev/rpc_check.py", "tools/dev/rpc_check.py", "tests", "multiplayer"),
    ("templates/project/scripts/core/rng.gd", "scripts/core/rng.gd", "tests", None),
    ("templates/project/tools/dev/new_worktree.sh", "tools/dev/new_worktree.sh", "worktrees", None),
    ("templates/project/tools/dev/finish_worktree.sh", "tools/dev/finish_worktree.sh", "worktrees", None),
    ("templates/project/.claude/.gdignore", ".claude/.gdignore", "worktrees", None),
    ("templates/project/.githooks/pre-commit", ".githooks/pre-commit", "hooks", None),
    ("agents/implementer.md", ".claude/agents/implementer.md", "agents", None),
    ("agents/reviewer.md", ".claude/agents/reviewer.md", "agents", None),
    ("skills/godot-round/SKILL.md", ".claude/skills/round/SKILL.md", "agents", None),
    ("templates/project/autoload/events.gd", "autoload/events.gd", "autoloads", None),
    ("templates/project/autoload/network.gd", "autoload/network.gd", "autoloads", "multiplayer"),
    ("templates/project/scripts/net/port_offset.gd", "scripts/net/port_offset.gd", "autoloads", "multiplayer"),
    ("templates/project/README.md", "README.md", "basics", None),
    ("templates/project/docs/design.md", "docs/design.md", "basics", None),
    ("templates/project/.editorconfig", ".editorconfig", "basics", None),
]
# Written once, then owned by the project (never DIFFERS, never overwritten).
BASE_SEEDS = {"README.md", "docs/design.md", ".editorconfig"}
# Files Godot's project manager writes; the kit's version replaces them while unedited.
GODOT_DEFAULTS = {".editorconfig": {"root = true", "[*]", "charset = utf-8"}}
SETTINGS_FILE = ".claude/settings.json"
# Commands agents run all the time; allowed so a round doesn't stall on prompts.
# Nothing here pushes, deletes or rewrites history.
ALLOW = ["Bash(%s -I tools/%s:*)" % (py, tool) for tool in ("test_runner.py", "dev/code_map.py")
         for py in ("python3", "python", "py")] + [
    "Bash(tools/dev/new_worktree.sh:*)", "Bash(tools/dev/finish_worktree.sh:*)",
    "Bash(bash tools/dev/new_worktree.sh:*)", "Bash(bash tools/dev/finish_worktree.sh:*)",
    "Bash(git status:*)", "Bash(git diff:*)", "Bash(git log:*)", "Bash(git show:*)",
    "Bash(git worktree list:*)", "Bash(git branch --show-current)", "Bash(git rev-parse:*)",
]
ALLOW_MODULES = {"build-release": ["Bash(tools/build_release.sh --check)", "Bash(bash tools/build_release.sh --check)"]}
# Scripts the other groups depend on (the hook needs the code map, etc.).
DEPENDS = {"hooks": ["code_map", "tests"]}
GITIGNORE_LINES = [".godot/", ".claude/worktrees/", ".claude/settings.local.json"]
# Shell scripts must keep LF on Windows checkouts (core.autocrlf), or bash fails on \r.
GITATTRIBUTES_LINES = ["*.sh text eol=lf", ".githooks/* text eol=lf"]
DEFAULTS = {"game_name": "", "dimension": "3D", "multiplayer": False, "max_players": 4,
            "text_language": "English", "default_port": 7777, "modules": None}


# --- detection ----------------------------------------------------------------

def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return None


def project_info(target):
    text = read(os.path.join(target, "project.godot")) or ""
    name = re.search(r'^config/name="([^"]*)"', text, re.M)
    feats = re.search(r'^config/features=PackedStringArray\(([^)]*)\)', text, re.M)
    version = "4"
    if feats:
        m = re.search(r'"(\d+\.\d+)"', feats.group(1))
        version = m.group(1) if m else version
    autoloads = re.findall(r'^(\w+)="\*?res://([^"]+)"', section(text, "autoload"), re.M)
    main = re.search(r'^run/main_scene="([^"]*)"', section(text, "application"), re.M)
    return {"has_project": bool(text), "name": name.group(1) if name else os.path.basename(target),
            "godot_version": version, "autoloads": autoloads, "main_scene": main.group(1) if main else "",
            "dimension_guess": "2D" if "gl_compatibility" in text.lower() and "3d" not in text.lower() else "3D"}


def section(text, name):
    m = re.search(r"^\[%s\]\s*$(.*?)(?=^\[|\Z)" % re.escape(name), text, re.M | re.S)
    return m.group(1) if m else ""


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def saved_state(target):
    text = read(os.path.join(target, ANSWERS_FILE))
    return json.loads(text) if text else {}


def is_git(target):
    return subprocess.run(["git", "-C", target, "rev-parse", "--is-inside-work-tree"],
                          capture_output=True, text=True).returncode == 0


def load_answers(target, given):
    answers = dict(DEFAULTS)
    saved = read(os.path.join(target, ANSWERS_FILE))
    if saved:
        answers.update(json.loads(saved).get("answers", {}))
    if given:
        answers.update(json.loads(given))
    if not answers["game_name"]:
        answers["game_name"] = project_info(target)["name"]
    answers["multiplayer"] = str(answers["multiplayer"]).lower() in ("true", "1", "yes", "y")
    kit_frame.normalise(answers)
    mods = answers.get("modules")
    if mods is None:
        mods = kit_frame.recommended_names(answers)
    elif isinstance(mods, str):
        mods = [m.strip() for m in mods.split(",") if m.strip()]
    answers["modules"] = [m["name"] for m in kit_modules.active(mods, answers)]
    return answers


# --- rendering ------------------------------------------------------------------

def render(text, answers, info, blocks=True):
    mods = kit_modules.active(answers["modules"], answers)
    flags = {"MULTIPLAYER": answers["multiplayer"], "3D": answers["dimension"].upper() == "3D"}
    for m in kit_modules.all_modules():
        flags[kit_modules.flag_name(m["name"])] = any(a["name"] == m["name"] for a in mods)
    flags["MODULES"] = bool(mods)
    for key, on in flags.items():
        text = re.sub(r"\{\{#%s\}\}(.*?)\{\{/%s\}\}" % (key, key), lambda m: m.group(1) if on else "", text, flags=re.S)
        text = re.sub(r"\{\{\^%s\}\}(.*?)\{\{/%s\}\}" % (key, key), lambda m: "" if on else m.group(1), text, flags=re.S)
    values = {
        "GAME_NAME": answers["game_name"], "DIMENSION": answers["dimension"],
        "MAX_PLAYERS": str(answers["max_players"]), "PITCH": answers["pitch"].strip().rstrip("."),
        "TEXT_LANGUAGE": answers["text_language"], "DEFAULT_PORT": str(answers["default_port"]),
        "GODOT_VERSION": info["godot_version"],
        # Release tag for downloads (CI): the installed Godot, else <project version>-stable.
        "GODOT_RELEASE": installed_godot_release() or info["godot_version"] + "-stable",
        "MODULE_LIST": ", ".join(m["name"] for m in mods),
        # File-name safe forms of the game name: "My Game!" -> MyGame / mygame.
        "GAME_SLUG": re.sub(r"[^A-Za-z0-9]", "", answers["game_name"].title()) or "Game",
        "GAME_ID": re.sub(r"[^a-z0-9]", "", answers["game_name"].lower()) or "game",
        # Prefix for environment variables the tests use ({{GAME_ENV}}_PORT_OFFSET).
        "GAME_ENV": re.sub(r"^(?=\d)", "G", re.sub(r"[^A-Z0-9]", "", answers["game_name"].upper()) or "GAME"),
    }
    # Block placeholders sit on a line of their own and vanish with it when empty.
    if blocks and re.search(r"\{\{(MODULE|FRAME|DESIGN|STATUS)_", text):
        found = dict(module_blocks(mods, answers, info), **kit_frame.blocks(answers))
        for key, lines in found.items():
            text = text.replace("{{%s}}\n" % key, "".join(l + "\n" for l in lines))
    for key, val in values.items():
        text = text.replace("{{%s}}" % key, val)
    left = re.findall(r"\{\{[#^/]?[A-Z_0-9]+\}\}", text)
    if left:
        raise SystemExit("template has unknown placeholders: %s" % ", ".join(sorted(set(left))))
    return text


def module_blocks(mods, answers, info):
    return {
        "MODULE_SUITES": kit_modules.suite_lines(mods, lambda line: render(line, answers, info, False)),
        "MODULE_CHANGE_TAGS": kit_modules.change_tag_lines(mods),
        "MODULE_CLAUDE_MD": [render(m["claude_md"], answers, info, False) for m in mods if m["claude_md"]],
    }


def selected_groups(only, answers):
    """(groups, module names) to apply. Modules named in --only join answers["modules"]."""
    if not only:
        return set(GROUPS), list(answers["modules"])
    names = {n.strip() for n in only.split(",") if n.strip()}
    known_mods = kit_modules.by_name()
    mods = [n for n in kit_modules.ORDER if n in names and n in known_mods]
    groups = {"core"} | (names - set(mods))
    for g in list(groups):
        groups |= set(DEPENDS.get(g, []))
    bad = groups - set(GROUPS)
    if bad:
        raise SystemExit("unknown groups or modules: %s (see: scaffold.py groups)" % ", ".join(sorted(bad)))
    skipped = [n for n in mods if not kit_modules.fits(known_mods[n], answers)]
    if skipped:
        print("NOTE: module(s) skipped, this game can't use them (multiplayer-only or %s-only): %s" % (
            "3D" if answers["dimension"].upper() == "2D" else "2D", ", ".join(skipped)))
    mods = [n for n in mods if n not in skipped]
    answers["modules"] = [m["name"] for m in kit_modules.active(list(answers["modules"]) + mods, answers)]
    return groups, mods


def plan(target, answers, groups, mods=()):
    info = project_info(target)
    items = []
    written = saved_state(target).get("files", {})
    sources = [(src, dst, group, cond) for src, dst, group, cond in MANIFEST]
    active = kit_modules.active(list(mods), answers)
    seeds = {p for m in active for p in m["seed"]} | BASE_SEEDS
    for m in active:
        for src, dst in kit_modules.files(m, answers):
            sources.append((os.path.relpath(src, KIT_ROOT), dst, m["name"], None))
    for src, dst, group, cond in sources:
        if group not in groups and group not in mods:
            continue
        if cond == "multiplayer" and not answers["multiplayer"]:
            continue
        content = render(read(os.path.join(KIT_ROOT, src)), answers, info)
        current = read(os.path.join(target, dst))
        state = "NEW" if current is None else ("SAME" if current == content or dst in seeds else "DIFFERS")
        detail = "project-owned (seed)" if current is not None and dst in seeds else ""
        if current is not None and dst in GODOT_DEFAULTS and current != content and \
                {l.strip() for l in current.splitlines() if l.strip() and not l.startswith("#")} <= GODOT_DEFAULTS[dst]:
            state, detail = "UPDATE", "Godot's default; the kit's version adds to it"
        elif state == "DIFFERS" and written.get(dst) == digest(current):
            state, detail = "UPDATE", "newer kit template; the file was not edited since the kit wrote it"
        elif state == "DIFFERS":
            detail = "edited in the project" if dst in written else "no record of what the kit wrote (kit < 0.3.0)"
        items.append({"path": dst, "group": group, "state": state, "content": content, "detail": detail,
                      "exec": src.endswith(("pre-commit",)) or kit_modules.is_exec(src)})
    new_paths = {it["path"] for it in items if it["state"] == "NEW"}
    # Patches to existing files: only adds missing lines.
    gi = read(os.path.join(target, ".gitignore")) or ""
    want_gi = list(GITIGNORE_LINES) + [l for m in active for l in m["gitignore"]]
    missing = [l for l in dict.fromkeys(want_gi) if l not in gi.splitlines()]
    items.append({"path": ".gitignore", "group": "core", "state": "PATCH" if missing else "SAME",
                  "patch": missing, "detail": "add " + ", ".join(missing) if missing else ""})
    ga = read(os.path.join(target, ".gitattributes")) or ""
    missing = [l for l in GITATTRIBUTES_LINES if l not in ga.splitlines()]
    items.append({"path": ".gitattributes", "group": "core", "state": "PATCH" if missing else "SAME",
                  "patch": missing, "detail": "add " + ", ".join(missing) if missing else ""})
    want = []
    if "autoloads" in groups:
        want = [("Events", "autoload/events.gd")]
        if answers["multiplayer"]:
            want.insert(0, ("Network", "autoload/network.gd"))
    want += [tuple(a) for m in active for a in m["autoloads"]]
    have = {n for n, _ in info["autoloads"]}
    add = [(n, p) for n, p in want if n not in have]
    text = read(os.path.join(target, "project.godot")) or ""
    # The frame's settings first (pixel art beats the starter's stretch mode); the first one of a key wins.
    first = {}
    for by_section in [kit_frame.settings(answers)] + [m["settings"] for m in active]:
        for sec, kv in by_section.items():
            for key, val in kv.items():
                first.setdefault((sec, key), val)
    settings = [(sec, key, val) for (sec, key), val in first.items()
                if not re.search(r"^%s=" % re.escape(key), section(text, sec), re.M)]
    if want or settings:
        detail = []
        if add:
            detail.append("register autoload " + ", ".join(n for n, _ in add))
        if settings:
            detail.append("add " + ", ".join("%s/%s" % (s_, k) for s_, k, _ in settings))
        items.append({"path": "project.godot", "group": "autoloads" if "autoloads" in groups else "modules",
                      "state": "PATCH" if add or settings else "SAME", "patch": add, "settings": settings,
                      "detail": "; ".join(detail)})
    # Module suites and CHANGE_TAGS in files that exist and were not written from the template.
    suites_path, runner_path = "tests/integration/suites.txt", "tools/test_runner.py"
    lines = kit_modules.suite_lines(active, lambda line: render(line, answers, info, False))
    if lines and suites_path not in new_paths:
        cur = read(os.path.join(target, suites_path))
        if cur is None:
            items.append({"path": suites_path, "group": "modules", "state": "SKIP",
                          "detail": "no suite list: add the `tests` group, or register the suites by hand"})
        else:
            names = {l.split()[0] for l in cur.splitlines() if l.strip() and not l.startswith("#")}
            miss = [l for l in lines if l.split()[0] not in names]
            items.append({"path": suites_path + " (modules)", "group": "modules", "file": suites_path,
                          "state": "PATCH" if miss else "SAME", "lines": miss,
                          "detail": "add suites " + ", ".join(l.split()[0] for l in miss) if miss else ""})
    tags = kit_modules.change_tag_lines(active)
    if tags and runner_path not in new_paths:
        cur = read(os.path.join(target, runner_path))
        if cur is not None and re.search(r"^CHANGE_TAGS = \[", cur, re.M):
            miss = [l for l in tags if l.strip().split(",")[0] + "," not in cur]
            items.append({"path": runner_path + " (CHANGE_TAGS)", "group": "modules", "file": runner_path,
                          "state": "PATCH" if miss else "SAME", "lines": miss,
                          "detail": "add %d CHANGE_TAGS line(s)" % len(miss) if miss else ""})
    if "permissions" in groups:
        items.append(plan_permissions(target, active))
    if "hooks" in groups:
        hp = subprocess.run(["git", "-C", target, "config", "core.hooksPath"], capture_output=True,
                            text=True).stdout.strip() if is_git(target) else ""
        items.append({"path": "git config core.hooksPath", "group": "hooks",
                      "state": "SAME" if hp == ".githooks" else ("PATCH" if is_git(target) else "SKIP"),
                      "detail": "set to .githooks" + (" (was %s)" % hp if hp else "") if hp != ".githooks" else "",
                      "patch": True})
    if "code_map" in groups and not os.path.exists(os.path.join(target, "docs", "code_map.md")):
        items.append({"path": "docs/code_map.md", "group": "code_map", "state": "GENERATE",
                      "detail": "run tools/dev/code_map.py", "patch": True})
    return items


def plan_permissions(target, active):
    """Adds the kit's allow rules to .claude/settings.json (merged; nothing removed)."""
    want = ALLOW + [r for m in active for r in ALLOW_MODULES.get(m["name"], [])]
    text = read(os.path.join(target, SETTINGS_FILE))
    try:
        data = json.loads(text) if text else {}
        have = data.get("permissions", {}).get("allow", [])
        assert isinstance(data, dict) and isinstance(have, list)
    except (ValueError, AttributeError, AssertionError):
        return {"path": SETTINGS_FILE, "group": "permissions", "state": "SKIP",
                "detail": "not a JSON object with a permissions.allow list; add the rules by hand"}
    missing = [r for r in want if r not in have]
    return {"path": SETTINGS_FILE, "group": "permissions", "state": "PATCH" if missing else "SAME",
            "patch": missing, "detail": "allow %d command(s)" % len(missing) if missing else ""}


def patch_permissions(target, rules):
    path = os.path.join(target, SETTINGS_FILE)
    data = json.loads(read(path) or "{}")
    data.setdefault("permissions", {}).setdefault("allow", []).extend(rules)
    write(path, json.dumps(data, indent=2) + "\n")


def drop_starter_if_not_new(target, answers):
    """Modules marked new_project_only (the starter game) only go into a project that has no
    main scene yet, or that got them from the kit before."""
    info = project_info(target)
    written = saved_state(target).get("files", {})
    for m in kit_modules.active(answers["modules"], answers):
        if m.get("new_project_only") and info["main_scene"] and \
                not any(dst in written for _, dst in kit_modules.files(m, answers)):
            answers["modules"].remove(m["name"])
            print("NOTE: module %s skipped: the project already has a main scene (%s)" % (m["name"],
                                                                                        info["main_scene"]))


def print_plan(items):
    for it in items:
        print("%-9s %-40s %-16s %s" % (it["state"], it["path"], it["group"], it.get("detail", "")))
    differs = [it["path"] for it in items if it["state"] == "DIFFERS"]
    if differs:
        print("\nExisting files that differ (kept unless named in --overwrite): " + ", ".join(differs))
    updates = [it["path"] for it in items if it["state"] == "UPDATE"]
    if updates:
        print("\nUnedited kit files with a newer template (apply replaces them): " + ", ".join(updates))


# --- applying -------------------------------------------------------------------

def write(path, content, executable=False):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    if executable:
        os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _add_to_section(text, name, lines):
    if not lines:
        return text
    if re.search(r"^\[%s\]\s*$" % re.escape(name), text, re.M):
        return re.sub(r"^(\[%s\]\s*\n\n?)" % re.escape(name), lambda m: m.group(1) + lines, text, count=1,
                      flags=re.M)
    block = "[%s]\n\n" % name + lines + "\n"
    m = re.search(r"^\[(?!application\])", text, re.M)
    # Godot keeps sections alphabetical after [application]; any place loads fine.
    return text[:m.start()] + block + text[m.start():] if m else text.rstrip() + "\n\n" + block


def patch_project_godot(target, add, settings=()):
    path = os.path.join(target, "project.godot")
    text = read(path)
    text = _add_to_section(text, "autoload", "".join('%s="*res://%s"\n' % (n, p) for n, p in add))
    for sec in dict.fromkeys(s for s, _, _ in settings):
        text = _add_to_section(text, sec, "".join("%s=%s\n" % (k, v) for s, k, v in settings if s == sec))
    write(path, text)


def patch_lines(target, it):
    """Adds module lines to suites.txt (at the end) or CHANGE_TAGS (top of the list)."""
    path = os.path.join(target, it["file"])
    text = read(path)
    if it["file"].endswith("suites.txt"):
        text = text + ("" if text.endswith("\n") else "\n") + "".join(l + "\n" for l in it["lines"])
    else:
        text = re.sub(r"^(CHANGE_TAGS = \[\n)", lambda m: m.group(1) + "".join(l + "\n" for l in it["lines"]),
                      text, count=1, flags=re.M)
    write(path, text)


_godot_release = []


def installed_godot_release():
    """Release tag of the Godot found like tools/dev/godot_env.sh does ("4.7.2-stable"), else ""."""
    if not _godot_release:
        tag = ""
        godot = doctor.find_godot()
        if godot:
            try:
                out = subprocess.run([godot, "--headless", "--version"], capture_output=True, text=True,
                                     timeout=60).stdout
                m = re.search(r"(\d+\.\d+(?:\.\d+)?)\.([a-z]+\d*)", out)
                tag = "%s-%s" % m.groups() if m else ""
            except (OSError, subprocess.TimeoutExpired):
                pass
        _godot_release.append(tag)
    return _godot_release[0]


def installed_godot_version():
    """Major.minor of the installed Godot, else 4.4."""
    m = re.match(r"\d+\.\d+", installed_godot_release())
    return m.group(0) if m else "4.4"


def create_project(target, answers):
    path = os.path.join(target, "project.godot")
    if os.path.exists(path):
        return False
    feature = kit_frame.project_feature(answers)
    method = {"GL Compatibility": "gl_compatibility", "Mobile": "mobile"}.get(feature)
    write(path, "; Engine configuration file.\n\nconfig_version=5\n\n[application]\n\n"
                'config/name="%s"\nconfig/features=PackedStringArray("%s", "%s")\n'
          % (answers["game_name"], installed_godot_version(), feature) +
          ('\n[rendering]\n\nrenderer/rendering_method="%s"\nrenderer/rendering_method.mobile="%s"\n'
           % (method, method) if method else ""))
    return True


def apply(target, answers, groups, mods, overwrite, overwrite_all):
    items = plan(target, answers, groups, mods)
    done, kept = [], []
    old = saved_state(target)
    written = dict(old.get("files", {}))
    for it in items:
        dst = os.path.join(target, it["path"])
        if it["state"] in ("NEW", "UPDATE") or (it["state"] == "DIFFERS" and (overwrite_all or it["path"] in overwrite)):
            write(dst, it["content"], it["exec"])
            written[it["path"]] = digest(it["content"])
            done.append(("UPDATED" if it["state"] == "UPDATE" else "WROTE", it["path"]))
        elif it["state"] == "SAME" and "content" in it and not it["detail"]:
            written[it["path"]] = digest(it["content"])
        elif it["state"] == "DIFFERS":
            kept.append(it["path"])
        elif it["state"] == "PATCH" and it["path"] in (".gitignore", ".gitattributes"):
            text = read(dst) or ""
            write(dst, text + ("" if not text or text.endswith("\n") else "\n") +
                  "# godot-claude-kit\n" + "\n".join(it["patch"]) + "\n")
            done.append(("PATCHED", it["path"]))
        elif it["state"] == "PATCH" and it["path"] == SETTINGS_FILE:
            patch_permissions(target, it["patch"])
            done.append(("PATCHED", it["path"]))
        elif it["state"] == "PATCH" and it["path"] == "project.godot":
            patch_project_godot(target, it["patch"], it.get("settings", ()))
            done.append(("PATCHED", "project.godot"))
        elif it["state"] == "PATCH" and it.get("lines"):
            patch_lines(target, it)
            done.append(("PATCHED", it["path"]))
        elif it["state"] == "PATCH" and it["path"].startswith("git config"):
            subprocess.run(["git", "-C", target, "config", "core.hooksPath", ".githooks"], check=True)
            done.append(("SET", "core.hooksPath=.githooks"))
    if "code_map" in groups and os.path.exists(os.path.join(target, "tools", "dev", "code_map.py")) \
            and not os.path.exists(os.path.join(target, "docs", "code_map.md")):
        subprocess.run([sys.executable, "-I", os.path.join(target, "tools", "dev", "code_map.py")], cwd=target,
                       capture_output=True)
        done.append(("GENERATED", "docs/code_map.md"))
    # Keep other keys (e.g. "windows" for the window guard) that the user or a tool added.
    saved = dict(old)
    saved.update({"kit_version": KIT_VERSION, "answers": kit_frame.saved(answers), "files": dict(sorted(written.items()))})
    write(os.path.join(target, ANSWERS_FILE), json.dumps(saved, indent=2, ensure_ascii=False) + "\n")
    for what, path in done:
        print("%-9s %s" % (what, path))
    if kept:
        print("KEPT (differs, not overwritten): " + ", ".join(kept))
    if not done:
        print("Nothing to do: everything is already in place.")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["detect", "plan", "apply", "groups", "recommend"])
    ap.add_argument("--target", default=".")
    ap.add_argument("--answers", help="JSON object with answers (merged over saved answers)")
    ap.add_argument("--only", help="comma-separated groups (default: all)")
    ap.add_argument("--overwrite", default="", help="comma-separated paths that may be overwritten")
    ap.add_argument("--overwrite-all", action="store_true")
    ap.add_argument("--create-project", action="store_true", help="write a minimal project.godot if none")
    ap.add_argument("--git-init", action="store_true", help="git init the target if it is not a repo")
    opts = ap.parse_args()
    target = os.path.abspath(opts.target)

    if opts.command == "groups":
        for g, d in GROUPS.items():
            print("%-17s %s" % (g, d))
        print("\nModules (default = recommended; mp = multiplayer only):")
        for m in kit_modules.all_modules():
            tag = ",".join(t for t, on in (("default", m["default"]), ("mp", m["multiplayer"])) if on)
            print("%-17s %-11s %s" % (m["name"], tag, m["summary"]))
        return 0
    if opts.command == "detect":
        info = project_info(target)
        saved = read(os.path.join(target, ANSWERS_FILE))
        info.update({"target": target, "git": is_git(target), "kit_version": KIT_VERSION,
                     "saved_answers": json.loads(saved)["answers"] if saved else None,
                     "saved_kit_version": json.loads(saved).get("kit_version") if saved else None,
                     "modules_available": [m["name"] for m in kit_modules.all_modules()],
                     "existing": [dst for _, dst, _, _ in MANIFEST if os.path.exists(os.path.join(target, dst))],
                     "claude_md_bytes": os.path.getsize(os.path.join(target, "CLAUDE.md"))
                     if os.path.exists(os.path.join(target, "CLAUDE.md")) else 0})
        print(json.dumps(info, indent=1, ensure_ascii=False))
        return 0

    answers = load_answers(target, opts.answers)
    if opts.command == "recommend":
        for name, state, why in kit_frame.recommend(answers):
            print("%-9s %-17s %s" % (state.upper(), name, why))
        return 0
    groups, mods = selected_groups(opts.only, answers)
    drop_starter_if_not_new(target, answers)
    mods = [m for m in mods if m in answers["modules"]]
    if opts.command == "plan":
        if not project_info(target)["has_project"]:
            print("NOTE: no project.godot in %s (apply --create-project writes a minimal one)" % target)
        print("Modules: %s" % (", ".join(answers["modules"]) or "none"))
        print_plan(plan(target, answers, groups, mods))
        return 0
    if opts.create_project and create_project(target, answers):
        print("CREATED  project.godot")
    if not project_info(target)["has_project"]:
        raise SystemExit("no project.godot in %s: run inside a Godot project or pass --create-project" % target)
    if opts.git_init and not is_git(target):
        subprocess.run(["git", "init", "-q", target], check=True)
        print("GIT INIT %s" % target)
    overwrite = {p.strip() for p in opts.overwrite.split(",") if p.strip()}
    return apply(target, answers, groups, mods, overwrite, opts.overwrite_all)


if __name__ == "__main__":
    sys.exit(main())
