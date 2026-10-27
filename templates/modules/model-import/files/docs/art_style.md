# Art style

> **TL;DR** (fill in; agents read this before making or changing any model, texture or material)
> The look in one line:
> Scale: the player is 1.75 m (change it here and in `tools/dev/asset_rules.json`).
> Where models come from: (scripts in `tools/blender/models/`, hand-made .blend, packs, generators ...)
> Checks: suite `assets` (`tools/dev/asset_check.py`), rules in `tools/dev/asset_rules.json`.

One page that keeps every model in the same style, whoever or whatever makes it. Short and
concrete beats long: numbers, names, examples. Owned by the project; the kit never changes it.

## The look in one paragraph

(Mood, shapes, how chunky or detailed, light and colour. What a screenshot should feel like.)

## Palette

(Colour names and values, what each is for. One accent per model? Which colours may glow?
Shared materials live in `assets/materials/<name>.tres`; a model material with that name uses it.)

## Proportions

(Player height, door and corridor sizes, table/counter heights, pickup sizes. Everything in metres.)

## Detail and budgets

(Triangles per kind of model, texture sizes, materials per model; keep `asset_rules.json` in step.
What carries the detail: silhouette, bevels, colour shading, normal maps?)

## Reading at gameplay distance

(The camera distance, what must read from there, what can be dropped.)

## Conventions

- Metres; the model stands on its origin (bottom centre) unless its folder says otherwise.
- Front faces Godot +Z (Blender -Y). Apply all transforms before export.
- Part names are a visual-only contract (animation, swapping); gameplay never depends on them.
- No Godot import suffixes by accident (`-col`, `_wheel`, `-rigid`, `-noimp` ...).
- Each model goes inside a `*_visual.tscn` scene; logic lives on the parent.

## Sources and licences

(Asset packs used, their licence and credit line; generator terms.)
