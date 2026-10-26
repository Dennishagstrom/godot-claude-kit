class_name DevCheats
extends RefCounted
## Developer cheats toggled from the sandbox panel (F1). Game code reads them
## where it matters, e.g. `if DevCheats.no_cooldowns: cooldown = 0.0`.
## They are only ever switched on in the sandbox (`-- --sandbox`); in
## multiplayer the server's values count (it simulates), clients follow.

## Abilities and timers skip their cooldowns.
static var no_cooldowns: bool = false
## Players take no damage.
static var god_mode: bool = false


static func reset() -> void:
	no_cooldowns = false
	god_mode = false
