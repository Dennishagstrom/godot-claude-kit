extends SceneTree
## One side of the two-process starter test (tests/starter/run_starter_net.sh).
## Both run the real main scene. Host: hosts, waits for the client's Player, and
## when the server moved it, teleports it. Client: joins, holds move_right, and
## passes when its Player (replicated from the server) has moved (input RPC ->
## server simulation -> MultiplayerSynchronizer) and then arrived at the teleport
## target with the teleported signal (serial synced in the same packet as position).
##   ... -s res://tests/starter/starter_peer.gd -- --role=host|client --port=7784

const MAIN_SCENE: String = "res://scenes/main/main.tscn"
const SERVER_ID: int = 1
const TIMEOUT_S: float = 30.0
## Seconds the host stays up after passing, so the client sees the movement too.
const LINGER_S: float = 2.0
const MIN_DISTANCE: float = {{#3D}}0.5{{/3D}}{{^3D}}20.0{{/3D}}
const TELEPORT_TO: {{#3D}}Vector3 = Vector3(-8, 0, 4){{/3D}}{{^3D}}Vector2 = Vector2(-300, 120){{/3D}}
## How far from the target the client may see it (it keeps walking right afterwards).
const TELEPORT_TOLERANCE: float = {{#3D}}0.5{{/3D}}{{^3D}}20.0{{/3D}}

var _host: bool = true
var _port: int = 7784
var _main: Node = null
var _elapsed: float = 0.0
var _start_x: float = NAN
var _passed_at: float = -1.0
var _summary: String = ""
var _moved: float = 0.0
var _teleport_seen: String = ""
var _teleport_ok: bool = false


func _initialize() -> void:
	for arg: String in OS.get_cmdline_user_args():
		if arg.begins_with("--port="):
			_port = arg.get_slice("=", 1).to_int()
		elif arg == "--role=client":
			_host = false


func _process(delta: float) -> bool:
	_elapsed += delta
	if _main == null:
		_main = (load(MAIN_SCENE) as PackedScene).instantiate()
		root.add_child(_main)
		var network: Node = root.get_node(^"Network")
		network.set(&"player_name", "Host" if _host else "Client")
		var err: Error = network.call(&"host_game", _port) if _host else network.call(&"join_game", "127.0.0.1", _port)
		if err != OK:
			return _finish(false, "start failed: %s" % error_string(err))
		return false
	if _passed_at >= 0.0:
		return _finish(true, _summary) if not _host or _elapsed - _passed_at > LINGER_S else false
	if _elapsed > TIMEOUT_S:
		return _finish(false, "timeout (players: %s)" % _player_names())
	var world: World = _main.get(&"world")
	if world == null:
		return false
	var mover: Player = _client_player(world)
	if mover == null:
		return false
	if is_nan(_start_x):
		_start_x = mover.position.x
		# Connected before anything moves: the teleport may reach the client in the
		# same frame as the last movement.
		mover.teleported.connect(func() -> void:
			_teleport_seen = str(mover.position)
			_teleport_ok = mover.position.distance_to(TELEPORT_TO) <= TELEPORT_TOLERANCE)
		if not _host:
			Input.action_press(&"move_right")
		return false
	# The host teleports only well after MIN_DISTANCE, so the client (a few frames
	# behind) has seen the movement first.
	var wanted: float = MIN_DISTANCE * (3.0 if _host else 1.0)
	if _moved < wanted and _teleport_seen.is_empty():
		_moved = maxf(_moved, mover.position.x - _start_x)
		if _moved >= wanted and world.get_player(SERVER_ID) != null and _host:
			mover.teleport(TELEPORT_TO)
		return false
	if not _teleport_seen.is_empty():
		if _moved < MIN_DISTANCE:
			return _finish(false, "teleported before the client saw its player move")
		if not _teleport_ok:
			return _finish(false, "teleported signal but the player is at %s, not near %s" % [_teleport_seen, TELEPORT_TO])
		_passed_at = _elapsed
		_summary = "%s sees players %s, client player moved %.2f, teleported to %s" % [
			"host" if _host else "client", _player_names(), _moved, _teleport_seen]
	return false


## The client's Player (host side: any player that is not the host).
func _client_player(world: World) -> Player:
	if not _host:
		return world.get_player(root.multiplayer.get_unique_id())
	for child: Node in world.players.get_children():
		if child.name.to_int() != SERVER_ID:
			return child as Player
	return null


func _player_names() -> String:
	var world: World = _main.get(&"world") if _main != null else null
	if world == null:
		return "no world"
	return ",".join(world.players.get_children().map(func(n: Node) -> String: return String(n.name)))


func _finish(ok: bool, what: String) -> bool:
	print("RESULT %s %s" % ["PASS" if ok else "FAIL", what])
	quit(0 if ok else 1)
	return true
