---
name: doctor
description: Check that this machine has everything godot-claude-kit needs (Python, git, bash/Git Bash, Godot 4, and per module perl, export templates, Blender, GodotSteam) and say what is missing and how to fix it. Use when the user asks whether their setup is ready, when a kit command fails with "not found", or before the first godot-start on a new machine.
---

# doctor: is this machine ready for the kit?

Answer the user in their language. Run (read-only, about a second):

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/py.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py" --target .
```

- If it prints `Python 3 not found`, Python is missing: tell the user to install it from
  https://www.python.org/downloads/ (Windows: tick "Add python.exe to PATH"), then
  restart Claude Code. Nothing else in the kit works without it.
- `MISS` = required, the kit will not work until it is fixed. `warn` = needed by a module
  the project uses. `info` = only for optional modules or nice to know.
- Report as a short checklist: each item, ok or not, and for anything missing the one
  fix line the doctor printed. Don't install anything yourself; offer to set an
  environment variable (e.g. `GODOT`) in their shell profile if they want.
- No project yet (no `.claude/godot-kit.json`): it checks for every module, so optional
  tools show as `info`. `--modules a,b` checks for a planned module list.
