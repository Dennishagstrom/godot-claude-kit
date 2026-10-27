"""Optional kit modules for scaffold.py (and analyse_modules.py).

A module lives in templates/modules/<name>/:

    module.json   metadata (see FIELDS below)
    README.md     short doc, installed as docs/modules/<name>.md
    files/...     files copied into the project at the same relative path

module.json fields:
    title           short human name
    summary         one line (shown by `scaffold.py groups` and in the README)
    default         true = on unless the user turns it off (godot-start)
    multiplayer     true = only offered when the game is multiplayer
    suites          lines for tests/integration/suites.txt (rendered like templates)
    change_tags     [[path prefix, [tags]]] for CHANGE_TAGS in tools/test_runner.py
    autoloads       [[Name, path]] registered in project.godot
    settings        {"section": {"key": "raw value"}} added to project.godot when missing
    gitignore       lines added to .gitignore
    claude_md       one rule line for CLAUDE.md ("" = none)
    when            {"relative/file/path": "3D" | "2D" | "multiplayer" | "singleplayer"}
    seed            paths the project owns once written (build number, release notes, tables):
                    never reported as DIFFERS, never overwritten by a re-run
    new_project_only  true = skipped in a project that already has a main scene (the starter game)
"""
import json
import os

KIT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULES_DIR = os.path.join(KIT_ROOT, "templates", "modules")
# Order shown to the user (and the order of lines in generated files).
ORDER = ["starter", "net-testing", "build-release", "ci", "smooth-motion", "window-guard", "perf-tests",
         "blender-pipeline", "data-pipeline", "safe-saves", "l10n-check", "sandbox", "ui-tokens", "steam"]
EXEC_SUFFIXES = (".sh", ".py")


def _load(name):
    with open(os.path.join(MODULES_DIR, name, "module.json"), encoding="utf-8") as f:
        meta = json.load(f)
    meta["name"] = name
    for key, empty in (("suites", []), ("change_tags", []), ("autoloads", []), ("settings", {}),
                       ("gitignore", []), ("claude_md", ""), ("when", {}), ("seed", []), ("default", False),
                       ("multiplayer", False), ("new_project_only", False)):
        meta.setdefault(key, empty)
    return meta


def all_modules():
    names = [n for n in ORDER if os.path.isfile(os.path.join(MODULES_DIR, n, "module.json"))]
    extra = sorted(n for n in os.listdir(MODULES_DIR) if n not in names and
                   os.path.isfile(os.path.join(MODULES_DIR, n, "module.json"))) if os.path.isdir(MODULES_DIR) else []
    return [_load(n) for n in names + extra]


def by_name():
    return {m["name"]: m for m in all_modules()}


def default_names(multiplayer):
    return [m["name"] for m in all_modules() if m["default"] and (multiplayer or not m["multiplayer"])]


def active(names, answers):
    """Module metadata for `names`, in kit order, dropping multiplayer-only ones in single player."""
    known = by_name()
    bad = [n for n in names if n not in known]
    if bad:
        raise SystemExit("unknown modules: %s (see: scaffold.py groups)" % ", ".join(bad))
    wanted = set(names)
    return [m for m in all_modules() if m["name"] in wanted and (answers["multiplayer"] or not m["multiplayer"])]


def _condition_ok(cond, answers):
    is_3d = answers["dimension"].upper() == "3D"
    return {None: True, "3D": is_3d, "2D": not is_3d, "multiplayer": answers["multiplayer"],
            "singleplayer": not answers["multiplayer"]}.get(cond, True)


def files(module, answers):
    """[(source path, project-relative target)] for one module."""
    out = []
    readme = os.path.join(MODULES_DIR, module["name"], "README.md")
    if os.path.isfile(readme):
        out.append((readme, "docs/modules/%s.md" % module["name"]))
    root = os.path.join(MODULES_DIR, module["name"], "files")
    for base, dirs, names in os.walk(root):
        dirs.sort()
        for n in sorted(names):
            if n in (".DS_Store",) or n.endswith(".pyc"):
                continue
            src = os.path.join(base, n)
            rel = os.path.relpath(src, root).replace(os.sep, "/")
            if _condition_ok(module["when"].get(rel), answers):
                out.append((src, rel))
    return out


def is_exec(path):
    return path.endswith(EXEC_SUFFIXES)


def suite_lines(mods, render_line):
    lines = []
    for m in mods:
        for line in m["suites"]:
            text = render_line(line).strip()
            if text:
                lines.append(text)
    return lines


def change_tag_lines(mods):
    return ['    ("%s", %s),' % (prefix, json.dumps(tags)) for m in mods for prefix, tags in m["change_tags"]]


def flag_name(name):
    return "MOD_" + name.upper().replace("-", "_")
