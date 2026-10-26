extends "res://tests/net_testing/net_test_base.gd"
## Client side of the sync test: joins, holds ui_right (Input.action_press,
## like a player), and passes when the value synced back from the server has
## moved right. The client never moves the value itself.

const Fixture := preload("res://tests/net_testing/sync_fixture.gd")
const MIN_DISTANCE: float = 1.5
const ACTION: StringName = &"ui_right"

var _fixture: Node = null
var _pressing: bool = false


func _initialize() -> void:
	super._initialize()
	role = "client"


func _step(_now: float) -> bool:
	if _fixture == null:
		_fixture = Fixture.new()
		root.add_child(_fixture)
	var connected: bool = root.multiplayer.has_multiplayer_peer() and \
			root.multiplayer.multiplayer_peer.get_connection_status() == MultiplayerPeer.CONNECTION_CONNECTED
	if connected and not _pressing:
		_pressing = true
		press(ACTION)
	var value: Vector2 = _fixture.get(&"value")
	if value.x >= MIN_DISTANCE:
		release(ACTION)
		return finish(true, "synced value %s after holding %s" % [value, ACTION])
	return false


func describe() -> String:
	return "value=%s pressing=%s" % [_fixture.get(&"value"), _pressing] if _fixture else "no fixture"
