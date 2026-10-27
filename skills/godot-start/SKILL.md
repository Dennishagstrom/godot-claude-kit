---
name: godot-start
description: Set up a new (or almost empty) Godot 4 project with a solid Claude Code structure, starting with a short interview (idea, frame, scope, design draft) that fills docs/design.md, status milestones, project settings and the module list — a runnable starter game (main menu → world → player, host/join for multiplayer, input map, project settings), folder layout, lean CLAUDE.md, docs skeleton with a design doc, code map, parallel headless test runner with a smoke test (and a host+client network test for multiplayer games), worktree-per-task scripts, pre-commit hook, permission allowlist, implementer/reviewer agents, round skill, Network/Events autoloads — plus optional modules (CI on GitHub Actions, network testing + lag proxy, build/release + patch notes, smooth motion, window guard, perf tests, Blender pipeline, CSV data pipeline, safe saves, l10n check, sandbox, UI tokens, Steam). Use when the user starts a new Godot game or asks to "set up the kit / structure / strategy" in a project.
argument-hint: "[pitch: what the player does]"
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
   (the `godot-doctor` skill explains the output). Anything `MISS`: tell the user what to install
   (the fix line) and stop until it is fixed. `warn`/`info` only matter for the modules
   they pick; mention them when they choose modules (e.g. Blender for `blender-pipeline`).

1. **Detect.** Run `python3 -I ${CLAUDE_PLUGIN_ROOT}/scripts/scaffold.py detect --target .`
   - No `project.godot`: ask whether to create a minimal one here (`--create-project`) or
     stop so they can create the project in Godot first.
   - Many scripts already (more than ~10) or a big CLAUDE.md: this is an existing
     project. Suggest `/godot-analyse` first; continue only if the user
     wants the scaffold anyway.
   - `saved_answers` present: the kit ran before. Reuse the answers; only ask what changed.
   - `main_scene` set: the project already runs something; the `starter` module (menu,
     world, player, input map, window settings) is skipped automatically. Don't offer it.
   - `saved_kit_version` older than `kit_version`: this is an upgrade. Skip the questions
     (reuse the answers) and go to the plan; offer modules that are new since then. Saved
     answers without `scope` (kit < 0.8.0): offer the frame questions (2b-2d, without the
     name) once; the answers add the project settings and module advice, while
     `docs/design.md` stays theirs (add a Frame section to it only if they want).

2. **Interview: idea, frame, strategy.** The goal is a game with a clear idea, a frame that
   fits it and a scope that can be finished, before any file exists. Everything decided here
   lands in `docs/design.md` (agents read it), `docs/status.md`, project settings and the
   module list. Ask in the user's language; put the recommended option first, chosen for
   *their* idea (not a fixed default), and say in its description why.

   **a. The idea (plain chat, one message).** If the command came with text
   (`/godot-start a co-op heist game ...`), that is the pitch: skip to b. Otherwise ask:
   what does the player do, what should feel good about it, and which games is it a bit
   like? No idea yet: offer three short pitches that suit a first project (small, one core
   verb each) and let them pick or mix.

   **b. Frame** (one AskUserQuestion call, 4 questions):
   - *Name*: the project's name (recommended) and one or two names drawn from the pitch.
   - *View*: dimension and camera in one answer, the two or three that fit the pitch
     (e.g. "3D third-person", "3D top-down", "2D side-view", "2D top-down").
   - *Players*: single player / online co-op up to 2 / 4 / 8. Recommend single player for
     a first game unless the pitch is about playing together: multiplayer roughly doubles
     the work of every feature.
   - *Platforms* (multiSelect): PC (Windows, macOS, Linux) / Steam / web (itch.io, browser) /
     mobile. Consoles only via "Other" (needs a third-party port).

   **c. Strategy** (one AskUserQuestion call, 4 questions):
   - *Scope*: jam or weekend (days) / small (1-3 months) / larger (6+ months). If the frame
     is big for the scope (online + 3D + a jam, or an open world for a first game), say so
     in the option text and offer the smaller version.
   - *Team*: solo / 2-4 friends / 5+.
   - *Look*: two or three styles that fit the view (2D: pixel art, hand-drawn, flat vector;
     3D: low-poly stylised, toon, realistic). Pixel art sets nearest filtering, a 640x360
     base resolution and integer scaling.
   - *Input* (multiSelect): keyboard + mouse / gamepad / touch.

   **d. Details** (one AskUserQuestion call, 2-3 questions):
   - *Saves*: nothing (a run or a jam) / settings only / player progress.
   - *Player text language* (default English; text always goes through `tr()`).
   - 3D only, *models from* (multiSelect): scripted in Blender by Claude / asset packs /
     made by hand / generators. Scripts suit props, buildings and machines; characters
     and organic shapes come out better by hand or from packs (say so).

   **e. Design draft (plain chat, then one question).** From a-d, write a short draft and
   show it: the pitch in one or two sentences; the core loop in 3-5 steps; two or three
   pillars (rules a feature must serve, concrete enough to say no with: "every fight is
   over in a minute", not "fun combat"); the first playable as 3-6 checkboxes (the smallest
   version that tests whether the core loop is fun, placeholder art); not doing (3-5 tempting
   ideas that are out for now, scope traps first); open questions (the two or three riskiest
   assumptions, tested first). Then AskUserQuestion: "Use this design?" Use it / Change
   something (they say what in "Other") / Leave design.md for me to fill. At most two
   rounds of changes; it is a starting point, not a contract.

   **f. Modules.** `scaffold.py recommend --target . --answers '<json>'` prints every module
   that fits the game as ON / OFF / OPTIONAL with a reason drawn from the answers (a jam
   drops CI and perf tests, Steam as a target turns on `steam`, scripted models turn on
   `blender-pipeline`, a larger game turns on `ui-tokens` and `sandbox`). Show the ON ones
   as one short list ("Keep these?" Yes / Let me change some) and the OPTIONAL ones in a
   multiSelect question; add `data-pipeline` to the recommendations yourself when the pitch
   has many items, units, cards or levels defined as data. `ci` on a private repo spends
   GitHub Actions minutes (a few per push); say so. One sentence of "why" per module is in
   `${CLAUDE_PLUGIN_ROOT}/STRATEGY.md` section 10 if they ask.

   Short on time ("just set it up", "use defaults"): ask only b, use the pitch they gave,
   and leave the rest empty (empty answers change nothing). Never ask what the code or the
   saved answers already tell you.

3. **Plan.** Build the answers JSON (keys and values: the docstring of
   `${CLAUDE_PLUGIN_ROOT}/scripts/kit_frame.py`), for example
   `{"game_name": "Ember Run", "dimension": "2D", "multiplayer": false, "pitch": "...", "references": "Celeste meets Alto", "camera": "side-view", "platforms": ["desktop", "web"], "input": ["keyboard-mouse", "gamepad"], "art": "pixel", "scope": "small", "team": "solo", "saves": "progress", "text_language": "English", "core_loop": ["..."], "pillars": ["..."], "first_playable": ["..."], "not_doing": ["..."], "questions": ["..."], "modules": ["starter", "build-release", ...]}`
   (leave out the design lists if they chose to fill design.md themselves), and run `scaffold.py plan --target . --answers '<json>'`. Show the user a short table:
   NEW files, PATCH (adds lines to .gitignore / .gitattributes / project.godot autoloads, settings and
   input actions / `.claude/settings.json` allow rules / git hooks path),
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
   looks. Fix anything red before you finish. On an upgrade, `lint` may fail on the
   project's existing code (usually global `randf()`): list the findings per rule and offer
   to fix them; mark only cosmetic randomness `# lint: ok cosmetic`.

6. **Read back** `docs/design.md` once: the frame table, the notes it adds (what web,
   mobile, touch or pixel art mean for the code) and the design lists. If the pitch line in
   CLAUDE.md reads oddly, shorten it there. Don't pad CLAUDE.md; it must stay < 5 KB.

7. **Commit.** If the suites are green and this is a git repo, ask once (AskUserQuestion:
   "Commit the setup now?" Yes / Not now). Yes: `git add -A && git commit -m "Set up godot-claude-kit"`
   (the pre-commit hook runs the parse check). A missing git identity: show the doctor's fix line.

8. **Report** briefly in the user's language: what was created, what was kept, test
   results, and the next steps:
   - with `starter`: open the project in Godot and press Play (F5) (multiplayer on one
     machine: Debug → Customize Run Instances → 2 instances);
   - the first round: the "First playable" list in `docs/design.md`, as tasks for
     `/godot-round` (offer to start it); answer the open questions by playing, not planning;
   - with `ci`: push to GitHub and the suites run on every push;
   - give every new script a one-line `##` doc comment (it feeds `docs/code_map.md`);
   - several tasks at once: `/godot-round <tasks>`; one task: work in a worktree
     (`tools/dev/new_worktree.sh <name>`);
   - read `${CLAUDE_PLUGIN_ROOT}/STRATEGY.md` for the why behind each piece.

## Notes

- Files written once and then owned by the project (never `DIFFERS`, never overwritten):
  the starter scenes, `README.md`, `docs/design.md`, `.editorconfig` (Godot's own default
  one is replaced), the build number and patch notes. Change them freely.
- `.claude/settings.json` gets allow rules for the test runner, code map, worktree scripts and
  read-only git (merged into an existing file; nothing removed), so agents in a round
  don't stall on permission prompts.

- `window-guard` lives in the plugin (hook `hooks/hooks.json`); the module only switches
  it on for this project. Toggle with `/godot-windows on|off|status`.
- `build-release` needs a main scene and the export templates before the first real
  release; `tools/build_release.sh --check` says what is missing.

- Multiplayer scaffold: `autoload/network.gd` (ENet host/join, peer 1 = server, a
  validated `any_peer` RPC and a full-state roster sync for late joiners, `--host` /
  `--join` dev flags) and `tests/net/` (two headless processes). It is a starting point;
  adapt it rather than building a second one.
- Templates are in `${CLAUDE_PLUGIN_ROOT}/templates/project/`. Change the kit there, not in
  generated files, if a template is wrong.
