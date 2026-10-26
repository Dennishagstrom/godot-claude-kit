extends SceneTree
## Parse check: compiles every game script (not tests/ or addons/) and reports
## parse errors. Works without a main scene and also covers scripts that no
## scene references yet. Used by tools/test_runner.py and .githooks/pre-commit.
##   godot --headless --audio-driver Dummy --path . -s res://tests/parse_check.gd

const SKIP_DIRS: Array[String] = ["res://tests", "res://addons", "res://.godot", "res://.claude", "res://build"]

var _count: int = 0
var _failed: Array[String] = []


func _initialize() -> void:
	_scan("res://")
	if _failed.is_empty():
		print("RESULT PASS parse check: %d scripts" % _count)
		quit(0)
	else:
		for path: String in _failed:
			print("Parse Error: ", path)
		print("RESULT FAIL parse check: %d of %d scripts" % [_failed.size(), _count])
		quit(1)


func _scan(dir_path: String) -> void:
	if SKIP_DIRS.has(dir_path.trim_suffix("/")):
		return
	var dir: DirAccess = DirAccess.open(dir_path)
	if dir == null:
		return
	for sub: String in dir.get_directories():
		if not sub.begins_with("."):
			_scan(dir_path.path_join(sub))
	for file: String in dir.get_files():
		if file.ends_with(".gd"):
			_count += 1
			var script: Script = load(dir_path.path_join(file)) as Script
			if script == null or not (script.can_instantiate() or _is_abstract(script)):
				_failed.append(dir_path.path_join(file))


func _is_abstract(script: Script) -> bool:
	# @abstract scripts (Godot 4.5+) compile fine but can't be instantiated.
	return script.has_method(&"is_abstract") and script.call(&"is_abstract")
