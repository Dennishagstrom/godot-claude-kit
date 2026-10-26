# Module: data-pipeline

TL;DR: keep lots of similar data (items, enemies, upgrades) in CSV tables
and generate one `.tres` per row. Claude edits one readable table instead of
dozens of resource files, diffs stay small, and the Resource class is the
schema (no separate type list to keep in sync).

## Use

```bash
"$GODOT" --headless --audio-driver Dummy --path . -s res://tools/data/build_resources.gd           # all tables
"$GODOT" --headless --audio-driver Dummy --path . -s res://tools/data/build_resources.gd -- --check # validate only
#   -- --prune (delete .tres whose id left the table)   -- --table=example_items
```

A table (`data/db/<name>.csv`) starts with a directive, then the header:

```
# class=res://scripts/data/example_item_data.gd out=res://data/example_items/
id,display_name,description,rarity,value,weight,stackable,tags,tint
copper_coin,Copper Coin,"A small coin, worn thin by many hands.",common,1,0.01,true,currency;metal,#B87333
```

- Columns = exported properties of the class; unknown columns are errors.
- Cells: int, float, bool (true/false/yes/no), String, StringName, enum by name
  (case-insensitive), Color (`#rrggbb`), Vector2/3 (`x;y;z`), typed arrays
  (`a;b;c`), resources by `res://` path. Empty cell = the class default.
- `id` names the file. Unchanged rows are not rewritten. Rows are validated
  before anything is written; errors name file, line and column.
- Player-facing text in tables is English source text, shown through `tr()`.
- Example: `scripts/data/example_item_data.gd` + `data/db/example_items.csv`
  (replace both with your own; the builder is generic).

## Test

`python3 -I tools/test_runner.py data`: builds the example into `user://`,
checks the typed values, that a second run writes nothing, and that bad
tables are rejected with clear errors.
