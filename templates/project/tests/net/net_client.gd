extends SceneTree
## Headless multiplayer test, client side (started by tests/net/run_net.sh).
## Joins 127.0.0.1:--port and waits until the server's roster (synced by RPC)
## contains both the host and this client. Exits 0 on success.

const TIMEOUT_S: float = 30.0
const SERVER_ID: int = 1

var _port: int = 7781
var _elapsed: float = 0.0
var _started: bool = false


func _initialize() -> void:
	for arg: String in OS.get_cmdline_user_args():
		if arg.begins_with("--port="):
			_port = arg.get_slice("=", 1).to_int()


func _process(delta: float) -> bool:
	_elapsed += delta
	var network: Node = root.get_node_or_null("Network")
	if network == null:
		return _finish(false, "Network autoload missing")
	if not _started:
		_started = true
		network.player_name = "Client"
		var err: Error = network.join_game("127.0.0.1", _port)
		if err != OK:
			return _finish(false, "join_game failed: %s" % error_string(err))
	var my_id: int = root.multiplayer.get_unique_id()
	if network.players.has(SERVER_ID) and network.players.has(my_id) and my_id != SERVER_ID:
		return _finish(true, "client %d sees roster %s" % [my_id, str(network.players)])
	if _elapsed > TIMEOUT_S:
		return _finish(false, "timeout, roster=%s" % str(network.players))
	return false


func _finish(ok: bool, what: String) -> bool:
	print("RESULT %s %s" % ["PASS" if ok else "FAIL", what])
	quit(0 if ok else 1)
	return true
