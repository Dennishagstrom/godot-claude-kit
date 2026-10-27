#!/usr/bin/env python3
"""End-to-end test of the kit: scaffolds throwaway projects outside the repo,
runs their own suites headless, checks idempotency, the upgrade path, the
analyser and the doctor. This is the "test before every push" checklist as one command.

    python3 -I tests/test_scaffold.py              # both projects, with Godot suites
    python3 -I tests/test_scaffold.py --no-godot   # skip the Godot suites (no Godot installed)
    python3 -I tests/test_scaffold.py --keep       # keep the projects (path is printed)

Projects: multiplayer 3D with every module, single-player 2D with the defaults, and an
existing project (own main scene, Godot's .editorconfig, own .claude/settings.json).
Godot: $GODOT or the usual install paths (tools/dev/godot_env.sh finds it).
Exit code 0 = all checks passed.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

KIT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCAFFOLD = os.path.join(KIT, "scripts", "scaffold.py")
ANALYSE = os.path.join(KIT, "scripts", "analyse.py")
DOCTOR = os.path.join(KIT, "scripts", "doctor.py")
ALL_MODULES = sorted(os.listdir(os.path.join(KIT, "templates", "modules")))
PROJECTS = {
    "mp3d": {"game_name": "Kit Test MP", "dimension": "3D", "multiplayer": True, "max_players": 4,
             "genre": "Throwaway co-op test", "modules": ALL_MODULES},
    "sp2d": {"game_name": "Kit Test SP", "dimension": "2D", "multiplayer": False, "genre": "Throwaway 2D test"},
}
failures = []


def check(ok, what, detail=""):
    print("%s %s%s" % ("ok  " if ok else "FAIL", what, (": " + detail) if detail and not ok else ""))
    if not ok:
        failures.append(what)
    return ok


def run(args, cwd=None, timeout=900, env=None):
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                       env=dict(os.environ, **env) if env else None)
    return p.returncode, p.stdout + p.stderr


def scaffold(cmd, target, *extra):
    return run([sys.executable, "-I", SCAFFOLD, cmd, "--target", target, *extra])


def plan_rows(target):
    code, out = scaffold("plan", target)
    rows = [l.split(None, 2) for l in out.splitlines() if l and l.split()[0].isupper() and not l.startswith("NOTE")]
    return code, out, [(r[0], r[1]) for r in rows if len(r) > 1]


def godot_found():
    if os.environ.get("GODOT"):
        return os.path.exists(os.environ["GODOT"]) or shutil.which(os.environ["GODOT"])
    return any(os.path.exists(p) for p in ("/Applications/Godot.app/Contents/MacOS/Godot", "/usr/local/bin/godot",
                                           "/usr/bin/godot")) or shutil.which("godot4") or shutil.which("godot")


def test_project(root, name, answers, with_godot):
    target = os.path.join(root, name)
    os.makedirs(target)
    code, out = scaffold("apply", target, "--answers", json.dumps(answers), "--create-project", "--git-init")
    check(code == 0, "%s: scaffold apply" % name, out[-800:])
    code, out, rows = plan_rows(target)
    not_same = [r for r in rows if r[0] != "SAME"]
    check(code == 0 and rows and not not_same, "%s: second run is all SAME" % name, str(not_same or out[-800:]))
    size = os.path.getsize(os.path.join(target, "CLAUDE.md"))
    check(size < 5000, "%s: CLAUDE.md < 5 KB (%d bytes)" % (name, size))
    if with_godot:
        code, out = run([sys.executable, "-I", "tools/test_runner.py"], cwd=target, timeout=1800)
        check(code == 0, "%s: project suites pass headless" % name, out[-1500:])
    code, out = run([sys.executable, "-I", ANALYSE, "--target", target])
    check(code == 0 and "Actions:" in out, "%s: analyser runs" % name, out[-800:])
    if with_godot:
        code, out = run([sys.executable, "-I", DOCTOR, "--target", target])
        check(code == 0 and "RESULT PASS" in out, "%s: doctor passes" % name, out[-800:])
    return target


def test_existing(root):
    """A project made in Godot: own main scene, Godot's .editorconfig, own .claude/settings.json."""
    target = os.path.join(root, "existing")
    os.makedirs(os.path.join(target, ".claude"))
    with open(os.path.join(target, "project.godot"), "w") as f:
        f.write('config_version=5\n\n[application]\n\nconfig/name="Mine"\nrun/main_scene="res://game.tscn"\n')
    with open(os.path.join(target, ".editorconfig"), "w") as f:
        f.write("root = true\n\n[*]\n\ncharset = utf-8\n")
    mine = {"permissions": {"allow": ["Bash(make:*)"]}, "model": "opus"}
    json.dump(mine, open(os.path.join(target, ".claude", "settings.json"), "w"))
    code, out = scaffold("apply", target, "--answers", json.dumps({"dimension": "2D"}), "--git-init")
    check(code == 0 and "module starter skipped" in out, "existing: starter skipped (own main scene)", out[-800:])
    check(not os.path.exists(os.path.join(target, "scenes", "main")), "existing: no starter scenes written")
    check('run/main_scene="res://game.tscn"' in open(os.path.join(target, "project.godot")).read(),
          "existing: main scene kept")
    check("end_of_line = lf" in open(os.path.join(target, ".editorconfig")).read(),
          "existing: Godot's default .editorconfig replaced")
    got = json.load(open(os.path.join(target, ".claude", "settings.json")))
    allow = got.get("permissions", {}).get("allow", [])
    check(got.get("model") == "opus" and allow[0] == "Bash(make:*)" and
          "Bash(python3 -I tools/test_runner.py:*)" in allow, "existing: settings.json merged", str(got)[:400])
    _, out, rows = plan_rows(target)
    check(rows and all(s == "SAME" for s, _ in rows), "existing: second run is all SAME", out[-800:])


def test_release_check(target):
    """tools/build_release.sh run by hand (no PYTHON/GODOT from the test runner)."""
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHON", "GODOT")}
    p = subprocess.run(["bash", "tools/build_release.sh", "--check"], cwd=target, capture_output=True, text=True,
                       timeout=300, env=env)
    check(p.returncode == 0 and "RELEASE CHECK PASS" in p.stdout, "release: --check without PYTHON/GODOT set",
          (p.stdout + p.stderr)[-800:])


def test_doctor_missing(target):
    code, out = run([sys.executable, "-I", DOCTOR, "--target", target], env={"GODOT": "/nonexistent/godot"})
    check(code == 1 and "MISS Godot" in out and "fix:" in out, "doctor: reports a missing Godot", out[-800:])


def test_upgrade(target):
    """A kit file nobody edited is replaced by a newer template; an edited one is kept."""
    state_path = os.path.join(target, ".claude", "godot-kit.json")
    state = json.load(open(state_path))
    check(bool(state.get("files")), "upgrade: file hashes are recorded")
    old = "# old template\n"
    for rel in ("docs/dev_workflow.md", "docs/rounds/README.md"):
        with open(os.path.join(target, rel), "w") as f:
            f.write(old)
    # dev_workflow.md looks like an older kit wrote it; rounds/README.md like the user edited it.
    state["files"]["docs/dev_workflow.md"] = hashlib.sha256(old.encode()).hexdigest()[:16]
    json.dump(state, open(state_path, "w"))
    _, out, rows = plan_rows(target)
    states = dict((p, s) for s, p in rows)
    check(states.get("docs/dev_workflow.md") == "UPDATE", "upgrade: unedited kit file is UPDATE", out[-800:])
    check(states.get("docs/rounds/README.md") == "DIFFERS", "upgrade: edited file is DIFFERS", out[-800:])
    scaffold("apply", target)
    check(open(os.path.join(target, "docs/dev_workflow.md")).read() != old, "upgrade: apply replaced the file")
    check(open(os.path.join(target, "docs/rounds/README.md")).read() == old, "upgrade: apply kept the edited file")
    _, out, rows = plan_rows(target)
    check([p for s, p in rows if s != "SAME"] == ["docs/rounds/README.md"], "upgrade: only the edited file differs",
          out[-800:])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-godot", action="store_true", help="skip the projects' Godot suites")
    ap.add_argument("--keep", action="store_true", help="keep the throwaway projects")
    ap.add_argument("--root", help="create the projects here (an empty folder) instead of a temp dir; implies --keep")
    opts = ap.parse_args()
    with_godot = not opts.no_godot
    if with_godot and not godot_found():
        print("Godot not found: set GODOT=/path/to/godot or pass --no-godot")
        return 2
    root = os.path.abspath(opts.root) if opts.root else tempfile.mkdtemp(prefix="kit_test_")
    os.makedirs(root, exist_ok=True)
    opts.keep = opts.keep or bool(opts.root)
    print("Projects in %s" % root)
    try:
        for name, answers in PROJECTS.items():
            target = test_project(root, name, answers, with_godot)
            if with_godot and name == "mp3d":
                test_release_check(target)
        test_existing(root)
        test_upgrade(target)
        test_doctor_missing(target)
    finally:
        if not opts.keep:
            shutil.rmtree(root, ignore_errors=True)
    print("RESULT %s (%d failed)" % ("FAIL" if failures else "PASS", len(failures)))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
