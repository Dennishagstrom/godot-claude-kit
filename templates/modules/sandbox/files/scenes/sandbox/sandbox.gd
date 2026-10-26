class_name Sandbox
extends {{#3D}}Node3D{{/3D}}{{^3D}}Node2D{{/3D}}
## Training arena (dev tool, `-- --sandbox`): a flat arena built in code, an
## F1 panel (SandboxPanel) and a registry other code extends:
##   Sandbox.register_button("Enemies", "Kill all", _kill_all)
##   Sandbox.register_toggle("Cheats", "Freeze AI", func(on: bool) -> void: ...)
##   Sandbox.register_spawnable(&"slime", func() -> Node: return SLIME.instantiate())
## Built in: time scale, no cooldowns, god mode, spawn / clear. Requests go
## to the server, which validates them{{#MULTIPLAYER}} (spawns replicate through a
## MultiplayerSpawner, time scale is sent to every peer){{/MULTIPLAYER}}.
## Never part of the real game flow and never touches real saves.

const GROUP: StringName = &"sandbox"
const MAX_SPAWNED: int = 50
const TIME_SCALE_MIN: float = 0.1
const TIME_SCALE_MAX: float = 2.0
const SECTION_CHEATS: String = "Cheats"
const SECTION_SPAWN: String = "Spawn"
const DUMMY_ID: StringName = &"dummy"
{{#3D}}const FLOOR_SIZE: Vector3 = Vector3(60, 1, 60)
const CAMERA_POSITION: Vector3 = Vector3(0, 18, 18)
const LIGHT_ROTATION_DEG: Vector3 = Vector3(-50, -30, 0)
const DUMMY_SIZE: Vector3 = Vector3(1, 2, 1)
const SPAWN_HEIGHT: float = 3.0
const SPAWN_SPREAD: float = 8.0
{{/3D}}{{^3D}}const FLOOR_SIZE: Vector2 = Vector2(1600, 40)
const FLOOR_Y: float = 300.0
const DUMMY_SIZE: Vector2 = Vector2(32, 64)
const SPAWN_HEIGHT: float = -200.0
const SPAWN_SPREAD: float = 400.0
{{/3D}}
## A request was applied (for UI refresh and tests).
signal changed

## id -> Callable() -> Node (registered spawnables).
static var _spawnables: Dictionary = {}
## [{section, label, kind: "button"|"toggle", callable}] in registration order.
static var _tools: Array[Dictionary] = []

var panel: SandboxPanel = null
var spawned_root: Node = null
{{#MULTIPLAYER}}var _spawner: MultiplayerSpawner = null
{{/MULTIPLAYER}}var _rng := RandomNumberGenerator.new()


static func register_button(section: String, label: String, callable: Callable) -> void:
	_tools.append({"section": section, "label": label, "kind": "button", "callable": callable})


static func register_toggle(section: String, label: String, callable: Callable) -> void:
	_tools.append({"section": section, "label": label, "kind": "toggle", "callable": callable})


static func register_spawnable(id: StringName, factory: Callable) -> void:
	_spawnables[id] = factory


## Forgets every registered tool and spawnable (tests, hot reload).
static func clear_registry() -> void:
	_tools.clear()
	_spawnables.clear()


static func tools() -> Array[Dictionary]:
	return _tools


static func spawnable_ids() -> Array:
	return _spawnables.keys()


func _init() -> void:
	name = "Sandbox"
	add_to_group(GROUP)
	if not _spawnables.has(DUMMY_ID):
		register_spawnable(DUMMY_ID, _make_dummy)


func _ready() -> void:
	_build_arena()
	spawned_root = Node.new()
	spawned_root.name = "Spawned"
	add_child(spawned_root)
{{#MULTIPLAYER}}	_spawner = MultiplayerSpawner.new()
	_spawner.name = "Spawner"
	add_child(_spawner)
	_spawner.spawn_path = _spawner.get_path_to(spawned_root)
	_spawner.spawn_function = _spawn_from_id
{{/MULTIPLAYER}}	panel = SandboxPanel.new()
	add_child(panel)
	panel.setup(self)


func _exit_tree() -> void:
	Engine.time_scale = 1.0
	DevCheats.reset()


# --- requests (any peer -> server) ----------------------------------------

func request_time_scale(scale: float) -> void:
	_ask(&"_server_time_scale", [scale])


func request_cheat(cheat: StringName, on: bool) -> void:
	_ask(&"_server_cheat", [cheat, on])


func request_spawn(id: StringName, count: int = 1) -> void:
	_ask(&"_server_spawn", [id, count])


func request_clear() -> void:
	_ask(&"_server_clear", [])


func spawned_count() -> int:
	return spawned_root.get_child_count() if spawned_root else 0


# --- server side -----------------------------------------------------------

@rpc("any_peer", "call_remote", "reliable")
func _server_time_scale(scale: float) -> void:
	if not _sender_allowed() or not is_finite(scale):
		return
	var clamped: float = clampf(scale, TIME_SCALE_MIN, TIME_SCALE_MAX)
	if _online():
		_apply_time_scale.rpc(clamped)
	else:
		_apply_time_scale(clamped)


@rpc("any_peer", "call_remote", "reliable")
func _server_cheat(cheat: StringName, on: bool) -> void:
	if not _sender_allowed():
		return
	match cheat:
		&"no_cooldowns":
			DevCheats.no_cooldowns = on
		&"god_mode":
			DevCheats.god_mode = on
		_:
			return
	changed.emit()


@rpc("any_peer", "call_remote", "reliable")
func _server_spawn(id: StringName, count: int) -> void:
	if not _sender_allowed() or not _spawnables.has(id):
		return
	var room: int = clampi(count, 0, MAX_SPAWNED - spawned_count())
	for i: int in room:
{{#MULTIPLAYER}}		if _online():
			_spawner.spawn(id)
			continue
{{/MULTIPLAYER}}		spawned_root.add_child(_spawn_from_id(id), true)
	changed.emit()


@rpc("any_peer", "call_remote", "reliable")
func _server_clear() -> void:
	if not _sender_allowed():
		return
	for child: Node in spawned_root.get_children():
		child.queue_free()
	changed.emit()


@rpc("authority", "call_local", "reliable")
func _apply_time_scale(scale: float) -> void:
	Engine.time_scale = scale
	changed.emit()


# --- private ---------------------------------------------------------------

## Calls the server function directly on the server, else sends it there.
func _ask(method: StringName, args: Array) -> void:
	if _is_server():
		callv(method, args)
	else:
		callv(&"rpc_id", [1, method] + args)


func _is_server() -> bool:
	return not multiplayer.has_multiplayer_peer() or multiplayer.is_server()


## Server only, and the request comes from this peer (direct call) or a connected peer.
func _sender_allowed() -> bool:
	if not _is_server():
		return false
	var sender: int = multiplayer.get_remote_sender_id()
	return sender == 0 or sender == multiplayer.get_unique_id() or multiplayer.get_peers().has(sender)


func _online() -> bool:
	return multiplayer.has_multiplayer_peer() and not multiplayer.multiplayer_peer is OfflineMultiplayerPeer


func _spawn_from_id(id: Variant) -> Node:
	var node: Node = (_spawnables[StringName(id)] as Callable).call()
{{#3D}}	if node is Node3D:
		(node as Node3D).position = Vector3(_rng.randf_range(-SPAWN_SPREAD, SPAWN_SPREAD), SPAWN_HEIGHT,
				_rng.randf_range(-SPAWN_SPREAD, SPAWN_SPREAD))
{{/3D}}{{^3D}}	if node is Node2D:
		(node as Node2D).position = Vector2(_rng.randf_range(-SPAWN_SPREAD, SPAWN_SPREAD), SPAWN_HEIGHT)
{{/3D}}	return node


func _build_arena() -> void:
{{#3D}}	var ground := StaticBody3D.new()
	ground.name = "Floor"
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = FLOOR_SIZE
	shape.shape = box
	shape.position.y = -FLOOR_SIZE.y / 2.0
	ground.add_child(shape)
	var mesh := MeshInstance3D.new()
	var plane := BoxMesh.new()
	plane.size = FLOOR_SIZE
	mesh.mesh = plane
	mesh.position.y = -FLOOR_SIZE.y / 2.0
	ground.add_child(mesh)
	add_child(ground)
	var light := DirectionalLight3D.new()
	light.rotation_degrees = LIGHT_ROTATION_DEG
	light.shadow_enabled = true
	add_child(light)
	var camera := Camera3D.new()
	camera.position = CAMERA_POSITION
	add_child(camera)
	camera.look_at(Vector3.ZERO)
	camera.current = true
{{/3D}}{{^3D}}	var ground := StaticBody2D.new()
	ground.name = "Floor"
	ground.position.y = FLOOR_Y
	var shape := CollisionShape2D.new()
	var rect := RectangleShape2D.new()
	rect.size = FLOOR_SIZE
	shape.shape = rect
	ground.add_child(shape)
	add_child(ground)
	var camera := Camera2D.new()
	add_child(camera)
	camera.make_current()
{{/3D}}

static func _make_dummy() -> Node:
{{#3D}}	var body := RigidBody3D.new()
	body.name = "Dummy"
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = DUMMY_SIZE
	shape.shape = box
	body.add_child(shape)
	var mesh := MeshInstance3D.new()
	var box_mesh := BoxMesh.new()
	box_mesh.size = DUMMY_SIZE
	mesh.mesh = box_mesh
	body.add_child(mesh)
{{/3D}}{{^3D}}	var body := RigidBody2D.new()
	body.name = "Dummy"
	var shape := CollisionShape2D.new()
	var rect := RectangleShape2D.new()
	rect.size = DUMMY_SIZE
	shape.shape = rect
	body.add_child(shape)
{{/3D}}	return body
