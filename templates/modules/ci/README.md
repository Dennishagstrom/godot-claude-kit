# Module: ci

TL;DR: `.github/workflows/test.yml` runs `tools/test_runner.py` (every suite,
headless) on GitHub Actions on each push and pull request, so a broken merge
shows up on GitHub even when nobody ran the tests locally.

- Godot: `GODOT_VERSION` at the top of the workflow ({{GODOT_RELEASE}} when the kit
  wrote it). Keep it equal to the editor version you use.
- Runs on `ubuntu-latest`. Suites that need tools CI lacks skip themselves
  (Blender, GodotSteam); perf budgets are reported, not asserted (`CI=true`).
- A failed run uploads `tests/integration/suite/` (the suite logs) as an
  artifact: `gh run download <run id>` or the run's page on GitHub.
- Private repos spend Actions minutes (free tier: 2000 per month); a run takes a
  few minutes. Remove the file or limit `on:` if you don't want that.
