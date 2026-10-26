class_name SandboxPanel
extends CanvasLayer
## The sandbox tool panel on this peer (toggle with F1): time scale, cheats,
## spawning and every button/toggle registered with Sandbox.register_*().
## F1 is read directly from the key event (not an input action) because
## this is a dev tool; F-keys are not part of the game's controls.
## Dev-only text, English, not translated.

const TOGGLE_KEY: Key = KEY_F1
const LAYER: int = 20
const MARGIN: Vector2 = Vector2(16, 16)
const PANEL_WIDTH: float = 320.0
const SPACING: int = 6
const TITLE: String = "Sandbox (F1)"
const TIME_SCALE_LABEL: String = "Time scale"
const TIME_SCALE_STEP: float = 0.05
const SPAWN_BUTTON: String = "Spawn"
const CLEAR_BUTTON: String = "Clear spawned"
const CHEATS: Dictionary = {&"no_cooldowns": "No cooldowns", &"god_mode": "God mode"}

var _sandbox: Sandbox = null
var _panel: PanelContainer = null
var _sections: Dictionary = {}
var _time_slider: HSlider = null
var _spawn_option: OptionButton = null
var _buttons: Dictionary = {}


func _ready() -> void:
	layer = LAYER


func setup(sandbox: Sandbox) -> void:
	_sandbox = sandbox
	_build()
	_panel.visible = false
	sandbox.changed.connect(_sync)


func is_open() -> bool:
	return _panel != null and _panel.visible


func set_open(open: bool) -> void:
	_panel.visible = open
	if open:
		_sync()


## The control registered under `label` (tests and tools).
func find_control(label: String) -> Control:
	return _buttons.get(label)


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo and (event as InputEventKey).physical_keycode == TOGGLE_KEY:
		set_open(not is_open())
		get_viewport().set_input_as_handled()


func _build() -> void:
	_panel = PanelContainer.new()
	_panel.position = MARGIN
	_panel.custom_minimum_size.x = PANEL_WIDTH
	add_child(_panel)
	var column := VBoxContainer.new()
	column.add_theme_constant_override(&"separation", SPACING)
	_panel.add_child(column)
	column.add_child(_label(TITLE))
	column.add_child(_label(TIME_SCALE_LABEL))
	_time_slider = HSlider.new()
	_time_slider.min_value = Sandbox.TIME_SCALE_MIN
	_time_slider.max_value = Sandbox.TIME_SCALE_MAX
	_time_slider.step = TIME_SCALE_STEP
	_time_slider.value = Engine.time_scale
	_time_slider.value_changed.connect(func(v: float) -> void: _sandbox.request_time_scale(v))
	column.add_child(_time_slider)
	for cheat: StringName in CHEATS:
		_add_toggle(column, CHEATS[cheat], func(on: bool) -> void: _sandbox.request_cheat(cheat, on))
	column.add_child(_label(Sandbox.SECTION_SPAWN))
	_spawn_option = OptionButton.new()
	for id: StringName in Sandbox.spawnable_ids():
		_spawn_option.add_item(String(id))
	column.add_child(_spawn_option)
	_add_button(column, SPAWN_BUTTON, _spawn_selected)
	_add_button(column, CLEAR_BUTTON, func() -> void: _sandbox.request_clear())
	for tool: Dictionary in Sandbox.tools():
		var section: VBoxContainer = _section(column, str(tool["section"]))
		if tool["kind"] == "toggle":
			_add_toggle(section, str(tool["label"]), tool["callable"])
		else:
			_add_button(section, str(tool["label"]), tool["callable"])


func _section(column: VBoxContainer, title: String) -> VBoxContainer:
	if not _sections.has(title):
		column.add_child(_label(title))
		var box := VBoxContainer.new()
		column.add_child(box)
		_sections[title] = box
	return _sections[title]


func _add_button(parent: Control, text: String, callable: Callable) -> void:
	var button := Button.new()
	button.text = text
	button.auto_translate_mode = Node.AUTO_TRANSLATE_MODE_DISABLED
	button.pressed.connect(callable)
	parent.add_child(button)
	_buttons[text] = button


func _add_toggle(parent: Control, text: String, callable: Callable) -> void:
	var check := CheckBox.new()
	check.text = text
	check.auto_translate_mode = Node.AUTO_TRANSLATE_MODE_DISABLED
	check.toggled.connect(callable)
	parent.add_child(check)
	_buttons[text] = check


func _label(text: String) -> Label:
	var label := Label.new()
	label.text = text
	label.auto_translate_mode = Node.AUTO_TRANSLATE_MODE_DISABLED
	return label


func _spawn_selected() -> void:
	if _spawn_option.selected >= 0:
		_sandbox.request_spawn(StringName(_spawn_option.get_item_text(_spawn_option.selected)))


func _sync() -> void:
	_time_slider.set_value_no_signal(Engine.time_scale)
	(_buttons[CHEATS[&"no_cooldowns"]] as CheckBox).set_pressed_no_signal(DevCheats.no_cooldowns)
	(_buttons[CHEATS[&"god_mode"]] as CheckBox).set_pressed_no_signal(DevCheats.god_mode)
