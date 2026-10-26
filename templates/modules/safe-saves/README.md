# Module: safe-saves

TL;DR: tests and tools must never overwrite the player's saves or settings,
and a crash during a save must not lose the file. `SaveSlots` puts every save
under `user://saves/<slot>/`, headless runs get a throwaway slot, and
`Settings` refuses to write the player's settings file when headless.

## SaveSlots (autoload)

- Slot: `default` for players; `--save=<slot>` picks another (tests, tools,
  worlds); headless and `-s` script runs without `--save` use `headless`.
- `SaveSlots.path("world.json")`, `save_json(file, data)`, `load_json(file, fallback)`,
  `exists`, `delete_file`, `list_slots`.
- Atomic writes: temp file, old file → `.bak`, rename. A corrupt file loads its backup.
- Parallel tests: give each suite its own `--save=<slot>`; the runner locks
  slots, so two suites with the same slot never run at once.

## Settings (autoload skeleton)

- `DEFAULTS` holds every setting and its type; `RANGES` clamps numbers.
  `set_value(key, value)` clamps, applies (`_apply`), saves (deferred) and emits `changed`.
- Bindings: `rebind(action, event, pad)`, `reset_bindings()`; only actions that
  differ from project.godot are stored.
- Headless: defaults only, and `save_settings()` is a no-op for
  `user://settings.cfg`. A test that saves calls `load_settings("user://<own>.cfg")` first.
- `get_action_label(action)`: "Q", "LMB", "A" / "✕", "LT" for the last used
  device. Never hardcode key names in UI text.
- Extend it: add keys to `DEFAULTS` (+ `RANGES`) and a `match` arm in `_apply`.

## Tests

`python3 -I tools/test_runner.py saves`: the throwaway slot and a forced slot,
atomic save + backup rescue, the headless settings guard, labels for keyboard and pad.
