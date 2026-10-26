extends SceneTree
## Base for headless host + client tests (extend it by path:
## `extends "res://tests/net_testing/net_test_base.gd"`; tests/ is not imported,
## so class_name would not resolve).
##
## Override _step(elapsed) -> bool: return true when the test is finished (call
## finish() first). The base parses `-- --port=N --role=host|client`, connects
## in the first frame (autoloads don't exist in _initialize()), times out, and
## prints "RESULT PASS/FAIL" for tools/test_runner.py.
## Helpers: network(), instantiate_main_scene(), press(action), release(action),
## press_for(action, seconds), wait_until-style polling via _step().
## Wait on state, never on frame counts.

const DEFAULT_PORT: int = 7790
const DEFAULT_TIMEOUT_S: float = 30.0
const LOCALHOST: String = "127.0.0.1"

var port: int = DEFAULT_PORT
var role: String = "host"
var timeout_s: float = DEFAULT_TIMEOUT_S
var elapsed: float = 0.0
## Main scene instance (instantiate_main_scene()), null if none.
var main: Node = null

var _connected_once: bool = false
var _done: bool = false
## action -> seconds left to hold it (press_for()).
var _held: Dictionary = {}


func _initialize() -> void:
	for arg: String in OS.get_cmdline_user_args():
		if arg.begins_with("--port="):
			port = arg.get_slice("=", 1).to_int()
		elif arg.begins_with("--role="):
			role = arg.get_slice("=", 1)
		elif arg.begins_with("--timeout="):
			timeout_s = arg.get_slice("=", 1).to_float()


func _process(delta: float) -> bool:
	if _done:
		return true
	elapsed += delta
	_update_held(delta)
	if not _connected_once:
		_connected_once = true
		var err: Error = _connect()
		if err != OK:
			return finish(false, "%s could not start: %s" % [role, error_string(err)])
	if _step(elapsed):
		return true
	if elapsed > timeout_s:
		return finish(false, "%s timed out after %.0f s: %s" % [role, timeout_s, describe()])
	return false


## Override: one step of the test. Return true once finish() was called.
func _step(_elapsed: float) -> bool:
	return false


## Override: state for the timeout message.
func describe() -> String:
	return ""


func is_host() -> bool:
	return role == "host"


func network() -> Node:
	return root.get_node_or_null(^"Network")


## Instantiates the project's main scene (if set) under root. Call it in _step
## on the first frame if the test needs the real game.
func instantiate_main_scene() -> Node:
	var path: String = ProjectSettings.get_setting("application/run/main_scene", "")
	if path.is_empty():
		return null
	main = (load(path) as PackedScene).instantiate()
	root.add_child(main)
	return main


func press(action: StringName) -> void:
	Input.action_press(action)


func release(action: StringName) -> void:
	_held.erase(action)
	Input.action_release(action)


## Holds an action for `seconds` (released automatically).
func press_for(action: StringName, seconds: float) -> void:
	_held[action] = seconds
	Input.action_press(action)


func finish(ok: bool, what: String) -> bool:
	if _done:
		return true
	_done = true
	for action: StringName in _held.keys():
		Input.action_release(action)
	print("RESULT %s %s: %s" % ["PASS" if ok else "FAIL", role, what])
	quit(0 if ok else 1)
	return true


func _connect() -> Error:
	var net: Node = network()
	if net == null:
		return ERR_UNCONFIGURED
	net.set(&"player_name", role.capitalize())
	if is_host():
		return net.call(&"host_game", port)
	return net.call(&"join_game", LOCALHOST, port)


func _update_held(delta: float) -> void:
	for action: StringName in _held.keys():
		_held[action] = float(_held[action]) - delta
		if float(_held[action]) <= 0.0:
			release(action)
