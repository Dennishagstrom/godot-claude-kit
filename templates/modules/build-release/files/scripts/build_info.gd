class_name BuildInfo
extends RefCounted
## Build number and time, written by tools/build_release.sh before each export
## (0 = running from source). The game version is application/config/version
## in project.godot. Edit through the build script, not by hand.

const NUMBER: int = 0
const TIME: String = ""
## Shown instead of the number when running from source.
const DEV_LABEL: String = "dev"


## "0.1.0" from project.godot.
static func version() -> String:
	return str(ProjectSettings.get_setting("application/config/version", "0.0.0"))


## "v0.1.0 (build 12)" / "v0.1.0 (build dev)". Not translated: it is an id.
static func label(game_version: String = version(), build: int = NUMBER) -> String:
	return "v%s (build %s)" % [game_version, str(build) if build > 0 else DEV_LABEL]
