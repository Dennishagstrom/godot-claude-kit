class_name UiButton
extends Button
## Button in one of three variants (theme type variations from UiTokens).
## PRIMARY is the one action a screen wants (one per screen), DANGER only for
## destructive actions. Text is English source text (auto-translated).

enum Variant { SECONDARY, PRIMARY, DANGER }

var variant: Variant = Variant.SECONDARY:
	set(value):
		variant = value
		theme_type_variation = [&"", UiTokens.VAR_PRIMARY, UiTokens.VAR_DANGER][value]


static func make(label: String, on_pressed: Callable = Callable(), kind: Variant = Variant.SECONDARY) -> UiButton:
	var button := UiButton.new()
	button.text = label
	button.variant = kind
	if on_pressed.is_valid():
		button.pressed.connect(on_pressed)
	return button


func _init() -> void:
	custom_minimum_size.y = UiTokens.BUTTON_HEIGHT
	focus_mode = Control.FOCUS_ALL
