# Module: smooth-motion

TL;DR: physics runs at 60 Hz, screens draw at 120–240 Hz. Bodies moved in
`_physics_process` then judder (the same position for 2–4 frames), and on
clients synced transforms arrive in steps. Put the visuals under a
{{#3D}}`VisualSmoother`{{/3D}}{{^3D}}`VisualSmoother2D`{{/3D}} and they move every drawn frame.

## Use

```
Player ({{#3D}}CharacterBody3D{{/3D}}{{^3D}}CharacterBody2D{{/3D}}, moved in _physics_process, synced)
├── CollisionShape
└── {{#3D}}VisualSmoother{{/3D}}{{^3D}}VisualSmoother2D{{/3D}}          (scripts/components/{{#3D}}visual_smoother.gd{{/3D}}{{^3D}}visual_smoother_2d.gd{{/3D}})
    ├── Model / Sprite
    └── Camera rig     (the camera follows the smoothed visual, not the body)
```

- Host / single player: interpolates between the last two physics ticks
  (`Engine.get_physics_interpolation_fraction()`); trails by at most one tick.
- Client: eases toward the synced transform (`position_speed`, `rotation_speed`).
- Teleports: gaps over `snap_distance` snap; call `snap()` after a respawn. With the
  starter Player: `player.teleported.connect(smoother.snap)` (fires on every peer).
- Logic, hit detection and networking use the body. Never read the visual.
- Godot's built-in physics interpolation is turned off for this node (it would
  interpolate twice); you may leave the project setting on for other nodes.

## Test

`python3 -I tools/test_runner.py smooth` runs `tests/smooth/test_smooth.gd`
with `--fixed-fps 240` (tagged `exclusive`, runs alone): the visual and the
camera must move on ≥ 90 % of drawn frames and stay within one tick of the
body; client mode must ease, converge and snap.
