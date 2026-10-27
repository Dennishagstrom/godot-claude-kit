# Module: blender-pipeline

TL;DR: models are short Python scripts that headless Blender turns into `.glb` files.
Claude can make and change models without anyone opening Blender, every model shares one
palette and material, and `--preview` renders a contact sheet (four views, a player-size
figure) that Claude looks at before calling a model done. Other ways in (Blender by hand,
live Blender over MCP, packs) are in `docs/modules/model-import.md`; all of them meet the
same checks.

## Use

```bash
tools/blender/build.sh                          # every model in tools/blender/models/
tools/blender/build.sh example_lamp --preview   # one model + tests/blender_previews/example_lamp.png
tools/blender/build.sh 'prop_*' --no-import     # a glob; skip the Godot re-import
```

- Output: `assets/models/<name>.glb` (`OUT_DIR=` to change), then the model check
  (`tools/dev/asset_check.py`) and a headless `godot --import`. Sheets go to
  `tests/blender_previews/` (git-ignored, not imported by Godot).
- Blender: `$BLENDER`, else `blender` on PATH, else the usual install paths. Always
  `--background --factory-startup`: no UI, no user add-ons, the same result on every machine.
- The build prints `PARTS`, `JOINT` (part, parent, joint position), `BOUNDS`, `TRIS`, `MATERIALS`.

## Making a model that looks made, not assembled

Copy `models/example_crate.py` (a prop) or `models/example_lamp.py` (moving parts). Work in
this order and look at the sheet after each step:

1. **Silhouette.** Most of the read comes from the outline. `kit_shapes.lathe` (spun
   profiles: posts, bottles, bowls, shades) and `kit_shapes.extrude` (drawn outlines: signs,
   blades, brackets) beat stacks of boxes.
2. **Edges.** Nothing real has razor edges: `bevel=` on `kit.box`/`kit.cylinder`
   (`segments=` > 1 rounds it). Then trim: `plank_panel`, `band` (with rivets), `rivets`,
   `rock`, `crystal`, `rounded` (subdivision for soft forms), `array`.
3. **Colour.** `colour=` names a `kit_base.PALETTE` entry. `paint` shades each part lighter
   on top and darker below (`SHADE`); `metal=True` uses the metal material. `kit.glow(obj, "#FFD089")`
   for the one thing that gives light. Change `PALETTE` to restyle every model.
4. **Hand-made.** `shapes.jitter(seed)` gives planks and rocks a small fixed wobble: the same
   model on every build, but not machine-perfect.

Constants on top, no magic numbers in the parts. Budgets and style: `docs/art_style.md`.

## Contact sheet

`--preview` writes one PNG: **front | side** on top, **top | three-quarter** below. The
orthographic views have a grey figure of the player's height (`KIT_REFERENCE_HEIGHT`,
default 1.75 m) beside the model; the three-quarter view shows the model alone, large.
Check: does the front face the camera in "front", is the size right next to the figure, do
parts float or poke through, does it read at the size it will have on screen?
Open the PNG file; never start Blender to look.

## Moving parts (no rig needed)

Give each moving part its origin at the joint it turns around and hang it under its
parent: `kit.origin_to(part, joint)`, `kit.attach(child, parent)`. In Godot the glb keeps
the hierarchy, so the model's `*_visual.gd` turns `lamp_arm_lower.rotation.x` and the arm
swings about the base joint. Part names are a contract with that visual script only.
Avoid Godot import suffixes in names (`_wheel`, `-col`, `-rigid` ...): the model check flags them.

## Shared material

Painted parts use the material `palette` (or `palette_metal`): base colour from vertex
colours, no texture. On import, `tools/import/shared_materials.gd` swaps it for
`assets/materials/palette.tres`, so every model shares one material and Godot batches them.
Tune roughness/metallic there (and `ROUGHNESS` in kit_base.py for the previews).

## Live Blender (MCP), optional

An MCP server lets Claude drive a running Blender: look at a .blend someone made, query the
scene, try something interactively. Choices: Blender's own server (Blender Lab,
https://www.blender.org/lab/mcp-server/, Blender 5.1+) or a community one. Install it by
its own instructions; in Claude Code that ends in `claude mcp add ...` (`--scope project`
shares it with the team through `.mcp.json`). `/godot-doctor` shows whether one
is configured.

- It runs code Claude writes inside your Blender, without safeguards (Blender Lab says so
  too): keep backups and use it on project files, not your only copy.
- Blender has a visible window: you open it. The window guard still stops agents from
  starting it themselves until you allow windows (`/godot-windows on`).
- Anything that should survive becomes a model script here (or an exported .glb, see
  model-import): a live session can't be rebuilt, reviewed in a diff or changed by the next agent.

## Test

`python3 -I tools/test_runner.py blender` builds both examples into a scratch folder with
sheets and checks them: the files exist, the model check passes, the lamp's joints hang
under each other, the palette material is used. Passes as "skipped" without Blender.
