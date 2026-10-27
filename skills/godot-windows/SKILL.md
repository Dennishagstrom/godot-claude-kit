---
name: godot-windows
description: Allow or forbid visible Godot/Blender windows for this project (the window-guard hook). Use when the user says windows are OK now ("vinduer er lov", "you may open the editor"), says they are not, or asks whether windows are allowed. Arguments - on [hours] | off | status.
argument-hint: on [hours] | off | status
---

# godot-windows: toggle the window guard

The `window-guard` module (installed by godot-start) makes a PreToolUse hook
block every command that would open a visible Godot or Blender window:
Godot without `--headless` (except `--import`, `--export-*`, `--check-only`,
`--version`), Blender without `--background`, `open -a Godot/Blender`, and the
Godot MCP tools that launch the editor or game. The user often works on the
same machine, so windows stealing focus is a real cost.

Run (answer in the user's language):

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/py.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/window_guard.py" $ARGUMENTS
```

- `on [hours]`: allow windows for this project (default 12 h, `on 0` = until `off`).
  Writes `.claude/godot-kit.windows` (git-ignored).
- `off`: headless only again. `status` (or no argument): show the state.

Rules:
- Turn windows **on only when the user said so in this conversation**. A
  blocked command is not a reason to turn it on: ask the user, or run the
  command headless (`--headless --audio-driver Dummy`, Blender `--background`).
- When the work that needed windows is done, offer to turn them off.
- Permanent allow (e.g. a dedicated machine): `"windows": "allow"` in
  `.claude/godot-kit.json`; per shell: `GODOT_KIT_WINDOWS=1`.
