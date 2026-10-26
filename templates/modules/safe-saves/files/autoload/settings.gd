extends Node
## Player-local settings (audio, mouse, display, key bindings) in
## user://settings.cfg, applied on start and live. Change values with
## set_value(key, value) so they are clamped, applied, saved and announced.
## Bindings edit the InputMap; only actions that differ from project.godot are saved.
##
## Headless runs (tests, servers) use the defaults and never write the
## player's file, so a player's preferences can never change a test result;
## a test that needs saving calls load_settings(<its own path>) first.
## Also tracks the last input device, so get_action_label() shows "Q" or "A".
## No class_name on purpose (autoload).

## A setting changed (KEY_BINDINGS for bindings, KEY_ALL after a load/reset).
signal changed(key: StringName)
signal input_device_changed(is_gamepad: bool)

enum PadStyle { XBOX, PLAYSTATION }

const SettingsLabels := preload("res://autoload/settings_labels.gd")
const DEFAULT_PATH: String = "user://settings.cfg"
const SECTION_VALUES: String = "settings"
const SECTION_BINDINGS: String = "bindings"
const KEY_BINDINGS: StringName = &"bindings"
const KEY_ALL: StringName = &"all"
## Every setting with its default (the default's type is the setting's type).
const DEFAULTS: Dictionary = {
	&"master_volume": 1.0,
	&"mouse_sensitivity": 1.0,
	&"invert_y": false,
	&"fullscreen": false,
}
## [min, max] for numeric settings.
const RANGES: Dictionary = {
	&"master_volume": [0.0, 1.0],
	&"mouse_sensitivity": [0.1, 5.0],
}
const MASTER_BUS: StringName = &"Master"
const GAMEPAD_AXIS_DEADZONE: float = 0.5
const PS_NAME_HINTS: Array[String] = ["playstation", "dualshock", "dualsense", "ps4", "ps5", "sony"]

var config_path: String = DEFAULT_PATH
var last_input_was_gamepad: bool = false
var pad_style: PadStyle = PadStyle.XBOX

var _values: Dictionary = {}
var _default_bindings: Dictionary = {}
var _headless: bool = false
var _save_queued: bool = false
var _labels: RefCounted = SettingsLabels.new(self)


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	_headless = DisplayServer.get_name() == "headless"
	for action: StringName in InputMap.get_actions():
		_default_bindings[action] = InputMap.action_get_events(action).duplicate()
	_values = DEFAULTS.duplicate()
	if not _headless:
		load_settings()


func _input(event: InputEvent) -> void:
	if event is InputEventJoypadButton or (event is InputEventJoypadMotion
			and absf((event as InputEventJoypadMotion).axis_value) >= GAMEPAD_AXIS_DEADZONE):
		_set_device(true, event.device)
	elif (event is InputEventKey or event is InputEventMouseButton) and event.is_pressed():
		_set_device(false, -1)


func get_value(key: StringName) -> Variant:
	return _values.get(key, DEFAULTS.get(key))


## Clamps, stores, applies, saves (deferred) and emits changed(key).
func set_value(key: StringName, value: Variant) -> void:
	if not DEFAULTS.has(key):
		push_warning("Settings: unknown key %s" % key)
		return
	_values[key] = _coerce(key, value)
	_apply(key)
	_queue_save()
	changed.emit(key)


## Loads `path` (default config_path); a missing file means defaults.
func load_settings(path: String = "") -> void:
	if not path.is_empty():
		config_path = path
	var cfg := ConfigFile.new()
	var ok: bool = cfg.load(config_path) == OK
	for key: StringName in DEFAULTS:
		_values[key] = _coerce(key, cfg.get_value(SECTION_VALUES, String(key), DEFAULTS[key]) if ok else DEFAULTS[key])
	_restore_default_bindings()
	if ok and cfg.has_section(SECTION_BINDINGS):
		for action_name: String in cfg.get_section_keys(SECTION_BINDINGS):
			var events: Variant = cfg.get_value(SECTION_BINDINGS, action_name, [])
			if InputMap.has_action(action_name) and events is Array:
				InputMap.action_erase_events(action_name)
				for event: Variant in events:
					if event is InputEvent:
						InputMap.action_add_event(action_name, event)
	for key: StringName in DEFAULTS:
		_apply(key)
	changed.emit(KEY_ALL)


func save_settings() -> Error:
	_save_queued = false
	if _is_protected_path():
		return OK
	var cfg := ConfigFile.new()
	for key: StringName in DEFAULTS:
		cfg.set_value(SECTION_VALUES, String(key), _values[key])
	for action: StringName in _default_bindings:
		var current: Array[InputEvent] = InputMap.action_get_events(action)
		if not _same_events(current, _default_bindings[action]):
			cfg.set_value(SECTION_BINDINGS, String(action), current)
	return cfg.save(config_path)


## Replaces the keyboard/mouse (pad = false) or gamepad binding of an action.
func rebind(action: StringName, event: InputEvent, pad: bool) -> void:
	for old: InputEvent in InputMap.action_get_events(action):
		if _is_pad(old) == pad:
			InputMap.action_erase_event(action, old)
	InputMap.action_add_event(action, event)
	_queue_save()
	changed.emit(KEY_BINDINGS)


func reset_bindings() -> void:
	_restore_default_bindings()
	_queue_save()
	changed.emit(KEY_BINDINGS)


## First binding of an action for one device kind (null if none).
func get_binding(action: StringName, pad: bool) -> InputEvent:
	if not InputMap.has_action(action):
		return null
	for event: InputEvent in InputMap.action_get_events(action):
		if _is_pad(event) == pad:
			return event
	return null


## UI label for an action on the last used device ("Q", "LMB", "A", "✕").
## Never hardcode key names in UI text: use this.
func get_action_label(action: StringName) -> String:
	return _labels.call(&"get_action_label", action)


func event_label(event: InputEvent) -> String:
	return _labels.call(&"event_label", event)


# --- private ---------------------------------------------------------------

func _coerce(key: StringName, value: Variant) -> Variant:
	var default: Variant = DEFAULTS[key]
	var result: Variant = type_convert(value, typeof(default))
	if RANGES.has(key):
		result = clampf(float(result), float(RANGES[key][0]), float(RANGES[key][1]))
	return result


func _apply(key: StringName) -> void:
	match key:
		&"master_volume":
			var bus: int = AudioServer.get_bus_index(MASTER_BUS)
			if bus >= 0:
				AudioServer.set_bus_volume_db(bus, linear_to_db(float(_values[key])))
		&"fullscreen":
			if not _headless:
				DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_FULLSCREEN if _values[key]
						else DisplayServer.WINDOW_MODE_WINDOWED)


func _restore_default_bindings() -> void:
	for action: StringName in _default_bindings:
		InputMap.action_erase_events(action)
		for event: InputEvent in _default_bindings[action]:
			InputMap.action_add_event(action, event)


func _queue_save() -> void:
	if _save_queued or _is_protected_path():
		return
	_save_queued = true
	save_settings.call_deferred()


## Headless runs never write the player's own file.
func _is_protected_path() -> bool:
	return _headless and config_path == DEFAULT_PATH


func _set_device(gamepad: bool, device: int) -> void:
	if gamepad and device >= 0:
		var joy_name: String = Input.get_joy_name(device).to_lower()
		pad_style = PadStyle.PLAYSTATION if PS_NAME_HINTS.any(func(h: String) -> bool: return joy_name.contains(h)) \
				else PadStyle.XBOX
	if gamepad != last_input_was_gamepad:
		last_input_was_gamepad = gamepad
		input_device_changed.emit(gamepad)


static func _is_pad(event: InputEvent) -> bool:
	return event is InputEventJoypadButton or event is InputEventJoypadMotion


static func _same_events(a: Array, b: Array) -> bool:
	if a.size() != b.size():
		return false
	for i: int in a.size():
		if not (a[i] as InputEvent).is_match(b[i] as InputEvent, true):
			return false
	return true
