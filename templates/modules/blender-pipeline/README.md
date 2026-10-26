# Module: blender-pipeline

TL;DR: models are short Python scripts that headless Blender turns into
`.glb` files. Claude can make and change props without anyone opening
Blender, every model shares one palette, and a `--preview` PNG shows the
result without a window.

## Use

```bash
tools/blender/build.sh                         # every model in tools/blender/models/
tools/blender/build.sh example_crate --preview # one model + tests/blender_previews/example_crate.png
tools/blender/build.sh 'prop_*' --no-import    # a glob; skip the Godot re-import
```

- Output: `assets/models/<name>.glb` (`OUT_DIR=` to change), then a headless
  `godot --import`. Previews go to `tests/blender_previews/` (git-ignored).
- Blender: `$BLENDER`, else `blender` on PATH, else the usual install paths.
  Always `--background --factory-startup`: no UI, no user add-ons.
- A new model: copy `models/example_crate.py`, build parts with
  `kit.box / cylinder / sphere / torus`, `kit.join`, `kit.mirror_x`,
  `kit.pivot_to_floor`, and end with `kit.run(build)`. Constants at the top,
  no magic numbers in the parts.
- `kit_base.PALETTE` (name -> hex) is the whole look. One material per colour,
  shared by name, so Godot batches the models.
- Conventions: metres, Z up in Blender, standing on z = 0, front = -Y (Godot +Z).
  Scenes put the glb inside a `*_visual.tscn`; logic never depends on mesh names.

## Test

`python3 -I tools/test_runner.py blender` builds the example into a scratch
folder with a preview and checks both files (passes as "skipped" without Blender).
Look at a preview by opening the PNG file, not by starting Blender.
