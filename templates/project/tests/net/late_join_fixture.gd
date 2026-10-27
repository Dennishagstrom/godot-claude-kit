extends Node
## Example of the late-join contract (copy it for every system with state): register
## with Network in _ready, return the full state in net_snapshot(), apply it in
## net_apply_snapshot(). Here: a door that the host opened before the client joined.

const STATE_ID: StringName = &"test_door"

var opened: bool = false
var applied: int = 0


func _ready() -> void:
	get_node(^"/root/Network").call(&"register_state", STATE_ID, self)


func net_snapshot() -> Dictionary:
	return {"opened": opened}


func net_apply_snapshot(data: Dictionary) -> void:
	opened = bool(data.get("opened", false))
	applied += 1
