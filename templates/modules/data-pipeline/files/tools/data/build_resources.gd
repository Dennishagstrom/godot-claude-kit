extends SceneTree
## Data tables -> Resources: every data/db/<table>.csv becomes one .tres per
## row (CsvResourceBuilder). Deterministic and re-runnable; the CSV wins.
##   godot --headless --audio-driver Dummy --path . -s res://tools/data/build_resources.gd
##   ... -- --check          validate only, write nothing (exit 1 on errors)
##   ... -- --prune          delete .tres files whose id is no longer in the table
##   ... -- --table=items    only data/db/items.csv

const TABLE_DIR: String = "res://data/db/"
const TABLE_EXTENSION: String = "csv"


func _initialize() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	var check_only: bool = args.has("--check")
	var prune: bool = args.has("--prune")
	var only: String = ""
	for arg: String in args:
		if arg.begins_with("--table="):
			only = arg.get_slice("=", 1)
	var failed: bool = false
	var tables: int = 0
	for file_name: String in DirAccess.get_files_at(TABLE_DIR):
		if file_name.get_extension() != TABLE_EXTENSION or (not only.is_empty() and file_name.get_basename() != only):
			continue
		tables += 1
		var builder := CsvResourceBuilder.new()
		var rows: Array[Resource] = builder.build(TABLE_DIR + file_name, check_only, prune)
		for warning: String in builder.warnings:
			print("[data] WARNING ", warning)
		for error: String in builder.errors:
			print("[data] ERROR ", error)
		print("[data] %s: %d rows, %d written, %d unchanged, %d pruned, %d errors%s" % [file_name, rows.size(),
				builder.written, builder.unchanged, builder.pruned, builder.errors.size(), " (check)" if check_only else ""])
		failed = failed or not builder.errors.is_empty()
	if tables == 0:
		print("[data] no tables in %s" % TABLE_DIR)
	quit(1 if failed else 0)
