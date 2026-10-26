extends RefCounted
## Join handshake: a client must have the host's game version and build number
## (BuildInfo) before it counts as connected. Uses SceneMultiplayer
## authentication, so a mismatched client never sees game RPCs or state.
## Installed by the Network autoload when this file exists (no class_name:
## Network loads it by path).
##
## Client -> host: {version, build}. Host -> client: {result: ok} or
## {result: reject, version, build}; the host then drops the client after
## REJECT_DISCONNECT_DELAY so the answer arrives first.

const AUTH_TIMEOUT: float = 5.0
const REJECT_DISCONNECT_DELAY: float = 0.5
const KEY_VERSION: String = "version"
const KEY_BUILD: String = "build"
const KEY_RESULT: String = "result"
const RESULT_OK: String = "ok"
const RESULT_REJECT: String = "reject"
const MSG_VERSION_MISMATCH: String = "The host runs %s, you run %s. Everyone needs the same build."
const MSG_REJECTED: String = "The host refused the connection."

## Tests only: pretend to be this build (-1 = the real BuildInfo.NUMBER).
static var build_override: int = -1

var _mp: SceneMultiplayer = null
var _on_rejected: Callable
var _reject_reason: String = ""


## Hooks the handshake into `api` (the autoload's multiplayer). on_rejected(reason: String)
## runs on the client when the host refuses it.
func install(api: MultiplayerAPI, on_rejected: Callable) -> void:
	_mp = api as SceneMultiplayer
	if _mp == null:
		return
	_on_rejected = on_rejected
	_mp.auth_callback = _on_auth_data
	_mp.auth_timeout = AUTH_TIMEOUT
	_mp.peer_authenticating.connect(_on_peer_authenticating)
	_mp.peer_authentication_failed.connect(_on_peer_authentication_failed)


static func current_build() -> int:
	return build_override if build_override >= 0 else BuildInfo.NUMBER


func _hello() -> PackedByteArray:
	return var_to_bytes({KEY_VERSION: BuildInfo.version(), KEY_BUILD: current_build()})


static func _read(data: PackedByteArray) -> Dictionary:
	var value: Variant = bytes_to_var(data)
	return value if value is Dictionary else {}


func _on_peer_authenticating(peer_id: int) -> void:
	if not _mp.is_server() and peer_id == MultiplayerPeer.TARGET_PEER_SERVER:
		_reject_reason = ""
		_mp.send_auth(peer_id, _hello())


func _on_auth_data(peer_id: int, data: PackedByteArray) -> void:
	var message: Dictionary = _read(data)
	if _mp.is_server():
		var version: String = str(message.get(KEY_VERSION, "?"))
		var build: int = int(message[KEY_BUILD]) if message.get(KEY_BUILD) is int else -1
		if version == BuildInfo.version() and build == current_build():
			_mp.send_auth(peer_id, var_to_bytes({KEY_RESULT: RESULT_OK}))
			_mp.complete_auth(peer_id)
			return
		print("[Network] rejected peer %d: %s vs host %s" % [peer_id, BuildInfo.label(version, build),
				BuildInfo.label(BuildInfo.version(), current_build())])
		_mp.send_auth(peer_id, var_to_bytes({
			KEY_RESULT: RESULT_REJECT, KEY_VERSION: BuildInfo.version(), KEY_BUILD: current_build(),
		}))
		var tree: SceneTree = Engine.get_main_loop() as SceneTree
		tree.create_timer(REJECT_DISCONNECT_DELAY, true, false, true).timeout.connect(_kick.bind(peer_id))
		return
	if peer_id != MultiplayerPeer.TARGET_PEER_SERVER:
		return
	match str(message.get(KEY_RESULT, "")):
		RESULT_OK:
			_mp.complete_auth(peer_id)
		RESULT_REJECT:
			var host_build: int = int(message[KEY_BUILD]) if message.get(KEY_BUILD) is int else 0
			var host_label: String = BuildInfo.label(str(message.get(KEY_VERSION, "?")), host_build)
			_reject(TranslationServer.translate(MSG_VERSION_MISMATCH) % [host_label,
					BuildInfo.label(BuildInfo.version(), current_build())])
		_:
			_reject(TranslationServer.translate(MSG_REJECTED))


func _kick(peer_id: int) -> void:
	if _mp.has_multiplayer_peer() and _mp.is_server() and _mp.get_authenticating_peers().has(peer_id):
		_mp.disconnect_peer(peer_id)


func _on_peer_authentication_failed(peer_id: int) -> void:
	if not _mp.is_server() and peer_id == MultiplayerPeer.TARGET_PEER_SERVER and _reject_reason.is_empty():
		_reject(TranslationServer.translate(MSG_REJECTED))


func _reject(reason: String) -> void:
	if not _reject_reason.is_empty():
		return
	_reject_reason = reason
	print("[Network] join refused: %s" % reason)
	_on_rejected.call(reason)
