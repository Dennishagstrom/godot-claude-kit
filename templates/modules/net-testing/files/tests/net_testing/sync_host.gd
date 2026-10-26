extends "res://tests/net_testing/net_test_base.gd"
## Host side of the sync test (tests/net_testing/run_sync.sh): hosts, gives
## the first client ownership of the fixture, and passes once the client's
## input has moved the server-side value far enough. Lingers so the final
## state reaches the client.

const Fixture := preload("res://tests/net_testing/sync_fixture.gd")
## How far the client must move the value (units).
const MIN_DISTANCE: float = 1.5
const LINGER_S: float = 2.0

var _fixture: Node = null
var _passed_at: float = -1.0


func _step(_now: float) -> bool:
	if _fixture == null:
		_fixture = Fixture.new()
		root.add_child(_fixture)
		network().peer_connected.connect(_on_peer_connected)
	var moved: float = (_fixture.get(&"value") as Vector2).length()
	if _passed_at < 0.0 and moved >= MIN_DISTANCE:
		_passed_at = elapsed
	if _passed_at >= 0.0 and elapsed - _passed_at > LINGER_S:
		return finish(true, "client input moved the value %.2f (rejected requests: %d)" % [moved, _fixture.get(&"rejected")])
	return false


func describe() -> String:
	return "value=%s owner=%s" % [_fixture.get(&"value"), _fixture.get(&"owner_peer")] if _fixture else "no fixture"


func _on_peer_connected(peer_id: int) -> void:
	if int(_fixture.get(&"owner_peer")) == 0:
		_fixture.set(&"owner_peer", peer_id)
