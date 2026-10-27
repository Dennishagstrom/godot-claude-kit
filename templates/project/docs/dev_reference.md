# Developer reference

TL;DR: commands to run the game and tests, the tools in `tools/`, and notes per
system. Moved out of CLAUDE.md so it doesn't load every turn. Read only the section
you need.

Sections: Run · Tests · Layout · Tools · Systems

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
- Isolation: each runner claims a port block (`~/.cache/godot-claude-kit/port_blocks/`)
  and its suites get `{{GAME_ENV}}_PORT_OFFSET=<block*1000>`{{#MULTIPLAYER}} (Network adds it via
  `PortOffset`, so does the lag proxy){{/MULTIPLAYER}} and a private `HOME` (own `user://`,
  saves, settings). Runners in other worktrees never collide; a suite run by
  hand uses the normal ports. Suites of one runner share that `user://`: give
  each suite its own file names or `--save=<slot>`.
- Flake rules: wait on state, and count physics ticks for deadlines
  (`seconds * Engine.physics_ticks_per_second`), never wall clock: under load a
  real-time deadline expires before the game got there. Single-process suites
  that simulate game time run with `--fixed-fps 60` (each frame = one physics
  tick, as fast as the CPU allows).{{#MULTIPLAYER}} Two-process network suites run in real time
  and must tolerate several physics ticks per frame.{{/MULTIPLAYER}}
- Timing budgets belong in `exclusive` suites. Others run with
  `{{GAME_ENV}}_PARALLEL=1` and should only print wall-clock budgets.
- Long suites split into parts that run side by side: one suites.txt line per
  part (`-- --shard=1/3`), the test skips the other parts.
- A test is a `SceneTree` script run with `-s res://tests/<area>/test_x.gd`. It prints
  `RESULT PASS` / `RESULT FAIL ...` and exits 0/1. Touch autoloads from the first
  `_process` frame, not in `_initialize()`.
{{#MULTIPLAYER}}- Network tests: a shell script starts a host and a client headless
  (`tests/net/run_net.sh` is the example). Each networked suite uses its own `--port`.
{{/MULTIPLAYER}}- `tests/.gdignore` keeps tests out of the Godot import; `tests/.gitignore` keeps
  only sources in git.

## Layout

```
scenes/<feature>/   a feature's scenes with their scripts (player/, world/, menu/, enemies/ ...)
scripts/<area>/     shared code that is not one scene's (components/, net/, ui/, data types)
autoload/           singletons, registered in project.godot (no class_name)
assets/             imported art/<feature>/, audio/{music,sfx}/, fonts/ (sources stay out of res://)
data/               game data: tables, .tres resources, patch notes
tests/<area>/       suites (listed in tests/integration/suites.txt), tools/ dev and build scripts
```

New folder = a `CHANGE_TAGS` line in `tools/test_runner.py` so `--changed` runs its suites.
{{#MOD_STARTER}}Entry point: `scenes/main/main.tscn` (menu → world → players, `docs/modules/starter.md`).
Input actions (`move_left/right/up/down`, `jump`, `interact`, `pause`) are in project.godot.
{{/MOD_STARTER}}{{#MOD_CI}}CI: `.github/workflows/test.yml` runs every suite on push (`docs/modules/ci.md`).
{{/MOD_CI}}
## Tools

- `tools/dev/code_map.py`: rewrites `docs/code_map.md` (`--check` in the pre-commit hook).
- `tools/dev/new_worktree.sh` / `finish_worktree.sh`: one worktree per task.
- `.githooks/pre-commit`: parse check + code map check (`git config core.hooksPath .githooks`).
- `.claude/settings.json`: commands agents run without asking (test runner, code map, worktree
  scripts, read-only git). Shared in git; personal additions go in `.claude/settings.local.json`.

## Systems

Add one short section per system here (what it is, which files own it, how to
test it), or a separate `docs/<system>.md` with a TL;DR at the top.
