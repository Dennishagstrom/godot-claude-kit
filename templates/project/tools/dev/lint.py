#!/usr/bin/env python3
"""Project lint: cheap static checks for mistakes that cost real projects whole rounds.

    python3 -I tools/dev/lint.py                # whole project, about a second; exit 1 on findings
    python3 -I tools/dev/lint.py --root DIR     # another project (godot-analyse does this)

Runs as the `lint` suite and in the pre-commit hook. Silence one line with a trailing
`# lint: ok <why>`. Rules:

  static-self-cache  `static var` holding an instance of its own class: Godot's script
                     shutdown then leaks the whole script graph ("leaked at exit").
                     Use load() (the resource cache shares the instance) or a member.
  global-rand        randf()/randi()/pick_random()/shuffle() use the global RNG: runs can't
                     be replayed and tests flake. Use Rng.stream(&"<system>") (scripts/core/rng.gd).
  autoload-by-name   a class_name script that an -s test script uses (type, preload) names an
                     autoload directly. `-s` test scripts compile it before autoloads exist,
                     so the test fails to compile (and Godot hangs). Use get_node("/root/<Name>")
                     or pass it in. Constants (`Network.MAX_PLAYERS`) compile fine.
  load-in-loop       load() inside _process/_physics_process: a disk lookup per frame.
                     preload() into a const, or load once into a member.
  layer-number       collision layer/mask set to a number in code: use Layers constants
                     (scripts/core/layers.gd), so the layer matrix stays in one place.
                     Only when that file exists.
  test-unlisted      a test entry point (extends SceneTree, or a .sh) that no suite or
                     script runs: it silently goes stale.
  suite-missing      a suite in tests/integration/suites.txt points at a file that is gone.
  absolute-path      a machine-specific path in tests/: worktrees and CI then test the wrong tree.
"""
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SKIP_DIRS = {".godot", ".git", ".claude", "addons", "build", "node_modules"}
NOT_GAME = ("tests/", "tools/", "addons/")
SUITES = "tests/integration/suites.txt"
OK_MARK = "# lint: ok"

RAND = re.compile(r"(?<![\w.])(randf|randi|randf_range|randi_range|randfn|randomize)\s*\(|\.(pick_random|shuffle)\s*\(")
LOAD = re.compile(r"(?<![\w.])load\s*\(|ResourceLoader\.load\s*\(")
LAYER = re.compile(r"\bcollision_(layer|mask)\s*=\s*[1-9]|\bset_collision_(layer|mask)_value\s*\(\s*\d")
ABS_PATH = re.compile(r"(/Users/\w|/home/\w|\b[A-Za-z]:[\\/]Users\b)")
FUNC = re.compile(r"^(\s*)(static\s+)?func\s+(\w+)")
STRINGS = re.compile(r"&?\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*'")

findings = []
HAS_LAYERS = False
TEST_TEXT = ""  # every `extends SceneTree` test script (run with -s), joined


def rel(path):
    return os.path.relpath(path, ROOT).replace(os.sep, "/")


def walk():
    for base, dirs, names in os.walk(ROOT):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for n in sorted(names):
            yield rel(os.path.join(base, n))


def read(path):
    try:
        with open(os.path.join(ROOT, path), encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def code_of(line):
    """The line without strings and comments."""
    return STRINGS.sub('""', line).split("#", 1)[0]


def add(path, line_no, rule, msg):
    findings.append("%s:%d: %s: %s" % (path, line_no, rule, msg))


def autoload_names():
    text = read("project.godot")
    m = re.search(r"^\[autoload\]\s*$(.*?)(?=^\[|\Z)", text, re.M | re.S)
    return re.findall(r"^(\w+)=", m.group(1), re.M) if m else []


def lint_gd(path, text, autoloads):
    game = not path.startswith(NOT_GAME)
    cls = re.search(r"^class_name\s+(\w+)", text, re.M)
    cls = cls.group(1) if cls else ""
    used_by_tests = cls and (re.search(r"\b%s\b" % cls, TEST_TEXT) or "res://" + path in TEST_TEXT)
    auto_re = re.compile(r"(?<![\w.$%/])(" + "|".join(autoloads) + r")\b(?!\s*:)(?!\.[A-Z][A-Z0-9_]*\b)") if autoloads and used_by_tests \
        else None
    func = ""
    for no, line in enumerate(text.splitlines(), 1):
        if OK_MARK in line:
            continue
        code = code_of(line)
        m = FUNC.match(code)
        if m:
            func = m.group(3)
        elif code.strip() and not code.startswith((" ", "\t")):
            func = ""
        if cls and re.match(r"\s*static\s+var\s+\w+.*\b%s\b" % cls, code):
            add(path, no, "static-self-cache", "static var holds a %s: leaks at exit; use load() or a member" % cls)
        if game and RAND.search(code):
            add(path, no, "global-rand", "global RNG; use Rng.stream(&\"<system>\") (seeded, replayable)")
        if auto_re and not m:
            hit = auto_re.search(code)
            if hit:
                add(path, no, "autoload-by-name", "%s names autoload %s; use get_node(\"/root/%s\")" % (
                    cls, hit.group(1), hit.group(1)))
        if game and func in ("_process", "_physics_process") and LOAD.search(code):
            add(path, no, "load-in-loop", "load() in %s; preload into a const or load once" % func)
        if game and HAS_LAYERS and LAYER.search(code):
            add(path, no, "layer-number", "layer/mask as a number; use Layers constants")


def lint_tests(files):
    if not os.path.exists(os.path.join(ROOT, SUITES)):
        return  # no kit test runner: nothing to be listed in
    suites = read(SUITES)
    corpus = {f: read(f) for f in files if f.startswith(("tests/", "tools/", ".githooks/")) and
              f.endswith((".gd", ".sh", ".py", ".txt")) or f.startswith(".githooks/")}
    for f in files:
        if not f.startswith("tests/") or not f.endswith((".gd", ".sh")):
            continue
        text = corpus.get(f, "")
        if f.endswith(".gd") and (not re.search(r"^extends\s+SceneTree", text, re.M) or
                                  re.search(r"^class_name", text, re.M)):
            continue
        stem = os.path.splitext(os.path.basename(f))[0]
        word = re.compile(r"(?<![\w-])%s(?![\w-])" % re.escape(stem))
        if not any(word.search(t) for g, t in corpus.items() if g != f):
            add(f, 1, "test-unlisted", "no suite in %s (and no script) runs it" % SUITES)
        for no, line in enumerate(text.splitlines(), 1):
            if OK_MARK not in line and ABS_PATH.search(line):
                add(f, no, "absolute-path", "machine-specific path; use paths relative to the project")
    for no, line in enumerate(suites.splitlines(), 1):
        if not line.strip() or line.startswith("#"):
            continue
        for target in re.findall(r"res://(\S+)", line) + re.findall(r"sh:(\S+)", line):
            if not os.path.exists(os.path.join(ROOT, target)):
                add(SUITES, no, "suite-missing", "%s does not exist" % target)


def lint(root):
    """Findings ("path:line: rule: message") for the project at root."""
    global ROOT, HAS_LAYERS, TEST_TEXT
    ROOT, HAS_LAYERS = root, os.path.exists(os.path.join(root, "scripts", "core", "layers.gd"))
    del findings[:]
    files = list(walk())
    sources = [read(f) for f in files if f.startswith("tests/") and f.endswith(".gd")]
    TEST_TEXT = "\n".join(code_of(l) for t in sources if re.search(r"^extends\s+SceneTree", t, re.M)
                          for l in t.splitlines())
    autoloads = autoload_names()
    for f in files:
        if f.endswith(".gd"):
            lint_gd(f, read(f), autoloads)
    lint_tests(files)
    return list(findings), len(files)


def main():
    root = ROOT
    if "--root" in sys.argv:
        root = os.path.abspath(sys.argv[sys.argv.index("--root") + 1])
    found, n_files = lint(root)
    for line in found:
        print(line)
    if found:
        print("RESULT FAIL lint: %d finding(s); fix them or end the line with `%s <why>`" % (len(found), OK_MARK))
        return 1
    print("RESULT PASS lint (%d files)" % n_files)
    return 0


if __name__ == "__main__":
    sys.exit(main())
