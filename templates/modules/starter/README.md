# Module: starter

TL;DR: a new project gets a game you can run at once: main menu → world →
player moving on the input actions{{#MULTIPLAYER}}, host and join included{{/MULTIPLAYER}}. These files are
yours from the first commit: change or replace them; the kit never touches them again.

## Files

```
scenes/main/main.tscn     Main (application/run/main_scene): menu <-> world flow{{#MULTIPLAYER}}, Network signals{{/MULTIPLAYER}}
scenes/menu/main_menu.*   MainMenu: {{#MULTIPLAYER}}name, Host, Join (address[:port]){{/MULTIPLAYER}}{{^MULTIPLAYER}}Play{{/MULTIPLAYER}}, Quit; emits signals, does nothing itself
scenes/world/world.*      World: {{#3D}}floor, sun, sky, camera{{/3D}}{{^3D}}camera{{/3D}}, Players{{#MULTIPLAYER}}, PlayerSpawner{{/MULTIPLAYER}}
scenes/player/player.*    Player ({{#3D}}CharacterBody3D{{/3D}}{{^3D}}CharacterBody2D, top-down{{/3D}}): move_*{{#3D}}, jump{{/3D}}{{#MULTIPLAYER}}, Sync (position){{/MULTIPLAYER}}
default_bus_layout.tres   audio buses Master, Music, SFX
assets/README.md          where art, audio and fonts go
```

Project settings (added only when missing): main scene, input actions
`move_left/right/up/down`, `jump`, `interact`, `pause` (keyboard WASD/arrows +
gamepad), window 1280×720 with `canvas_items` stretch, and a warning for
untyped declarations (`debug/gdscript/warnings/untyped_declaration`).
{{#MULTIPLAYER}}
## Multiplayer flow

- Host / Join → `Network.hosted` / `joined` → Main loads the World.
- The server adds one Player per `Network.players` entry (on `roster_changed`),
  named `str(peer_id)`; `PlayerSpawner` creates them on the clients. Players
  who leave are freed, the spawner removes them everywhere.
- Server authority: the owning peer sends `_send_input` every physics tick
  (unreliable); the server checks the sender, simulates, and `Sync` replicates
  `position`. Add new synced properties to `Sync`, new input to `_send_input`.
- Pause (Esc / Start) leaves the session → back to the menu.
{{/MULTIPLAYER}}
## Grow it

- New feature = `scenes/<feature>/` with its `.tscn` and `.gd` together.
- Keep Main thin: it only switches scenes. Game rules go in the World or their own nodes.
- Pixel art (2D): Project Settings → Rendering → Textures → Default Texture Filter = Nearest.
- Not a top-down game? Change `_simulate()` in player.gd; the tests only need move_right to move it right.

## Test

`python3 -I tools/test_runner.py starter`: `test_starter.gd` runs the real main
scene in one process (menu → world → move_right moves the player → pause → menu){{#MULTIPLAYER}};
`run_starter_net.sh` runs host and client in two processes and checks the client's
input moves its player on the server and back on the client{{/MULTIPLAYER}}. Change the tests
with the scenes when you change the flow.
