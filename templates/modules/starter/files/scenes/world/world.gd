class_name World
extends {{#3D}}Node3D{{/3D}}{{^3D}}Node2D{{/3D}}
## The play area: {{#3D}}floor, light, camera{{/3D}}{{^3D}}camera{{/3D}} and one Player per player{{#MULTIPLAYER}}. The server adds a
## Player for every roster entry (Network.players) and $PlayerSpawner replicates them
## to the clients; clients never add players themselves{{/MULTIPLAYER}}.

signal player_added(player: Player)

const PLAYER_SCENE: PackedScene = preload("res://scenes/player/player.tscn")
## Distance between spawn points.
const SPAWN_SPACING: float = {{#3D}}2.0{{/3D}}{{^3D}}64.0{{/3D}}
{{^MULTIPLAYER}}const LOCAL_PLAYER_ID: int = 1
{{/MULTIPLAYER}}
@onready var players: {{#3D}}Node3D{{/3D}}{{^3D}}Node2D{{/3D}} = $Players
{{#MULTIPLAYER}}## Network by path, not by its global name: test scripts (-s) compile class_name
## scripts like this one before the autoloads exist.
@onready var _network: Node = get_node(^"/root/Network")
{{/MULTIPLAYER}}

func _ready() -> void:
{{#MULTIPLAYER}}	if not multiplayer.is_server():
		return
	_network.connect(&"roster_changed", _sync_players)
	_sync_players()
{{/MULTIPLAYER}}{{^MULTIPLAYER}}	_add_player(LOCAL_PLAYER_ID)
{{/MULTIPLAYER}}


## The Player for a peer, or null.
func get_player(peer_id: int) -> Player:
	return players.get_node_or_null(str(peer_id)) as Player
{{#MULTIPLAYER}}


## Server: one Player per roster entry (adds new ones, frees the ones who left).
func _sync_players() -> void:
	var roster: Dictionary = _network.get(&"players")
	for child: Node in players.get_children():
		if not roster.has(child.name.to_int()):
			child.queue_free()
	for peer_id: int in roster:
		if get_player(peer_id) == null:
			_add_player(peer_id)
{{/MULTIPLAYER}}


func _add_player(peer_id: int) -> void:
	var player: Player = PLAYER_SCENE.instantiate() as Player
	# The name is the peer id: Player reads it, and the path is the same on every peer.
	player.name = str(peer_id)
	var index: int = players.get_child_count()
{{#3D}}	player.position = Vector3(index * SPAWN_SPACING, 0.0, 0.0)
{{/3D}}{{^3D}}	player.position = Vector2(index * SPAWN_SPACING, 0.0)
{{/3D}}	players.add_child(player, true)
	player_added.emit(player)
