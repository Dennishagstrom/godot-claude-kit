extends SceneTree
## CSV -> Resource pipeline: builds the example table into a scratch folder
## and checks typed values (enum by name, typed array, colour, quoted commas),
## that a second build rewrites nothing, and that bad tables give errors
## (unknown column, bad int, bad enum, duplicate id). Prints RESULT PASS/FAIL.

const EXAMPLE_TABLE: String = "res://data/db/example_items.csv"
const SCRATCH: String = "user://data_pipeline_test/"
const BAD_TABLE: String = SCRATCH + "bad.csv"
const BAD_CSV: String = """# class=res://scripts/data/example_item_data.gd out=%sbad/
id,display_name,rarity,value
good_one,Good,common,1
bad_int,Bad,common,lots
bad_enum,Bad,legendaryish,2
good_one,Twice,common,3
"""
const UNKNOWN_COLUMN_CSV: String = """# class=res://scripts/data/example_item_data.gd out=%sunknown/
id,colour_of_the_sky
x,blue
"""

var _fails: Array[String] = []


func _initialize() -> void:
	_clean()
	DirAccess.make_dir_recursive_absolute(SCRATCH)
	var out: String = SCRATCH + "items/"
	var builder := CsvResourceBuilder.new()
	var rows: Array[Resource] = builder.build(EXAMPLE_TABLE, false, false, out)
	_check(builder.errors.is_empty(), "example table builds: %s" % str(builder.errors))
	_check(rows.size() == 3 and builder.written == 3, "3 rows written (%d, %d)" % [rows.size(), builder.written])
	var coin: Resource = ResourceLoader.load(out + "copper_coin.tres", "", ResourceLoader.CACHE_MODE_IGNORE)
	_check(coin != null, "copper_coin.tres exists")
	if coin:
		_check(coin.get(&"value") == 1 and is_equal_approx(coin.get(&"weight"), 0.01), "int and float")
		_check(coin.get(&"description") == "A small coin, worn thin by many hands.", "quoted commas")
		_check(coin.get(&"tags") == ["currency", "metal"], "typed array %s" % str(coin.get(&"tags")))
		_check((coin.get(&"tint") as Color).is_equal_approx(Color.html("#B87333")), "colour")
	var map: Resource = ResourceLoader.load(out + "old_map.tres", "", ResourceLoader.CACHE_MODE_IGNORE)
	_check(map != null and map.get(&"rarity") == 2 and map.get(&"stackable") == false, "enum by name + bool")
	var again := CsvResourceBuilder.new()
	again.build(EXAMPLE_TABLE, false, false, out)
	_check(again.written == 0 and again.unchanged == 3, "second build rewrites nothing (%d written)" % again.written)
	_write(BAD_TABLE, BAD_CSV % SCRATCH)
	var bad := CsvResourceBuilder.new()
	bad.build(BAD_TABLE, true)
	var text: String = "\n".join(bad.errors)
	_check(text.contains("not an int"), "bad int reported")
	_check(text.contains("legendaryish"), "bad enum reported")
	_check(text.contains("duplicate id"), "duplicate id reported")
	_write(SCRATCH + "unknown.csv", UNKNOWN_COLUMN_CSV % SCRATCH)
	var unknown := CsvResourceBuilder.new()
	unknown.build(SCRATCH + "unknown.csv", true)
	_check("\n".join(unknown.errors).contains("colour_of_the_sky"), "unknown column reported")
	_clean()
	if _fails.is_empty():
		print("RESULT PASS data pipeline")
		quit(0)
	else:
		for f: String in _fails:
			print("FAIL ", f)
		print("RESULT FAIL data pipeline: %d" % _fails.size())
		quit(1)


func _check(ok: bool, what: String) -> void:
	if not ok:
		_fails.append(what)


func _write(path: String, text: String) -> void:
	var f: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	f.store_string(text)
	f.close()


func _clean() -> void:
	_remove_tree(SCRATCH)


func _remove_tree(dir: String) -> void:
	if not DirAccess.dir_exists_absolute(dir):
		return
	for sub: String in DirAccess.get_directories_at(dir):
		_remove_tree(dir.path_join(sub))
	for file: String in DirAccess.get_files_at(dir):
		DirAccess.remove_absolute(dir.path_join(file))
	DirAccess.remove_absolute(dir)
