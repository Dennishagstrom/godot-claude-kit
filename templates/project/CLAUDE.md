# {{GAME_NAME}}

{{PITCH}}. A {{DIMENSION}} game in **Godot {{GODOT_VERSION}}** with **GDScript**{{#MULTIPLAYER}}, online for up to {{MAX_PLAYERS}} players{{/MULTIPLAYER}}. Talk to the user in their language; code, file names and comments are in English.
{{FRAME_CLAUDE_MD}}

Loads on every agent turn: keep it < 5 KB. Details in docs/ (TL;DR on top): read only the section you need.

## Where to look

- `docs/code_map.md`: every script and its purpose; grep it before searching the tree.
- `docs/design.md`: pitch, frame, core loop, scope. `docs/status.md`: milestones.
- `docs/dev_reference.md`: run/test commands, layout, tools, systems.
- `docs/dev_workflow.md`: branches, worktrees, review. `docs/rounds/`: round plans and handoffs.

## Rules that are never optional

1. **Player text is {{TEXT_LANGUAGE}}** and goes through translation: `tr("...")` in code, auto-translate on Controls.
{{#MULTIPLAYER}}2. **Multiplayer from day one.** Done = works host + client. Single player is a host without clients.
3. **The server decides.** Peer 1 (host) simulates physics, AI, damage and state; clients send input and show what they receive.
4. **Validate every RPC on the server**: sender (`multiplayer.get_remote_sender_id()`), ownership, distance, cooldown, ranges.
5. **Late joiners** get the full state (`Network.register_state()` + a test). Jumps: `teleport()`.
{{/MULTIPLAYER}}{{^MULTIPLAYER}}2. **Small first, then extend.** Build the smallest playable version of an idea, test it, iterate.
{{/MULTIPLAYER}}
{{#MULTIPLAYER}}## Network architecture

- Autoload `Network`: ENet host/join (port {{DEFAULT_PORT}}), roster, `adopt_peer()` for other transports.
- Continuous state via `MultiplayerSynchronizer`, events via `@rpc`; no per-frame reliable RPCs.
- Only the server instantiates (`MultiplayerSpawner`). Player nodes are named `str(peer_id)`; the client owns only its input node.
- Physics runs on the server; clients `freeze = true` and get the transform synced.
- After a split, `@rpc` and synced properties stay on the owner node (`tools/dev/rpc_check.py`).

{{/MULTIPLAYER}}## Code conventions

- Layout: `scenes/<feature>/` (its .tscn + .gd), shared code `scripts/<area>/`, `assets/`, `data/`.
- Static types. `snake_case` files/functions/vars, `PascalCase` classes/nodes, `UPPER_SNAKE` constants. `class_name` on reusable types, **not on autoloads**.
- Script order: extends → `##` doc line → signals → enums/consts → @export → vars → @onready → built-ins → public → private.
- Signals up, calls down; global events via `Events`. No magic numbers (`@export`, constants, `data/`). Input via actions; never hardcode keys.
- Logic never depends on node names of visuals. Randomness: `Rng.stream(&"<system>")`, never `randf()`.
- Suite `lint` (also pre-commit) enforces the pitfalls in `docs/dev_reference.md`: read them once.
- **No script over 800 lines**: split into helpers (RefCounted + back-reference) or components; the public API stays as forwarders.

## Run and test

```bash
python3 -I tools/test_runner.py --changed   # while working: the suites the diff touches
python3 -I tools/test_runner.py net core    # chosen tags or suites
python3 -I tools/test_runner.py             # everything (after merging a round)
```

New behaviour = new suite in `tests/<area>/` + a line in `tests/integration/suites.txt`; new folders: a `CHANGE_TAGS` line. Wait on state (count physics ticks), never wall clock. Godot: `$GODOT` (`tools/dev/godot_env.sh`). Windows: Git Bash; `python` if `python3` is missing.

**Visible windows:** ask the user before opening any Godot window; until then headless only (`--headless --audio-driver Dummy`).{{#MOD_WINDOW_GUARD}} A hook enforces it (`/godot-windows on`).{{/MOD_WINDOW_GUARD}}
{{#MODULES}}
## Kit modules (`docs/modules/<name>.md`)

{{MODULE_CLAUDE_MD}}
{{/MODULES}}
## Workflow

One task = one branch + worktree (`tools/dev/new_worktree.sh <name>` / `finish_worktree.sh`). Several tasks: `/godot-round`. Commits `[#<task>] <what>`, merged `--no-ff`. Hot files (one owner at a time): list them here.

Token discipline: grep, then read big files in parts; agent reports ≤ 40 lines; briefs point at `file:line`.
To the user: how long a long job takes, whether you're done; files to open as `file:///abs/path` links.
