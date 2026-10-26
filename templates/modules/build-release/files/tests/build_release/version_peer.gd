extends SceneTree
## One side of the join version test (run_version.sh).
##   -- --role=host|client --port=N --expect=ok|reject [--fake-build=N]
## Host: ok = a client must connect; reject = nobody may connect within
## REJECT_WINDOW_S. Client: ok = joined; reject = join_failed with a reason.
## --fake-build makes this process claim another build number.

const VersionCheck := preload("res://scripts/net/version_check.gd")
const TIMEOUT_S: float = 20.0
const REJECT_WINDOW_S: float = 6.0
const LINGER_S: float = 1.0

var _role: String = "host"
var _port: int = 7795
var _expect: String = "ok"
var _elapsed: float = 0.0
var _started: bool = false
var _connected_peers: int = 0
var _joined: bool = false
var _fail_reason: String = ""
var _ok_at: float = -1.0


func _initialize() -> void:
	for arg: String in OS.get_cmdline_user_args():
		var value: String = arg.get_slice("=", 1)
		if arg.begins_with("--role="):
			_role = value
		elif arg.begins_with("--port="):
			_port = value.to_int()
		elif arg.begins_with("--expect="):
			_expect = value
		elif arg.begins_with("--fake-build="):
			VersionCheck.build_override = value.to_int()


func _process(delta: float) -> bool:
	_elapsed += delta
	var net: Node = root.get_node_or_null(^"Network")
	if net == null:
		return _finish(false, "Network autoload missing")
	if not _started:
		_started = true
		net.peer_connected.connect(func(_id: int) -> void: _connected_peers += 1)
		net.joined.connect(func() -> void: _joined = true)
		net.join_failed.connect(func(reason: String) -> void: _fail_reason = reason)
		var err: Error = net.host_game(_port) if _role == "host" else net.join_game("127.0.0.1", _port)
		if err != OK:
			return _finish(false, "could not start: %s" % error_string(err))
	if _role == "host":
		if _expect == "ok" and _connected_peers > 0 and _ok_at < 0.0:
			_ok_at = _elapsed
		if _ok_at >= 0.0 and _elapsed - _ok_at > LINGER_S:
			return _finish(true, "matching client connected")
		if _expect == "reject" and _elapsed > REJECT_WINDOW_S:
			return _finish(_connected_peers == 0, "connected peers with a wrong build: %d" % _connected_peers)
	else:
		if _expect == "ok" and _joined:
			return _finish(true, "joined")
		if _expect == "reject" and not _fail_reason.is_empty():
			return _finish(true, "refused: %s" % _fail_reason)
		if _expect == "ok" and not _fail_reason.is_empty():
			return _finish(false, "refused: %s" % _fail_reason)
	if _elapsed > TIMEOUT_S:
		return _finish(false, "timeout (joined=%s reason=%s peers=%d)" % [_joined, _fail_reason, _connected_peers])
	return false


func _finish(ok: bool, what: String) -> bool:
	print("RESULT %s %s %s: %s" % ["PASS" if ok else "FAIL", _role, _expect, what])
	quit(0 if ok else 1)
	return true
