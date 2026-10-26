---
name: godot-analyse
description: Analyse an existing Godot 4 project for working well with Claude Code (script sizes and split seams, CLAUDE.md token cost, docs without summaries, tests and runner, git workflow/hooks/agents, multiplayer authority and RPC validation, typing, hardcoded UI text, node-name coupling) and write a prioritised action list to docs/claude_kit_analysis.md. Read-only until the user picks items to apply. Use when the user asks what to improve, wants an audit/analysis of their Godot project, or wants to adopt the kit in an existing project.
---

# godot-analyse: cheap analysis of an existing Godot project

Answer the user in their language. The report file is English.

**Keep it token-cheap.** The bundled script measures everything; you read its summary
and the report, not the code. Do not read source files during the analysis except to
double-check one or two surprising findings (with Grep / Read `offset`+`limit`).

## 1. Measure (read-only)

```bash
python3 -I ${CLAUDE_PLUGIN_ROOT}/scripts/analyse.py --target . --out docs/claude_kit_analysis.md
```

It writes only `docs/claude_kit_analysis.md` (ask first if that file exists and was not
written by the kit). It prints a ~15-line summary with the numbered action list.

## 2. Sanity-check

Read the report's sections 7 (multiplayer) and 10 (actions). For RPC findings, open the
flagged lines (a few lines each) to confirm before you present them: the heuristics can
miss a validation helper with an unusual name. Correct the report if a finding is wrong
(say so in the report). Don't run broad audits beyond this.

## 3. Present

In the user's language, short: 3–6 key findings with numbers (file:line where it
matters), then the action table (number, action, impact, effort). Give the report path.
Then ask: **"Which items should I apply? (e.g. 1, 3, 4)"**.

## 4. Apply chosen items (adapt, never blind-copy)

First run `python3 -I ${CLAUDE_PLUGIN_ROOT}/scripts/scaffold.py detect --target .` and
respect what exists: existing folders, test framework (GUT/gdUnit4), naming, CLAUDE.md
language and content. For items marked `Kit: <group>`:

- Run `scaffold.py plan --target . --only <group> --answers '<json>'` (ask for the answers
  the group needs: game name, multiplayer, text language; reuse saved ones). Show NEW /
  DIFFERS; never overwrite a differing file without a yes.
- `claude_md`: don't replace their CLAUDE.md. Restructure it: keep rules and add "where
  to look" pointers; move run/test details to `docs/dev_reference.md` and milestones to
  `docs/status.md` (create them from the kit's `docs` group). Target < 5 KB. Show the
  before/after size.
- `tests`: install the runner + parse check + smoke suite, then register their existing
  tests in `tests/integration/suites.txt` (one line per test/scene; GUT/gdUnit4 via
  their CLI) and add `CHANGE_TAGS` lines for their folders. Run `--quick` headless.
- `code_map`, `hooks`, `worktrees`, `agents`: apply the group, then adjust paths in the
  generated files to the project's folders (e.g. code_map `EXCLUDE`, hook path filters).
  For `agents`, add the project's own rules (hot files, conventions) to the copies.

Manual items (splits, RPC validation, flaky tests, TL;DRs, tr()): these are code changes.
For more than one or two, use the `round` skill (worktree + implementer + reviewer per
task; Sonnet for mechanical work like splits and TL;DRs). For a split, the brief must
include: pure refactor, RefCounted helper with back-reference created in `_init`, all
`@rpc` functions and synced properties stay on the owner node, public API as one-line
forwarders, grep string-named calls (`call(&"x")`, `has_method`, `Callable(obj, "x")`,
`rpc("x")`, `connect("x")`) before moving, run the file's suites before and after.

Visible Godot windows: never, unless the user allows it. Tests run headless.

## 5. Finish

Re-run the analyser to show the before/after numbers for what was applied, and suggest
committing (one commit per applied item is easiest to review).
