# Module: sandbox

TL;DR: a training arena for feel and balance work. `-- --sandbox` starts a
flat arena with an F1 panel: time scale, no cooldowns, god mode, spawn and
clear. Anything else registers itself, so the sandbox never reaches into
private game code.

## Start

```bash
"$GODOT" --path . -- --sandbox          # visible window: ask the user first
{{#MULTIPLAYER}}"$GODOT" --path . -- --sandbox --port=7777   # hosts; friends join as usual
{{/MULTIPLAYER}}```

`autoload/sandbox_boot.gd` replaces the current scene with a `Sandbox`
(`scenes/sandbox/sandbox.gd`) when the flag is present, and does nothing otherwise.

## Extend

```gdscript
Sandbox.register_spawnable(&"slime", func() -> Node: return SLIME_SCENE.instantiate())
Sandbox.register_button("Enemies", "Kill all", _kill_all)
Sandbox.register_toggle("Debug", "Show hitboxes", func(on: bool) -> void: _show_hitboxes = on)
```

- Game code reads cheats from `DevCheats` (`no_cooldowns`, `god_mode`).
- Requests go to the server and are validated there (known id, `MAX_SPAWNED`,
  clamped time scale){{#MULTIPLAYER}}; spawns replicate with a `MultiplayerSpawner`
  (custom spawn function, so factories work) and time scale reaches every peer{{/MULTIPLAYER}}.
- Panel text is dev-only English (not translated; `scenes/sandbox/` is in the
  l10n allowlist). F1 is read directly, not as an input action.
- The sandbox must never write real saves: run it with `--save=sandbox` if
  your game saves.

## Test

`python3 -I tools/test_runner.py sandbox` (runs with `--fixed-fps 60 -- --sandbox`):
boot, F1, a registered tool, time scale + clamp, cheats, spawn validation and cap, clear.
