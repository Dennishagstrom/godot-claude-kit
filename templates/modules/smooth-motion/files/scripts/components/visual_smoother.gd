class_name VisualSmoother
extends Node3D
## Put visuals (meshes, the camera rig) under this node so they move smoothly
## at any frame rate. It is top-level and follows its parent body:
## - server and single player: interpolates between the parent's last two
##   physics ticks (Engine.get_physics_interpolation_fraction), so a body that
##   moves at the 60 Hz physics rate draws smoothly at 120/144/240 Hz. The
##   visual trails the body by up to one tick.
## - clients: eases toward the parent's synced transform every frame, which
##   hides network jitter and the synchronizer's update rate.
## Both snap when the gap is larger than snap_distance (teleports, respawns).
## Logic never reads this node: gameplay uses the parent body.

## Runs after normal nodes in each physics tick, so it reads where the body
## ended up this tick (not where it was before the body's own script ran).
const PHYSICS_PRIORITY: int = 100

## Client easing speeds (1/s): higher = tighter, lower = smoother.
@export var position_speed: float = 18.0
@export var rotation_speed: float = 14.0
## Gaps larger than this (metres) snap instead of sliding.
@export var snap_distance: float = 4.0
## Optional: move this node (made top-level) instead of the smoother itself,
## so a model can keep its path under the body.
var drive: Node3D = null

var _previous: Transform3D = Transform3D.IDENTITY
var _latest: Transform3D = Transform3D.IDENTITY

@onready var _target: Node3D = get_parent() as Node3D


func _ready() -> void:
	top_level = true
	process_physics_priority = PHYSICS_PRIORITY
	# This node interpolates by itself; Godot's built-in interpolation would do it twice.
	physics_interpolation_mode = Node.PHYSICS_INTERPOLATION_MODE_OFF
	if drive:
		drive.top_level = true
	snap()


func _physics_process(_delta: float) -> void:
	if _target == null:
		return
	_previous = _latest
	_latest = _target.global_transform
	if _previous.origin.distance_to(_latest.origin) > snap_distance:
		_previous = _latest


func _process(delta: float) -> void:
	if _target == null:
		return
	var moved: Node3D = drive if drive else self
	if _is_authority():
		moved.global_transform = _previous.interpolate_with(_latest, Engine.get_physics_interpolation_fraction())
		return
	var goal: Transform3D = _target.global_transform
	if moved.global_position.distance_to(goal.origin) > snap_distance:
		moved.global_transform = goal
		return
	var weight_pos: float = 1.0 - exp(-position_speed * delta)
	var weight_rot: float = 1.0 - exp(-rotation_speed * delta)
	var current: Quaternion = moved.global_transform.basis.get_rotation_quaternion()
	var target_rot: Quaternion = goal.basis.get_rotation_quaternion()
	var basis := Basis(current.slerp(target_rot, weight_rot)).scaled(goal.basis.get_scale())
	moved.global_transform = Transform3D(basis, moved.global_position.lerp(goal.origin, weight_pos))


## Snaps to the parent now (call after a teleport the code knows about).
func snap() -> void:
	if _target == null:
		return
	_previous = _target.global_transform
	_latest = _previous
	(drive if drive else self).global_transform = _previous


## True where the parent's transform is simulated locally (server, single player).
func _is_authority() -> bool:
	return not multiplayer.has_multiplayer_peer() or multiplayer.is_server()
