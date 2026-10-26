#!/bin/bash
# Sourced by the tools and tests: sets $GODOT to the Godot 4 binary and $PYTHON
# to a working Python 3 (Windows often has no real python3, only a Store alias).
# Override with:  export GODOT=/path/to/godot   (Windows: the *_console.exe)
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
if [ -z "$GODOT" ] && [ -n "${WINDIR:-}" ]; then
	# Windows (Git Bash): Godot is a loose .exe; look in the usual folders, console build first.
	upath() { cygpath -u "$1" 2>/dev/null || echo "$1"; }  # C:\x -> /c/x
	PF=$(upath "${PROGRAMFILES:-C:\\Program Files}"); LAD=$(upath "${LOCALAPPDATA:-/nonexistent}")
	UP=$(upath "${USERPROFILE:-$HOME}")
	for d in "$PF/Godot" "$LAD/Programs/Godot" "$LAD/Microsoft/WinGet/Packages" "$UP/scoop/apps/godot/current" \
		"$UP/Godot" "$UP/Desktop" "$UP/Downloads" /c/Godot; do
		[ -d "$d" ] || continue
		GODOT=$(find "$d" -maxdepth 3 -iname 'godot*console.exe' 2>/dev/null | sort -r | head -1)
		[ -n "$GODOT" ] || GODOT=$(find "$d" -maxdepth 3 -iname 'godot*.exe' 2>/dev/null | sort -r | head -1)
		[ -n "$GODOT" ] && break
	done
	# C:/x/godot.exe works for bash and for the Python tools that read $GODOT.
	[ -n "$GODOT" ] && GODOT=$(cygpath -m "$GODOT" 2>/dev/null || echo "$GODOT")
fi
export GODOT
if [ -z "$PYTHON" ]; then
	for c in python3 python py; do  # py = the Windows launcher (newest Python 3)
		if "$c" -c "import sys; sys.exit(sys.version_info < (3, 8))" > /dev/null 2>&1; then PYTHON=$c; break; fi
	done
fi
export PYTHON=${PYTHON:-python3}
