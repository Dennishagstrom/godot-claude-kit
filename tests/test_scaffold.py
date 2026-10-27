#!/usr/bin/env python3
"""End-to-end test of the kit: scaffolds throwaway projects outside the repo,
runs their own suites headless, checks idempotency, the upgrade path, the
analyser, the doctor, every lint and model-check rule (with generated .glb samples) and, with
Blender, the real model flow (build.sh -> check -> Godot import -> shared material). This is the "test before every push" checklist as one command.

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
import struct
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
    mods = json.load(open(os.path.join(target, ".claude", "godot-kit.json")))["answers"]["modules"]
    check(("model-import" in mods) == (answers["dimension"] == "3D"), "%s: model-import only in 3D" % name, str(mods))
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
    """tools/build_release.sh run by hand: no PYTHON from the test runner (set -u)."""
    env = {k: v for k, v in os.environ.items() if k != "PYTHON"}
    sys.path.insert(0, os.path.join(KIT, "scripts"))
    import doctor  # Git Bash on Windows, not WSL's bash.exe
    p = subprocess.run([doctor.find_bash() or "bash", "tools/build_release.sh", "--check"], cwd=target,
                       capture_output=True, text=True, timeout=300, env=env)
    check(p.returncode == 0 and "RELEASE CHECK PASS" in p.stdout, "release: --check without PYTHON set",
          (p.stdout + p.stderr)[-800:])


LINT_SAMPLE = """class_name BadThing
extends Node
## Lint samples, one per rule.
static var _default: BadThing = null
var roll: float = randf()
var fine: float = randf()  # lint: ok cosmetic


func _process(_delta: float) -> void:
\tvar scene: PackedScene = load("res://x.tscn")
\tNetwork.leave()


func _layer(body: CollisionObject3D) -> void:
\tbody.collision_layer = 4
"""
LINT_RULES = ["static-self-cache", "global-rand", "load-in-loop", "autoload-by-name", "layer-number",
              "test-unlisted", "absolute-path", "suite-missing"]


def test_lint_and_rpc(target):
    """Every lint rule fires on a bad sample (and only there); rpc_check catches a dropped RPC."""
    lint = [sys.executable, "-I", "tools/dev/lint.py"]
    code, out = run(lint, cwd=target)
    check(code == 0, "lint: scaffolded project is clean", out[-800:])
    bad = os.path.join(target, "scripts", "lint_bad.gd")
    stale = os.path.join(target, "tests", "stale", "test_forgotten_case.gd")
    suites = os.path.join(target, "tests", "integration", "suites.txt")
    before = open(suites).read()
    os.makedirs(os.path.dirname(stale))
    open(bad, "w").write(LINT_SAMPLE)
    # An -s test that uses BadThing: only then does BadThing's autoload use break compilation.
    open(stale, "w").write('extends SceneTree\n## x\nconst P: String = "/Users/someone/x"\nvar b: BadThing\n')
    open(suites, "a").write("ghost 10 core -s res://tests/ghost/test_ghost.gd\n")
    code, out = run(lint, cwd=target)
    fired = {r for r in LINT_RULES if ": %s:" % r in out}
    check(code == 1 and fired == set(LINT_RULES) and out.count("global-rand") == 1, "lint: every rule fires once",
          "missing %s\n%s" % (sorted(set(LINT_RULES) - fired), out[-1200:]))
    os.remove(bad)
    shutil.rmtree(os.path.dirname(stale))
    open(suites, "w").write(before)
    rpc = [sys.executable, "-I", "tools/dev/rpc_check.py"]
    run(["git", "add", "-A"], cwd=target)
    run(["git", "commit", "-qm", "base", "--no-verify"], cwd=target)
    code, out = run(rpc, cwd=target)
    check(code == 0 and "RPC CHECK PASS" in out, "rpc_check: unchanged tree passes", out[-600:])
    net = os.path.join(target, "autoload", "network.gd")
    orig = open(net).read()
    open(net, "w").write(orig.replace("func _sync_state(", "func _sync_all_state("))
    code, out = run(rpc, cwd=target)
    check(code == 1 and "REMOVED autoload/network.gd._sync_state" in out, "rpc_check: renamed RPC is caught",
          out[-600:])
    open(net, "w").write(orig)


def make_glb(path, parts, materials=("palette",), image=None, root_rotation=None):
    """A minimal glb: a root node with one box per part [(name, size, centre)], every box with
    vertex colours and material i % len(materials); optionally an embedded PNG and a rotated root."""
    blob, views, accessors, meshes, nodes = bytearray(), [], [], [], []

    def add_view(data, target=None):
        while len(blob) % 4:
            blob.append(0)
        views.append(dict({"buffer": 0, "byteOffset": len(blob), "byteLength": len(data)},
                          **({"target": target} if target else {})))
        blob.extend(data)
        return len(views) - 1

    for i, (name, size, centre) in enumerate(parts):
        corners = [[centre[a] + (size[a] / 2 if (k >> a) & 1 else -size[a] / 2) for a in range(3)] for k in range(8)]
        quads = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
        idx = [v for a, b, c, d in quads for v in (a, b, c, a, c, d)]
        pos = add_view(struct.pack("<24f", *[c for p in corners for c in p]), 34962)
        col = add_view(struct.pack("<32f", *([0.5, 0.3, 0.2, 1.0] * 8)), 34962)
        ind = add_view(struct.pack("<36H", *idx), 34963)
        accessors += [{"bufferView": pos, "componentType": 5126, "count": 8, "type": "VEC3",
                       "min": [min(p[a] for p in corners) for a in range(3)],
                       "max": [max(p[a] for p in corners) for a in range(3)]},
                      {"bufferView": col, "componentType": 5126, "count": 8, "type": "VEC4"},
                      {"bufferView": ind, "componentType": 5123, "count": 36, "type": "SCALAR"}]
        meshes.append({"name": name, "primitives": [{"attributes": {"POSITION": len(accessors) - 3, "COLOR_0":
                       len(accessors) - 2}, "indices": len(accessors) - 1, "material": i % len(materials)}]})
        nodes.append({"name": name, "mesh": i})
    root = {"name": "root", "children": list(range(len(parts)))}
    if root_rotation:
        root["rotation"] = root_rotation
    nodes.append(root)
    doc = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [len(nodes) - 1]}], "nodes": nodes,
           "meshes": meshes, "materials": [{"name": m} for m in materials], "accessors": accessors}
    if image:
        doc["images"] = [{"name": "atlas", "mimeType": "image/png", "bufferView": add_view(image)}]
    doc["bufferViews"] = views
    doc["buffers"] = [{"byteLength": len(blob)}]
    js = json.dumps(doc).encode()
    js += b" " * (-len(js) % 4)
    blob += b"\0" * (-len(blob) % 4)
    with open(path, "wb") as f:
        f.write(struct.pack("<4sII", b"glTF", 2, 28 + len(js) + len(blob)))
        f.write(struct.pack("<I4s", len(js), b"JSON") + js + struct.pack("<I4s", len(blob), b"BIN\0") + bytes(blob))


ASSET_RULES = ["tris", "size", "pivot", "root-transform", "materials", "texture-size", "duplicate-texture",
               "name-suffix", "unreadable"]


def test_assets(target, with_godot):
    """Every model-check rule fires on a bad sample; a good model gets the shared material on import."""
    check_cmd = [sys.executable, "-I", "tools/dev/asset_check.py"]
    models = os.path.join(target, "assets", "models")
    os.makedirs(models, exist_ok=True)
    make_glb(os.path.join(models, "kit_good.glb"), [("body", (1, 1, 1), (0, 0.5, 0)), ("lid", (1, 0.1, 1),
                                                                                         (0, 1.05, 0))])
    code, out = run(check_cmd + ["--report"], cwd=target)
    check(code == 0 and "kit_good.glb | 24 |" in out, "assets: a good model passes", out[-800:])
    bad = os.path.join(target, "assets", "kit_bad")
    os.makedirs(bad)
    big_png = b"\x89PNG\r\n\x1a\n" + struct.pack(">I4sII", 13, b"IHDR", 4096, 4096) + b"\0" * 64
    box = [("body", (1, 1, 1), (0, 0.5, 0))]
    make_glb(os.path.join(bad, "tris.glb"), [("p%d" % i, (0.1, 0.1, 0.1), (0, 0.05 + i * 0.1, 0)) for i in range(40)])
    make_glb(os.path.join(bad, "size.glb"), [("body", (500, 500, 500), (0, 250, 0))])
    make_glb(os.path.join(bad, "pivot.glb"), [("body", (1, 1, 1), (0, 5, 0))])
    make_glb(os.path.join(bad, "turned.glb"), box, root_rotation=[0.7071068, 0, 0, 0.7071068])
    make_glb(os.path.join(bad, "mats.glb"), [("p%d" % i, (0.2, 0.2, 0.2), (0, 0.1, 0)) for i in range(5)],
             materials=("a", "b", "c", "d", "e"))
    make_glb(os.path.join(bad, "atlas_a.glb"), box, image=big_png)
    make_glb(os.path.join(bad, "atlas_b.glb"), box, image=big_png)
    make_glb(os.path.join(bad, "cart.glb"), [("cart", (1, 1, 1), (0, 0.5, 0)), ("front_wheel", (0.2, 0.2, 0.2),
                                                                                 (0.4, 0.1, 0))])
    open(os.path.join(bad, "broken.glb"), "wb").write(b"not a model")
    open(os.path.join(bad, "source.blend"), "wb").write(b"BLENDER")
    rules_path = os.path.join(target, "tools", "dev", "asset_rules.json")
    rules_before = open(rules_path).read()
    rules = json.loads(rules_before)
    rules["files"]["assets/kit_bad/tris.glb"] = {"max_tris": 100}
    json.dump(rules, open(rules_path, "w"))
    code, out = run(check_cmd, cwd=target)
    fired = {r for r in ASSET_RULES if ": %s: " % r in out}
    check(code == 1 and fired == set(ASSET_RULES) and "NOTE assets/kit_bad/source.blend: blend-source" in out and
          "kit_good.glb" not in out, "assets: every rule fires (and only on the bad samples)",
          "missing %s\n%s" % (sorted(set(ASSET_RULES) - fired), out[-1500:]))
    shutil.rmtree(bad)
    open(rules_path, "w").write(rules_before)
    if not with_godot:
        return
    sys.path.insert(0, os.path.join(KIT, "scripts"))
    import doctor
    built = []
    if doctor.find_blender():  # the real flow: build.sh -> model check -> Godot import -> shared material
        code, out = run([doctor.find_bash() or "bash", "tools/blender/build.sh", "example_lamp"], cwd=target,
                        timeout=600)
        check(code == 0 and "RESULT PASS assets" in out, "assets: build.sh builds, checks and imports a model",
              out[-1000:])
        built = ["example_lamp.glb"]
    godot = doctor.find_godot()
    run([godot, "--headless", "--audio-driver", "Dummy", "--path", target, "--import"], timeout=300)
    code, out = run([godot, "--headless", "--audio-driver", "Dummy", "--path", target, "-s",
                     "res://tests/assets/test_shared_materials.gd"], timeout=300)
    want = "RESULT PASS shared_materials: %d models, %d shared surfaces" % (1 + len(built), 2 + 4 * len(built))
    check(code == 0 and want in out, "assets: models get the shared palette material on import", out[-1000:])
    for name in ["kit_good.glb"] + built:
        for f in (name, name + ".import"):
            if os.path.exists(os.path.join(models, f)):
                os.remove(os.path.join(models, f))


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
            if name == "mp3d":
                test_lint_and_rpc(target)
                test_assets(target, with_godot)
                if with_godot:
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
