extends SceneTree
## Late-join test, client side: joins after the host opened the door and adds its
## own door only REGISTER_DELAY_S after joining, so the snapshot arrives before the
## node exists (it must wait and be applied on registration). Passes when the door
## is open, applied exactly once.

const Fixture := preload("res://tests/net/late_join_fixture.gd")
const TIMEOUT_S: float = 30.0
const REGISTER_DELAY_S: float = 1.0

var _port: int = 7785
var _elapsed: float = 0.0
var _started: bool = false
var _joined_at: float = -1.0
var _door: Node = null


func _initialize() -> void:
	for arg: String in OS.get_cmdline_user_args():
		if arg.begins_with("--port="):
			_port = arg.get_slice("=", 1).to_int()


func _process(delta: float) -> bool:
	_elapsed += delta
	var network: Node = root.get_node(^"Network")
	if not _started:
		_started = true
		network.connect(&"joined", func() -> void: _joined_at = _elapsed)
		var err: Error = network.call(&"join_game", "127.0.0.1", _port)
		if err != OK:
			return _finish(false, "join_game failed: %s" % error_string(err))
	if _door == null and _joined_at >= 0.0 and _elapsed - _joined_at > REGISTER_DELAY_S:
		_door = Fixture.new()
		root.add_child(_door)
	if _door != null and _door.get(&"applied") > 0:
		var ok: bool = _door.get(&"opened") == true and _door.get(&"applied") == 1
		return _finish(ok, "door opened=%s, snapshot applied %d time(s)" % [_door.get(&"opened"), _door.get(&"applied")])
	if _elapsed > TIMEOUT_S:
		return _finish(false, "timeout: no snapshot (joined at %.1f s)" % _joined_at)
	return false


func _finish(ok: bool, what: String) -> bool:
	print("RESULT %s %s" % ["PASS" if ok else "FAIL", what])
	quit(0 if ok else 1)
	return true
