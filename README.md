# godot-claude-kit

A Claude Code plugin for Godot 4 (GDScript) projects. It gives a project the structure
we learned (the hard way) while building a co-op game almost entirely with Claude Code
agents: a short CLAUDE.md, a code map, a parallel headless test runner, one worktree per
task, implementer and reviewer agents, a "round" workflow, and multiplayer guardrails.

It works for **new projects** (sets everything up) and **existing projects** (measures
the project and tells you what to fix first). Why each piece exists: [STRATEGY.md](STRATEGY.md).

**New to Claude Code?** Read [GUIDE.md](GUIDE.md) first (ten minutes): the play → list →
round loop, how to write tasks agents get right, and the habits that decide how far your
usage goes (one of them once cost ~60 % of a usage window in a single message).

## Install

In Claude Code:

```
/plugin marketplace add Dennishagstrom/godot-claude-kit
/plugin install godot-claude-kit@godot-claude-kit
```

Or from a local copy (for testing): `/plugin marketplace add /path/to/godot-claude-kit`.
Restart Claude Code (or run `/reload-plugins`) after installing.

Requirements: Godot 4 (tested with 4.7; found automatically, or set `GODOT=/path/to/godot`), Python 3.8+,
git, bash (on Windows: Git Bash).

**Check your machine:** `/godot-doctor` lists every requirement as ok or
missing, with the fix for each one: the four above, plus what your modules need (perl,
export templates, Blender and an optional Blender MCP server, GodotSteam). `godot-start`
and `godot-analyse` run it first.

### Windows

1. Install [Git for Windows](https://git-scm.com) (includes Git Bash; Claude Code uses it
   for shell commands) and [Python](https://www.python.org/downloads/) (tick "Add
   python.exe to PATH"). The kit uses `python3`, `python` or `py`, whichever works.
2. Godot is a loose `.exe`. The kit looks in `Program Files\Godot`, `%LOCALAPPDATA%\Programs\Godot`,
   winget and scoop folders, `~\Godot`, `C:\Godot`, Desktop and Downloads (the `*_console.exe` first).
   Anywhere else: set `GODOT` to the **console** exe, e.g. in `~/.bashrc`:
   `export GODOT="C:/Tools/Godot/Godot_v4.7.2-stable_win64_console.exe"`.
3. Scaffolded projects get `.gitattributes` lines that keep shell scripts on LF line
   endings, so they keep working in worktrees with `core.autocrlf`.

## Use it

Open Claude Code in your Godot project folder (the one with `project.godot`).

### New project: `/godot-start`

Type it alone or with your idea: `/godot-start a co-op heist game where ...`. Claude starts
with a short interview, with suggestions fitted to your idea (or three ideas to choose
from if you have none yet):

1. **The idea**: what the player does, what should feel good, which games it is like.
2. **Frame**: name, view (2D/3D and camera), single player or online co-op, platforms.
3. **Strategy**: scope (jam, small, larger), team size, look, input devices.
4. **Details**: saves, language of player text, where 3D models come from.
5. **Design draft**: core loop, pillars, first playable, not doing, open questions,
   for you to approve or change.

The answers decide real things: `docs/design.md` (agents read it before core features),
milestones in `docs/status.md` sized to the scope, project settings (pixel art filtering
and integer scaling, the Compatibility renderer for web, Mobile for phones, touch emulation)
and which modules are recommended, each with a reason (a jam drops CI, Steam as a target
adds `steam` ...). "Just set it up" skips everything but the frame. Then it creates:

- a game you can run at once (module `starter`, new projects only): main menu → world →
  a player that moves on the input actions; for multiplayer Host/Join, players spawned by
  the server and moved by it (input sent by RPC, position synced). Plus the input map
  (keyboard + gamepad), window/stretch settings, audio buses and a folder layout
  (`scenes/<feature>/`, `scripts/`, `assets/`, `data/`). These files are yours from then on.
- `CLAUDE.md` (< 5 KB: rules + where to look) and `docs/` (design, reference, status, workflow, rounds)
- `tools/dev/code_map.py` → `docs/code_map.md`
- `tools/test_runner.py` + `tests/` (parse check, smoke test, the real game started and
  quit cleanly in real time, and for multiplayer host + client and late-join tests in two
  headless processes)
- `tools/dev/lint.py` (suite + pre-commit): catches the mistakes that cost us whole rounds,
  such as caches that leak at exit, `randf()` in gameplay, autoloads that break `-s` tests,
  `load()` every frame, layer numbers, forgotten or missing test suites
- `scripts/core/rng.gd`: seeded random streams per system (`-- --seed=N` replays a run);
  for multiplayer `Network.register_state()` (one late-join contract for every system) and
  `tools/dev/rpc_check.py` (merging a branch that dropped or changed an RPC is refused)
- `tools/dev/new_worktree.sh` / `finish_worktree.sh`, `.githooks/pre-commit`
- `.claude/agents/implementer.md`, `reviewer.md`, `.claude/skills/round/`
- `autoload/events.gd`, and for multiplayer `autoload/network.gd` (host/join, peer 1 = server)
- `.claude/settings.json` allow rules (test runner, code map, worktree scripts, read-only git),
  so agents don't stop for permission prompts; `README.md`, `.editorconfig`

Then it offers optional **modules** (each self-contained, with its own test suite and a
short doc in `docs/modules/`):

| Module | Default | What it adds |
|---|---|---|
| `starter` | on (new projects) | main scene (menu → world → player), host/join flow, `teleport()`, input map, project settings, audio buses, physics layer registry + test, flow tests (fixed fps and real time) |
| `ci` | on | GitHub Actions workflow: every suite headless on push (private repos spend Actions minutes) |
| `net-testing` | on (multiplayer) | host + client test helpers (`Input.action_press`, synced-state asserts), UDP lag proxy |
| `build-release` | on | `tools/build_release.sh` (export, build number, zip, headless smoke test), patch notes → "What's new", version check on join |
| `smooth-motion` | on | `VisualSmoother` (interpolation on the host, easing on clients) + 240 Hz test |
| `window-guard` | on | plugin hook that blocks visible Godot/Blender windows until you allow them (`/godot-windows on`) |
| `perf-tests` | on | exclusive perf budget suite + F3 overlay that logs hitches |
| `safe-saves` | on | `--save=<slot>` save slots, throwaway slot for tests, Settings skeleton that never writes your file in tests |
| `l10n-check` | on | test that finds UI text built without `tr()` |
| `model-import` | on (3D) | check for every model whatever made it (budget, units, pivot, duplicate textures, Godot name suffixes), shared materials on import, `docs/art_style.md` |
| `blender-pipeline` | ask (3D) | models as Python in headless Blender: detail shapes, palette shading, glow, jointed parts, contact-sheet previews with a player-size figure; live Blender over MCP documented |
| `data-pipeline` | ask | CSV tables → typed `.tres` resources |
| `sandbox` | ask | `-- --sandbox` arena with an F1 dev panel and a tool registry |
| `ui-tokens` | ask | design tokens, theme, base components, no-hardcoded-colours test |
| `steam` | ask (multiplayer) | GodotSteam lobbies/invites behind `Network`, ENet fallback, Steamworks checklist |

It never overwrites a file you have edited without asking, and it is safe to run again
(a second run changes nothing). Then it runs all suites headless (no windows) and
offers to commit. A project that already has a main scene keeps it: `starter` is skipped.

### Existing project: `/godot-analyse`

Claude runs a fast script (about a second, few tokens) that measures your project and
writes `docs/claude_kit_analysis.md`: big scripts with split suggestions, CLAUDE.md
size and token cost per turn, big docs without a summary, tests, git workflow and
hooks, multiplayer RPC validation, typing, hardcoded UI text, node-name coupling, the kit
lint's findings (global RNG, exit-leak caches, unregistered tests ...), the model check
(duplicate embedded textures, units, pivots, Godot name suffixes), and
which optional modules would help. You get a prioritised list and pick what to apply
("apply 1, 3, 4", or later `/godot-analyse apply 1,3`); modules are applied adapted to your project. Nothing changes until
you say so, and it adapts to your structure instead of copying files over yours.

### Several tasks at once: `/godot-round`

The command you'll use most: play, write what you saw as a numbered list, hand it over.

Give Claude a list of tasks (`/godot-round fix the jump; add a pause menu`). It plans by file ownership, runs up to 3 implementer
agents in parallel (each in its own git worktree), reviews each branch with the
reviewer agent, merges, and runs the full test suite. It says up front how long it will
take, checks risky branches before merging them (removed names still used by tests, perf),
and if you say you're away it decides design questions itself and lists them for you to
override. The agents are also available
directly as `godot-claude-kit:implementer` and `godot-claude-kit:reviewer`.

### Is my machine ready? `/godot-doctor`

Read-only checklist of what the kit needs on this machine, with a fix line for anything
missing (see Install).

### Windows on or off: `/godot-windows on|off|status`

With the `window-guard` module, commands that would open a Godot or Blender window are
blocked (headless runs, `--import` and exports never are). `on [hours]` allows windows
for this project (default 12 h), `off` goes back to headless only.

All skills answer in your language. Files and code are written in English.

## Update

```
/plugin marketplace update godot-claude-kit
```

Then restart Claude Code. Files the kit already created in your project don't change by
themselves: run `/godot-start` again. Kit files you never edited are updated (`UPDATE`);
files you changed are listed as `DIFFERS` and kept unless you choose to overwrite them.
Coming from 0.1.0 or 0.2.0? Read [CHANGELOG.md](CHANGELOG.md) first.

## Status

[![test](https://github.com/Dennishagstrom/godot-claude-kit/actions/workflows/test.yml/badge.svg)](https://github.com/Dennishagstrom/godot-claude-kit/actions/workflows/test.yml)

Every push is tested on **Windows (Git Bash), macOS and Linux** with headless Godot 4.7.2
(`tests/test_scaffold.py` in GitHub Actions): scaffold of a multiplayer 3D project with
every module and a single-player 2D project, all their suites (including two-process
network tests and the lag proxy), re-runs, upgrades, the analyser and the doctor. Also
verified on macOS: the window guard in a live Claude Code session, a Windows release
export with its headless boot/host/join smoke test, and a macOS export (the `.app` boots
headless; its template fetched with `tools/fetch_export_template.py`).

Not verified yet: the window guard inside Claude Code on Windows, release exports on
Windows/Linux, and a real Steam lobby (the `steam` module is tested
without GodotSteam). Perf budgets are reported, not asserted, on CI runners (shared
machines). Reports and fixes are welcome.

## Repo layout

```
.claude-plugin/   plugin.json, marketplace.json
skills/           godot-start, godot-analyse, godot-round, godot-doctor, godot-windows
agents/           implementer, reviewer
hooks/            hooks.json (window guard, PreToolUse)
scripts/          scaffold.py + kit_modules.py + kit_frame.py (render templates; the interview's frame), analyse.py + analyse_checks.py +
                  analyse_modules.py, window_guard.py (the hook), doctor.py, py.sh (picks a working Python)
templates/project files copied into a project ({{PLACEHOLDERS}} filled in)
templates/modules optional modules: <name>/module.json, README.md, files/
tests/            test_window_guard.py (hook samples), test_scaffold.py (end-to-end, see CLAUDE.md)
GUIDE.md          how to work with it: the loop, writing tasks, what costs usage
STRATEGY.md       the playbook: what we learned and why
CHANGELOG.md      what changed per version, with upgrade notes
.gitattributes    keeps shell scripts on LF line endings (Windows checkouts)
```
