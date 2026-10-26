---
name: godot-start
description: Set up a new (or almost empty) Godot 4 project with a solid Claude Code structure — lean CLAUDE.md, docs skeleton, code map, parallel headless test runner with a smoke test (and a host+client network test for multiplayer games), worktree-per-task scripts, pre-commit hook, implementer/reviewer agents, round skill, and optional Network/Events autoloads. Use when the user starts a new Godot game or asks to "set up the kit / structure / strategy" in a project.
---

# godot-start: scaffold a Godot project for Claude Code

Answer the user in their language (they may write Norwegian or anything else). Files
you create are English unless the user picks another language for player text.

The kit lives at `${CLAUDE_PLUGIN_ROOT}`. The scaffolder is
`python3 -I ${CLAUDE_PLUGIN_ROOT}/scripts/scaffold.py` (always run it with `python3 -I`).
It never overwrites a file that differs unless you name it, and running it twice is safe.

## Steps

1. **Detect.** Run `python3 -I ${CLAUDE_PLUGIN_ROOT}/scripts/scaffold.py detect --target .`
   - No `project.godot`: ask whether to create a minimal one here (`--create-project`) or
     stop so they can create the project in Godot first.
   - Many scripts already (more than ~10) or a big CLAUDE.md: this is an existing
     project. Suggest `/godot-claude-kit:godot-analyse` first; continue only if the user
     wants the scaffold anyway.
   - `saved_answers` present: the kit ran before. Reuse the answers; only ask what changed.

2. **Ask** (one AskUserQuestion call, up to 4 questions; free text via "Other"):
   - Game name (default: the name in project.godot).
   - 2D or 3D.
   - Multiplayer? No / Yes, up to 2 / up to 4 / up to 8 players.
   - Language of player-facing text (default English; text always goes through `tr()`).
   Then ask for a one-line genre/pitch in plain chat if you don't have it (e.g. "co-op
   roguelite dungeon crawler"). Don't ask more than this; everything else has defaults.

3. **Plan.** Build the answers JSON:
   `{"game_name": "...", "dimension": "3D", "multiplayer": true, "max_players": 4, "genre": "...", "text_language": "English"}`
   and run `scaffold.py plan --target . --answers '<json>'`. Show the user a short table:
   NEW files, PATCH (adds lines to .gitignore / project.godot autoloads / git hooks path),
   and every `DIFFERS` file (exists with other content).
   - For `DIFFERS` files ask once (AskUserQuestion, multiSelect) which to overwrite. Default
     is to keep theirs. For a differing CLAUDE.md, offer to merge instead: keep their file
     and add the kit's missing sections yourself, staying under 5 KB.
   - The user can skip whole groups (`scaffold.py groups` lists them); pass `--only`.

4. **Apply.** `scaffold.py apply --target . --answers '<json>' [--overwrite a,b] [--only ...]`
   (add `--git-init` if it is not a git repo and the user agreed, `--create-project` if
   agreed in step 1).

5. **Verify headless** (never open visible Godot windows unless the user allows it):
   `python3 -I tools/test_runner.py --quick` (and `net` for multiplayer). If Godot is not
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

- Multiplayer scaffold: `autoload/network.gd` (ENet host/join, peer 1 = server, a
  validated `any_peer` RPC and a full-state roster sync for late joiners, `--host` /
  `--join` dev flags) and `tests/net/` (two headless processes). It is a starting point;
  adapt it rather than building a second one.
- Templates are in `${CLAUDE_PLUGIN_ROOT}/templates/project/`. Change the kit there, not in
  generated files, if a template is wrong.
