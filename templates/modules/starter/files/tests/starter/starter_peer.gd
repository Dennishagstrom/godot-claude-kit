extends SceneTree
## One side of the two-process starter test (tests/starter/run_starter_net.sh).
## Both run the real main scene. Host: hosts, waits for the client's Player and
## passes when the server moved it. Client: joins, holds move_right and passes
## when its Player (replicated from the server) has moved: input RPC -> server
## simulation -> MultiplayerSynchronizer -> client.
##   ... -s res://tests/starter/starter_peer.gd -- --role=host|client --port=7784

const MAIN_SCENE: String = "res://scenes/main/main.tscn"
const SERVER_ID: int = 1
const TIMEOUT_S: float = 30.0
## Seconds the host stays up after passing, so the client sees the movement too.
const LINGER_S: float = 2.0
const MIN_DISTANCE: float = {{#3D}}0.5{{/3D}}{{^3D}}20.0{{/3D}}

var _host: bool = true
var _port: int = 7784
var _main: Node = null
var _elapsed: float = 0.0
var _start_x: float = NAN
var _passed_at: float = -1.0
var _summary: String = ""


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
		if not _host:
			Input.action_press(&"move_right")
		return false
	var moved: float = mover.position.x - _start_x
	if moved >= MIN_DISTANCE and world.get_player(SERVER_ID) != null:
		_passed_at = _elapsed
		_summary = "%s sees players %s, client player moved %.2f" % ["host" if _host else "client", _player_names(), moved]
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
