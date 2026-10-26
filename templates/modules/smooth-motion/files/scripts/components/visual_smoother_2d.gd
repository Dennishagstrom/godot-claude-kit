class_name VisualSmoother2D
extends Node2D
## Put visuals (sprites, the Camera2D) under this node so they move smoothly
## at any frame rate. It is top-level and follows its parent body:
## - server and single player: interpolates between the parent's last two
##   physics ticks (Engine.get_physics_interpolation_fraction), so a body that
##   moves at the 60 Hz physics rate draws smoothly at 120/144/240 Hz.
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
## Gaps larger than this (pixels) snap instead of sliding.
@export var snap_distance: float = 256.0

var _previous: Transform2D = Transform2D.IDENTITY
var _latest: Transform2D = Transform2D.IDENTITY

@onready var _target: Node2D = get_parent() as Node2D


func _ready() -> void:
	top_level = true
	process_physics_priority = PHYSICS_PRIORITY
	# This node interpolates by itself; Godot's built-in interpolation would do it twice.
	physics_interpolation_mode = Node.PHYSICS_INTERPOLATION_MODE_OFF
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
	if _is_authority():
		global_transform = _previous.interpolate_with(_latest, Engine.get_physics_interpolation_fraction())
		return
	var goal: Transform2D = _target.global_transform
	if global_position.distance_to(goal.origin) > snap_distance:
		global_transform = goal
		return
	var weight_pos: float = 1.0 - exp(-position_speed * delta)
	var weight_rot: float = 1.0 - exp(-rotation_speed * delta)
	global_position = global_position.lerp(goal.origin, weight_pos)
	global_rotation = lerp_angle(global_rotation, goal.get_rotation(), weight_rot)
	global_scale = goal.get_scale()


## Snaps to the parent now (call after a teleport the code knows about).
func snap() -> void:
	if _target == null:
		return
	_previous = _target.global_transform
	_latest = _previous
	global_transform = _previous


## True where the parent's transform is simulated locally (server, single player).
func _is_authority() -> bool:
	return not multiplayer.has_multiplayer_peer() or multiplayer.is_server()
