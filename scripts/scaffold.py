#!/usr/bin/env python3
"""godot-claude-kit scaffolder: renders the kit's templates into a Godot project.

Never overwrites a file that differs unless it is named with --overwrite (or
--overwrite-all). Files that are already identical are skipped, so running it
twice is safe (idempotent). Answers are saved in <target>/.claude/godot-kit.json
and reused on the next run.

    python3 -I scaffold.py detect --target DIR
    python3 -I scaffold.py plan   --target DIR --answers '{"game_name": "X", ...}' [--only tests,hooks]
    python3 -I scaffold.py apply  --target DIR [--answers ...] [--only ...] [--overwrite CLAUDE.md,docs/status.md]
                                  [--overwrite-all] [--create-project] [--git-init]
    python3 -I scaffold.py groups

Answer keys: game_name, dimension ("2D"/"3D"), multiplayer (bool), max_players (int),
genre (one line), text_language (e.g. "English"), default_port (int, default 7777).
"""
import argparse
import json
import os
import re
import stat
import subprocess
import sys

KIT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TPL = os.path.join(KIT_ROOT, "templates", "project")
KIT_VERSION = json.load(open(os.path.join(KIT_ROOT, ".claude-plugin", "plugin.json"))).get("version", "0")
ANSWERS_FILE = ".claude/godot-kit.json"

GROUPS = {
    "core": "Godot path helper, .gitignore lines, saved answers (always included)",
    "claude_md": "Lean CLAUDE.md (< 5 KB) with rules and 'where to look' pointers",
    "docs": "docs/dev_reference.md, status.md, dev_workflow.md, rounds/",
    "code_map": "tools/dev/code_map.py + generated docs/code_map.md",
    "tests": "tools/test_runner.py (parallel), tests/ skeleton, smoke suite (+ host/client net test)",
    "worktrees": "tools/dev/new_worktree.sh / finish_worktree.sh, .claude/.gdignore",
    "hooks": ".githooks/pre-commit (parse check + code map) and core.hooksPath",
    "agents": ".claude/agents implementer + reviewer, .claude/skills/round",
    "autoloads": "autoload/events.gd (+ autoload/network.gd if multiplayer), registered in project.godot",
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
    ("templates/project/tools/dev/new_worktree.sh", "tools/dev/new_worktree.sh", "worktrees", None),
    ("templates/project/tools/dev/finish_worktree.sh", "tools/dev/finish_worktree.sh", "worktrees", None),
    ("templates/project/.claude/.gdignore", ".claude/.gdignore", "worktrees", None),
    ("templates/project/.githooks/pre-commit", ".githooks/pre-commit", "hooks", None),
    ("agents/implementer.md", ".claude/agents/implementer.md", "agents", None),
    ("agents/reviewer.md", ".claude/agents/reviewer.md", "agents", None),
    ("skills/round/SKILL.md", ".claude/skills/round/SKILL.md", "agents", None),
    ("templates/project/autoload/events.gd", "autoload/events.gd", "autoloads", None),
    ("templates/project/autoload/network.gd", "autoload/network.gd", "autoloads", "multiplayer"),
]
# Scripts the other groups depend on (the hook needs the code map, etc.).
DEPENDS = {"hooks": ["code_map", "tests"]}
GITIGNORE_LINES = [".godot/", ".claude/worktrees/", ".claude/settings.local.json"]
DEFAULTS = {"game_name": "", "dimension": "3D", "multiplayer": False, "max_players": 4,
            "genre": "A game", "text_language": "English", "default_port": 7777}


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
    return {"has_project": bool(text), "name": name.group(1) if name else os.path.basename(target),
            "godot_version": version, "autoloads": autoloads,
            "dimension_guess": "2D" if "gl_compatibility" in text.lower() and "3d" not in text.lower() else "3D"}


def section(text, name):
    m = re.search(r"^\[%s\]\s*$(.*?)(?=^\[|\Z)" % re.escape(name), text, re.M | re.S)
    return m.group(1) if m else ""


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
    return answers


# --- rendering ------------------------------------------------------------------

def render(text, answers, info):
    flags = {"MULTIPLAYER": answers["multiplayer"], "3D": answers["dimension"].upper() == "3D"}
    for key, on in flags.items():
        text = re.sub(r"\{\{#%s\}\}(.*?)\{\{/%s\}\}" % (key, key), lambda m: m.group(1) if on else "", text, flags=re.S)
        text = re.sub(r"\{\{\^%s\}\}(.*?)\{\{/%s\}\}" % (key, key), lambda m: "" if on else m.group(1), text, flags=re.S)
    values = {
        "GAME_NAME": answers["game_name"], "DIMENSION": answers["dimension"],
        "MAX_PLAYERS": str(answers["max_players"]), "GENRE": answers["genre"].strip().rstrip("."),
        "TEXT_LANGUAGE": answers["text_language"], "DEFAULT_PORT": str(answers["default_port"]),
        "GODOT_VERSION": info["godot_version"],
    }
    for key, val in values.items():
        text = text.replace("{{%s}}" % key, val)
    left = re.findall(r"\{\{[#^/]?[A-Z_0-9]+\}\}", text)
    if left:
        raise SystemExit("template has unknown placeholders: %s" % ", ".join(sorted(set(left))))
    return text


def selected_groups(only):
    if not only:
        return set(GROUPS)
    groups = {"core"} | set(only.split(","))
    for g in list(groups):
        groups |= set(DEPENDS.get(g, []))
    bad = groups - set(GROUPS)
    if bad:
        raise SystemExit("unknown groups: %s (see: scaffold.py groups)" % ", ".join(sorted(bad)))
    return groups


def plan(target, answers, groups):
    info = project_info(target)
    items = []
    for src, dst, group, cond in MANIFEST:
        if group not in groups or (cond == "multiplayer" and not answers["multiplayer"]):
            continue
        content = render(read(os.path.join(KIT_ROOT, src)), answers, info)
        current = read(os.path.join(target, dst))
        state = "NEW" if current is None else ("SAME" if current == content else "DIFFERS")
        items.append({"path": dst, "group": group, "state": state, "content": content,
                      "exec": src.endswith((".sh", "pre-commit"))})
    # Patches to existing files: only adds missing lines.
    gi = read(os.path.join(target, ".gitignore")) or ""
    missing = [l for l in GITIGNORE_LINES if l not in gi.splitlines()]
    items.append({"path": ".gitignore", "group": "core", "state": "PATCH" if missing else "SAME",
                  "patch": missing, "detail": "add " + ", ".join(missing) if missing else ""})
    if "autoloads" in groups:
        want = [("Events", "autoload/events.gd")]
        if answers["multiplayer"]:
            want.insert(0, ("Network", "autoload/network.gd"))
        have = {n for n, _ in info["autoloads"]}
        add = [(n, p) for n, p in want if n not in have]
        items.append({"path": "project.godot", "group": "autoloads", "state": "PATCH" if add else "SAME",
                      "patch": add, "detail": "register autoload " + ", ".join(n for n, _ in add) if add else ""})
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


def print_plan(items):
    for it in items:
        print("%-9s %-34s %-10s %s" % (it["state"], it["path"], it["group"], it.get("detail", "")))
    differs = [it["path"] for it in items if it["state"] == "DIFFERS"]
    if differs:
        print("\nExisting files that differ (kept unless named in --overwrite): " + ", ".join(differs))


# --- applying -------------------------------------------------------------------

def write(path, content, executable=False):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    if executable:
        os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def patch_project_godot(target, add):
    path = os.path.join(target, "project.godot")
    text = read(path)
    lines = "".join('%s="*res://%s"\n' % (n, p) for n, p in add)
    if re.search(r"^\[autoload\]\s*$", text, re.M):
        text = re.sub(r"^(\[autoload\]\s*\n\n?)", lambda m: m.group(1) + lines, text, count=1, flags=re.M)
    else:
        block = "[autoload]\n\n" + lines + "\n"
        m = re.search(r"^\[(?!application\])", text, re.M)
        # Godot keeps sections alphabetical after [application]; any place loads fine.
        text = text[:m.start()] + block + text[m.start():] if m else text.rstrip() + "\n\n" + block
    write(path, text)


def installed_godot_version():
    """Major.minor of the Godot found like tools/dev/godot_env.sh does, else 4.4."""
    godot = os.environ.get("GODOT") or next((p for p in (
        "/Applications/Godot.app/Contents/MacOS/Godot", "/usr/local/bin/godot", "/usr/bin/godot")
        if os.path.exists(p)), None)
    if not godot:
        import shutil
        godot = shutil.which("godot4") or shutil.which("godot")
    if godot:
        try:
            out = subprocess.run([godot, "--version"], capture_output=True, text=True, timeout=30).stdout
            m = re.match(r"(\d+\.\d+)", out.strip())
            if m:
                return m.group(1)
        except (OSError, subprocess.TimeoutExpired):
            pass
    return "4.4"


def create_project(target, answers):
    path = os.path.join(target, "project.godot")
    if os.path.exists(path):
        return False
    renderer = "Forward Plus" if answers["dimension"].upper() == "3D" else "GL Compatibility"
    write(path, "; Engine configuration file.\n\nconfig_version=5\n\n[application]\n\n"
                'config/name="%s"\nconfig/features=PackedStringArray("%s", "%s")\n'
          % (answers["game_name"], installed_godot_version(), renderer))
    return True


def apply(target, answers, groups, overwrite, overwrite_all):
    items = plan(target, answers, groups)
    done, kept = [], []
    for it in items:
        dst = os.path.join(target, it["path"])
        if it["state"] == "NEW" or (it["state"] == "DIFFERS" and (overwrite_all or it["path"] in overwrite)):
            write(dst, it["content"], it["exec"])
            done.append(("WROTE", it["path"]))
        elif it["state"] == "DIFFERS":
            kept.append(it["path"])
        elif it["state"] == "PATCH" and it["path"] == ".gitignore":
            old = read(dst) or ""
            write(dst, old + ("" if not old or old.endswith("\n") else "\n") +
                  "# godot-claude-kit\n" + "\n".join(it["patch"]) + "\n")
            done.append(("PATCHED", ".gitignore"))
        elif it["state"] == "PATCH" and it["path"] == "project.godot":
            patch_project_godot(target, it["patch"])
            done.append(("PATCHED", "project.godot"))
        elif it["state"] == "PATCH" and it["path"].startswith("git config"):
            subprocess.run(["git", "-C", target, "config", "core.hooksPath", ".githooks"], check=True)
            done.append(("SET", "core.hooksPath=.githooks"))
    if "code_map" in groups and os.path.exists(os.path.join(target, "tools", "dev", "code_map.py")) \
            and not os.path.exists(os.path.join(target, "docs", "code_map.md")):
        subprocess.run([sys.executable, "-I", os.path.join(target, "tools", "dev", "code_map.py")], cwd=target,
                       capture_output=True)
        done.append(("GENERATED", "docs/code_map.md"))
    saved = {"kit_version": KIT_VERSION, "answers": answers}
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
    ap.add_argument("command", choices=["detect", "plan", "apply", "groups"])
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
            print("%-10s %s" % (g, d))
        return 0
    if opts.command == "detect":
        info = project_info(target)
        saved = read(os.path.join(target, ANSWERS_FILE))
        info.update({"target": target, "git": is_git(target), "kit_version": KIT_VERSION,
                     "saved_answers": json.loads(saved)["answers"] if saved else None,
                     "existing": [dst for _, dst, _, _ in MANIFEST if os.path.exists(os.path.join(target, dst))],
                     "claude_md_bytes": os.path.getsize(os.path.join(target, "CLAUDE.md"))
                     if os.path.exists(os.path.join(target, "CLAUDE.md")) else 0})
        print(json.dumps(info, indent=1, ensure_ascii=False))
        return 0

    answers = load_answers(target, opts.answers)
    groups = selected_groups(opts.only)
    if opts.command == "plan":
        if not project_info(target)["has_project"]:
            print("NOTE: no project.godot in %s (apply --create-project writes a minimal one)" % target)
        print_plan(plan(target, answers, groups))
        return 0
    if opts.create_project and create_project(target, answers):
        print("CREATED  project.godot")
    if not project_info(target)["has_project"]:
        raise SystemExit("no project.godot in %s: run inside a Godot project or pass --create-project" % target)
    if opts.git_init and not is_git(target):
        subprocess.run(["git", "init", "-q", target], check=True)
        print("GIT INIT %s" % target)
    overwrite = {p.strip() for p in opts.overwrite.split(",") if p.strip()}
    return apply(target, answers, groups, overwrite, opts.overwrite_all)


if __name__ == "__main__":
    sys.exit(main())
