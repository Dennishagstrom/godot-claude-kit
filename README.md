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
/plugin marketplace add <github-owner>/godot-claude-kit
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

It asks before it overwrites any file that already exists, and it is safe to run again.
Then it runs the smoke test headless (no windows).

### Existing project: `/godot-claude-kit:godot-analyse`

Claude runs a fast script (about a second, few tokens) that measures your project and
writes `docs/claude_kit_analysis.md`: big scripts with split suggestions, CLAUDE.md
size and token cost per turn, big docs without a summary, tests, git workflow and
hooks, multiplayer RPC validation, typing, hardcoded UI text, node-name coupling. You
get a prioritised list and pick what to apply ("apply 1, 3, 4"). Nothing changes until
you say so, and it adapts to your structure instead of copying files over yours.

### Several tasks at once: `/godot-claude-kit:round`

Give Claude a list of tasks. It plans by file ownership, runs up to 3 implementer
agents in parallel (each in its own git worktree), reviews each branch with the
reviewer agent, merges, and runs the full test suite. The agents are also available
directly as `godot-claude-kit:implementer` and `godot-claude-kit:reviewer`.

All skills answer in your language. Files and code are written in English.

## Update

```
/plugin marketplace update godot-claude-kit
```

Then restart Claude Code. Files the kit already created in your project don't change by
themselves: run `godot-start` again to see which templates differ, and choose what to
update.

## Repo layout

```
.claude-plugin/   plugin.json, marketplace.json
skills/           godot-start, godot-analyse, round
agents/           implementer, reviewer
scripts/          scaffold.py (renders templates), analyse.py (the analysis)
templates/project files copied into a project ({{PLACEHOLDERS}} filled in)
STRATEGY.md       the playbook: what we learned and why
```
