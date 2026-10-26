extends Node
## Steam lobbies and networking through GodotSteam, behind the Network
## autoload: a lobby host gets a SteamMultiplayerPeer and hands it to
## Network.adopt_peer(), so the roster, RPCs and synchronizers work exactly
## like with ENet (which stays the fallback and the dev/test transport).
## Degrades gracefully: without the GodotSteam GDExtension (or without a
## running Steam client) is_available() is false and every call fails with a
## reason instead of an error. All Steam calls go through Engine.get_singleton
## and ClassDB, so this script parses without GodotSteam installed.
## Setup and Steamworks steps: docs/modules/steam.md. No class_name (autoload).

signal lobby_created(lobby_id: int)
signal lobby_joined(lobby_id: int)
## Creating or joining failed; reason is player-facing (translated).
signal lobby_failed(reason: String)

## Valve's public test app (Spacewar). Replace with your own app id, or set
## the project setting below (GodotSteam 4.14+ also reads it itself).
const TEST_APP_ID: int = 480
const APP_ID_SETTING: String = "steam/initialization/app_id"
const SINGLETON: StringName = &"Steam"
const PEER_CLASS: StringName = &"SteamMultiplayerPeer"
## Steamworks ELobbyType.
const LOBBY_PRIVATE: int = 0
const LOBBY_FRIENDS_ONLY: int = 1
const LOBBY_PUBLIC: int = 2
## Steamworks EResult / EChatRoomEnterResponse success values.
const RESULT_OK: int = 1
const ENTER_SUCCESS: int = 1
const INIT_OK: int = 0
## Virtual port for SteamMultiplayerPeer (like an ENet port, but per Steam id).
const VIRTUAL_PORT: int = 0
## Launch option Steam passes when a friend accepts an invite before the game runs.
const CONNECT_ARG: String = "+connect_lobby"
const LOBBY_NAME_KEY: String = "name"
const MSG_UNAVAILABLE: String = "Steam is not available. Use direct connect instead."
const MSG_CREATE_FAILED: String = "Could not create a Steam lobby."
const MSG_JOIN_FAILED: String = "Could not join the Steam lobby."
const MSG_NO_PEER: String = "This GodotSteam build has no SteamMultiplayerPeer."

## The lobby we are in (0 = none).
var lobby_id: int = 0
## Why Steam is unavailable ("" when it is available).
var unavailable_reason: String = ""

var _steam: Object = null


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	if not Engine.has_singleton(SINGLETON):
		unavailable_reason = "GodotSteam is not installed"
		print("[Steam] %s: ENet only" % unavailable_reason)
		return
	var steam: Object = Engine.get_singleton(SINGLETON)
	var result: Variant = steam.call(&"steamInitEx", app_id(), false)
	var status: int = int((result as Dictionary).get("status", -1)) if result is Dictionary else -1
	if status != INIT_OK:
		unavailable_reason = "Steam did not start (%s)" % str(result)
		print("[Steam] %s: ENet only" % unavailable_reason)
		return
	_steam = steam
	_steam.connect(&"lobby_created", _on_lobby_created)
	_steam.connect(&"lobby_joined", _on_lobby_joined)
	_steam.connect(&"join_requested", _on_join_requested)
	print("[Steam] ready as %s (app %d)" % [_steam.call(&"getPersonaName"), app_id()])
	_join_from_launch_args.call_deferred()


func _process(_delta: float) -> void:
	if _steam:
		_steam.call(&"run_callbacks")


func is_available() -> bool:
	return _steam != null


static func app_id() -> int:
	return int(ProjectSettings.get_setting(APP_ID_SETTING, TEST_APP_ID))


## Creates a lobby; on success this peer hosts through Steam (lobby_created).
func host_lobby(max_players: int, lobby_type: int = LOBBY_FRIENDS_ONLY) -> Error:
	if not _ready_for_peers():
		return ERR_UNAVAILABLE
	_steam.call(&"createLobby", lobby_type, max_players)
	return OK


func join_lobby(id: int) -> Error:
	if not _ready_for_peers():
		return ERR_UNAVAILABLE
	_steam.call(&"joinLobby", id)
	return OK


## Opens the Steam overlay's invite dialog for the current lobby.
func invite_friends() -> bool:
	if _steam == null or lobby_id == 0:
		return false
	_steam.call(&"activateGameOverlayInviteDialog", lobby_id)
	return true


func leave_lobby() -> void:
	if _steam and lobby_id != 0:
		_steam.call(&"leaveLobby", lobby_id)
	lobby_id = 0
	var network: Node = _network()
	if network:
		network.call(&"leave")


func _ready_for_peers() -> bool:
	if _steam == null:
		lobby_failed.emit(tr(MSG_UNAVAILABLE))
		return false
	if not ClassDB.class_exists(PEER_CLASS):
		lobby_failed.emit(tr(MSG_NO_PEER))
		return false
	return true


func _on_lobby_created(result: int, id: int) -> void:
	if result != RESULT_OK:
		lobby_failed.emit(tr(MSG_CREATE_FAILED))
		return
	lobby_id = id
	_steam.call(&"setLobbyData", id, LOBBY_NAME_KEY, str(_steam.call(&"getPersonaName")))
	var peer: MultiplayerPeer = ClassDB.instantiate(PEER_CLASS)
	if peer.call(&"create_host", VIRTUAL_PORT) != OK:
		lobby_failed.emit(tr(MSG_CREATE_FAILED))
		return
	_network().call(&"adopt_peer", peer, true)
	lobby_created.emit(id)


func _on_lobby_joined(id: int, _permissions: int, _locked: bool, response: int) -> void:
	if response != ENTER_SUCCESS:
		lobby_failed.emit(tr(MSG_JOIN_FAILED))
		return
	lobby_id = id
	var owner_id: int = int(_steam.call(&"getLobbyOwner", id))
	if owner_id == int(_steam.call(&"getSteamID")):
		return  # our own lobby: we already host
	var peer: MultiplayerPeer = ClassDB.instantiate(PEER_CLASS)
	if peer.call(&"create_client", owner_id, VIRTUAL_PORT) != OK:
		lobby_failed.emit(tr(MSG_JOIN_FAILED))
		return
	_network().call(&"adopt_peer", peer, false)
	lobby_joined.emit(id)


## A friend's invite was accepted in the overlay while the game runs.
func _on_join_requested(id: int, _friend_id: int) -> void:
	join_lobby(id)


func _join_from_launch_args() -> void:
	var args: PackedStringArray = OS.get_cmdline_args()
	var index: int = args.find(CONNECT_ARG)
	if index >= 0 and index + 1 < args.size() and args[index + 1].is_valid_int():
		join_lobby(args[index + 1].to_int())


func _network() -> Node:
	return get_tree().root.get_node_or_null(^"Network")
