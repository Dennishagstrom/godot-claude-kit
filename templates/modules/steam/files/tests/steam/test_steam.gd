extends SceneTree
## SteamService degrades gracefully: without GodotSteam (or a running Steam
## client) it reports unavailable, every lobby call fails with a reason and no
## script error, and ENet hosting through Network still works. With Steam
## available it only checks the init (live lobbies need a logged-in client
## and a second account, so they are tested by hand: docs/modules/steam.md).

const ENET_PORT: int = 7799

var _fails: Array[String] = []
var _reasons: Array[String] = []
var _frame: int = 0


func _process(_delta: float) -> bool:
	_frame += 1
	if _frame == 1:
		return false  # autoloads finish _ready first
	var steam: Node = root.get_node_or_null(^"SteamService")
	if steam == null:
		_fails.append("SteamService autoload missing")
		return _finish("?")
	steam.connect(&"lobby_failed", func(reason: String) -> void: _reasons.append(reason))
	var available: bool = steam.call(&"is_available")
	if available:
		_check(int(steam.call(&"app_id")) > 0, "app id set")
		return _finish("Steam available (live lobbies: manual test)")
	_check(not String(steam.get(&"unavailable_reason")).is_empty(), "unavailable reason is set")
	_check(steam.call(&"host_lobby", 4) == ERR_UNAVAILABLE, "host_lobby fails without Steam")
	_check(steam.call(&"join_lobby", 12345) == ERR_UNAVAILABLE, "join_lobby fails without Steam")
	_check(steam.call(&"invite_friends") == false, "invite_friends is a no-op")
	_check(_reasons.size() == 2 and not _reasons[0].is_empty(), "lobby_failed gives a reason (%d)" % _reasons.size())
	steam.call(&"leave_lobby")
	var network: Node = root.get_node(^"Network")
	_check(network.call(&"host_game", ENET_PORT) == OK, "ENet still hosts")
	network.call(&"leave")
	return _finish("not installed: %s" % steam.get(&"unavailable_reason"))


func _check(ok: bool, what: String) -> void:
	if not ok:
		_fails.append(what)


func _finish(mode: String) -> bool:
	if _fails.is_empty():
		print("RESULT PASS steam (%s)" % mode)
		quit(0)
	else:
		for f: String in _fails:
			print("FAIL ", f)
		print("RESULT FAIL steam: %d" % _fails.size())
		quit(1)
	return true
