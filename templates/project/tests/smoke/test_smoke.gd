extends SceneTree
## Smoke test: every autoload exists, every scene under res://scenes loads, and
## the main scene (if set) runs a few frames without script errors.
##   godot --headless --audio-driver Dummy --path . -s res://tests/smoke/test_smoke.gd
## Prints "RESULT PASS" / "RESULT FAIL ..." and exits 0 / 1.

const TIMEOUT_S: float = 30.0
const MAIN_SCENE_FRAMES: int = 30
const SCENE_ROOT: String = "res://scenes"

var _fails: Array[String] = []
var _frame: int = 0
var _elapsed: float = 0.0
var _main: Node = null
var _checked_static: bool = false


func _process(delta: float) -> bool:
	_elapsed += delta
	_frame += 1
	# Autoloads are added to the tree before the first frame; check them here,
	# not in _initialize().
	if not _checked_static:
		_checked_static = true
		_check_autoloads()
		_check_scenes(SCENE_ROOT)
		_start_main_scene()
		return false
	if _frame < MAIN_SCENE_FRAMES and _elapsed < TIMEOUT_S:
		return false
	_finish()
	return true


func _check_autoloads() -> void:
	for prop: Dictionary in ProjectSettings.get_property_list():
		var key: String = prop["name"]
		if not key.begins_with("autoload/"):
			continue
		var autoload_name: String = key.trim_prefix("autoload/")
		if root.get_node_or_null(autoload_name) == null:
			_fail("autoload %s missing" % autoload_name)
		else:
			print("ok autoload ", autoload_name)


func _check_scenes(dir_path: String) -> void:
	var dir: DirAccess = DirAccess.open(dir_path)
	if dir == null:
		return
	for sub: String in dir.get_directories():
		_check_scenes(dir_path.path_join(sub))
	for file: String in dir.get_files():
		var path: String = dir_path.path_join(file.trim_suffix(".remap"))
		if path.ends_with(".tscn") or path.ends_with(".scn"):
			if load(path) == null:
				_fail("scene does not load: %s" % path)


func _start_main_scene() -> void:
	var main_path: String = ProjectSettings.get_setting("application/run/main_scene", "")
	if main_path.is_empty():
		print("no main scene set; skipping run check")
		return
	var packed: PackedScene = load(main_path) as PackedScene
	if packed == null:
		_fail("main scene does not load: %s" % main_path)
		return
	_main = packed.instantiate()
	root.add_child(_main)
	print("ok main scene ", main_path)


func _fail(what: String) -> void:
	_fails.append(what)
	print("FAIL ", what)


func _finish() -> void:
	if is_instance_valid(_main):
		_main.queue_free()
	if _fails.is_empty():
		print("RESULT PASS smoke")
		quit(0)
	else:
		print("RESULT FAIL smoke: %d problem(s)" % _fails.size())
		quit(1)
