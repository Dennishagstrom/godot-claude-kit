extends Node
## Minimal server-authoritative object for the network tests: the owning
## client sends its input (ui_left/right/up/down) by RPC, the server
## validates it and moves `value`, and a MultiplayerSynchronizer (built in
## code) mirrors `value` to every peer. Same node path on host and client.

const NODE_NAME: String = "NetSyncFixture"
## Units per second at full input.
const SPEED: float = 4.0
const ACTIONS: Array[StringName] = [&"ui_left", &"ui_right", &"ui_up", &"ui_down"]
## Input is a stream (unreliable): resend at least this often so a lost
## packet only costs a moment.
const RESEND_S: float = 0.1

## Synced from the server.
var value: Vector2 = Vector2.ZERO
## Server: the only peer whose input is accepted (0 = nobody yet).
var owner_peer: int = 0
## Server: requests that were rejected (wrong sender, bad input).
var rejected: int = 0

var _input: Vector2 = Vector2.ZERO
var _sent: Vector2 = Vector2.ZERO
var _since_send: float = 0.0


func _init() -> void:
	name = NODE_NAME


func _ready() -> void:
	var sync := MultiplayerSynchronizer.new()
	sync.name = "Sync"
	var config := SceneReplicationConfig.new()
	var property := NodePath(".:value")
	config.add_property(property)
	config.property_set_replication_mode(property, SceneReplicationConfig.REPLICATION_MODE_ALWAYS)
	sync.replication_config = config
	add_child(sync)
	sync.root_path = sync.get_path_to(self)


func _physics_process(delta: float) -> void:
	if not multiplayer.has_multiplayer_peer():
		return
	if multiplayer.is_server():
		value += _input * SPEED * delta
		return
	if multiplayer.multiplayer_peer.get_connection_status() != MultiplayerPeer.CONNECTION_CONNECTED:
		return
	var dir: Vector2 = Input.get_vector(ACTIONS[0], ACTIONS[1], ACTIONS[2], ACTIONS[3])
	_since_send += delta
	if dir != _sent or _since_send >= RESEND_S:
		_sent = dir
		_since_send = 0.0
		_request_input.rpc_id(1, dir)


## Client -> server. Validated: sender must own the fixture, input is clamped.
@rpc("any_peer", "call_remote", "unreliable_ordered")
func _request_input(dir: Vector2) -> void:
	if not multiplayer.is_server():
		return
	if multiplayer.get_remote_sender_id() != owner_peer or not dir.is_finite():
		rejected += 1
		return
	_input = dir.limit_length(1.0)
