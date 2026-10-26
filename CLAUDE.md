# godot-claude-kit (developing the plugin itself)

A Claude Code plugin that gives Godot 4 projects a solid foundation for agent-driven development. Users: the author (speaks Norwegian — answer in Norwegian) and friends who make their own Godot games. Everything the plugin ships is **game-agnostic English**.

**Read first:** README.md (what it is, install), STRATEGY.md (the playbook and why), `skills/*/SKILL.md` (godot-start, godot-analyse, round, windows).

## Layout

- `.claude-plugin/plugin.json` + `marketplace.json` (one repo = marketplace + plugin, `source: "./"`). Bump `version` in plugin.json for every release.
- `skills/` — godot-start (scaffold a project), godot-analyse (read-only report + "apply items N"), round (multi-task workflow), windows (window-guard toggle).
- `agents/` — implementer (inherits model), reviewer (Sonnet).
- `hooks/hooks.json` → `scripts/window_guard.py` (only active in projects whose `.claude/godot-kit.json` lists `window-guard`).
- `scripts/scaffold.py` (renders `templates/` with `{{PLACEHOLDER}}` / `{{#MULTIPLAYER}}`, NEW/SAME/DIFFERS/PATCH plan, idempotent), `scripts/analyse.py` + `analyse_modules.py`.
- `templates/project/` — base files; `templates/modules/<name>/` — module.json + README + files/ (12 modules).

## Rules

- Keep scripts < 800 lines (analyse.py is over — split it when touched).
- Scaffold must stay idempotent: a second run on a scaffolded project shows only SAME.
- Generated CLAUDE.md for a project must stay < 5 KB.
- Never copy game-specific content (the source project is ~/sites/unnamed_game — read-only reference).
- Godot: `/Applications/Godot.app/Contents/MacOS/Godot`, **headless only** (`--headless --audio-driver Dummy`) unless the user allows windows. Blender: `--background` only.

## Test before every push

```bash
python3 -I tests/test_window_guard.py
claude plugin validate .
# scaffold a throwaway project and run its suites (put it outside the repo, e.g. /tmp/kit_test/<name>):
#   multiplayer 3D with all modules, and single-player 2D with defaults; re-run scaffold → all SAME
python3 -I scripts/analyse.py <some Godot project>   # sanity-check the report
```

Commit with clear messages; push to `origin main` (public repo, MIT) only after the tests pass. Commits use the GitHub noreply address (already in the repo's git config).

## Open items (2026-10-26)

- Not verified: hook firing inside a live Claude Code session, a real Steam lobby, macOS export, Windows/Linux paths of scripts.
- analyse.py > 800 lines.
- Release notes: projects scaffolded with 0.1.0 see base-template files as DIFFERS after upgrading.
