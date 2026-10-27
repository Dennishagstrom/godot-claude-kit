extends SceneTree
## Late-join test, host side (tests/net/run_net.sh late_join_host late_join_client 7785):
## hosts, opens the door before anyone joins, then waits until the client is in
## the roster and lingers so the snapshot reaches it.

const Fixture := preload("res://tests/net/late_join_fixture.gd")
const TIMEOUT_S: float = 30.0
const LINGER_S: float = 1.5

var _port: int = 7785
var _elapsed: float = 0.0
var _door: Node = null
var _joined_at: float = -1.0


func _initialize() -> void:
	for arg: String in OS.get_cmdline_user_args():
		if arg.begins_with("--port="):
			_port = arg.get_slice("=", 1).to_int()


func _process(delta: float) -> bool:
	_elapsed += delta
	var network: Node = root.get_node(^"Network")
	if _door == null:
		_door = Fixture.new()
		root.add_child(_door)
		var err: Error = network.call(&"host_game", _port)
		if err != OK:
			return _finish(false, "host_game failed: %s" % error_string(err))
		_door.set(&"opened", true)  # changed before the client exists: only a snapshot can tell it
		return false
	var roster: Dictionary = network.get(&"players")
	if _joined_at < 0.0 and roster.size() >= 2:
		_joined_at = _elapsed
	if _joined_at >= 0.0 and _elapsed - _joined_at > LINGER_S:
		return _finish(true, "client joined after the door opened")
	if _elapsed > TIMEOUT_S:
		return _finish(false, "timeout, roster=%s" % str(roster))
	return false


func _finish(ok: bool, what: String) -> bool:
	print("RESULT %s %s" % ["PASS" if ok else "FAIL", what])
	quit(0 if ok else 1)
	return true
