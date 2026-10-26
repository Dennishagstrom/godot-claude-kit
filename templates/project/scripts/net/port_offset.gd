class_name PortOffset
extends RefCounted
## Test isolation: the environment variable {{GAME_ENV}}_PORT_OFFSET shifts
## every port the game hosts or joins on (Network, test peers, the lag proxy).
## tools/test_runner.py gives each runner its own block, so suites in
## different worktrees that use the same port number never collide.
## Unset (players, manual runs) = 0.

const ENV_VAR: String = "{{GAME_ENV}}_PORT_OFFSET"
## Highest offset honoured; keeps shifted ports below the ephemeral range.
const MAX_OFFSET: int = 40000

static var _offset: int = -1


## `port` shifted by the test runner's block offset.
static func apply(port: int) -> int:
	return port + get_offset()


static func get_offset() -> int:
	if _offset < 0:
		var raw: String = OS.get_environment(ENV_VAR)
		_offset = clampi(raw.to_int(), 0, MAX_OFFSET) if raw.is_valid_int() else 0
	return _offset
