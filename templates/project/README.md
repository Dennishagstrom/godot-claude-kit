# {{GAME_NAME}}

{{PITCH}}. A {{DIMENSION}} game made with Godot {{GODOT_VERSION}}{{#MULTIPLAYER}}, for up to {{MAX_PLAYERS}} players online{{/MULTIPLAYER}}.

## Play / develop

- Open the folder in Godot {{GODOT_VERSION}} and press Play (F5){{#MULTIPLAYER}}. To test multiplayer
  on one machine: Debug → Customize Run Instances → 2 instances; one hosts, the
  other joins `127.0.0.1`{{/MULTIPLAYER}}.
- Needs Python 3.8+, git and bash (Windows: Git Bash) for the tools and tests.

## Tests

```bash
python3 -I tools/test_runner.py            # every suite, headless (about a minute)
python3 -I tools/test_runner.py --changed  # only what your changes touch
```

Godot is found automatically, or set `GODOT=/path/to/godot` (Windows: the `*_console.exe`).

## Layout

| Folder | What |
|---|---|
| `scenes/<feature>/` | a feature's scenes and their scripts, side by side |
| `scripts/<area>/` | shared code that is not one scene's (components, net, data types) |
| `autoload/` | singletons (Events{{#MULTIPLAYER}}, Network{{/MULTIPLAYER}}) |
| `assets/` | imported art, audio, fonts |
| `data/` | game data (tables, resources) |
| `tests/` | test suites, listed in `tests/integration/suites.txt` |
| `tools/` | test runner, dev scripts{{#MOD_BUILD_RELEASE}}, `build_release.sh`{{/MOD_BUILD_RELEASE}} |
| `docs/` | design, reference, status, workflow |

Working with Claude Code: `CLAUDE.md` and `docs/dev_workflow.md`.
