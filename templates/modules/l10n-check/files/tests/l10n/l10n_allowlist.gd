extends RefCounted
## Exceptions for tests/l10n/check_strings.gd. Keep it short and say why.

## Exact string literals that may be shown untranslated (ids, brand names, debug text).
const STRINGS: Array[String] = []
## Files or folders (res:// prefixes) that are not player-facing (dev tools, debug overlays).
const PATHS: Array[String] = [
	"res://scripts/dev/",
	"res://scenes/sandbox/",
]
