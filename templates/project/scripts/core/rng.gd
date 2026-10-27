class_name Rng
extends RefCounted
## Seeded randomness for gameplay: one run seed (`-- --seed=N`, else random) and one
## stream per system, so a run can be replayed and a test that draws loot does not
## change what the enemies roll. Never use randf()/randi()/shuffle() for gameplay
## (the lint suite flags them); cosmetic-only randomness may end the line `# lint: ok cosmetic`.
##   var rng: RandomNumberGenerator = Rng.stream(&"loot")
##   var item: Variant = Rng.pick(&"loot", table)
{{#MULTIPLAYER}}## Multiplayer: only the server rolls gameplay randomness and sends the results.
{{/MULTIPLAYER}}
const SEED_ARG: String = "--seed="

static var _seed: int = 0
static var _seeded: bool = false
## stream name -> RandomNumberGenerator
static var _streams: Dictionary = {}


## The run seed (from --seed=N on the command line, else picked once at random).
static func run_seed() -> int:
	if not _seeded:
		_seeded = true
		_seed = 0
		for arg: String in OS.get_cmdline_user_args():
			if arg.begins_with(SEED_ARG):
				_seed = arg.trim_prefix(SEED_ARG).to_int()
		if _seed == 0:
			var boot := RandomNumberGenerator.new()
			boot.randomize()
			_seed = boot.randi()
		print("[Rng] run seed %d (replay: -- %s%d)" % [_seed, SEED_ARG, _seed])
	return _seed


## Starts a new run: every stream restarts from this seed.
static func reseed(new_seed: int) -> void:
	_seed = new_seed
	_seeded = true
	_streams.clear()


## The stream for one system; the same seed always gives the same sequence per name.
static func stream(system: StringName) -> RandomNumberGenerator:
	var rng: RandomNumberGenerator = _streams.get(system)
	if rng == null:
		rng = RandomNumberGenerator.new()
		rng.seed = hash([run_seed(), String(system)])
		_streams[system] = rng
	return rng


static func pick(system: StringName, items: Array) -> Variant:
	if items.is_empty():
		return null
	return items[stream(system).randi_range(0, items.size() - 1)]


## Shuffles in place (Fisher-Yates on the system's stream).
static func shuffle(system: StringName, items: Array) -> void:
	var rng: RandomNumberGenerator = stream(system)
	for i: int in range(items.size() - 1, 0, -1):
		var j: int = rng.randi_range(0, i)
		var tmp: Variant = items[i]
		items[i] = items[j]
		items[j] = tmp
