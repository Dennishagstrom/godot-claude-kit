# Changelog

Update the plugin with `/plugin marketplace update godot-claude-kit`, restart Claude Code,
then run `/godot-claude-kit:godot-start` in your project to see what changed.

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
