# Developer reference

TL;DR: commands to run the game and tests, the tools in `tools/`, and notes per
system. Moved out of CLAUDE.md so it doesn't load every turn. Read only the section
you need.

Sections: Run · Tests · Layout · Tools · Pitfalls · Systems

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
- `tools/dev/lint.py`: static checks for the pitfalls below (suite `lint`, pre-commit).
  A line that is fine anyway ends with `# lint: ok <why>`.{{#MULTIPLAYER}}
- `tools/dev/rpc_check.py`: RPCs removed/moved/changed vs a revision; `finish_worktree.sh`
  runs it before merging (`RPC_OK=1` when the change is intended).{{/MULTIPLAYER}}
- `tools/dev/new_worktree.sh` / `finish_worktree.sh`: one worktree per task.
- `.githooks/pre-commit`: parse check + code map check (`git config core.hooksPath .githooks`).
- `.claude/settings.json`: commands agents run without asking (test runner, code map, worktree
  scripts, read-only git). Shared in git; personal additions go in `.claude/settings.local.json`.

## Pitfalls

Each of these cost a real project whole rounds; most are checked by `lint` or a suite.

- **Exit leaks.** Godot frees scripts at exit in one order-sensitive loop; one script
  freed mid-loop leaks the whole graph ("leaked at exit", "resources still in use").
  Causes: a `static var` holding an instance of its own class (use `load()`: the resource
  cache shares it), particle/effect scenes instanced from code in `_ready` (put them in the
  `.tscn`). Guard: suite `main` (the real game, clean quit){{#MOD_BUILD_RELEASE}}, the release smoke test{{/MOD_BUILD_RELEASE}}{{#MULTIPLAYER}}, net suites{{/MULTIPLAYER}}.
- **Randomness.** Gameplay draws from `Rng.stream(&"<system>")` (scripts/core/rng.gd):
  one run seed (`-- --seed=N` replays a run), one stream per system, so a test that adds a
  loot roll doesn't change what enemies do. A bare `randf()` made a suite fail 1 run in 3.{{#MULTIPLAYER}}
  Only the server rolls; clients get results.{{/MULTIPLAYER}}
- **Autoloads in reusable scripts.** `-s` test scripts and tools compile `class_name`
  scripts before autoloads exist: `Events.x` in a component breaks every test that loads
  it. Use `get_node("/root/Events")` at runtime, or pass the dependency in.
- **Loading on the hot path.** No `load()` per frame or per lookup (one did 66 ms per call,
  many times per tick: 3 FPS). Data resources store scene *paths*, not PackedScenes; a
  catalog caches by path. Instancing many heavy scenes: one per frame. Threaded loads
  race the dummy renderer in headless: load on the main thread there.{{#MOD_STARTER}}
- **Physics layers.** Named in project.godot, constants and the allowed matrix in
  `scripts/core/layers.gd`, suite `layers` checks every scene. One hurtbox on the pickup
  layer gave stuck projectiles and a desync.{{/MOD_STARTER}}{{#MULTIPLAYER}}
- **Late joiners.** Every system with state registers with `Network.register_state(id, self)`
  and implements `net_snapshot()` / `net_apply_snapshot(data)`; the server sends all
  snapshots after the roster, and one that arrives before its node is ready waits. Each
  such system gets a late-join test (copy `tests/net/late_join_*`). Ad-hoc
  `_on_peer_connected` handlers missed one field each time.
- **Teleports.** A jump in position goes through `teleport()` (bumps a synced serial in the
  same packet), never `position =`: otherwise clients smooth it as motion, prediction slides
  for seconds, footsteps hear a 40 m/s run. Listeners reset on `teleported`.{{/MULTIPLAYER}}
- **Refactors.** Splits keep public API as forwarders{{#MULTIPLAYER}} and every `@rpc` on its node
  (`rpc_check.py`){{/MULTIPLAYER}}. Never rename with a regex over files: it rewrites strings too (a
  scripted rename once broke every chest lid). Grep string-named calls before moving code.
- **Fixed fps hides bugs.** `--fixed-fps` makes tests deterministic but every frame is one
  physics tick; per-frame code (animation, sound, nav, cameras) also needs a real-time or
  high-refresh run (suites `main`{{#MOD_STARTER}}, `starter_rt`{{/MOD_STARTER}}{{#MOD_SMOOTH_MOTION}}, `smooth` at 240 Hz{{/MOD_SMOOTH_MOTION}}). A navmesh that was empty
  in real play passed every fixed-fps test.
- **Generated files** (scenes, resources from tables/tools) must be deterministic: build
  twice, no diff; keep node `unique_id`s when regenerating a `.tscn`, or every regen is a
  huge diff and merges conflict.

## Systems

Add one short section per system here (what it is, which files own it, how to
test it), or a separate `docs/<system>.md` with a TL;DR at the top.
