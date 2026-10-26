# {{GAME_NAME}}

{{GENRE}} — a {{DIMENSION}} game in **Godot {{GODOT_VERSION}}** with **GDScript**{{#MULTIPLAYER}}, co-op/multiplayer for up to {{MAX_PLAYERS}} players{{/MULTIPLAYER}}. Talk to the user in their language; code, file names and comments are in English.

This file loads on every turn of every agent: keep it < 5 KB. Details live in the docs; read only the section you need.

## Where to look

- `docs/code_map.md`: every script, its class, size and purpose. Grep it before searching the tree.
- `docs/dev_reference.md`: run/test commands, tools, systems. `docs/status.md`: milestones.
- `docs/dev_workflow.md`: branches, worktrees, review. `docs/rounds/`: round plans and handoffs.
- Large docs start with a TL;DR and a section index: read that first.

## Rules that are never optional

1. **Player text is {{TEXT_LANGUAGE}}** and goes through translation: `tr("...")` in code, auto-translate on Controls.
{{#MULTIPLAYER}}2. **Multiplayer from day one.** Done = works host + client. Single player is a host without clients.
3. **The server decides.** Peer 1 is host/server and simulates physics, AI, damage, game state. Clients send input/requests and show what they receive.
4. **Validate every RPC on the server**: sender (`multiplayer.get_remote_sender_id()`), ownership, distance, cooldown, ranges.
5. **Late joiners** get the full current state, not only deltas.
{{/MULTIPLAYER}}{{^MULTIPLAYER}}2. **Small first, then extend.** Build the smallest playable version of an idea, test it, iterate.
{{/MULTIPLAYER}}
{{#MULTIPLAYER}}## Network architecture

- Autoload `Network` (autoload/network.gd): ENet host/join (port {{DEFAULT_PORT}}), roster, `adopt_peer()` for other transports.
- Continuous state via `MultiplayerSynchronizer`, events via `@rpc`; no per-frame reliable RPCs.
- Only the server instantiates (`MultiplayerSpawner`). Player nodes are named `str(peer_id)`; the client owns only its input node.
- Physics runs on the server; clients `freeze = true` and get the transform synced.
- RPC declarations match on every peer: after a split, `@rpc` and synced properties stay on the owner node.

{{/MULTIPLAYER}}## Code conventions

- Static types everywhere. `snake_case` files/functions/vars, `PascalCase` classes/nodes, `UPPER_SNAKE` constants. `class_name` on reusable types, **not on autoloads**.
- Script order: class_name/extends → one-line `##` doc comment (feeds the code map) → signals → enums/consts → @export → vars → private `_vars` → @onready → built-ins → public → private.
- Signals up, calls down; global events via `Events`. No magic numbers (`@export`, constants, `data/`). Input via actions; never hardcode keys.
- Logic never depends on node names of visuals.
- **No script over 800 lines**: extract a helper (RefCounted with a back-reference) or a child component; public API stays as forwarders.

## Run and test

```bash
python3 -I tools/test_runner.py --changed   # while working: parse check + suites the diff touches
python3 -I tools/test_runner.py net core    # chosen tags or suites
python3 -I tools/test_runner.py             # full regression (after merging a round)
```

New behaviour = new suite in `tests/<area>/` + a line in `tests/integration/suites.txt`; new folders get a `CHANGE_TAGS` line. Wait on state (count physics ticks), never wall clock. Godot: `$GODOT` (`tools/dev/godot_env.sh`).

**Visible windows:** ask the user before opening any Godot window. Until they say yes: headless only (`--headless --audio-driver Dummy`).
{{#MODULES}}
## Kit modules (`docs/modules/<name>.md`)

{{MODULE_CLAUDE_MD}}
{{/MODULES}}
## Workflow

One task = one branch + worktree (`tools/dev/new_worktree.sh <name>` / `finish_worktree.sh`). Several tasks: the `round` skill with the `implementer` and `reviewer` agents. Commits `[#<task>] <what>`, merged `--no-ff`. Hot files (one owner at a time): list them here.

Token discipline: grep, then read big files in parts; agent reports ≤ 40 lines; briefs point at `file:line`.
