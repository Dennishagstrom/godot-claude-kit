# godot-claude-kit

A Claude Code plugin for Godot 4 (GDScript) projects. It gives a project the structure
we learned (the hard way) while building a co-op game almost entirely with Claude Code
agents: a short CLAUDE.md, a code map, a parallel headless test runner, one worktree per
task, implementer and reviewer agents, a "round" workflow, and multiplayer guardrails.

It works for **new projects** (sets everything up) and **existing projects** (measures
the project and tells you what to fix first). Why each piece exists: [STRATEGY.md](STRATEGY.md).

## Install

In Claude Code:

```
/plugin marketplace add Dennishagstrom/godot-claude-kit
/plugin install godot-claude-kit@godot-claude-kit
```

Or from a local copy (for testing): `/plugin marketplace add /path/to/godot-claude-kit`.
Restart Claude Code (or run `/reload-plugins`) after installing.

Requirements: Godot 4 (found automatically, or set `GODOT=/path/to/godot`), Python 3,
git, bash (on Windows: Git Bash).

## Use it

Open Claude Code in your Godot project folder (the one with `project.godot`).

### New project: `/godot-claude-kit:godot-start`

Claude asks a few questions (name, 2D/3D, multiplayer and max players, genre, language
of player text) and then creates:

- `CLAUDE.md` (< 5 KB: rules + where to look) and `docs/` (reference, status, workflow, rounds)
- `tools/dev/code_map.py` → `docs/code_map.md`
- `tools/test_runner.py` + `tests/` (parse check, smoke test, and for multiplayer a
  host + client test in two headless processes)
- `tools/dev/new_worktree.sh` / `finish_worktree.sh`, `.githooks/pre-commit`
- `.claude/agents/implementer.md`, `reviewer.md`, `.claude/skills/round/`
- `autoload/events.gd`, and for multiplayer `autoload/network.gd` (host/join, peer 1 = server)

Then it offers optional **modules** (each self-contained, with its own test suite and a
short doc in `docs/modules/`):

| Module | Default | What it adds |
|---|---|---|
| `net-testing` | on (multiplayer) | host + client test helpers (`Input.action_press`, synced-state asserts), UDP lag proxy |
| `build-release` | on | `tools/build_release.sh` (export, build number, zip, headless smoke test), patch notes → "What's new", version check on join |
| `smooth-motion` | on | `VisualSmoother` (interpolation on the host, easing on clients) + 240 Hz test |
| `window-guard` | on | plugin hook that blocks visible Godot/Blender windows until you allow them (`/godot-claude-kit:windows on`) |
| `perf-tests` | on | exclusive perf budget suite + F3 overlay that logs hitches |
| `safe-saves` | on | `--save=<slot>` save slots, throwaway slot for tests, Settings skeleton that never writes your file in tests |
| `l10n-check` | on | test that finds UI text built without `tr()` |
| `blender-pipeline` | ask | models as Python, headless Blender build + PNG previews |
| `data-pipeline` | ask | CSV tables → typed `.tres` resources |
| `sandbox` | ask | `-- --sandbox` arena with an F1 dev panel and a tool registry |
| `ui-tokens` | ask | design tokens, theme, base components, no-hardcoded-colours test |
| `steam` | ask (multiplayer) | GodotSteam lobbies/invites behind `Network`, ENet fallback, Steamworks checklist |

It asks before it overwrites any file that already exists, and it is safe to run again.
Then it runs all suites headless (no windows).

### Existing project: `/godot-claude-kit:godot-analyse`

Claude runs a fast script (about a second, few tokens) that measures your project and
writes `docs/claude_kit_analysis.md`: big scripts with split suggestions, CLAUDE.md
size and token cost per turn, big docs without a summary, tests, git workflow and
hooks, multiplayer RPC validation, typing, hardcoded UI text, node-name coupling, and
which optional modules would help. You get a prioritised list and pick what to apply
("apply 1, 3, 4"); modules are applied adapted to your project. Nothing changes until
you say so, and it adapts to your structure instead of copying files over yours.

### Several tasks at once: `/godot-claude-kit:round`

Give Claude a list of tasks. It plans by file ownership, runs up to 3 implementer
agents in parallel (each in its own git worktree), reviews each branch with the
reviewer agent, merges, and runs the full test suite. The agents are also available
directly as `godot-claude-kit:implementer` and `godot-claude-kit:reviewer`.

### Windows on or off: `/godot-claude-kit:windows on|off|status`

With the `window-guard` module, commands that would open a Godot or Blender window are
blocked (headless runs, `--import` and exports never are). `on [hours]` allows windows
for this project (default 12 h), `off` goes back to headless only.

All skills answer in your language. Files and code are written in English.

## Update

```
/plugin marketplace update godot-claude-kit
```

Then restart Claude Code. Files the kit already created in your project don't change by
themselves: run `godot-start` again. Kit files you never edited are updated (`UPDATE`);
files you changed are listed as `DIFFERS` and kept unless you choose to overwrite them.
Coming from 0.1.0 or 0.2.0? Read [CHANGELOG.md](CHANGELOG.md) first.

## Status

Tested before every release on macOS with headless Godot 4.7 (`tests/test_scaffold.py`):
scaffold of a multiplayer 3D project with every module and a single-player 2D project,
all their suites (including two-process network tests and the lag proxy), re-runs,
upgrades and the analyser. Also verified on macOS: the window guard in a live Claude Code
session, and a Windows release export with its headless boot/host/join smoke test.

Not verified yet: running on Windows and Linux (scripts are written for Git Bash and
bash, but untested there), macOS export, and a real Steam lobby (the `steam` module is
tested without GodotSteam). Reports and fixes are welcome.

## Repo layout

```
.claude-plugin/   plugin.json, marketplace.json
skills/           godot-start, godot-analyse, round, windows
agents/           implementer, reviewer
hooks/            hooks.json (window guard, PreToolUse)
scripts/          scaffold.py + kit_modules.py (render templates), analyse.py + analyse_checks.py +
                  analyse_modules.py, window_guard.py (the hook)
templates/project files copied into a project ({{PLACEHOLDERS}} filled in)
templates/modules optional modules: <name>/module.json, README.md, files/
tests/            test_window_guard.py (hook samples), test_scaffold.py (end-to-end, see CLAUDE.md)
STRATEGY.md       the playbook: what we learned and why
```
