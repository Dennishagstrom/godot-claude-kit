extends SceneTree
## Starter flow in one process: the main scene shows the menu, starting a game
## {{#MULTIPLAYER}}(hosting, no clients) {{/MULTIPLAYER}}loads the world with the local player, the move_right
## action moves it, teleport() moves it at once and resets its motion, and pause goes
## back to the menu. Runs with --fixed-fps 60 (suite starter) and in real time (starter_rt).
##   godot --headless --audio-driver Dummy --fixed-fps 60 --path . -s res://tests/starter/test_starter.gd{{#MULTIPLAYER}} -- --port=7783{{/MULTIPLAYER}}
## Prints "RESULT PASS" / "RESULT FAIL ..." and exits 0 / 1.

const MAIN_SCENE: String = "res://scenes/main/main.tscn"
## Physics ticks the player walks (and the most any step may wait).
const MOVE_TICKS: int = 30
const WAIT_TICKS: int = 300
const MIN_DISTANCE: float = {{#3D}}0.5{{/3D}}{{^3D}}20.0{{/3D}}
const TELEPORT_TO: {{#3D}}Vector3 = Vector3(-6, 0, 3){{/3D}}{{^3D}}Vector2 = Vector2(-200, 80){{/3D}}

var _main: Node = null
var _step: int = 0
var _ticks: int = 0
var _player: Player = null
var _start_x: float = 0.0
var _teleports: int = 0
{{#MULTIPLAYER}}var _port: int = 7783
{{/MULTIPLAYER}}

func _initialize() -> void:
{{#MULTIPLAYER}}	for arg: String in OS.get_cmdline_user_args():
		if arg.begins_with("--port="):
			_port = arg.get_slice("=", 1).to_int()
{{/MULTIPLAYER}}	physics_frame.connect(func() -> void: _ticks += 1)


func _process(_delta: float) -> bool:
	match _step:
		0:
			# Autoloads exist from the first frame; build the game here, not in _initialize().
			_main = (load(MAIN_SCENE) as PackedScene).instantiate()
			root.add_child(_main)
			_next()
		1:
			if _main.get(&"menu") == null:
				return _finish(false, "no menu after start")
{{#MULTIPLAYER}}			var err: Error = root.get_node(^"Network").call(&"host_game", _port)
			if err != OK:
				return _finish(false, "host_game failed: %s" % error_string(err))
{{/MULTIPLAYER}}{{^MULTIPLAYER}}			_main.call(&"start_game")
{{/MULTIPLAYER}}			_next()
		2:
			var world: World = _main.get(&"world")
			_player = world.get_player(1) if world != null else null
			if _player != null and _player.is_inside_tree():
				_start_x = _player.position.x
				Input.action_press(&"move_right")
				_next()
			elif _ticks > WAIT_TICKS:
				return _finish(false, "no local player in the world")
		3:
			if _ticks >= MOVE_TICKS:
				Input.action_release(&"move_right")
				var moved: float = _player.position.x - _start_x
				if moved < MIN_DISTANCE:
					return _finish(false, "move_right moved the player %.2f (want >= %.2f)" % [moved, MIN_DISTANCE])
				_player.teleported.connect(func() -> void: _teleports += 1)
				_player.teleport(TELEPORT_TO)
				if _teleports != 1 or _player.position.distance_to(TELEPORT_TO) > 0.01 or \
						_player.velocity.length() > 0.01:
					return _finish(false, "teleport: signals %d, at %s, velocity %s" % [
						_teleports, _player.position, _player.velocity])
				_press_pause()
				_next()
		4:
			if _main.get(&"menu") != null and _main.get(&"world") == null:
				return _finish(true, "menu -> world -> player moves -> teleport -> pause -> menu")
			if _ticks > WAIT_TICKS:
				return _finish(false, "pause did not return to the menu")
	return false


func _next() -> void:
	_step += 1
	_ticks = 0


func _press_pause() -> void:
	var event := InputEventAction.new()
	event.action = &"pause"
	event.pressed = true
	Input.parse_input_event(event)


func _finish(ok: bool, what: String) -> bool:
	print("RESULT %s starter: %s" % ["PASS" if ok else "FAIL", what])
	quit(0 if ok else 1)
	return true
