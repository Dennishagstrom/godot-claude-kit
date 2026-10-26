extends SceneTree
## Safe saves: headless runs use the throwaway slot (or --save=<slot>), JSON
## saves are atomic with a backup that rescues a corrupt file, Settings never
## writes the player's settings file when headless but does write a custom
## path, and action labels follow the last used device.
##   -- [--save=<slot>] [--expect-slot=<slot>]

const FILE: String = "kit_test.json"
const CUSTOM_SETTINGS: String = "user://kit_test_settings.cfg"
const PLAYER_SETTINGS: String = "user://settings.cfg"
const TEST_ACTION: StringName = &"kit_test_action"

var _fails: Array[String] = []
var _expect_slot: String = "headless"
var _frame: int = 0


func _initialize() -> void:
	for arg: String in OS.get_cmdline_user_args():
		if arg.begins_with("--expect-slot="):
			_expect_slot = arg.get_slice("=", 1)


func _process(_delta: float) -> bool:
	_frame += 1
	if _frame == 1:
		_static_checks()
		# Gamepad press: the label must switch to the pad binding next frame.
		var press := InputEventJoypadButton.new()
		press.button_index = JOY_BUTTON_A
		press.pressed = true
		Input.parse_input_event(press)
		return false
	if _frame < 4:
		return false
	var settings: Node = root.get_node(^"Settings")
	_check(settings.get(&"last_input_was_gamepad") == true, "gamepad input switches the device")
	_check(settings.call(&"get_action_label", TEST_ACTION) == "A", "pad label (%s)" % settings.call(&"get_action_label", TEST_ACTION))
	_finish()
	return true


func _static_checks() -> void:
	var slots: Node = root.get_node(^"SaveSlots")
	_check(slots.get(&"slot") == _expect_slot, "slot is %s (got %s)" % [_expect_slot, slots.get(&"slot")])
	_check(slots.get(&"is_test_run") == true, "headless counts as a test run")
	_check(str(slots.call(&"path", FILE)).begins_with("user://saves/%s/" % _expect_slot), "path inside the slot")
	_check(slots.call(&"save_json", FILE, {"a": 1}) == OK, "save_json")
	_check(slots.call(&"save_json", FILE, {"a": 2}) == OK, "save_json again (makes a .bak)")
	_check(int(slots.call(&"load_json", FILE, {})["a"]) == 2, "load_json round trip")
	var f: FileAccess = FileAccess.open(slots.call(&"path", FILE), FileAccess.WRITE)
	f.store_string("{ corrupt")
	f.close()
	_check(int(slots.call(&"load_json", FILE, {}).get("a", 0)) == 1, "corrupt file falls back to the backup")
	slots.call(&"delete_file", FILE)
	_check(not slots.call(&"exists", FILE), "delete_file")
	var settings: Node = root.get_node(^"Settings")
	var before: int = FileAccess.get_modified_time(PLAYER_SETTINGS) if FileAccess.file_exists(PLAYER_SETTINGS) else -1
	settings.call(&"set_value", &"mouse_sensitivity", 99.0)
	_check(is_equal_approx(settings.call(&"get_value", &"mouse_sensitivity"), 5.0), "values are clamped")
	settings.call(&"save_settings")
	var after: int = FileAccess.get_modified_time(PLAYER_SETTINGS) if FileAccess.file_exists(PLAYER_SETTINGS) else -1
	_check(before == after, "headless never writes the player's settings file")
	settings.call(&"load_settings", CUSTOM_SETTINGS)
	settings.call(&"set_value", &"invert_y", true)
	settings.call(&"save_settings")
	settings.call(&"load_settings", CUSTOM_SETTINGS)
	_check(settings.call(&"get_value", &"invert_y") == true, "custom settings path saves and loads")
	DirAccess.remove_absolute(CUSTOM_SETTINGS)
	InputMap.add_action(TEST_ACTION)
	var key := InputEventKey.new()
	key.physical_keycode = KEY_Q
	InputMap.action_add_event(TEST_ACTION, key)
	var pad := InputEventJoypadButton.new()
	pad.button_index = JOY_BUTTON_A
	InputMap.action_add_event(TEST_ACTION, pad)
	_check(settings.call(&"get_action_label", TEST_ACTION) == "Q", "keyboard label (%s)" % settings.call(&"get_action_label", TEST_ACTION))


func _check(ok: bool, what: String) -> void:
	if not ok:
		_fails.append(what)


func _finish() -> void:
	if _fails.is_empty():
		print("RESULT PASS safe saves (slot %s)" % _expect_slot)
		quit(0)
	else:
		for f: String in _fails:
			print("FAIL ", f)
		print("RESULT FAIL safe saves: %d" % _fails.size())
		quit(1)
