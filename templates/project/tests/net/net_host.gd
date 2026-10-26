extends SceneTree
## Headless multiplayer test, host side (started by tests/net/run_net.sh).
## Hosts on --port, waits until the client has registered in the roster, then
## lingers so the roster sync reaches the client. Exits 0 on success.
## Wait on state, never on frame counts: a fixed frame count is a flaky test.

const TIMEOUT_S: float = 30.0
const LINGER_S: float = 1.5
const EXPECTED_PLAYERS: int = 2

var _port: int = 7781
var _elapsed: float = 0.0
var _started: bool = false
var _passed_at: float = -1.0
var _roster_at_pass: String = ""


func _initialize() -> void:
	for arg: String in OS.get_cmdline_user_args():
		if arg.begins_with("--port="):
			_port = arg.get_slice("=", 1).to_int()


func _process(delta: float) -> bool:
	_elapsed += delta
	# Autoloads exist from the first frame; don't touch them in _initialize().
	var network: Node = root.get_node_or_null("Network")
	if network == null:
		return _finish(false, "Network autoload missing")
	if not _started:
		_started = true
		network.player_name = "Host"
		var err: Error = network.host_game(_port)
		if err != OK:
			return _finish(false, "host_game failed: %s" % error_string(err))
		print("hosting on ", _port)
	if _passed_at < 0.0 and network.players.size() >= EXPECTED_PLAYERS:
		_passed_at = _elapsed
		_roster_at_pass = str(network.players)
	if _passed_at >= 0.0 and _elapsed - _passed_at > LINGER_S:
		return _finish(true, "host roster %s" % _roster_at_pass)
	if _elapsed > TIMEOUT_S:
		return _finish(false, "timeout, roster=%s" % str(network.players))
	return false


func _finish(ok: bool, what: String) -> bool:
	print("RESULT %s %s" % ["PASS" if ok else "FAIL", what])
	quit(0 if ok else 1)
	return true
