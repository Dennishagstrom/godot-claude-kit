# Development workflow: fast and safe

TL;DR: one task = one branch + worktree; split work by files, not themes; agents
test narrowly, the main session runs one full regression per round; nothing merges
without a test and a review.

## 1. One task = one branch + one worktree

```bash
tools/dev/new_worktree.sh jump     # .claude/worktrees/jump on branch task/jump (import cache copied)
tools/dev/finish_worktree.sh jump  # merge --no-ff, remove worktree and branch
```

- Agents work ONLY in their worktree and commit on their branch. The main session merges.
- `.claude/.gdignore` stops the main project from scanning the worktree copies
  (duplicate `class_name` errors otherwise).

## 2. Split work by files, not by theme

- **Hot files** (big shared scripts like a game-state autoload) have one owner at a
  time. Other tasks hook in through signals (`Events`) and new files.
- When a hot file grows, split it into a hub + modules (`Game.<module>.<func>()`), so
  two tasks can own two modules at the same time.
- New scenes, scripts and data are safe to create in parallel.

## 3. Test pyramid

| Level | Who | What | Time |
|---|---|---|---|
| Parse check | everyone, always | `tests/parse_check.gd` compiles every script (runner + pre-commit) | seconds |
| Targeted | the agent | only its own suites + the closest existing ones (named in the brief) | 1–3 min |
| New feature | the agent | new suite in `suites.txt`{{#MULTIPLAYER}}; host + client for anything synced{{/MULTIPLAYER}} | part of "done" |
| Visual | the user | agents write what to check by eye in `docs/testliste.md` (no windows unless allowed) | – |
| Full regression | main session | `python3 -I tools/test_runner.py` after merging a round | minutes |

- Three agents each running the full suite collide on ports and CPU and triple the
  wait. One full regression after all merges covers it.
- Flaky tests are bugs: wait on state, not frame counts. Fix them at once.

## 4. Quality gate before merging

1. Parse check and targeted suites are green; the new test exists and is green.
2. The diff is reviewed (the `reviewer` agent says `MERGE`): correctness{{#MULTIPLAYER}}, server
   authority, RPC validation, late join{{/MULTIPLAYER}}, conventions, performance.
3. Docs updated (the system's doc, the code map if scripts moved).

## 5. Commits

`[#<task>] <imperative summary>`, one branch per task, merged with `--no-ff`, so a
task can be found and reverted alone (`git revert -m 1 <merge>`).
