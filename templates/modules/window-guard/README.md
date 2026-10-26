# Module: window-guard

TL;DR: a Claude Code hook (shipped with the godot-claude-kit plugin) blocks
commands that would open a visible Godot or Blender window, until the user
allows windows. Agents keep testing headless while you use the machine.

## What is blocked

- Godot without `--headless` / `--display-driver headless`. Never blocked:
  `--import`, `--export-release/debug/pack`, `--check-only`, `--version`,
  `--help`, `--doctor`, `--dump-*`.
- Blender without `--background` / `-b`.
- `open -a Godot`, `open …/Blender.app`, and the Godot MCP tools
  `run_project` / `launch_editor`.

Blocked calls come back to Claude with the reason and how to run headless.

## Allow windows

- `/godot-claude-kit:windows on` (12 h), `on 0` (until off), `off`, `status`.
  The state lives in `.claude/godot-kit.windows` (git-ignored, per machine).
- Permanent: `"windows": "allow"` in `.claude/godot-kit.json`.
- One shell: `GODOT_KIT_WINDOWS=1`.

The guard is active because `window-guard` is listed under `modules` in
`.claude/godot-kit.json`; remove it there to turn the guard off for good.
Requires the godot-claude-kit plugin to be enabled (the hook lives in the
plugin, so it updates with it).
