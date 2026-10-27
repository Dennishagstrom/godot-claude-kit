extends SceneTree
## Rng (scripts/core/rng.gd): the same seed replays the same rolls per stream, and
## drawing from one stream never changes another.
##   godot --headless --audio-driver Dummy --path . -s res://tests/core/test_rng.gd

const DRAWS: int = 20

var _fails: Array[String] = []


func _initialize() -> void:
	Rng.reseed(1234)
	var loot_a: Array[int] = _draw(&"loot")
	Rng.reseed(1234)
	_draw(&"enemies")  # another system draws first
	var loot_b: Array[int] = _draw(&"loot")
	_check(loot_a == loot_b, "same seed, same loot rolls, whatever other systems draw")
	Rng.reseed(99)
	_check(_draw(&"loot") != loot_a, "another seed gives other rolls")
	var items: Array = [1, 2, 3, 4, 5, 6, 7, 8]
	Rng.reseed(7)
	Rng.shuffle(&"deck", items)
	var once: Array = items.duplicate()
	items = [1, 2, 3, 4, 5, 6, 7, 8]
	Rng.reseed(7)
	Rng.shuffle(&"deck", items)
	_check(items == once and items.size() == 8, "shuffle replays")
	_check(Rng.pick(&"deck", []) == null, "pick from an empty array is null")
	print("RESULT %s rng%s" % ["PASS" if _fails.is_empty() else "FAIL", "" if _fails.is_empty() else ": " + ", ".join(_fails)])
	quit(0 if _fails.is_empty() else 1)


func _draw(system: StringName) -> Array[int]:
	var out: Array[int] = []
	for i: int in DRAWS:
		out.append(Rng.stream(system).randi_range(0, 1000))
	return out


func _check(ok: bool, what: String) -> void:
	print("%s %s" % ["ok  " if ok else "FAIL", what])
	if not ok:
		_fails.append(what)
