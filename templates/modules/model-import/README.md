# Module: model-import

TL;DR: every 3D model meets the same checks, whatever made it. Suite `assets`
(`tools/dev/asset_check.py`, pure Python, a second) checks triangles, size, pivot, root
transform, materials, textures, duplicate embedded textures and Godot's name suffixes
against `tools/dev/asset_rules.json`. Materials named like a file in `assets/materials/`
become that shared material on import. The look lives in `docs/art_style.md`.

## Ways in (pick per model; mix freely)

| Source | Good for | Do |
|---|---|---|
| Scripts (`blender-pipeline` module) | props, buildings, machines, anything rebuilt or varied | `tools/blender/build.sh <name> --preview`; diffable, any agent can change it |
| Blender by hand | characters, organic shapes, sculpted or textured work | export glTF (below); keep the .blend in a source folder outside `assets/` |
| Live Blender over MCP | inspecting or fixing a .blend, trying shapes interactively | see `docs/modules/blender-pipeline.md`; save results as a script or an exported .glb |
| Asset packs | a consistent base quickly | one folder per pack, its licence in `docs/art_style.md`, folder rules in `asset_rules.json` |
| Generators (AI meshes, scans) | first drafts, background clutter | expect high triangle counts and odd pivots: decimate, re-pivot, check |

Scripts make plain, stylised, hard-surface shapes very well. Characters and organic forms
rarely look good from primitives; make those by hand, take them from a pack or a generator,
and let the checks catch the import mistakes.

## Exporting from Blender by hand

File > Export > glTF 2.0 (.glb): +Y Up on, Apply Modifiers on, only the selected objects.
Before: metres (Scene > Units), all transforms applied (Ctrl+A), origin at the bottom centre
(or where the folder's pivot rule says), front facing -Y, no Godot suffixes in object names
unless you mean them. Name a material `palette` (or another file in `assets/materials/`) to
get the shared material.

Godot can also import `.blend` files directly, but only where Blender is installed: every
teammate and the CI runner. Exporting .glb avoids that; the check lists .blend files as a note.

## The check

```bash
python3 -I tools/dev/asset_check.py              # whole project
python3 -I tools/dev/asset_check.py --report     # plus a table per model
python3 -I tools/dev/asset_check.py some.glb --as assets/models/props/   # judge a file by a folder's rules
```

Rules and why are in the script's header. Limits per folder in `tools/dev/asset_rules.json`
(the longest matching folder wins; `files` for one file; `ignore` to skip). A pack with its
own conventions gets its own folder entry (e.g. `"pivot": "any"`), not an exception per file.
It reads each model's `.import`: suffixes turned off or embedded images discarded there
count as handled.

## Shared materials and textures

`tools/import/shared_materials.gd` runs for every scene import (`[importer_defaults]` in
project.godot): a surface whose material is named like `assets/materials/<name>.tres` uses
that file. One material for many models = batching and one texture in memory. Packs that
embed the same atlas in every file (`duplicate-texture`) get the same treatment: save the
atlas material once as `assets/materials/<name>.tres` and reimport the pack.
Models imported before the script was set keep private copies until reimported (delete
their `.import`); suite `shared_materials` lists them.

## Godot import facts worth knowing

- Name suffixes: `-col`, `-convcol`, `-colonly`, `-rigid`, `-vehicle`, `-wheel`, `-navmesh`,
  `-occ`, `-noimp` (also with `_` or `$`) turn nodes into bodies, wheels or nothing. Use
  them on purpose (`"allow_suffixes": true` for that folder) or not at all.
- LODs are generated on import (`meshes/generate_lods`); you rarely need hand-made ones.
- Put each model inside a `*_visual.tscn` scene; logic lives on the parent and never
  depends on mesh names.
