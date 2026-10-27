class_name MainMenu
extends Control
## Main menu: {{#MULTIPLAYER}}player name, Host, Join (address or address:port){{/MULTIPLAYER}}{{^MULTIPLAYER}}Play{{/MULTIPLAYER}} and Quit. Emits what the
## player picked; scenes/main/main.gd acts on it. Text is translated by the Controls
## (auto-translate); status lines come in already translated.

{{#MULTIPLAYER}}signal host_pressed(player_name: String)
signal join_pressed(player_name: String, address: String)
{{/MULTIPLAYER}}{{^MULTIPLAYER}}signal play_pressed
{{/MULTIPLAYER}}signal quit_pressed

{{#MULTIPLAYER}}@onready var _name_edit: LineEdit = %NameEdit
@onready var _address_edit: LineEdit = %AddressEdit
@onready var _status: Label = %Status
{{/MULTIPLAYER}}

func _ready() -> void:
{{#MULTIPLAYER}}	%HostButton.pressed.connect(func() -> void: host_pressed.emit(_player_name()))
	%JoinButton.pressed.connect(func() -> void: join_pressed.emit(_player_name(), _address_edit.text))
	%HostButton.grab_focus()
{{/MULTIPLAYER}}{{^MULTIPLAYER}}	%PlayButton.pressed.connect(play_pressed.emit)
	%PlayButton.grab_focus()
{{/MULTIPLAYER}}	%QuitButton.pressed.connect(quit_pressed.emit)
{{#MULTIPLAYER}}

## Shows one line under the buttons (pass translated text).
func show_status(text: String) -> void:
	_status.text = text


func _player_name() -> String:
	return _name_edit.text.strip_edges()
{{/MULTIPLAYER}}
