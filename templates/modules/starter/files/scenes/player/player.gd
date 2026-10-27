class_name Player
extends {{#3D}}CharacterBody3D{{/3D}}{{^3D}}CharacterBody2D{{/3D}}
## A player character, moved by the move_* actions{{#3D}} (jump: jump){{/3D}}. Only the server moves
## it{{#MULTIPLAYER}}: the peer that owns it sends its input every physics tick (_send_input,
## validated on the server) and $Sync replicates the position to every peer{{/MULTIPLAYER}}.

{{#3D}}const SPEED: float = 6.0
const JUMP_VELOCITY: float = 5.0
{{/3D}}{{^3D}}const SPEED: float = 300.0
{{/3D}}
## The peer that controls this player (the node name is str(peer_id)).
var peer_id: int = 1

var _move: Vector2 = Vector2.ZERO
{{#3D}}var _jump: bool = false
var _gravity: float = ProjectSettings.get_setting("physics/3d/default_gravity", 9.8)
{{/3D}}

func _enter_tree() -> void:
	peer_id = name.to_int() if name.is_valid_int() else 1


func _physics_process(delta: float) -> void:
	if is_local():
		var move: Vector2 = Input.get_vector(&"move_left", &"move_right", &"move_up", &"move_down")
{{#3D}}		var jump: bool = Input.is_action_pressed(&"jump")
{{/3D}}{{#MULTIPLAYER}}		if not multiplayer.is_server():
			_send_input.rpc_id(1, move{{#3D}}, jump{{/3D}})
		else:
			_set_input(move{{#3D}}, jump{{/3D}})
{{/MULTIPLAYER}}{{^MULTIPLAYER}}		_set_input(move{{#3D}}, jump{{/3D}})
{{/MULTIPLAYER}}	if multiplayer.is_server():
		_simulate(delta)


## True on the peer that controls this player.
func is_local() -> bool:
	return peer_id == multiplayer.get_unique_id()
{{#MULTIPLAYER}}


## Owner -> server, every physics tick (unreliable: the next one replaces a lost one).
@rpc("any_peer", "call_remote", "unreliable_ordered")
func _send_input(move: Vector2{{#3D}}, jump: bool{{/3D}}) -> void:
	# Only the server simulates, and only the owner may steer this player.
	if not multiplayer.is_server() or multiplayer.get_remote_sender_id() != peer_id:
		return
	_set_input(move{{#3D}}, jump{{/3D}})
{{/MULTIPLAYER}}


func _set_input(move: Vector2{{#3D}}, jump: bool{{/3D}}) -> void:
	_move = move.limit_length(1.0) if move.is_finite() else Vector2.ZERO
{{#3D}}	_jump = jump
{{/3D}}

func _simulate(delta: float) -> void:
{{#3D}}	if not is_on_floor():
		velocity.y -= _gravity * delta
	elif _jump:
		velocity.y = JUMP_VELOCITY
	velocity.x = _move.x * SPEED
	velocity.z = _move.y * SPEED
{{/3D}}{{^3D}}	velocity = _move * SPEED
{{/3D}}	move_and_slide()
