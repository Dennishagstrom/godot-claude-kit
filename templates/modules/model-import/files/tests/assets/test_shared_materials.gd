extends SceneTree
## Every imported model whose material has a shared copy in assets/materials/ really uses
## it (tools/import/shared_materials.gd). A model imported before the script was set, or
## with its own import script, keeps a private copy: reimport it (delete its .import).
##   godot --headless --audio-driver Dummy --path . -s res://tests/assets/test_shared_materials.gd

const ROOTS: Array[String] = ["res://assets"]
const EXTENSIONS: Array[String] = ["glb", "gltf", "blend", "fbx"]
const SharedMaterials: GDScript = preload("res://tools/import/shared_materials.gd")

var _models: int = 0
var _shared: int = 0
var _failed: Array[String] = []


func _initialize() -> void:
	for root: String in ROOTS:
		_scan(root)
	for line: String in _failed:
		print("FAIL ", line)
	if _failed.is_empty():
		print("RESULT PASS shared_materials: %d models, %d shared surfaces" % [_models, _shared])
		quit(0)
	else:
		print("RESULT FAIL shared_materials: %d surfaces with a private copy of a shared material" % _failed.size())
		quit(1)


func _scan(dir_path: String) -> void:
	var dir: DirAccess = DirAccess.open(dir_path)
	if dir == null:
		return
	for sub: String in dir.get_directories():
		if not sub.begins_with("."):
			_scan(dir_path.path_join(sub))
	for file: String in dir.get_files():
		if EXTENSIONS.has(file.get_extension().to_lower()):
			_check(dir_path.path_join(file))


func _check(path: String) -> void:
	var scene: PackedScene = load(path) as PackedScene
	if scene == null:
		return
	_models += 1
	var root: Node = scene.instantiate()
	_walk(root, path)
	root.free()


func _walk(node: Node, path: String) -> void:
	if node is MeshInstance3D and (node as MeshInstance3D).mesh:
		var mesh: Mesh = (node as MeshInstance3D).mesh
		for i: int in mesh.get_surface_count():
			var mat: Material = mesh.surface_get_material(i)
			var want: String = SharedMaterials.shared_path(mat)
			if want.is_empty():
				continue
			if mat.resource_path == want:
				_shared += 1
			else:
				_failed.append("%s: %s surface %d has its own %s; reimport it (delete %s.import)" % [
					path, node.name, i, mat.resource_name, path.get_file()])
	for child: Node in node.get_children():
		_walk(child, path)
