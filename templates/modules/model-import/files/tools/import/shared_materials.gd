@tool
extends EditorScenePostImport
## Post-import script for every 3D model (project.godot [importer_defaults] scene): a
## surface whose material is named like a file in assets/materials/ (Blender material
## "palette" -> assets/materials/palette.tres) gets that shared material instead of its own
## copy. Models then share one material (and texture), so Godot batches them and keeps
## one texture in memory. Other materials stay as imported.
## Models imported before this script was set keep their own materials: reimport them
## (delete the .glb.import) - suite shared_materials lists them.

const DIR: String = "res://assets/materials/"


func _post_import(scene: Node) -> Object:
	_swap(scene)
	return scene


func _swap(node: Node) -> void:
	if node is MeshInstance3D and (node as MeshInstance3D).mesh:
		var mesh: Mesh = (node as MeshInstance3D).mesh
		for i: int in mesh.get_surface_count():
			var shared: Material = _shared_for(mesh.surface_get_material(i))
			if shared and mesh is ArrayMesh:
				(mesh as ArrayMesh).surface_set_material(i, shared)
	elif node is ImporterMeshInstance3D and (node as ImporterMeshInstance3D).mesh:
		var importer_mesh: ImporterMesh = (node as ImporterMeshInstance3D).mesh
		for i: int in importer_mesh.get_surface_count():
			var shared: Material = _shared_for(importer_mesh.get_surface_material(i))
			if shared:
				importer_mesh.set_surface_material(i, shared)
	for child: Node in node.get_children():
		_swap(child)


static func shared_path(mat: Material) -> String:
	if mat == null or mat.resource_name.is_empty() or not mat.resource_name.is_valid_filename():
		return ""
	var path: String = DIR + mat.resource_name + ".tres"
	return path if ResourceLoader.exists(path) else ""


func _shared_for(mat: Material) -> Material:
	var path: String = shared_path(mat)
	return load(path) as Material if path else null
