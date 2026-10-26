#!/usr/bin/env python3
"""Parallel test runner for headless Godot suites.

Reads the suite list from tests/integration/suites.txt and runs suites side by side:

    python3 -I tools/test_runner.py                 # everything (default ~cpu/2 at a time)
    python3 -I tools/test_runner.py --changed       # only suites touched by the git diff (+ smoke)
    python3 -I tools/test_runner.py --quick         # parse check + smoke suites
    python3 -I tools/test_runner.py net core        # suites with these tags or names
    python3 -I tools/test_runner.py --jobs 4 --list

Godot binary: $GODOT, else godot4/godot on PATH, else the usual install paths.

Rules that keep parallel runs honest (a parallel run must never change a verdict):
- Every runner claims its own port block and user-data folder (lock file
  ~/.cache/godot-claude-kit/port_blocks/block_<k>.lock, shared by all kit
  projects on this machine). Its suites get {{GAME_ENV}}_PORT_OFFSET=<k*1000>
  (Network / PortOffset and tools/lag_proxy.py add it to every port) and a
  private HOME (~/.cache/godot-claude-kit/test_home/{{GAME_ID}}/b<k>), so
  user://, save slots and settings are private to the runner. Runners in
  different worktrees never wait for each other and never touch the player's
  own saves. A suite run by hand uses block 0 (the normal ports).
- Within one run, suites that use the same network port (or --save=<slot>)
  never overlap. Ports are read from the command (--port=N), the test script
  (PORT constants, host_game(N)), shell scripts and numeric shell-suite
  arguments. A suite that hosts but names no port locks DEFAULT_PORT.
- Suites tagged `exclusive` (timing-sensitive: perf, high fixed fps, real time)
  run alone at the end. All others get {{GAME_ENV}}_PARALLEL=1: wall-clock
  budgets are then printed, not asserted.
- Long suites split themselves: list one line per part with an argument such
  as `-- --shard=1/3` and let the test skip the other parts.
- A parse check (Godot --import, then tests/parse_check.gd compiles every game
  script) runs first; if it fails, nothing else runs.

Each run writes one log per suite to tests/integration/suite/<name>.log and the
durations to tests/integration/durations.json (longest suites start first next time).
Exit code 0 = all passed.

suites.txt, one suite per line (blank lines and # comments are ignored):
    <name> <timeout_s> <tags,comma> <godot args ...>        e.g. -s res://tests/x/test_x.gd -- --port=7790
    <name> <timeout_s> <tags,comma> sh:<script> [args ...]   the LAST output line must contain PASS
A Godot suite passes when it exits 0, prints no SCRIPT ERROR and its last
PASS/FAIL/RESULT lines contain no FAIL.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SUITES = os.path.join(ROOT, "tests", "integration", "suites.txt")
LOG_DIR = os.path.join(ROOT, "tests", "integration", "suite")
DURATIONS = os.path.join(ROOT, "tests", "integration", "durations.json")
DEFAULT_PORT = {{DEFAULT_PORT}}
# Shell suites usually start two Godot processes (host + client): they count twice for --jobs.
SH_WEIGHT = 2
CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "godot-claude-kit")
BLOCK_LOCK_DIR = os.path.join(CACHE_DIR, "port_blocks")
TEST_HOME_DIR = os.path.join(CACHE_DIR, "test_home", "{{GAME_ID}}")
# Block k shifts every port by k * PORT_BLOCK; block 0 is left to manual runs.
PORT_BLOCK = 1000
MAX_BLOCKS = 30
PORT_OFFSET_ENV = "{{GAME_ENV}}_PORT_OFFSET"
PARALLEL_ENV = "{{GAME_ENV}}_PARALLEL"
# Environment for every suite of this runner (claim_block() fills it in).
SUITE_ENV = dict(os.environ)
# Shell suites use the Python running this runner (Windows often has no real python3).
SUITE_ENV.setdefault("PYTHON", sys.executable.replace(os.sep, "/"))
GODOT_CANDIDATES = [
    "/Applications/Godot.app/Contents/MacOS/Godot",
    "/Applications/Godot_mono.app/Contents/MacOS/Godot",
    os.path.expanduser("~/Applications/Godot.app/Contents/MacOS/Godot"),
    "/usr/local/bin/godot", "/usr/bin/godot",
]

# Changed path prefix -> tags (or suite names) that must run for --changed.
# A changed file that matches nothing runs EVERYTHING, so add a line for every
# new folder. Tests and .md files are handled automatically.
CHANGE_TAGS = [
{{MODULE_CHANGE_TAGS}}
    ("autoload/network.gd", ["net", "core"]),
    ("scripts/net/", ["net", "core"]),
    ("autoload/", ["core"]),
    ("scenes/", ["core"]),
    ("scripts/", ["core"]),
    ("data/", ["core"]),
    ("assets/", []),
    ("project.godot", ["core"]),
    ("docs/", []),
    (".claude/", []),
    (".githooks/", []),
    ("tools/", []),
    ("CLAUDE.md", []),
    (".gitignore", []),
]
# Always part of --changed / --quick.
SMOKE_TAGS = ["smoke"]


def find_godot():
    env = os.environ.get("GODOT")
    if env:
        return env
    for name in ("godot4", "godot", "Godot"):
        path = shutil.which(name)
        if path:
            return path
    for path in GODOT_CANDIDATES:
        if os.path.exists(path):
            return path
    if os.name == "nt":
        # Godot on Windows is a loose .exe: look in the usual folders, console build first
        # (the plain .exe prints nothing to a pipe).
        import glob
        home = os.path.expanduser("~")
        roots = [os.path.join(os.environ.get("PROGRAMFILES", r"C:\Program Files"), "Godot"),
                 os.path.join(os.environ.get("LOCALAPPDATA", home), "Programs", "Godot"),
                 os.path.join(os.environ.get("LOCALAPPDATA", home), "Microsoft", "WinGet", "Packages"),
                 os.path.join(home, "scoop", "apps", "godot", "current"), os.path.join(home, "Godot"),
                 os.path.join(home, "Desktop"), os.path.join(home, "Downloads"), r"C:\Godot"]
        for pattern in ("[Gg]odot*console.exe", "[Gg]odot*.exe"):
            for root in roots:
                hits = sorted(glob.glob(os.path.join(root, "**", pattern), recursive=True), reverse=True)
                if hits:
                    return hits[0]
    return ""


def find_bash():
    """bash for sh: suites. On Windows that must be Git Bash: the bash.exe in System32 is WSL."""
    if os.name != "nt":
        return "bash"
    path = shutil.which("bash")
    if path and "system32" not in path.lower() and "windowsapps" not in path.lower():
        return path
    for root in (os.environ.get("PROGRAMFILES", r"C:\Program Files"), os.environ.get("LOCALAPPDATA", "")):
        for rel in (r"Git\bin\bash.exe", r"Programs\Git\bin\bash.exe"):
            if root and os.path.exists(os.path.join(root, rel)):
                return os.path.join(root, rel)
    raise SystemExit("Git Bash not found: install Git for Windows (https://git-scm.com)")


GODOT = find_godot()


class Suite:
    def __init__(self, name, timeout, tags, args):
        self.name = name
        self.timeout = timeout
        self.tags = tags
        self.args = args
        self.is_sh = bool(args) and args[0].startswith("sh:")
        self.ports = set()
        self.weight = SH_WEIGHT if self.is_sh else 1
        self.result = None


def load_suites():
    suites = []
    if not os.path.exists(SUITES):
        return suites
    with open(SUITES, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            name, timeout, tags = parts[0], int(parts[1]), [t for t in parts[2].split(",") if t]
            suites.append(Suite(name, timeout, tags + [name], parts[3:]))
    return suites


def _read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def _res_to_path(res):
    return os.path.join(ROOT, res[len("res://"):]) if res.startswith("res://") else os.path.join(ROOT, res)


HOSTS_RE = re.compile(r"host_game\(|join_game\(|create_server\(|create_client\(|--host\b|--join\b")
PORT_RE = re.compile(r"(?:PORT\s*(?::\s*int)?\s*[:=]=?\s*|--port=|host_game\(|join_game\([^,]+,\s*)(\d{4,5})")


def _script_ports(path, seen, hosts):
    """Ports a test script (or scene, or shell script) uses. hosts[0] becomes
    True when anything in the chain hosts or joins."""
    if path in seen or not os.path.exists(path):
        return set()
    seen.add(path)
    text = _read(path)
    if HOSTS_RE.search(text):
        hosts[0] = True
    ports = {int(m.group(1)) for m in PORT_RE.finditer(text)}
    if path.endswith(".sh"):
        hosts[0] = hosts[0] or "--port" in text or "PORT" in text
        ports |= {int(m.group(1)) for m in re.finditer(r"\b([5-9][0-9]{3})\b", text)}
    for m in re.finditer(r"(res://[\w/.\-]+\.(?:gd|tscn))", text):
        ports |= _script_ports(_res_to_path(m.group(1)), seen, hosts)
    return ports


def detect_ports(suite):
    hosts = [any(a in ("--host", "--join") or a.startswith("--join=") for a in suite.args)]
    ports = set()
    for a in suite.args:
        m = re.match(r"--port=(\d+)", a)
        if m:
            ports.add(int(m.group(1)))
    found = set()
    if suite.is_sh:
        found = _script_ports(os.path.join(ROOT, suite.args[0][3:]), set(), hosts)
        # A port passed to the script (run_net.sh 7790) is locked too.
        ports |= {int(a) for a in suite.args[1:] if re.fullmatch(r"[1-9]\d{3,4}", a)}
    else:
        for a in suite.args:
            if a.startswith("res://") and a.endswith((".gd", ".tscn")):
                found |= _script_ports(_res_to_path(a), set(), hosts)
    if not ports and hosts[0]:
        ports = found or {DEFAULT_PORT}
    keys = {"port:%d" % p for p in ports}
    slot = next((a.split("=", 1)[1] for a in suite.args if a.startswith("--save=")), "")
    if slot:
        keys.add("slot:%s" % slot)
    suite.ports = keys


def godot_command(suite):
    args = list(suite.args)
    cmd = [GODOT, "--headless", "--path", ROOT]
    if "--audio-driver" not in args:
        cmd += ["--audio-driver", "Dummy"]
    return cmd + args


def verdict_godot(code, log):
    script_errors = len(re.findall(r"^SCRIPT ERROR", log, re.M))
    tail = [l for l in log.strip().splitlines() if re.search(r"PASS|FAIL|failures|RESULT", l)][-3:]
    failed_line = any(re.search(r"\bFAIL\b", l) and not re.search(r"failures=0|\b0 failures|0 failed", l)
                      for l in tail)
    ok = code == 0 and script_errors == 0 and not failed_line
    return ok, script_errors, " ".join(tail)[-160:]


def verdict_sh(code, log):
    lines = [l for l in log.strip().splitlines() if l.strip()]
    last = lines[-1] if lines else ""
    script_errors = len(re.findall(r"SCRIPT ERROR", log))
    ok = code == 0 and "PASS" in last and "FAIL" not in last
    return ok, script_errors, last[-160:]


class FileLock:
    """Exclusive lock on a file, shared by every runner on this machine."""

    def __init__(self, path):
        self.handle = open(path, "a+")

    def try_acquire(self):
        """True if the lock was free (and is now held until release/exit)."""
        try:
            if os.name == "nt":
                import msvcrt
                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            return False

    def release(self):
        try:
            if os.name == "nt":
                import msvcrt
                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle, fcntl.LOCK_UN)
        finally:
            self.handle.close()


def claim_block():
    """Takes the first free port block (held until this runner exits) and points
    the suites' environment at it: port offset + private user-data folder."""
    os.makedirs(BLOCK_LOCK_DIR, exist_ok=True)
    for block in range(1, MAX_BLOCKS + 1):
        lock = FileLock(os.path.join(BLOCK_LOCK_DIR, "block_%d.lock" % block))
        if not lock.try_acquire():
            lock.handle.close()
            continue
        home = os.path.join(TEST_HOME_DIR, "b%d" % block)
        os.makedirs(home, exist_ok=True)
        SUITE_ENV[PORT_OFFSET_ENV] = str(block * PORT_BLOCK)
        # user:// lives under HOME (macOS/Linux), APPDATA (Windows), XDG_DATA_HOME (Linux, if set).
        SUITE_ENV["HOME"] = home
        if os.name == "nt":
            SUITE_ENV["APPDATA"] = home
        if "XDG_DATA_HOME" in os.environ:
            SUITE_ENV["XDG_DATA_HOME"] = os.path.join(home, ".local", "share")
        return block, lock
    raise SystemExit("no free test port block (%d runners already running?)" % MAX_BLOCKS)


def run_suite(suite, parallel=True):
    return _run_suite(suite, parallel)


def _run_suite(suite, parallel):
    log_path = os.path.join(LOG_DIR, suite.name + ".log")
    start = time.time()
    if suite.is_sh:
        cmd = [find_bash(), os.path.join(ROOT, suite.args[0][3:])] + suite.args[1:]
    else:
        cmd = godot_command(suite)
    env = dict(SUITE_ENV, GODOT=GODOT)
    if parallel:
        # Wall-clock budgets are asserted only when a suite runs alone (exclusive).
        env[PARALLEL_ENV] = "1"
    timed_out = False
    with open(log_path, "w") as out:
        try:
            code = subprocess.run(cmd, cwd=ROOT, stdout=out, stderr=subprocess.STDOUT, timeout=suite.timeout,
                                  env=env).returncode
        except subprocess.TimeoutExpired:
            code, timed_out = 124, True
    log = _read(log_path)
    ok, errs, summary = (verdict_sh if suite.is_sh else verdict_godot)(code, log)
    if timed_out:
        ok, summary = False, "TIMEOUT after %ds. %s" % (suite.timeout, summary)
    suite.result = {"ok": ok, "code": code, "errors": errs, "summary": summary, "seconds": time.time() - start}
    return suite


def parse_check():
    # Import first: after a merge or pull, new class_names and assets are unknown to
    # the import cache (.godot) until a scan, and every suite would fail to parse.
    base = [GODOT, "--headless", "--audio-driver", "Dummy", "--path", ROOT]
    subprocess.run(base + ["--import"], cwd=ROOT, capture_output=True, text=True, timeout=600, env=SUITE_ENV)
    # A script, not --quit: --quit hangs without a main scene and only parses what it loads.
    proc = subprocess.run(base + ["-s", "res://tests/parse_check.gd"], cwd=ROOT, capture_output=True, text=True, env=SUITE_ENV,
                          timeout=300)
    errors = [l for l in (proc.stdout + proc.stderr).splitlines() if "SCRIPT ERROR" in l or "Parse Error" in l]
    if proc.returncode != 0 and not errors:
        errors = (proc.stdout + proc.stderr).strip().splitlines()[-5:] or ["parse check exited %d" % proc.returncode]
    return errors


def changed_tags(base, suites):
    files = set()
    for cmd in (["git", "diff", "--name-only", base], ["git", "diff", "--name-only", "--cached", base],
                ["git", "ls-files", "--others", "--exclude-standard"]):
        out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True).stdout
        files |= {l.strip() for l in out.splitlines() if l.strip()}
    tags, unknown = set(SMOKE_TAGS), []
    for f in sorted(files):
        if f.startswith("tests/"):
            # A changed test runs the suites that use its folder.
            folder = os.path.dirname(f) + "/"
            tags |= {s.name for s in suites if any(folder in a for a in s.args)}
            continue
        if f.endswith(".md"):
            continue
        hit = [t for prefix, t in CHANGE_TAGS if f.startswith(prefix)]
        if hit:
            for t in hit:
                tags |= set(t)
        else:
            unknown.append(f)
    return files, tags, unknown


def print_result(s):
    r = s.result
    print("%s %-20s %5.0fs  %s" % ("PASS" if r["ok"] else "FAIL", s.name, r["seconds"],
                                  "" if r["ok"] else r["summary"]), flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("select", nargs="*", help="tags or suite names (default: all)")
    ap.add_argument("--jobs", type=int, default=max(2, min(8, (os.cpu_count() or 4) // 2 + 1)))
    ap.add_argument("--changed", nargs="?", const="HEAD", metavar="BASE",
                    help="run suites for files changed since BASE (default HEAD, incl. uncommitted)")
    ap.add_argument("--quick", action="store_true", help="parse check + smoke suites only")
    ap.add_argument("--list", action="store_true", help="list the selected suites and their locks")
    ap.add_argument("--no-parse", action="store_true", help="skip the parse check")
    opts = ap.parse_args()

    suites = load_suites()
    for s in suites:
        detect_ports(s)
    wanted = set(opts.select)
    if opts.quick:
        wanted |= set(SMOKE_TAGS)
    if opts.changed:
        files, tags, unknown = changed_tags(opts.changed, suites)
        if unknown:
            print("changed files without a CHANGE_TAGS line -> running everything:", ", ".join(unknown[:8]))
            wanted = set()
        else:
            wanted |= tags
            print("changed: %d files -> tags %s" % (len(files), ",".join(sorted(tags))))
    selected = [s for s in suites if not wanted or wanted & set(s.tags)]
    unknown_sel = set(opts.select) - {t for s in suites for t in s.tags}
    if unknown_sel:
        print("unknown tags/suites:", ", ".join(sorted(unknown_sel)))

    if opts.list:
        for s in selected:
            print("%-20s %4ds %-28s locks=%s" % (s.name, s.timeout, ",".join(s.tags[:-1]), sorted(s.ports)))
        print("%d suites" % len(selected))
        return 0
    if not GODOT:
        print("Godot not found. Set GODOT=/path/to/godot (Godot 4).")
        return 2

    os.makedirs(LOG_DIR, exist_ok=True)
    block, _block_lock = claim_block()
    print("port block %d (ports +%d, user data %s)" % (block, block * PORT_BLOCK, SUITE_ENV["HOME"]))
    t0 = time.time()
    if not opts.no_parse:
        errors = parse_check()
        if errors:
            print("PARSE CHECK FAILED:")
            print("\n".join(errors[:20]))
            return 1
        print("parse check ok (%.0fs)" % (time.time() - t0))

    durations = json.loads(_read(DURATIONS) or "{}")
    normal = [s for s in selected if "exclusive" not in s.tags]
    exclusive = [s for s in selected if "exclusive" in s.tags]
    normal.sort(key=lambda s: -durations.get(s.name, s.timeout / 4))

    cond = threading.Condition()
    busy_ports = set()
    busy_weight = [0]
    done = []

    def worker(s):
        with cond:
            while (s.ports & busy_ports) or (busy_weight[0] and busy_weight[0] + s.weight > opts.jobs):
                cond.wait()
            busy_ports.update(s.ports)
            busy_weight[0] += s.weight
        try:
            run_suite(s)
        finally:
            with cond:
                busy_ports.difference_update(s.ports)
                busy_weight[0] -= s.weight
                done.append(s)
                print_result(s)
                cond.notify_all()

    # More threads than jobs: a thread waiting for a port must not hold a free slot.
    with ThreadPoolExecutor(max_workers=max(len(normal), 1)) as pool:
        list(pool.map(worker, normal))
    for s in exclusive:
        run_suite(s, parallel=False)
        done.append(s)
        print_result(s)

    for s in done:
        durations[s.name] = round(s.result["seconds"], 1)
    with open(DURATIONS, "w") as f:
        json.dump(durations, f, indent=1, sort_keys=True)
    failed = [s for s in done if not s.result["ok"]]
    print("\n%d/%d passed in %.0fs (jobs=%d)%s" % (len(done) - len(failed), len(done), time.time() - t0, opts.jobs,
                                                  "" if not failed else "; FAILED: " + ", ".join(s.name for s in failed)))
    if failed:
        print("logs: tests/integration/suite/<name>.log (read the tail, not the whole log)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
