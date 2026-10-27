extends SceneTree
## Physics layers (scripts/core/layers.gd): the names in project.godot match the
## registry, and no body or area in any scene under res://scenes sits on an
## unregistered layer or detects more than Layers.MASKS allows.
##   godot --headless --audio-driver Dummy --path . -s res://tests/starter/test_layers.gd

const SCENE_ROOT: String = "res://scenes"
const SETTING: String = "layer_names/{{#3D}}3d{{/3D}}{{^3D}}2d{{/3D}}_physics/layer_%d"

var _fails: Array[String] = []
var _checked: int = 0


func _initialize() -> void:
	for bit: int in Layers.NAMES:
		var index: int = int(log(bit) / log(2)) + 1
		var name_set: String = ProjectSettings.get_setting(SETTING % index, "")
		if name_set != Layers.NAMES[bit]:
			_fails.append("layer %d is \"%s\" in project.godot, \"%s\" in Layers" % [index, name_set, Layers.NAMES[bit]])
	_scan(SCENE_ROOT)
	for line: String in _fails:
		print("FAIL ", line)
	print("RESULT %s layers (%d bodies/areas in scenes)" % ["PASS" if _fails.is_empty() else "FAIL", _checked])
	quit(0 if _fails.is_empty() else 1)


func _scan(dir_path: String) -> void:
	var dir: DirAccess = DirAccess.open(dir_path)
	if dir == null:
		return
	for sub: String in dir.get_directories():
		_scan(dir_path.path_join(sub))
	for file: String in dir.get_files():
		var path: String = dir_path.path_join(file.trim_suffix(".remap"))
		if path.ends_with(".tscn"):
			var packed: PackedScene = load(path) as PackedScene
			if packed != null:
				var node: Node = packed.instantiate()
				_check_tree(node, path)
				node.free()


func _check_tree(node: Node, scene: String) -> void:
	if node is CollisionObject{{#3D}}3D{{/3D}}{{^3D}}2D{{/3D}}:
		var body := node as CollisionObject{{#3D}}3D{{/3D}}{{^3D}}2D{{/3D}}
		_checked += 1
		var where: String = "%s:%s" % [scene, node.name]
		if body.collision_layer & ~Layers.all():
			_fails.append("%s is on an unregistered layer (%d)" % [where, body.collision_layer])
		var extra: int = body.collision_mask & ~Layers.allowed_mask(body.collision_layer)
		if extra:
			_fails.append("%s detects layers %d beyond Layers.MASKS" % [where, extra])
	for child: Node in node.get_children():
		_check_tree(child, scene)
