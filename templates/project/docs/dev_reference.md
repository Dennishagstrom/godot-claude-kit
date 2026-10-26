# Developer reference

TL;DR: commands to run the game and tests, the tools in `tools/`, and notes per
system. Moved out of CLAUDE.md so it doesn't load every turn. Read only the section
you need.

Sections: Run · Tests · Tools · Systems

## Run

```bash
source tools/dev/godot_env.sh          # sets $GODOT (or export GODOT=/path/to/godot)
"$GODOT" --editor --path .             # editor (visible window: ask the user first)
"$GODOT" --path .                      # run the game (visible window: ask first)
"$GODOT" --headless --audio-driver Dummy --path . -s res://tests/parse_check.gd   # parse check
{{#MULTIPLAYER}}"$GODOT" --path . -- --host &               # dev shortcut: host at once
"$GODOT" --path . -- --join                 # join 127.0.0.1 (--join=<ip>, --port=N)
{{/MULTIPLAYER}}```

## Tests

- Runner: `tools/test_runner.py` (parallel, port/slot locks across worktrees,
  `exclusive` suites last, parse check first). Suite list: `tests/integration/suites.txt`.
- Logs: `tests/integration/suite/<name>.log`. Read the tail, not the whole log.
- A test is a `SceneTree` script run with `-s res://tests/<area>/test_x.gd`. It prints
  `RESULT PASS` / `RESULT FAIL ...` and exits 0/1. Touch autoloads from the first
  `_process` frame, not in `_initialize()`.
{{#MULTIPLAYER}}- Network tests: a shell script starts a host and a client headless
  (`tests/net/run_net.sh` is the example). Each networked suite uses its own `--port`.
{{/MULTIPLAYER}}- `tests/.gdignore` keeps tests out of the Godot import; `tests/.gitignore` keeps
  only sources in git.

## Tools

- `tools/dev/code_map.py`: rewrites `docs/code_map.md` (`--check` in the pre-commit hook).
- `tools/dev/new_worktree.sh` / `finish_worktree.sh`: one worktree per task.
- `.githooks/pre-commit`: parse check + code map check (`git config core.hooksPath .githooks`).

## Systems

Add one short section per system here (what it is, which files own it, how to
test it), or a separate `docs/<system>.md` with a TL;DR at the top.
