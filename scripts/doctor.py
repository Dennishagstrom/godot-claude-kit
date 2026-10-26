#!/usr/bin/env python3
"""godot-claude-kit doctor: checks that this machine has what the kit needs and
says what is missing and how to fix it. Read-only; takes about a second.

    bash scripts/py.sh scripts/doctor.py [--target DIR] [--modules a,b] [--json]

Required: Python 3.8+, git, bash (Git Bash on Windows), Godot 4. Per module (the
project's saved modules, --modules, or all of them when neither is known):
perl, export templates, Blender, GodotSteam. Exit code 1 = something required is missing.
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys

WINDOWS = os.name == "nt"
HOME = os.path.expanduser("~")
results = []  # (level, name, detail, fix); level: ok / missing / warn / info


def add(level, name, detail, fix=""):
    results.append({"level": level, "name": name, "detail": detail, "fix": fix})


def run(args, timeout=30):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout + p.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return -1, str(e)


def find_godot():
    """Same places as tools/dev/godot_env.sh and tools/test_runner.py."""
    if os.environ.get("GODOT"):
        return os.environ["GODOT"]
    for name in ("godot4", "godot", "Godot"):
        if shutil.which(name):
            return shutil.which(name)
    for path in ("/Applications/Godot.app/Contents/MacOS/Godot", "/Applications/Godot_mono.app/Contents/MacOS/Godot",
                 os.path.join(HOME, "Applications/Godot.app/Contents/MacOS/Godot"), "/usr/local/bin/godot",
                 "/usr/bin/godot"):
        if os.path.exists(path):
            return path
    if WINDOWS:
        local = os.environ.get("LOCALAPPDATA", HOME)
        roots = [os.path.join(os.environ.get("PROGRAMFILES", r"C:\Program Files"), "Godot"),
                 os.path.join(local, "Programs", "Godot"), os.path.join(local, "Microsoft", "WinGet", "Packages"),
                 os.path.join(HOME, "scoop", "apps", "godot", "current"), os.path.join(HOME, "Godot"),
                 os.path.join(HOME, "Desktop"), os.path.join(HOME, "Downloads"), r"C:\Godot"]
        for pattern in ("[Gg]odot*console.exe", "[Gg]odot*.exe"):
            for root in roots:
                hits = sorted(glob.glob(os.path.join(root, "**", pattern), recursive=True), reverse=True)
                if hits:
                    return hits[0]
    return ""


def find_bash():
    path = shutil.which("bash")
    if not WINDOWS:
        return path or ""
    if path and "system32" not in path.lower() and "windowsapps" not in path.lower():
        return path
    for root in (os.environ.get("PROGRAMFILES", r"C:\Program Files"), os.environ.get("LOCALAPPDATA", "")):
        for rel in (r"Git\bin\bash.exe", r"Programs\Git\bin\bash.exe"):
            if root and os.path.exists(os.path.join(root, rel)):
                return os.path.join(root, rel)
    return ""


def find_blender():
    if os.environ.get("BLENDER"):
        return os.environ["BLENDER"]
    if shutil.which("blender"):
        return shutil.which("blender")
    paths = ["/Applications/Blender.app/Contents/MacOS/Blender",
             os.path.join(HOME, "Applications/Blender.app/Contents/MacOS/Blender"), "/usr/bin/blender",
             "/snap/bin/blender"]
    if WINDOWS:
        paths += sorted(glob.glob(os.path.join(os.environ.get("PROGRAMFILES", r"C:\Program Files"),
                                               "Blender Foundation", "*", "blender.exe")), reverse=True)
    return next((p for p in paths if os.path.exists(p)), "")


def project_modules(target, given):
    if given is not None:
        return [m.strip() for m in given.split(",") if m.strip()], "--modules"
    try:
        saved = json.load(open(os.path.join(target, ".claude", "godot-kit.json"), encoding="utf-8"))
        return saved.get("answers", {}).get("modules") or [], ".claude/godot-kit.json"
    except (OSError, ValueError):
        return None, ""


def check(target, modules):
    v = sys.version_info
    add("ok" if v >= (3, 8) else "missing", "Python", "%d.%d.%d (%s)" % (v[0], v[1], v[2], sys.executable),
        "" if v >= (3, 8) else "install Python 3.8 or newer: https://www.python.org/downloads/")
    if WINDOWS:
        p3 = shutil.which("python3") or ""
        if not p3 or "windowsapps" in p3.lower():
            add("info", "python3 command", "missing or the Microsoft Store alias; the kit uses python/py instead")

    code, out = run(["git", "--version"])
    if code != 0:
        add("missing", "git", "not found", "install git: https://git-scm.com/downloads")
    else:
        name = run(["git", "config", "user.name"])[1]
        email = run(["git", "config", "user.email"])[1]
        add("ok", "git", out.replace("git version ", ""))
        if not name or not email:
            add("warn", "git identity", "user.name/user.email not set: commits (and the round workflow) fail",
                'git config --global user.name "Your Name" && git config --global user.email you@example.com')
        if WINDOWS and run(["git", "config", "core.autocrlf"])[1] == "true":
            add("info", "git core.autocrlf", "true; fine, kit projects keep shell scripts on LF via .gitattributes")

    bash = find_bash()
    if bash:
        add("ok", "bash", bash)
    else:
        add("missing", "bash", "Git Bash not found" if WINDOWS else "not found",
            "install Git for Windows (includes Git Bash): https://git-scm.com/download/win" if WINDOWS
            else "install bash with your package manager")

    godot = find_godot()
    godot_version = ""
    if not godot:
        add("missing", "Godot", "not found",
            "install Godot 4 (https://godotengine.org/download) or set GODOT=/path/to/godot" +
            (" (the *_console.exe)" if WINDOWS else ""))
    else:
        code, out = run([godot, "--headless", "--version"], timeout=60)
        m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?\.(\w+)", out)
        if code != 0 or not m:
            add("missing", "Godot", "%s does not run (%s)" % (godot, out[-200:]),
                "set GODOT to a working Godot 4 binary")
        elif m.group(1) != "4":
            add("missing", "Godot", "%s is Godot %s, the kit needs Godot 4" % (godot, m.group(0)),
                "install Godot 4 and set GODOT to it")
        else:
            godot_version = "%s.%s%s.%s" % (m.group(1), m.group(2), "." + m.group(3) if m.group(3) else "",
                                            m.group(4))
            add("ok", "Godot", "%s (%s)" % (godot_version, godot))
            if WINDOWS and not godot.lower().endswith("console.exe"):
                add("warn", "Godot console", "the plain .exe prints nothing to Claude; use the *_console.exe",
                    "set GODOT to the Godot_*_console.exe next to it")

    if target and not os.path.exists(os.path.join(target, "project.godot")):
        add("info", "project.godot", "none in %s; godot-start can create a minimal one" % target)

    known = modules is not None
    mods = set(modules or [])

    # Unknown modules (no project yet): optional tools are info, not warnings.
    optional = "warn" if known else "info"

    def wanted(*names):
        return not known or bool(mods & set(names))

    if wanted("net-testing", "build-release"):
        users = ", ".join(n for n in ("net-testing", "build-release") if not known or n in mods)
        if run([bash or "bash", "-c", "perl -e 1"])[0] == 0:
            add("ok", "perl", "found (timeouts in %s scripts)" % users)
        else:
            add(optional, "perl", "not found; needed by %s" % users,
                "Git Bash includes perl; elsewhere install perl with your package manager")
    if wanted("build-release") and godot_version:
        dirs = [os.path.join(HOME, "Library", "Application Support", "Godot", "export_templates"),
                os.path.join(HOME, ".local", "share", "godot", "export_templates"),
                os.path.join(os.environ.get("APPDATA", os.path.join(HOME, "AppData", "Roaming")), "Godot",
                             "export_templates")]
        have = {f: any(os.path.exists(os.path.join(d, godot_version, f)) for d in dirs)
                for f in ("windows_release_x86_64.exe", "macos.zip", "linux_release.x86_64")}
        if any(have.values()):
            add("ok" if have["windows_release_x86_64.exe"] else "warn", "export templates",
                "%s: %s" % (godot_version, ", ".join("%s %s" % (f, "yes" if ok else "no") for f, ok in have.items())),
                "" if have["windows_release_x86_64.exe"] else "Godot editor > Editor > Manage Export Templates")
        else:
            add(optional, "export templates", "none for %s (needed by build-release to export)" %
                godot_version, "Godot editor > Editor > Manage Export Templates > Download and Install")
    if wanted("blender-pipeline"):
        blender = find_blender()
        if blender:
            add("ok", "Blender", blender)
        else:
            add(optional, "Blender", "not found (blender-pipeline builds models with it; its "
                "test passes as skipped)", "install Blender (https://www.blender.org) or set BLENDER=/path/to/blender")
    if wanted("steam"):
        steam = target and (glob.glob(os.path.join(target, "addons", "godotsteam*")) or
                            glob.glob(os.path.join(target, "addons", "*", "*steam*.gdextension")))
        if steam:
            add("ok", "GodotSteam", os.path.relpath(steam[0], target))
        else:
            add("info", "GodotSteam", "not in addons/ (the steam module falls back to ENet without it)",
                "Godot AssetLib: GodotSteam GDExtension, when you want real Steam lobbies")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", default=".")
    ap.add_argument("--modules", help="comma-separated modules to check for (default: the project's saved ones)")
    ap.add_argument("--json", action="store_true")
    opts = ap.parse_args()
    target = os.path.abspath(opts.target)
    modules, source = project_modules(target, opts.modules)
    check(target, modules)
    missing = [r for r in results if r["level"] == "missing"]
    if opts.json:
        print(json.dumps({"ok": not missing, "modules_from": source, "checks": results}, indent=1))
        return 1 if missing else 0
    print("godot-claude-kit doctor (%s)" % ("modules from " + source if source else "all modules"))
    tags = {"ok": "ok  ", "missing": "MISS", "warn": "warn", "info": "info"}
    for r in results:
        print("  %s %-17s %s" % (tags[r["level"]], r["name"], r["detail"]))
        if r["fix"] and r["level"] != "ok":
            print("       %-17s fix: %s" % ("", r["fix"]))
    warns = sum(r["level"] == "warn" for r in results)
    print("RESULT %s: %d missing, %d warnings" % ("FAIL" if missing else "PASS", len(missing), warns))
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
