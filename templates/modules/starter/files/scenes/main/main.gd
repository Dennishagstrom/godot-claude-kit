extends Node
## Game entry (application/run/main_scene): shows the main menu and swaps in the
## world when a game starts{{#MULTIPLAYER}} (hosted or joined), back to the menu when the session ends{{/MULTIPLAYER}}.
## Owns the flow only; the menu, world and players live in their own scenes.

const MENU_SCENE: PackedScene = preload("res://scenes/menu/main_menu.tscn")
const WORLD_SCENE: PackedScene = preload("res://scenes/world/world.tscn")
{{#MULTIPLAYER}}const MSG_HOST_FAILED: String = "Couldn't host: %s"
const MSG_JOINING: String = "Joining %s..."
{{/MULTIPLAYER}}
var menu: MainMenu = null
var world: World = null


func _ready() -> void:
{{#MULTIPLAYER}}	Network.hosted.connect(start_game)
	Network.joined.connect(start_game)
	Network.left.connect(show_menu)
	Network.join_failed.connect(_on_join_failed)
{{/MULTIPLAYER}}	if world == null:
		show_menu()


func _unhandled_input(event: InputEvent) -> void:
	if world != null and event.is_action_pressed(&"pause"):
		get_viewport().set_input_as_handled()
{{#MULTIPLAYER}}		if Network.is_online():
			Network.leave()  # emits left -> show_menu()
			return
{{/MULTIPLAYER}}		show_menu()


func show_menu() -> void:
	if menu != null and world == null:
		return
	_clear()
	menu = MENU_SCENE.instantiate() as MainMenu
{{#MULTIPLAYER}}	menu.host_pressed.connect(_on_host_pressed)
	menu.join_pressed.connect(_on_join_pressed)
{{/MULTIPLAYER}}{{^MULTIPLAYER}}	menu.play_pressed.connect(start_game)
{{/MULTIPLAYER}}	menu.quit_pressed.connect(get_tree().quit)
	add_child(menu)


func start_game() -> void:
	# A dev tool (e.g. --sandbox) may have replaced this scene already.
	if is_queued_for_deletion() or world != null:
		return
	_clear()
	world = WORLD_SCENE.instantiate() as World
	# Same node path on every peer, so spawns and syncs find their nodes.
	world.name = "World"
	add_child(world)


func _clear() -> void:
	for node: Node in [menu, world]:
		if node != null:
			# Out of the tree at once: a new World must get the name "World", not "World2".
			remove_child(node)
			node.queue_free()
	menu = null
	world = null
{{#MULTIPLAYER}}

func _on_host_pressed(player_name: String) -> void:
	Network.player_name = player_name
	var err: Error = Network.host_game()
	if err != OK and menu != null:
		menu.show_status(tr(MSG_HOST_FAILED) % error_string(err))


## address is "host" or "host:port".
func _on_join_pressed(player_name: String, address: String) -> void:
	Network.player_name = player_name
	var host: String = address.strip_edges()
	var port: int = Network.DEFAULT_PORT
	if host.contains(":"):
		port = host.get_slice(":", 1).to_int()
		host = host.get_slice(":", 0)
	if host.is_empty():
		host = Network.DEFAULT_ADDRESS
	if menu != null:
		menu.show_status(tr(MSG_JOINING) % host)
	Network.join_game(host, port)


func _on_join_failed(reason: String) -> void:
	if menu != null:
		menu.show_status(reason)
{{/MULTIPLAYER}}
