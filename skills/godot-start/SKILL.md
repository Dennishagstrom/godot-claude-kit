---
name: godot-start
description: Set up a new (or almost empty) Godot 4 project with a solid Claude Code structure — lean CLAUDE.md, docs skeleton, code map, parallel headless test runner with a smoke test (and a host+client network test for multiplayer games), worktree-per-task scripts, pre-commit hook, implementer/reviewer agents, round skill, Network/Events autoloads — plus optional modules (network testing + lag proxy, build/release + patch notes, smooth motion, window guard, perf tests, Blender pipeline, CSV data pipeline, safe saves, l10n check, sandbox, UI tokens, Steam). Use when the user starts a new Godot game or asks to "set up the kit / structure / strategy" in a project.
---

# godot-start: scaffold a Godot project for Claude Code

Answer the user in their language (they may write Norwegian or anything else). Files
you create are English unless the user picks another language for player text.

The kit lives at `${CLAUDE_PLUGIN_ROOT}`. The scaffolder is
`python3 -I ${CLAUDE_PLUGIN_ROOT}/scripts/scaffold.py` (always run it with `python3 -I`).
It never overwrites a file that differs unless you name it, and running it twice is safe.
On Windows, if `python3` is missing or opens the Microsoft Store, use `python` (or `py`)
instead in every command below; shell commands run in Git Bash.

## Steps

0. **Check the machine.** Run
   `bash "${CLAUDE_PLUGIN_ROOT}/scripts/py.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py" --target .`
   (the `doctor` skill explains the output). Anything `MISS`: tell the user what to install
   (the fix line) and stop until it is fixed. `warn`/`info` only matter for the modules
   they pick; mention them when they choose modules (e.g. Blender for `blender-pipeline`).

1. **Detect.** Run `python3 -I ${CLAUDE_PLUGIN_ROOT}/scripts/scaffold.py detect --target .`
   - No `project.godot`: ask whether to create a minimal one here (`--create-project`) or
     stop so they can create the project in Godot first.
   - Many scripts already (more than ~10) or a big CLAUDE.md: this is an existing
     project. Suggest `/godot-claude-kit:godot-analyse` first; continue only if the user
     wants the scaffold anyway.
   - `saved_answers` present: the kit ran before. Reuse the answers; only ask what changed.
   - `saved_kit_version` older than `kit_version`: this is an upgrade. Skip the questions
     (reuse the answers) and go to the plan; offer modules that are new since then.

2. **Ask** (one AskUserQuestion call, up to 4 questions; free text via "Other"):
   - Game name (default: the name in project.godot).
   - 2D or 3D.
   - Multiplayer? No / Yes, up to 2 / up to 4 / up to 8 players.
   - Language of player-facing text (default English; text always goes through `tr()`).
   Then ask for a one-line genre/pitch in plain chat if you don't have it (e.g. "co-op
   roguelite dungeon crawler").

   **Modules** (second AskUserQuestion call; `scaffold.py groups` lists them with one line each):
   - Recommended, ON unless the user says otherwise: `net-testing` (multiplayer only),
     `build-release`, `smooth-motion`, `window-guard`, `perf-tests`, `safe-saves`, `l10n-check`.
     Show them as one short list and ask "Keep all recommended modules?" (Yes / Let me remove some).
   - Optional, ask (multiSelect, default none): `blender-pipeline` (models as Python,
     headless Blender), `data-pipeline` (CSV tables → .tres), `sandbox` (`--sandbox`
     arena + F1 dev panel), `ui-tokens` (design tokens + components + no-hardcoded-colours
     test), and for multiplayer `steam` (GodotSteam lobbies; works without GodotSteam too).
   - Multiplayer-only modules are never offered for a single-player game.
   One sentence of "why" per module is in `${CLAUDE_PLUGIN_ROOT}/STRATEGY.md` section 10
   if the user asks. Don't ask anything else; everything has defaults.

3. **Plan.** Build the answers JSON:
   `{"game_name": "...", "dimension": "3D", "multiplayer": true, "max_players": 4, "genre": "...", "text_language": "English", "modules": ["net-testing", "build-release", ...]}`
   and run `scaffold.py plan --target . --answers '<json>'`. Show the user a short table:
   NEW files, PATCH (adds lines to .gitignore / .gitattributes / project.godot autoloads / git hooks path),
   UPDATE (a kit file nobody edited, with a newer template: apply replaces it), and every
   `DIFFERS` file (exists with other content: edited in the project, or written by a kit
   older than 0.3.0, which kept no record).
   - For `DIFFERS` files ask once (AskUserQuestion, multiSelect) which to overwrite. Default
     is to keep theirs. If they ask what changed, compare their file with the template
     under `${CLAUDE_PLUGIN_ROOT}/templates/`. For a differing CLAUDE.md, offer to merge
     instead: keep their file and add the kit's missing sections yourself, staying under 5 KB.
   - The user can skip whole groups (`scaffold.py groups` lists them); pass `--only`.
   - Modules add files under their own folders, `docs/modules/<name>.md`, suite lines,
     `CHANGE_TAGS` lines, autoloads and `.gitignore` lines (PATCH rows). Add one later with
     `scaffold.py apply --only <module>` (it joins the saved `modules` list).

4. **Apply.** `scaffold.py apply --target . --answers '<json>' [--overwrite a,b] [--only ...]`
   (add `--git-init` if it is not a git repo and the user agreed, `--create-project` if
   agreed in step 1).

5. **Verify headless** (never open visible Godot windows unless the user allows it):
   `python3 -I tools/test_runner.py` (all suites: parse check, smoke, net, and every
   installed module's suite; a few seconds to a minute). If Godot is not
   found, tell the user to set `GODOT=/path/to/godot` and show where `tools/dev/godot_env.sh`
   looks. Fix anything red before you finish.

6. **Fill in** what only the user knows: in CLAUDE.md, replace the genre line if it reads
   oddly, and list hot files later as they appear. Don't pad CLAUDE.md; it must stay < 5 KB.

7. **Report** briefly in the user's language: what was created, what was kept, test
   results, and the next steps:
   - commit (`git add -A && git commit -m "Set up godot-claude-kit"`), the pre-commit hook
     now runs the parse check;
   - give every new script a one-line `##` doc comment (it feeds `docs/code_map.md`);
   - several tasks at once: the `round` skill; one task: work in a worktree
     (`tools/dev/new_worktree.sh <name>`);
   - read `${CLAUDE_PLUGIN_ROOT}/STRATEGY.md` for the why behind each piece.

## Notes

- `window-guard` lives in the plugin (hook `hooks/hooks.json`); the module only switches
  it on for this project. Toggle with `/godot-claude-kit:windows on|off|status`.
- `build-release` needs a main scene and the export templates before the first real
  release; `tools/build_release.sh --check` says what is missing.

- Multiplayer scaffold: `autoload/network.gd` (ENet host/join, peer 1 = server, a
  validated `any_peer` RPC and a full-state roster sync for late joiners, `--host` /
  `--join` dev flags) and `tests/net/` (two headless processes). It is a starting point;
  adapt it rather than building a second one.
- Templates are in `${CLAUDE_PLUGIN_ROOT}/templates/project/`. Change the kit there, not in
  generated files, if a template is wrong.
