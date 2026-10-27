#!/usr/bin/env python3
"""Window guard: a Claude Code PreToolUse hook that stops Godot or Blender
from opening visible windows unless the user allowed it.

Active only in projects whose `.claude/godot-kit.json` lists the
`window-guard` module (godot-start sets it). Blocks:
  - Bash commands that run Godot without `--headless` (or
    `--display-driver headless`), unless the run never opens a window
    (`--import`, `--export-*`, `--check-only`, `--version`, `--help`,
    `--doctor`, `--dump-*`, `--build-solutions`);
  - Bash commands that run Blender without `--background` / `-b`;
  - `open -a Godot|Blender` and opening .app bundles of them;
  - the Godot MCP tools that launch the editor or the game.

Windows are allowed when any of these is true:
  - env GODOT_KIT_WINDOWS=1;
  - `.claude/godot-kit.windows` exists and has not expired (written by
    `window_guard.py on [hours]`, i.e. the godot-windows skill);
  - `"windows": "allow"` in `.claude/godot-kit.json` (permanent).

    window_guard.py                 hook mode: reads the hook JSON on stdin
    window_guard.py on [hours]      allow windows for this project (default 12 h; 0 = until off)
    window_guard.py off             forbid windows again
    window_guard.py status          print the current state
    window_guard.py --dir DIR ...   act on the project at DIR (default: cwd / CLAUDE_PROJECT_DIR)

The hook never fails closed: on any parse error it lets the command through.
"""
import json
import os
import re
import shlex
import sys
import time

KIT_FILE = os.path.join(".claude", "godot-kit.json")
FLAG_FILE = os.path.join(".claude", "godot-kit.windows")
MODULE = "window-guard"
DEFAULT_HOURS = 12.0
SECONDS_PER_HOUR = 3600.0
ENV_ALLOW = "GODOT_KIT_WINDOWS"
GODOT_RE = re.compile(r"^(?:\$\{?GODOT\w*\}?|godot[\w.\-]*|.*/godot[\w.\-]*)$", re.I)
BLENDER_RE = re.compile(r"^(?:\$\{?BLENDER\w*\}?|blender[\w.\-]*|.*/blender[\w.\-]*)$", re.I)
GODOT_SAFE_FLAGS = ("--headless", "--import", "--check-only", "--version", "--help", "-h", "--doctor",
                    "--build-solutions", "--gdscript-docs")
GODOT_SAFE_PREFIXES = ("--export", "--dump-")
BLENDER_SAFE_FLAGS = ("--background", "-b", "--version", "-v", "--help", "-h")
# Helper scripts named like the tools (tools/dev/godot_env.sh) are not the tools.
SCRIPT_SUFFIXES = (".sh", ".py", ".gd", ".md", ".txt", ".json", ".cfg")
WRAPPERS = {"exec", "nohup", "time", "command", "builtin", "caffeinate", "nice", "sudo", "env", "xargs"}
SEPARATORS = {";", "&&", "||", "|", "&", "\n", "(", ")", "{", "}", "then", "do", "else"}
MCP_WINDOW_TOOLS = re.compile(r"^mcp__.*godot.*__(run_project|launch_editor)$", re.I)
HOW_TO_ALLOW = ("Ask the user first (they may be using this machine). If they allow windows, they can run "
                "/godot-windows on (or you run it after an explicit yes). Otherwise run headless: "
                "add --headless --audio-driver Dummy (Godot) or --background (Blender).")


# --- project state ------------------------------------------------------------------

def find_project(start):
    """Nearest folder at or above `start` with .claude/godot-kit.json."""
    path = os.path.abspath(start or ".")
    while True:
        if os.path.isfile(os.path.join(path, KIT_FILE)):
            return path
        parent = os.path.dirname(path)
        if parent == path:
            return None
        path = parent


def read_kit(project):
    try:
        with open(os.path.join(project, KIT_FILE), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def guard_active(project):
    kit = read_kit(project)
    return MODULE in (kit.get("answers", {}).get("modules") or [])


def windows_allowed(project):
    """(allowed, why)."""
    if os.environ.get(ENV_ALLOW, "") in ("1", "true", "yes"):
        return True, "%s=1" % ENV_ALLOW
    if str(read_kit(project).get("windows", "")).lower() == "allow":
        return True, '"windows": "allow" in %s' % KIT_FILE
    flag = os.path.join(project, FLAG_FILE)
    try:
        with open(flag, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return False, "no %s" % FLAG_FILE
    until = float(data.get("until", 0))
    if until and until < time.time():
        return False, "allowance expired"
    return True, "allowed until %s" % (time.strftime("%H:%M", time.localtime(until)) if until else "turned off")


# --- command analysis ------------------------------------------------------------

def segments(command):
    """Splits a shell command into simple commands (lists of words)."""
    out = []
    for line in command.replace("\\\n", " ").splitlines():
        try:
            lexer = shlex.shlex(line, posix=True, punctuation_chars=";&|()")
            lexer.whitespace_split = True
            words = list(lexer)
        except ValueError:
            words = line.split()
        cur = []
        for w in words:
            if w in SEPARATORS or set(w) <= set(";&|()"):
                if cur:
                    out.append(cur)
                cur = []
            else:
                cur.append(w)
        if cur:
            out.append(cur)
    return out


def program(words):
    """(program word, its arguments) after env assignments and wrappers."""
    i = 0
    while i < len(words):
        w = words[i]
        if re.match(r"^[A-Za-z_]\w*=", w):
            i += 1
        elif os.path.basename(w) in WRAPPERS:
            i += 1
        elif os.path.basename(w) == "timeout" or os.path.basename(w) == "gtimeout":
            i += 1
            while i < len(words) and (words[i].startswith("-") or re.match(r"^\d", words[i])):
                i += 1
        elif os.path.basename(w) == "perl" and "-e" in words[i:i + 3]:
            # perl -e 'alarm N; exec @ARGV' [N] prog ...
            i = words.index("-e", i) + 2
            while i < len(words) and re.match(r"^\d+$", words[i]):
                i += 1
        else:
            return w, words[i + 1:]
    return "", []


def check_segment(words):
    """Reason string if this simple command would open a window, else ''."""
    prog, args = program(words)
    if not prog:
        return ""
    base = prog.rstrip("/")
    if base.endswith(SCRIPT_SUFFIXES):
        return ""
    if os.path.basename(base) == "open":
        joined = " ".join(args).lower()
        if re.search(r"(godot|blender)[^ ]*\.app|-a\s+\"?(godot|blender)", joined) or \
                any(re.search(r"(godot|blender)", a, re.I) for a in args if a.endswith(".app")):
            return "`open` would start a Godot/Blender window"
        return ""
    if GODOT_RE.match(base) or "godot.app/contents/macos/" in base.lower():
        if any(a in GODOT_SAFE_FLAGS for a in args) or any(a.startswith(GODOT_SAFE_PREFIXES) for a in args):
            return ""
        if "--display-driver" in args and args[args.index("--display-driver") + 1:][:1] == ["headless"]:
            return ""
        return "Godot without --headless opens a window"
    if BLENDER_RE.match(base) or "blender.app/contents/macos/" in base.lower():
        if any(a in BLENDER_SAFE_FLAGS for a in args):
            return ""
        return "Blender without --background opens its UI"
    return ""


def check_command(command):
    for seg in segments(command):
        reason = check_segment(seg)
        if reason:
            return reason
    return ""


# --- entry points ------------------------------------------------------------------

def deny(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": "deny",
        "permissionDecisionReason": "Window guard: %s. %s" % (reason, HOW_TO_ALLOW)}}))
    return 0


def hook(stdin_text):
    try:
        data = json.loads(stdin_text or "{}")
    except ValueError:
        return 0
    tool = data.get("tool_name", "")
    cwd = data.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    project = find_project(cwd) or find_project(os.environ.get("CLAUDE_PROJECT_DIR", ""))
    if not project or not guard_active(project):
        return 0
    if tool == "Bash":
        reason = check_command(str((data.get("tool_input") or {}).get("command", "")))
    elif MCP_WINDOW_TOOLS.match(tool):
        reason = "%s opens a Godot window" % tool
    else:
        return 0
    if not reason or windows_allowed(project)[0]:
        return 0
    return deny(reason)


def toggle(args):
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    if "--dir" in args:
        i = args.index("--dir")
        project_dir = args[i + 1]
        args = args[:i] + args[i + 2:]
    project = find_project(project_dir) or os.path.abspath(project_dir)
    flag = os.path.join(project, FLAG_FILE)
    cmd = args[0] if args else "status"
    if cmd == "on":
        hours = float(args[1]) if len(args) > 1 else DEFAULT_HOURS
        os.makedirs(os.path.dirname(flag), exist_ok=True)
        until = time.time() + hours * SECONDS_PER_HOUR if hours > 0 else 0
        with open(flag, "w", encoding="utf-8") as f:
            json.dump({"until": until, "set": time.time()}, f)
        print("Windows allowed in %s %s." % (project, "for %g h" % hours if hours > 0 else "until `off`"))
    elif cmd == "off":
        if os.path.exists(flag):
            os.remove(flag)
        print("Windows forbidden in %s (headless only)." % project)
    allowed, why = windows_allowed(project)
    active = guard_active(project)
    print("guard: %s; windows: %s (%s)" % ("active" if active else "not active (module window-guard not installed)",
                                           "allowed" if allowed else "headless only", why))
    return 0


def main(argv):
    if argv:
        return toggle(argv)
    try:
        return hook(sys.stdin.read())
    except Exception:  # never block work because the guard itself broke
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
