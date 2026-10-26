# {{GAME_NAME}}

{{GENRE}} — a {{DIMENSION}} game in **Godot {{GODOT_VERSION}}** with **GDScript**{{#MULTIPLAYER}}, co-op/multiplayer for up to {{MAX_PLAYERS}} players{{/MULTIPLAYER}}. Talk to the user in their language; code, file names and comments are in English.

This file loads on every turn of every agent: keep it short (< 5 KB). Details live in the docs below; read only the section you need.

## Where to look

- `docs/code_map.md`: every script, its class, size and purpose. Grep it before searching the tree.
- `docs/dev_reference.md`: run/test commands, tools, system notes. `docs/status.md`: milestones.
- `docs/dev_workflow.md`: branches, worktrees, tests, review. `docs/rounds/`: round plans and handoffs.
- Large docs start with a TL;DR and a section index: read that first.

## Rules that are never optional

1. **Player text is {{TEXT_LANGUAGE}}** and always goes through translation: `tr("...")` in code, auto-translate on Controls. No hardcoded player-facing strings.
{{#MULTIPLAYER}}2. **Multiplayer from day one.** A feature is done when it works host + client. Single player is a host without clients.
3. **The server decides.** Peer 1 is the host/server and simulates physics, AI, damage and game state. Clients send input/requests and show what they receive.
4. **Validate every RPC on the server**: sender id (`multiplayer.get_remote_sender_id()`), ownership, distance, cooldown, ranges. Never trust client data.
5. **Late joiners** must get the full current state (send full state on join, not only deltas).
{{/MULTIPLAYER}}{{^MULTIPLAYER}}2. **Small first, then extend.** Build the smallest playable version of an idea, test it, iterate.
{{/MULTIPLAYER}}
{{#MULTIPLAYER}}## Network architecture

- `ENetMultiplayerPeer`, host/join by IP (port {{DEFAULT_PORT}}). Autoload `Network` (autoload/network.gd) owns the connection and the roster.
- Continuous state (position, HP) via `MultiplayerSynchronizer`; events (abilities, hits, sounds) via `@rpc`. No per-frame RPCs.
- `MultiplayerSpawner` spawns players/enemies/objects; only the server instantiates. Player nodes are named `str(peer_id)`; the client owns only its input node (`set_multiplayer_authority(peer_id)`).
- Physics bodies simulate on the server only; on clients `freeze = true` and the transform comes from the synchronizer.
- RPC declarations must match on every peer (same functions, same order). After splitting a script, keep all `@rpc` and synced properties on the owner node.

{{/MULTIPLAYER}}## Code conventions

- Static types everywhere (`var speed: float = 5.0`, `func hit(amount: int) -> void:`).
- `snake_case` files/functions/vars, `PascalCase` classes/nodes, `UPPER_SNAKE` constants. `class_name` on reusable types, but **not on autoloads**.
- Script order: class_name/extends → doc comment (`##`, one line, shown in the code map) → signals → enums/consts → @export → public vars → private `_vars` → @onready → built-ins → public → private.
- Signals up, method calls down; global events via the `Events` autoload.
- No magic numbers: `@export`, constants or Resources in `data/`. Input through actions in project.godot; never hardcode keys.
- Logic never depends on mesh or node names of visuals (visual scenes are swappable).
- **No script over 800 lines.** Before adding to a big file, extract a helper (RefCounted with a back-reference) or a child component. Public API stays as one-line forwarders on the owner.

## Run and test

```bash
python3 -I tools/test_runner.py --changed   # while working: parse check + suites touched by the diff
python3 -I tools/test_runner.py net core    # chosen tags or suites
python3 -I tools/test_runner.py             # full regression (after merging a round)
```

New behaviour = new suite in `tests/<area>/`, registered in `tests/integration/suites.txt`{{#MULTIPLAYER}}; anything synced gets a host + client test{{/MULTIPLAYER}}. New folders get a `CHANGE_TAGS` line in `tools/test_runner.py`. Wait on state, not frame counts. Godot binary: `$GODOT` or see `tools/dev/godot_env.sh`.

**Visible windows:** ask the user before opening any Godot window. Until they say yes: headless only (`--headless --audio-driver Dummy`, also for `--import`).

## Workflow

One task = one branch + worktree (`tools/dev/new_worktree.sh <name>`, `tools/dev/finish_worktree.sh <name>`). Several tasks at once: the `round` skill with the `implementer` and `reviewer` agents (`.claude/`). Commits: `[#<task>] <what>`, merged with `--no-ff`. Hot files (one owner at a time): list them here when they appear.

Token discipline: grep, then read big files in parts (`offset`/`limit`); agent reports ≤ 40 lines; point at `file:line` in briefs.
