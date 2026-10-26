#!/usr/bin/env python3
"""Tests for scripts/window_guard.py with sample hook inputs (no Godot needed).

    python3 -I tests/test_window_guard.py
"""
import json
import os
import subprocess
import sys
import tempfile

GUARD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "window_guard.py")
G = "/Applications/Godot.app/Contents/MacOS/Godot"
BLOCK = [
    G + " --path .",
    G + " --editor --path .",
    "godot --path . -- --host &",
    '"$GODOT" --path . -s res://tests/x.gd',
    "cd /tmp && godot4 -e",
    "GODOT_X=1 nohup " + G + " --path . > log 2>&1 &",
    "perl -e 'alarm 60; exec @ARGV' 60 $GODOT --path . -- --join",
    "timeout 30 godot --path .",
    "open -a Godot",
    "open /Applications/Blender.app",
    "/Applications/Blender.app/Contents/MacOS/Blender model.blend",
    "blender --python build.py",
    "echo hi; " + G + " --path .",
    G + " --headless --path . --quit\n" + G + " --path .",
]
ALLOW = [
    G + " --headless --audio-driver Dummy --path . --quit",
    G + " --headless --path . -s res://tests/smoke/test_smoke.gd",
    G + " --path . --import",
    G + " --headless --path . --export-release Windows build/x.exe",
    G + " --path . --export-debug macOS build/x.zip",
    G + " --path . --check-only -s res://x.gd",
    G + " --version",
    G + " --display-driver headless --path .",
    "blender --background --python build.py",
    "/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python x.py",
    "python3 -I tools/test_runner.py --changed",
    "grep -rn godot docs/",
    "source tools/dev/godot_env.sh && echo $GODOT",
    "bash tools/dev/godot_env.sh",
    "git commit -m 'run godot --path . later'",
    "ls ~/Library/Application\\ Support/Godot",
]


def run(project, payload, env=None):
    p = subprocess.run([sys.executable, "-I", GUARD], input=json.dumps(payload), capture_output=True, text=True,
                       env=dict(os.environ, **(env or {})))
    if p.returncode != 0:
        raise SystemExit("guard exited %d: %s" % (p.returncode, p.stderr))
    return json.loads(p.stdout)["hookSpecificOutput"]["permissionDecision"] if p.stdout.strip() else "pass"


def bash(project, command, env=None):
    return run(project, {"tool_name": "Bash", "cwd": project, "tool_input": {"command": command}}, env)


def main():
    fails = []
    env = {"CLAUDE_PROJECT_DIR": "", "GODOT_KIT_WINDOWS": ""}
    with tempfile.TemporaryDirectory() as tmp:
        project = os.path.join(tmp, "game")
        sub = os.path.join(project, ".claude", "worktrees", "task")
        os.makedirs(sub)
        kit = os.path.join(project, ".claude", "godot-kit.json")
        # Not active without the module.
        json.dump({"answers": {"modules": ["net-testing"]}}, open(kit, "w"))
        if bash(project, BLOCK[0], env) != "pass":
            fails.append("guard active without the window-guard module")
        json.dump({"answers": {"modules": ["window-guard"]}}, open(kit, "w"))
        for cmd in BLOCK:
            if bash(project, cmd, env) != "deny":
                fails.append("not blocked: %r" % cmd)
        for cmd in ALLOW:
            if bash(project, cmd, env) != "pass":
                fails.append("blocked: %r" % cmd)
        if bash(sub, BLOCK[0], env) != "deny":
            fails.append("not blocked inside a worktree folder")
        mcp = {"tool_name": "mcp__godot__run_project", "cwd": project, "tool_input": {}}
        if run(project, mcp, env) != "deny":
            fails.append("Godot MCP run_project not blocked")
        if run(project, dict(mcp, tool_name="mcp__godot__get_project_info"), env) != "pass":
            fails.append("harmless MCP tool blocked")
        # Allowances.
        if bash(project, BLOCK[0], dict(env, GODOT_KIT_WINDOWS="1")) != "pass":
            fails.append("env allowance ignored")
        subprocess.run([sys.executable, "-I", GUARD, "on", "--dir", project], capture_output=True, check=True)
        if bash(project, BLOCK[0], env) != "pass":
            fails.append("`on` did not allow windows")
        subprocess.run([sys.executable, "-I", GUARD, "off", "--dir", project], capture_output=True, check=True)
        if bash(project, BLOCK[0], env) != "deny":
            fails.append("`off` did not forbid windows")
        json.dump({"until": 1.0}, open(os.path.join(project, ".claude", "godot-kit.windows"), "w"))
        if bash(project, BLOCK[0], env) != "deny":
            fails.append("expired allowance still allows")
        json.dump({"answers": {"modules": ["window-guard"]}, "windows": "allow"}, open(kit, "w"))
        if bash(project, BLOCK[0], env) != "pass":
            fails.append('"windows": "allow" ignored')
        # Broken input never blocks.
        p = subprocess.run([sys.executable, "-I", GUARD], input="{not json", capture_output=True, text=True)
        if p.returncode != 0 or p.stdout.strip():
            fails.append("broken input did not pass through")
        # Outside any kit project: nothing happens.
        if bash(tmp, BLOCK[0], env) != "pass":
            fails.append("active outside a kit project")
    for f in fails:
        print("FAIL", f)
    print("RESULT %s window guard (%d block + %d allow samples)" % ("FAIL" if fails else "PASS", len(BLOCK), len(ALLOW)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
