#!/usr/bin/env python3
"""End-to-end test of the kit: scaffolds throwaway projects outside the repo,
runs their own suites headless, checks idempotency, the upgrade path and the
analyser. This is the "test before every push" checklist as one command.

    python3 -I tests/test_scaffold.py              # both projects, with Godot suites
    python3 -I tests/test_scaffold.py --no-godot   # skip the Godot suites (no Godot installed)
    python3 -I tests/test_scaffold.py --keep       # keep the projects (path is printed)

Projects: multiplayer 3D with every module, single-player 2D with the defaults.
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


def run(args, cwd=None, timeout=900):
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)
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
    return target


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
    opts = ap.parse_args()
    with_godot = not opts.no_godot
    if with_godot and not godot_found():
        print("Godot not found: set GODOT=/path/to/godot or pass --no-godot")
        return 2
    root = tempfile.mkdtemp(prefix="kit_test_")
    print("Projects in %s" % root)
    try:
        for name, answers in PROJECTS.items():
            target = test_project(root, name, answers, with_godot)
        test_upgrade(target)
    finally:
        if not opts.keep:
            shutil.rmtree(root, ignore_errors=True)
    print("RESULT %s (%d failed)" % ("FAIL" if failures else "PASS", len(failures)))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
