extends SceneTree
## Sandbox: `-- --sandbox` starts the arena (SandboxBoot), F1 opens the panel,
## registered tools show up and run, time scale and cheats apply, spawning is
## validated (unknown ids ignored, MAX_SPAWNED cap) and clearing works.
##   godot --headless ... --fixed-fps 60 -s res://tests/sandbox/test_sandbox.gd -- --sandbox

const TIMEOUT_FRAMES: int = 600
const TOOL_LABEL: String = "Test tool"

var _fails: Array[String] = []
var _frame: int = 0
var _sandbox: Sandbox = null
var _tool_calls: int = 0
var _step: int = 0


func _initialize() -> void:
	Sandbox.register_button("Tests", TOOL_LABEL, func() -> void: _tool_calls += 1)


func _process(_delta: float) -> bool:
	_frame += 1
	if _frame > TIMEOUT_FRAMES:
		_fails.append("timeout at step %d" % _step)
		return _finish()
	match _step:
		0:
			_sandbox = root.get_tree().get_first_node_in_group(Sandbox.GROUP) as Sandbox
			if _sandbox == null or _sandbox.panel == null:
				return false
			_check(current_scene == _sandbox, "--sandbox makes the arena the current scene")
			_check(not _sandbox.panel.is_open(), "panel starts closed")
			var f1 := InputEventKey.new()
			f1.physical_keycode = KEY_F1
			f1.pressed = true
			Input.parse_input_event(f1)
			_step = 1
		1:
			if not _sandbox.panel.is_open():
				return false
			var tool: Button = _sandbox.panel.find_control(TOOL_LABEL) as Button
			_check(tool != null, "registered tool is in the panel")
			if tool:
				tool.pressed.emit()
			_check(_tool_calls == 1, "registered tool runs")
			_sandbox.request_time_scale(0.5)
			_check(is_equal_approx(Engine.time_scale, 0.5), "time scale applies (%.2f)" % Engine.time_scale)
			_sandbox.request_time_scale(100.0)
			_check(is_equal_approx(Engine.time_scale, Sandbox.TIME_SCALE_MAX), "time scale is clamped")
			_sandbox.request_cheat(&"no_cooldowns", true)
			_check(DevCheats.no_cooldowns, "no cooldowns cheat")
			_sandbox.request_spawn(&"no_such_thing", 3)
			_sandbox.request_spawn(Sandbox.DUMMY_ID, 3)
			_step = 2
		2:
			if _sandbox.spawned_count() < 3:
				return false
			_check(_sandbox.spawned_count() == 3, "3 dummies, unknown id ignored (%d)" % _sandbox.spawned_count())
			_sandbox.request_spawn(Sandbox.DUMMY_ID, Sandbox.MAX_SPAWNED * 2)
			_step = 3
		3:
			_check(_sandbox.spawned_count() == Sandbox.MAX_SPAWNED, "spawn cap (%d)" % _sandbox.spawned_count())
			_sandbox.request_clear()
			_step = 4
		4:
			if _sandbox.spawned_count() > 0:
				return false
			Engine.time_scale = 1.0
			DevCheats.reset()
			return _finish()
	return false


func _check(ok: bool, what: String) -> void:
	if not ok:
		_fails.append(what)


func _finish() -> bool:
	# Registered lambdas point at this script: drop them before the engine shuts down.
	Sandbox.clear_registry()
	if _fails.is_empty():
		print("RESULT PASS sandbox")
		quit(0)
	else:
		for f: String in _fails:
			print("FAIL ", f)
		print("RESULT FAIL sandbox: %d" % _fails.size())
		quit(1)
	return true
