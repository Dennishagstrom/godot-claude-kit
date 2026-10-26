#!/bin/bash
# Sourced by the tools and tests: sets $GODOT to the Godot 4 binary.
# Override with:  export GODOT=/path/to/godot
if [ -z "$GODOT" ]; then
	for c in godot4 godot Godot \
		/Applications/Godot.app/Contents/MacOS/Godot \
		/Applications/Godot_mono.app/Contents/MacOS/Godot \
		"$HOME/Applications/Godot.app/Contents/MacOS/Godot" \
		/usr/local/bin/godot /usr/bin/godot; do
		if command -v "$c" > /dev/null 2>&1; then GODOT=$(command -v "$c"); break; fi
		if [ -x "$c" ]; then GODOT=$c; break; fi
	done
fi
export GODOT
