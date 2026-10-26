"""Kit module detection for analyse.py: which optional modules (templates/modules/)
a project already has an equivalent of, and which ones are worth adding.

Each check returns (installed, evidence) from cheap file-name and text signals;
`recommend()` turns that plus project signals into (impact, effort, reason) or None.
"""
import json
import os
import re

UI_HINT = re.compile(r"(^|/)(ui|hud|menu|menus)/")
TOKENS_FILE = re.compile(r"(ui_?tokens|design_tokens|theme_tokens)\.gd$")


def _any(texts, pattern):
    rx = re.compile(pattern, re.M)
    return next((f for f, t in texts.items() if rx.search(t)), None)


def _count(texts, pattern, only=None):
    rx = re.compile(pattern, re.M)
    return sum(len(rx.findall(t)) for f, t in texts.items() if only is None or only(f))


def signals(target, files, read):
    """Reads what the checks need once (scripts, tests, tools, project.godot)."""
    gd = {f: read(target, f) for f in files if f.endswith(".gd")}
    game = {f: t for f, t in gd.items() if not f.startswith(("tests/", "test/", "addons/", "tools/"))}
    tests = {f: t for f, t in gd.items() if f.startswith(("tests/", "test/"))}
    shell = {f: read(target, f) for f in files if f.endswith((".sh", ".py")) and not f.startswith("addons/")}
    kit = {}
    try:
        kit = json.loads(read(target, ".claude/godot-kit.json") or "{}")
    except ValueError:
        pass
    return {
        "files": files, "game": game, "tests": tests, "shell": shell, "all_gd": gd,
        "project": read(target, "project.godot"),
        "kit_modules": set((kit.get("answers") or {}).get("modules") or []),
        "multiplayer": bool(_any(game, r"^[^#\n]*(MultiplayerSynchronizer|ENetMultiplayerPeer|@rpc\b)")),
        "bodies": _count(game, r"extends\s+(CharacterBody|RigidBody)[23]D"),
        "tres_in_data": sum(1 for f in files if f.startswith("data/") and f.endswith(".tres")),
        "csv": [f for f in files if f.endswith(".csv") and not f.startswith("addons/")],
        "glb": sum(1 for f in files if f.endswith((".glb", ".gltf", ".blend"))),
        "ui_colors": _count(game, r"\bColor8?\s*\(|\"#[0-9a-fA-F]{6}\"", lambda f: bool(UI_HINT.search(f)) and not TOKENS_FILE.search(f)),
        "user_writes": _any(game, r"(FileAccess\.open\(\s*\"user://[^\"]*\"\s*,\s*FileAccess\.WRITE|\.save\(\s*\"user://)"),
    }


def detect(s):
    """module name -> (installed, evidence)."""
    f, game, tests, shell = s["files"], s["game"], s["tests"], s["shell"]
    def has(path_prefix):
        return next((x for x in f if x.startswith(path_prefix)), None)
    out = {}
    lag = has("tools/lag_proxy.py") or _any(shell, r"lag_proxy|--rtt")
    two = _any(tests, r"join_game|create_client|--join")
    out["net-testing"] = (bool(lag and two), "lag proxy: %s, two-process tests: %s" % (lag or "none", two or "none"))
    build = _any(shell, r"--export-(release|debug)")
    notes = has("data/patch_notes/") or has("tools/patch_notes.py")
    out["build-release"] = (bool(build and notes),
                            "export script: %s, patch notes: %s" % (build or "none", "yes" if notes else "none"))
    smooth = _any(game, r"get_physics_interpolation_fraction") or \
        ("physics_interpolation=true" in s["project"] and "physics_interpolation" or None)
    out["smooth-motion"] = (bool(smooth), "interpolation: %s" % (smooth or "none"))
    out["window-guard"] = ("window-guard" in s["kit_modules"],
                           "kit hook enabled" if "window-guard" in s["kit_modules"] else "no window guard")
    perf = _any(tests, r"Performance\.get_monitor|TIME_PHYSICS_PROCESS")
    out["perf-tests"] = (bool(perf), "perf test: %s" % (perf or "none"))
    blender = has("tools/blender/") or _any(shell, r"^import bpy")
    out["blender-pipeline"] = (bool(blender), "Blender scripts: %s" % (blender or "none"))
    builder = _any(s["all_gd"], r"get_csv_line") or _any(shell, r"\.csv\b")
    out["data-pipeline"] = (bool(s["csv"] and builder), "CSV tables: %d, builder: %s" % (len(s["csv"]), builder or "none"))
    save_arg = _any(game, r"--save=")
    out["safe-saves"] = (bool(save_arg), "--save= handling: %s" % (save_arg or "none"))
    l10n = next((t for t in tests if "l10n" in t or "i18n" in t), None) or _any(tests, r"TranslationServer")
    out["l10n-check"] = (bool(l10n), "l10n test: %s" % (l10n or "none"))
    sandbox = _any(game, r"--sandbox")
    out["sandbox"] = (bool(sandbox), "sandbox flag: %s" % (sandbox or "none"))
    tokens = next((x for x in f if TOKENS_FILE.search(x)), None)
    out["ui-tokens"] = (bool(tokens), "tokens: %s; hardcoded UI colours: %d" % (tokens or "none", s["ui_colors"]))
    steam = has("addons/godotsteam") or _any(game, r"SteamMultiplayerPeer|get_singleton\(\s*\"Steam\"|\bSteam\.steamInit")
    out["steam"] = (bool(steam), "GodotSteam: %s" % (steam or "none"))
    return out


def recommend(name, installed, s, n_scripts):
    """(impact 1-3, effort 1-3, reason) or None."""
    if installed:
        return None
    mp = s["multiplayer"]
    if name == "net-testing" and mp:
        return 3, 1, "netcode bugs (validation, late joiners, timing) only show with two processes and real latency"
    if name == "build-release":
        return 2, 1, "one command for export + build number + zip + smoke test; patch notes without merge conflicts" + \
            ("; version check on join stops mismatched builds" if mp else "")
    if name == "smooth-motion" and s["bodies"]:
        return 2, 1, "%d physics body scripts move at 60 Hz; visuals judder on 120-240 Hz screens%s" % (
            s["bodies"], " and synced clients step" if mp else "")
    if name == "window-guard":
        return 2, 1, "agents can't steal your screen with Godot/Blender windows while you work"
    if name == "perf-tests" and n_scripts >= 20:
        return 2, 1, "a perf budget suite catches slow hot paths in the round that adds them"
    if name == "blender-pipeline" and s["glb"] >= 10:
        return 1, 2, "%d model files; models as Python let Claude make and change props headless" % s["glb"]
    if name == "data-pipeline" and s["tres_in_data"] >= 30 and not s["csv"]:
        return 2, 2, "%d .tres files in data/: one CSV per kind is easier to edit, diff and validate" % s["tres_in_data"]
    if name == "safe-saves" and s["user_writes"]:
        return 3, 1, "the game writes user:// (%s) but tests can't pick a save slot: tests may overwrite real saves" % (
            s["user_writes"])
    if name == "l10n-check":
        return 1, 1, "a 1-second suite that keeps formatted UI text going through tr()"
    if name == "sandbox" and n_scripts >= 30:
        return 1, 2, "a --sandbox arena with an F1 panel makes feel/balance work fast and safe"
    if name == "ui-tokens" and s["ui_colors"] >= 10:
        return 2, 2, "%d hardcoded colours in UI scripts: tokens + components keep many agents' UI consistent" % (
            s["ui_colors"])
    if name == "steam" and mp:
        return 1, 2, "Steam lobbies and overlay invites instead of IP addresses (ENet stays as fallback)"
    return None


def report_section(target, files, read, n_scripts, actions, findings):
    """Report lines for "10. Kit modules"; appends recommended modules to `actions`."""
    sig = signals(target, files, read)
    mods = detect(sig)
    lines = ["## 10. Kit modules", "",
             "Optional godot-claude-kit modules (`scaffold.py groups`). *Have* = the project already has this or an "
             "equivalent; recommended ones are in the action list as `Kit: module <name>`.", "",
             "| Module | Status | Evidence / why |", "|---|---|---|"]
    recommended = []
    for name, (have, evidence) in mods.items():
        rec = recommend(name, have, sig, n_scripts)
        lines.append("| %s | %s | %s |" % (name, "have" if have else ("recommended" if rec else "optional"),
                                          rec[2] if rec else evidence))
        if rec:
            recommended.append(name)
            actions.append((rec[0], rec[1], "Add kit module %s" % name, rec[2],
                            "Kit: module `%s` (`scaffold.py apply --only %s`, adapted)." % (name, name)))
    findings["modules"] = {n: h for n, (h, _) in mods.items()}
    findings["modules_recommended"] = recommended
    return lines + [""]
