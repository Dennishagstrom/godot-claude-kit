extends Node
## Starts the training arena when the game runs with `-- --sandbox`: replaces
## the current scene with a Sandbox{{#MULTIPLAYER}} and hosts (port from --port=N, so
## friends can join the same arena){{/MULTIPLAYER}}. Does nothing otherwise.
## Register sandbox tools from anywhere before or after it starts
## (Sandbox.register_button / register_toggle / register_spawnable).
## No class_name on purpose (autoload).

const FLAG: String = "--sandbox"
{{#MULTIPLAYER}}const PORT_ARG: String = "--port="
{{/MULTIPLAYER}}
## The running sandbox (null when not started).
var sandbox: Sandbox = null


func _ready() -> void:
	if OS.get_cmdline_user_args().has(FLAG):
		_start.call_deferred()


func is_requested() -> bool:
	return OS.get_cmdline_user_args().has(FLAG)


func _start() -> void:
	var tree: SceneTree = get_tree()
	var old: Node = tree.current_scene
	sandbox = Sandbox.new()
	tree.root.add_child(sandbox)
	tree.current_scene = sandbox
	if old != null:
		old.queue_free()
{{#MULTIPLAYER}}	var network: Node = tree.root.get_node_or_null(^"Network")
	if network == null or network.call(&"is_online"):
		return
	var port: int = int(network.get_script().get_script_constant_map().get("DEFAULT_PORT", 0))
	for arg: String in OS.get_cmdline_user_args():
		if arg.begins_with(PORT_ARG):
			port = arg.trim_prefix(PORT_ARG).to_int()
	network.call(&"host_game", port)
{{/MULTIPLAYER}}