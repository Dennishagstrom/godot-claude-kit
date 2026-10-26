# godot-claude-kit (developing the plugin itself)

A Claude Code plugin that gives Godot 4 projects a solid foundation for agent-driven development. Users: the author (speaks Norwegian — answer in Norwegian) and friends who make their own Godot games. Everything the plugin ships is **game-agnostic English**.

**Read first:** README.md (what it is, install), STRATEGY.md (the playbook and why), CHANGELOG.md, `skills/*/SKILL.md` (godot-start, godot-analyse, round, doctor, windows).

## Layout

- `.claude-plugin/plugin.json` + `marketplace.json` (one repo = marketplace + plugin, `source: "./"`). Bump `version` in plugin.json for every release.
- `skills/` — godot-start (scaffold a project), godot-analyse (read-only report + "apply items N"), round (multi-task workflow), doctor (machine checklist, `scripts/doctor.py`), windows (window-guard toggle).
- `agents/` — implementer (inherits model), reviewer (Sonnet).
- `hooks/hooks.json` → `scripts/window_guard.py` (only active in projects whose `.claude/godot-kit.json` lists `window-guard`).
- `scripts/scaffold.py` (renders `templates/` with `{{PLACEHOLDER}}` / `{{#MULTIPLAYER}}`, NEW/SAME/UPDATE/DIFFERS/PATCH plan, idempotent; hashes of written files in the project's `.claude/godot-kit.json` → UPDATE for unedited files), `scripts/analyse.py` (report) + `analyse_checks.py` (measurements) + `analyse_modules.py`.
- `templates/project/` — base files; `templates/modules/<name>/` — module.json + README + files/ (12 modules).
- `tests/` — `test_window_guard.py`, `test_scaffold.py`.

## Rules

- Keep scripts < 800 lines.
- Bump `version` and add a CHANGELOG.md entry (with upgrade notes) for every release.
- Scaffold must stay idempotent: a second run on a scaffolded project shows only SAME.
- Generated CLAUDE.md for a project must stay < 5 KB.
- Never copy game-specific content (the source project is ~/sites/unnamed_game — read-only reference).
- Godot: `/Applications/Godot.app/Contents/MacOS/Godot`, **headless only** (`--headless --audio-driver Dummy`) unless the user allows windows. Blender: `--background` only.

## Test before every push

```bash
python3 -I tests/test_window_guard.py
python3 -I tests/test_scaffold.py      # ~30 s: MP 3D all modules + SP 2D defaults in a temp dir, their suites,
                                       # re-run → all SAME, CLAUDE.md < 5 KB, upgrade (UPDATE/DIFFERS), analyser
claude plugin validate .
```

After a hook change, also check it live (godot is not on PATH, so nothing opens): in a scaffolded
project, `claude -p "Run exactly: godot --path ." --plugin-dir <kit> --allowedTools Bash --model haiku`
must report the window guard; after `scripts/window_guard.py on 1` it must reach "command not found".

Commit with clear messages; push to `origin main` (public repo, MIT) only after the tests pass. Commits use the GitHub noreply address (already in the repo's git config).

## Open items (2026-10-26)

- Not verified: running on Windows/Linux (0.3.1 added Windows support, untested on Windows), macOS export (needs `macos.zip` export template), a real Steam lobby.
- CI ready but not pushed: `.github/workflows/test.yml` (local, untracked) needs a token with `workflow` scope (`gh auth refresh -h github.com -s workflow`).
