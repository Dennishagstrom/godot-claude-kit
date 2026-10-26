extends Node
## Owns the multiplayer connection: host, join, leave, and the player roster.
## Peer 1 is always the host and the server. The server decides; clients send
## requests and show what the server tells them.
##
## No class_name on purpose: autoloads with class_name are compiled by `-s` test
## scripts before the autoload exists. Reach it as /root/Network (or `Network`).
##
## Dev shortcuts (after `--`): `--host` hosts at once, `--join[=address]` joins
## (default 127.0.0.1), `--port=N` picks the port.
##
## Other transports (e.g. Steam) build their own MultiplayerPeer and hand it
## over with adopt_peer(); everything else (roster, signals) stays the same.
## If res://scripts/net/version_check.gd exists (kit module build-release),
## joining runs a version + build handshake first.

signal hosted
signal joined
## Join failed or timed out; reason is player-facing (translated).
signal join_failed(reason: String)
## The session ended (we left, the host left, or the connection was lost).
signal left
signal peer_connected(peer_id: int)
signal peer_disconnected(peer_id: int)
## The server-authoritative roster changed (on every peer).
signal roster_changed

const SERVER_ID: int = 1
const DEFAULT_PORT: int = {{DEFAULT_PORT}}
const MAX_PLAYERS: int = {{MAX_PLAYERS}}
const DEFAULT_ADDRESS: String = "127.0.0.1"
const MAX_NAME_LENGTH: int = 16
## Seconds a join may take before we give up.
const CONNECT_TIMEOUT: float = 10.0
const MSG_CONNECT_FAILED: String = "Couldn't connect to %s:%d."
const MSG_TIMEOUT: String = "No answer from %s:%d."
const VERSION_CHECK_PATH: String = "res://scripts/net/version_check.gd"

## Display name of this player (set it in the menu before hosting/joining).
var player_name: String = "Player"
## peer_id -> display name. Written only by the server, mirrored to clients.
var players: Dictionary = {}

var _peer: MultiplayerPeer = null
## Optional join handshake (VERSION_CHECK_PATH), null when not installed.
var _version_check: RefCounted = null
var _join_timer: SceneTreeTimer = null
var _join_target: String = ""


func _ready() -> void:
	multiplayer.peer_connected.connect(_on_peer_connected)
	multiplayer.peer_disconnected.connect(_on_peer_disconnected)
	multiplayer.connected_to_server.connect(_on_connected_to_server)
	multiplayer.connection_failed.connect(_on_connection_failed)
	multiplayer.server_disconnected.connect(_on_server_disconnected)
	if ResourceLoader.exists(VERSION_CHECK_PATH):
		_version_check = (load(VERSION_CHECK_PATH) as GDScript).new()
		_version_check.call(&"install", multiplayer, _on_version_rejected)
	_handle_dev_args.call_deferred()


# --- Public API -------------------------------------------------------------

func host_game(port: int = DEFAULT_PORT) -> Error:
	var enet := ENetMultiplayerPeer.new()
	# Test runs shift every port into their own block (PortOffset); 0 otherwise.
	var bound: int = PortOffset.apply(port)
	var err: Error = enet.create_server(bound, MAX_PLAYERS - 1)
	if err != OK:
		return err
	adopt_peer(enet, true)
	print("[Network] hosting on port %d" % bound)
	return OK


func join_game(address: String = DEFAULT_ADDRESS, port: int = DEFAULT_PORT) -> Error:
	var enet := ENetMultiplayerPeer.new()
	var err: Error = enet.create_client(address, PortOffset.apply(port))
	if err != OK:
		leave()
		join_failed.emit(tr(MSG_CONNECT_FAILED) % [address, port])
		return err
	adopt_peer(enet, false)
	_join_target = "%s:%d" % [address, port]
	_join_timer = get_tree().create_timer(CONNECT_TIMEOUT)
	_join_timer.timeout.connect(_on_join_timeout.bind(address, port))
	return OK


## Uses a ready-made peer (ENet, Steam, WebRTC ...). hosting = this peer is the server.
func adopt_peer(peer: MultiplayerPeer, hosting: bool) -> void:
	leave()
	_peer = peer
	multiplayer.multiplayer_peer = _peer
	if hosting:
		players = {SERVER_ID: _clean_name(player_name)}
		roster_changed.emit()
		hosted.emit()


func leave() -> void:
	if _peer == null:
		return
	_peer.close()
	_peer = null
	_join_timer = null
	multiplayer.multiplayer_peer = OfflineMultiplayerPeer.new()
	players.clear()
	roster_changed.emit()
	left.emit()


func is_online() -> bool:
	return _peer != null


## True on the host and in single player (single player = a host without clients).
func is_server() -> bool:
	return _peer == null or multiplayer.is_server()


# --- RPCs (server authority) ---------------------------------------------------

## Client -> server: "this is my name". Validated on the server; never trusted.
@rpc("any_peer", "call_remote", "reliable")
func _request_register(requested_name: String) -> void:
	if not multiplayer.is_server():
		return
	var sender: int = multiplayer.get_remote_sender_id()
	# Validate: only connected peers, one entry each, sane input.
	if sender == SERVER_ID or not multiplayer.get_peers().has(sender):
		return
	players[sender] = _clean_name(requested_name)
	# Full state, so late joiners get everything in one message.
	_sync_roster.rpc(players)


## Server -> everyone: the authoritative roster.
@rpc("authority", "call_local", "reliable")
func _sync_roster(roster: Dictionary) -> void:
	players = roster.duplicate()
	roster_changed.emit()


# --- Private -------------------------------------------------------------------

func _clean_name(raw: String) -> String:
	var cleaned: String = raw.strip_edges().left(MAX_NAME_LENGTH)
	return cleaned if not cleaned.is_empty() else "Player"


func _handle_dev_args() -> void:
	var port: int = DEFAULT_PORT
	var mode: String = ""
	var address: String = DEFAULT_ADDRESS
	for arg: String in OS.get_cmdline_user_args():
		if arg == "--host":
			mode = "host"
		elif arg == "--join" or arg.begins_with("--join="):
			mode = "join"
			if arg.contains("="):
				address = arg.get_slice("=", 1)
		elif arg.begins_with("--port="):
			port = arg.get_slice("=", 1).to_int()
	if mode == "host":
		host_game(port)
	elif mode == "join":
		join_game(address, port)


func _on_peer_connected(peer_id: int) -> void:
	peer_connected.emit(peer_id)


func _on_peer_disconnected(peer_id: int) -> void:
	peer_disconnected.emit(peer_id)
	if multiplayer.is_server() and players.erase(peer_id):
		_sync_roster.rpc(players)


func _on_connected_to_server() -> void:
	_join_timer = null
	print("[Network] joined as peer %d" % multiplayer.get_unique_id())
	joined.emit()
	_request_register.rpc_id(SERVER_ID, player_name)


func _on_connection_failed() -> void:
	var target: String = _join_target
	leave()
	join_failed.emit(tr("Couldn't connect to %s.") % target)


func _on_join_timeout(address: String, port: int) -> void:
	# Still connecting after CONNECT_TIMEOUT: give up.
	if _join_timer != null and _peer != null and \
			_peer.get_connection_status() != MultiplayerPeer.CONNECTION_CONNECTED:
		leave()
		join_failed.emit(tr(MSG_TIMEOUT) % [address, port])


func _on_server_disconnected() -> void:
	leave()


func _on_version_rejected(reason: String) -> void:
	leave()
	join_failed.emit(reason)
