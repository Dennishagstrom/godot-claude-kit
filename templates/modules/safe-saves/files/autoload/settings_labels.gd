extends RefCounted
## Settings module: short labels for bindings ("Q", "LMB", "A", "✕", "LT"),
## following the last used device and pad style. Reached through
## Settings.get_action_label(). Preloaded without class_name so nothing
## compiles it before the autoloads exist. Key names are not translated.

const XBOX_BUTTONS: Dictionary = {
	JOY_BUTTON_A: "A", JOY_BUTTON_B: "B", JOY_BUTTON_X: "X", JOY_BUTTON_Y: "Y",
	JOY_BUTTON_BACK: "View", JOY_BUTTON_GUIDE: "Guide", JOY_BUTTON_START: "Menu",
	JOY_BUTTON_LEFT_STICK: "LS", JOY_BUTTON_RIGHT_STICK: "RS",
	JOY_BUTTON_LEFT_SHOULDER: "LB", JOY_BUTTON_RIGHT_SHOULDER: "RB",
	JOY_BUTTON_DPAD_UP: "D-pad up", JOY_BUTTON_DPAD_DOWN: "D-pad down",
	JOY_BUTTON_DPAD_LEFT: "D-pad left", JOY_BUTTON_DPAD_RIGHT: "D-pad right",
}
const PS_BUTTONS: Dictionary = {
	JOY_BUTTON_A: "✕", JOY_BUTTON_B: "○", JOY_BUTTON_X: "□", JOY_BUTTON_Y: "△",
	JOY_BUTTON_BACK: "Share", JOY_BUTTON_GUIDE: "PS", JOY_BUTTON_START: "Options",
	JOY_BUTTON_LEFT_STICK: "L3", JOY_BUTTON_RIGHT_STICK: "R3",
	JOY_BUTTON_LEFT_SHOULDER: "L1", JOY_BUTTON_RIGHT_SHOULDER: "R1",
	JOY_BUTTON_DPAD_UP: "D-pad up", JOY_BUTTON_DPAD_DOWN: "D-pad down",
	JOY_BUTTON_DPAD_LEFT: "D-pad left", JOY_BUTTON_DPAD_RIGHT: "D-pad right",
}
const XBOX_TRIGGERS: Dictionary = {JOY_AXIS_TRIGGER_LEFT: "LT", JOY_AXIS_TRIGGER_RIGHT: "RT"}
const PS_TRIGGERS: Dictionary = {JOY_AXIS_TRIGGER_LEFT: "L2", JOY_AXIS_TRIGGER_RIGHT: "R2"}
const STICK_NAMES: Dictionary = {
	JOY_AXIS_LEFT_X: "LS", JOY_AXIS_LEFT_Y: "LS", JOY_AXIS_RIGHT_X: "RS", JOY_AXIS_RIGHT_Y: "RS",
}
const MOUSE_BUTTONS: Dictionary = {
	MOUSE_BUTTON_LEFT: "LMB", MOUSE_BUTTON_RIGHT: "RMB", MOUSE_BUTTON_MIDDLE: "MMB",
	MOUSE_BUTTON_WHEEL_UP: "Wheel up", MOUSE_BUTTON_WHEEL_DOWN: "Wheel down",
}
const UNBOUND: String = "-"
const OTHER_PAD_BUTTON: String = "Button %d"
const OTHER_MOUSE_BUTTON: String = "M%d"

var _settings: Node = null


func _init(settings: Node) -> void:
	_settings = settings


## The action's binding on the last used device, falling back to the other device.
func get_action_label(action: StringName) -> String:
	var pad: bool = _settings.get(&"last_input_was_gamepad")
	var event: InputEvent = _settings.call(&"get_binding", action, pad)
	if event == null:
		event = _settings.call(&"get_binding", action, not pad)
	return event_label(event)


func event_label(event: InputEvent) -> String:
	var playstation: bool = int(_settings.get(&"pad_style")) == 1
	if event is InputEventKey:
		var key: InputEventKey = event
		return key.as_text_physical_keycode() if key.physical_keycode != KEY_NONE else key.as_text_keycode()
	if event is InputEventMouseButton:
		var index: int = (event as InputEventMouseButton).button_index
		return MOUSE_BUTTONS.get(index, OTHER_MOUSE_BUTTON % index)
	if event is InputEventJoypadButton:
		var button: int = (event as InputEventJoypadButton).button_index
		return (PS_BUTTONS if playstation else XBOX_BUTTONS).get(button, OTHER_PAD_BUTTON % button)
	if event is InputEventJoypadMotion:
		var axis: int = (event as InputEventJoypadMotion).axis
		var triggers: Dictionary = PS_TRIGGERS if playstation else XBOX_TRIGGERS
		return triggers.get(axis, STICK_NAMES.get(axis, UNBOUND))
	return UNBOUND
