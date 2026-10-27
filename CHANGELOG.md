# Changelog

Update the plugin with `/plugin marketplace update godot-claude-kit`, restart Claude Code,
then run `/godot-claude-kit:godot-start` in your project to see what changed.

## 0.6.0 (2026-10-27)

Lessons from building a co-op game with agents, turned into checks that run from day one
(the why for each: STRATEGY.md §8, the rules: `docs/dev_reference.md` "Pitfalls").

- **`tools/dev/lint.py`** (suite `lint`, pre-commit hook, about a second, no Godot):
  `static-self-cache` (exit leaks), `global-rand`, `autoload-by-name` (a class_name script
  an `-s` test uses reads an autoload member: the test can't compile and Godot hangs),
  `load-in-loop`, `layer-number`, `test-unlisted`, `suite-missing`, `absolute-path`.
  `# lint: ok <why>` silences a line. `godot-analyse` reports its findings too.
- **`scripts/core/rng.gd`**: `Rng.stream(&"loot")`, `Rng.pick()`, `Rng.shuffle()`: one run
  seed (`-- --seed=N`), one stream per system. Suite `rng`.
- **Suite `main`**: the real main scene in real time, then a clean quit; fails on script
  errors and exit leaks. The release smoke test and the net scripts also fail on leaks.
- Multiplayer: **`Network.register_state(id, node)`** with `net_snapshot()` /
  `net_apply_snapshot()`: the server sends every snapshot to a late joiner after the roster;
  one that arrives before its node is ready waits. Suite `late_join` (template to copy).
  `tests/net/run_net.sh <host> <client> [port]` runs any pair.
- Multiplayer: **`tools/dev/rpc_check.py`**: RPCs removed, moved, changed or reordered vs a
  revision. `finish_worktree.sh` refuses the merge (`RPC_OK=1` when intended); the reviewer
  runs it.
- starter: **`Player.teleport()`** (synced `teleport_serial` in the same packet, `teleported`
  signal on every peer, velocity reset), tested in one and two processes; **`Layers`**
  (`scripts/core/layers.gd`: named layers in project.godot, allowed detection matrix) and
  suite `layers` over every scene; suite `starter_rt` (the flow in real time).
- CLAUDE.md, implementer and reviewer: the new rules (Rng, register_state, teleport,
  identifier-by-identifier renames, lint and rpc_check before handing off).

Upgrade: run `godot-start` again. New files are added (lint, Rng, suites `main`, `lint`,
`rng`, `late_join`); `network.gd`, `run_net.sh`, `finish_worktree.sh`, `pre-commit`, the
suite list and CLAUDE.md are `UPDATE` if unedited. Then run `python3 -I tools/dev/lint.py`:
existing code will have findings (global `randf()` is the usual one); fix them or mark
cosmetic ones `# lint: ok cosmetic`. The starter's `teleport()`/`Layers` only reach new projects.

## 0.5.0 (2026-10-27)

- **New module `starter`** (on for new projects; skipped when the project already has a
  main scene): a game you can run at once. `scenes/main/` (menu → world flow),
  `scenes/menu/` (Play, or Host/Join with name and `address[:port]`), `scenes/world/`
  (floor, light, camera / 2D camera), `scenes/player/` (moves on the input actions). In
  multiplayer the server spawns one Player per roster entry (`MultiplayerSpawner`), moves
  it from the owner's input RPC (sender checked) and syncs the position. Also: input map
  (`move_left/right/up/down`, `jump`, `interact`, `pause`; keyboard + gamepad), 1280×720
  with `canvas_items` stretch, untyped-declaration warnings, audio buses Master/Music/SFX,
  `assets/README.md`. Tests: `starter` (one process: menu → world → move → pause → menu) and
  `starter_net` (two processes: the client's input moves its player on the server and back).
  The files are the project's own after the first run (never `DIFFERS`).
- **New module `ci`** (on): `.github/workflows/test.yml` runs every suite headless on
  GitHub Actions on push and pull request; suite logs are uploaded on failure. The Godot
  version is the one installed when the kit wrote it.
- **`.claude/settings.json`** (new group `permissions`): allow rules for the test runner,
  code map, worktree scripts and read-only git, merged into an existing file, so agents in
  a round don't stop at permission prompts.
- **Folder layout** in CLAUDE.md and `docs/dev_reference.md` (Layout section):
  `scenes/<feature>/` with its scripts, `scripts/<area>/`, `assets/`, `data/`, `tests/<area>/`.
- New group `basics`: `README.md` for the game, `docs/design.md` (pitch, core loop, pillars,
  scope, not doing) and `.editorconfig` (LF, tabs for GDScript), written only when missing;
  Godot's default `.editorconfig` is replaced.
- `godot-start` offers to commit the setup when the suites are green.
- `godot-analyse` reports `starter` (main scene) and `ci` (workflow) in the module table.
- Fix: `tools/build_release.sh` (and `tools/blender/build.sh`) failed with
  "PYTHON: unbound variable" when run by hand; `tools/dev/godot_env.sh` now works under `set -u`.

Upgrade: run `godot-start` again. `tools/dev/godot_env.sh`, `tools/build_release.sh` and
CLAUDE.md are `UPDATE` if you never edited them (a `DIFFERS` CLAUDE.md: let Claude merge
the Layout and design.md lines). `docs/design.md`, `.editorconfig` and the
`.claude/settings.json` rules are added. The new modules are not added by themselves:
`scaffold.py apply --only ci` (and `--only starter` in a project without a main scene).

## 0.4.1 (2026-10-26)

- CI on Windows (Git Bash), macOS and Linux runs the whole kit test on every push.
- Fix (Windows): `tools/patch_notes.py` crashed when the notes folder and the project were
  on different drives (`C:` / `D:`), which failed the release_tools suite.
- perf-tests: budgets are reported, not asserted, when `CI=true` (shared CI runners).
- build-release: the join version test no longer flakes on slow machines (the client
  lingers after joining, so the host sees the peer before it disconnects).

Upgrade: run `godot-start` again (`tools/patch_notes.py`, `tests/perf/test_perf.gd` and
`tests/build_release/version_peer.gd` are `UPDATE` if you never edited them).

## 0.4.0 (2026-10-26)

- **`/godot-claude-kit:doctor`**: a read-only checklist of what the kit needs on this
  machine (Python, git, bash/Git Bash, Godot 4; per module perl, export templates,
  Blender, GodotSteam) with a fix line for each missing item. `godot-start` stops on
  anything required that is missing; `godot-analyse` reports it first.
- build-release: zips with Python when `zip` is missing (Git Bash on Windows has none).
- Windows: Godot/Blender lookups convert `C:\...` paths for Git Bash, Blender is found in
  `Blender Foundation\Blender <version>\`, and a found Godot is exported as `C:/...`.

Upgrade: run `godot-start` again (`godot_env.sh`, `build_release.sh` and the Blender
`build.sh` are `UPDATE` if you never edited them).

## 0.3.1 (2026-10-26)

- **Windows support** (Git Bash): a working Python is picked from `python3`, `python` or `py`
  (hook: `scripts/py.sh`; projects: `$PYTHON` from `tools/dev/godot_env.sh`, and the test
  runner passes its own Python to shell suites); Godot is found in the usual Windows
  folders (console exe first); the test runner uses Git Bash, never WSL's `bash.exe`;
  `.gitattributes` keeps `*.sh` and `.githooks/*` on LF (also in the kit repo itself).
- Skills and agents tell Claude to use `python`/`py` when `python3` is missing.
- README: Windows setup.

Upgrade: run `godot-start` again; the changed kit files (`godot_env.sh`, `test_runner.py`,
the pre-commit hook and a few module scripts) are `UPDATE` if you never edited them.

## 0.3.0 (2026-10-26)

- **Upgrades without guesswork.** The scaffolder now records a hash of every file it
  writes (in `.claude/godot-kit.json`). On the next run, a kit file you never edited
  that has a newer template shows as `UPDATE` and is replaced; a file you edited stays
  `DIFFERS` and is only overwritten if you say so.
- `godot-start` notices an upgrade (`saved_kit_version`) and skips the questions.
- build-release: `--check` and the build name the export template file each preset is
  missing (`macos.zip`, `windows_release_x86_64.exe`) instead of only checking the folder.
- The analyser is split (`analyse.py` + `analyse_checks.py`); the report is unchanged.
- Kit test: `tests/test_scaffold.py` (scaffold two projects, run their suites headless,
  idempotency, upgrade path, analyser) as one command.
- The window-guard hook is verified in a live Claude Code session (blocks, and allows
  after `/godot-claude-kit:windows on`).

**Upgrading a project scaffolded with 0.1.0 or 0.2.0:** those versions kept no record of
what they wrote, so the first run with 0.3.0 shows every kit file whose template changed
as `DIFFERS`, even if you never touched it. If you did not edit a file (for example
`tools/test_runner.py`, `tools/dev/*.sh`, `.claude/agents/*`), overwriting it is safe;
keep the ones you changed (usually `CLAUDE.md` and `docs/`). From then on the kit knows
the difference and upgrades by itself.

## 0.2.0 (2026-10-26)

- Twelve optional modules (`templates/modules/`): net-testing, build-release,
  smooth-motion, window-guard, perf-tests, safe-saves, l10n-check, blender-pipeline,
  data-pipeline, sandbox, ui-tokens, steam.
- The analyser recommends modules; leaner generated CLAUDE.md; per-runner port blocks
  and private `HOME` in the test runner; `--smoke-exit` export smoke test.

## 0.1.0 (2026-10-26)

- First release: `godot-start`, `godot-analyse`, `round`; implementer and reviewer agents;
  lean CLAUDE.md, code map, parallel headless test runner, worktree scripts, pre-commit hook.
