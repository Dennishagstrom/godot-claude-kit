class_name UiModal
extends Control
## Modal dialog: dimmed backdrop, a centred UiPanel, closes on ui_cancel
## (Esc / B) and grabs focus for keyboard and gamepad. Build content in
## `panel.body`, or use UiModal.confirm() for a yes/no question.

signal closed
## confirm(): the player chose the confirm button.
signal confirmed

const DEFAULT_WIDTH: float = 520.0

var panel: UiPanel = null
var panel_width: float = DEFAULT_WIDTH
## Close when the player presses ui_cancel.
var cancellable: bool = true


## A yes/no modal under `parent`. Texts are English source text.
static func confirm(parent: Node, title: String, text: String, ok_text: String, cancel_text: String,
		dangerous: bool = false) -> UiModal:
	var modal := UiModal.new()
	modal.panel.title = title
	modal.panel.body.add_child(UiText.label(text, UiText.BODY, true))
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_END
	row.add_theme_constant_override(&"separation", UiTokens.S3)
	var cancel := UiButton.make(cancel_text, modal.close)
	var on_ok := func() -> void:
		modal.confirmed.emit()
		modal.close()
	var ok := UiButton.make(ok_text, on_ok, UiButton.Variant.DANGER if dangerous else UiButton.Variant.PRIMARY)
	row.add_child(cancel)
	row.add_child(ok)
	modal.panel.body.add_child(row)
	parent.add_child(modal)
	(cancel if dangerous else ok).grab_focus.call_deferred()
	return modal


func _init() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	theme = UiTokens.theme()
	var backdrop := ColorRect.new()
	backdrop.color = UiTokens.BACKDROP
	backdrop.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(backdrop)
	var center := CenterContainer.new()
	center.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(center)
	panel = UiPanel.new()
	center.add_child(panel)


func _ready() -> void:
	panel.custom_minimum_size.x = panel_width


func _unhandled_input(event: InputEvent) -> void:
	if cancellable and event.is_action_pressed(&"ui_cancel"):
		get_viewport().set_input_as_handled()
		close()


func close() -> void:
	closed.emit()
	queue_free()
