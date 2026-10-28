---
name: godot-round
description: Run a round of several tasks in a Godot project end to end — plan by file ownership, implement each task in its own git worktree with the implementer agent, review with the reviewer agent, merge, run the full regression, commit, hand off. Use when the user hands over more than one or two tasks at once, or says "round"/"new round".
argument-hint: "[the tasks, one per line or numbered]"
---

# Round: from a task list to merged, tested commits

On Windows, if `python3` is missing or opens the Microsoft Store, use `python` (or `py`)
instead in every command below; shell commands run in Git Bash.

Tasks typed after the command (`/godot-round fix the jump; add a pause menu`) are the task
list; without them, ask for it.

Answer the user in their language. Plans and handoffs may be in their language;
code, branch names and commit messages are English.

Agents: use the project's own `implementer` / `reviewer` agents if
`.claude/agents/implementer.md` exists, otherwise the plugin's
`godot-claude-kit:implementer` / `godot-claude-kit:reviewer`.

Prerequisites (if missing, offer `/godot-analyse` or `godot-start`):
`tools/dev/new_worktree.sh`, `tools/dev/finish_worktree.sh`, `tools/test_runner.py`.
Without them, create worktrees with `git worktree add -b task/<name> .claude/worktrees/<name>`.

## 1. Plan (before any code)

1. Write the plan to `docs/rounds/<YYYY-MM-DD>-<slug>.md`: one line per task with the
   user's number, a short English task name (branch `task/<name>`), area, hot files it
   needs, suites to run, size (S/M/L).
2. Group into **waves**: in one wave each hot file has at most one owner, and two tasks
   touching the same script/scene are merged into one task or put in different waves.
   Bugs and small UX fixes first, big content later. **At most 3 agents at once.**
3. **Ask once whether visible windows are allowed this round** (AskUserQuestion). Put
   `Windows: allowed` or `Windows: headless only` in every brief. Default: headless only
   (also when the user is away and didn't say).
4. Design decisions the user must make: write 2–3 concrete options with a
   recommendation and ask once, batched, before that wave. Don't block other waves.
   **The user is away** (asleep, at work, "just do it all"): don't wait. Pick the option
   you recommend, write it under `## Decisions (made while you were away; override any)`
   in the round doc with one line of why, and go on. The final report lists them first.
5. **Say how long it will take**: per wave and in total, plus the full regression
   (from `tests/integration/durations.json` or the last round doc). Separate building
   from running ("about 1 h to build; the test then takes 5–8 min per run").
6. Show the plan briefly, then start wave 1 unless the user asked to approve first.

## 2. Implement (parallel, per task)

- `tools/dev/new_worktree.sh <name>` per task (one after another; seconds each).
- **Batch small tasks:** several small fixes in one area go to ONE implementer (one
  branch). Every agent pays to load the project.
- **Model per task** (`model` on the Agent call):
  - `sonnet`: mechanical or well-specified work — splits/refactors, bug fixes with a
    known cause, text/data/balance, tests, docs. (Measured: a big file split cost
    ~135–190k tokens on Sonnet vs ~280–390k on Opus, same quality.)
  - inherit/Opus: new systems, netcode and sync design, bugs with unknown cause, content
    that needs design judgement.
  - Reviewers: `sonnet`, unless the branch is a large netcode system.
- **No broad audits by default.** A whole-project bug sweep (~250k tokens) only before a
  big playtest or when the user asks.
- One implementer per task (or batch), all in ONE message so they run in parallel. Brief:
  - worktree path and branch, task number, **the user's original text** verbatim plus
    your interpretation;
  - what you already know: files with line numbers, root-cause leads, out of scope —
    concrete pointers save the agent a whole search phase;
  - hot files it owns (or "none — use signals/new files");
  - `Windows: allowed` / `Windows: headless only`;
  - suites to run and which new test is expected;
  - commit attribution lines from the system reminder, if any.
- If main changes something running agents depend on, tell each one (SendMessage).
- Don't edit files agents own while they work. Plan the next wave instead.
- **Status in one line whenever you report**: done / not done, what is running, and
  roughly when it ends. The user should never have to ask "done?".

## 3. Review and merge (as each branch finishes)

1. Spawn a reviewer (`model: sonnet`) with the worktree path, task number, the
   `Windows:` line and the user's original text — not the implementer's summary.
2. `MERGE AFTER FIXES` / `REWORK`: send the findings to the same implementer while its
   context is warm (< 1 h). After a longer pause start a NEW implementer with a short
   brief (resuming a 300k-token agent with a cold cache is very expensive). Don't fix
   it yourself in the main checkout.
3. **Before merging a broad branch** (it removes or renames functions, statics, signals
   or files, or touches many gameplay scripts), check what the branch's own suites miss.
   Each miss found after the merge costs a full regression (~20 min in a real project):
   - grep `tests/` and `tools/` for every removed or renamed name (`git diff main...HEAD`
     lines starting with `-`). `tests/` is ignored by Godot, so the parse check never
     sees a test that calls something that is gone; the suite just hangs or fails;
   - run the `perf` suites if it touches code that runs every frame;
   - `git -C <worktree> status --short --ignored tests/`: a file the tests need that
     shows `!!` is ignored and will be missing on main; add a `!` line to `tests/.gitignore`.
4. `MERGE`: `tools/dev/finish_worktree.sh <name>` from the main checkout. On conflicts,
   keep both sides' intent and run the affected suites. Then stop that branch's agents
   (TaskStop) if any still run: a finished agent left waiting on a monitor still costs.

## 4. Close the wave

1. Full regression on the merged result: `python3 -I tools/test_runner.py` (background).
   Fix red suites before the next wave builds on top.
2. Update the round doc (status per task) and `docs/status.md` if a milestone finished.
3. Scripts added/moved: `python3 -I tools/dev/code_map.py`, commit the map.

## 5. Close the round

- Write a handoff at the bottom of the round doc (merged, open, next steps) and suggest
  `/clear`: a long session re-reads its whole history every turn; a fresh session from
  the handoff is much cheaper.
- Final report in the user's language: decisions made while they were away (if any),
  per task done / partly / not done, what to test by hand (eyes, feel), decisions still
  open. Files the user should open (builds, previews, logs) as full clickable links
  (`[name](file:///abs/path)`), never relative paths or code spans.
- Add one line to the round doc on what slowed the round down, if anything did (a test
  that missed a bug, a slow suite, a brief that sent an agent searching). The next plan
  reads it; that is how the workflow gets faster.
