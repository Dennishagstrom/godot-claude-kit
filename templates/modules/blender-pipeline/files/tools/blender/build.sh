#!/usr/bin/env bash
# Builds models (tools/blender/models/<name>.py) with headless Blender.
#
#   tools/blender/build.sh                  # every model
#   tools/blender/build.sh crate barrel     # only these
#   tools/blender/build.sh 'prop_*'         # a glob over the script names
#   tools/blender/build.sh --preview ...    # also a contact sheet PNG per model (to a file, never a window)
#   tools/blender/build.sh --no-import ...  # skip the headless Godot re-import
#
# Output: $OUT_DIR/<name>.glb (default assets/models/), previews in
# $PREVIEW_DIR (default tests/blender_previews/, git-ignored), then the model check
# (tools/dev/asset_check.py) and a headless `godot --import` so the game sees the new files.
# Blender: $BLENDER, else `blender` on PATH, else the usual install paths.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT_DIR="${OUT_DIR:-$ROOT/assets/models}"
PREVIEW_DIR="${PREVIEW_DIR:-$ROOT/tests/blender_previews}"
source "$ROOT/tools/dev/godot_env.sh"
if [ -z "${BLENDER:-}" ]; then
	for c in blender /Applications/Blender.app/Contents/MacOS/Blender "$HOME/Applications/Blender.app/Contents/MacOS/Blender" \
		/usr/bin/blender /snap/bin/blender; do
		if command -v "$c" > /dev/null 2>&1; then BLENDER=$(command -v "$c"); break; fi
	done
fi
if [ -z "${BLENDER:-}" ] && [ -n "${WINDIR:-}" ]; then
	# Windows installs into "Blender Foundation/Blender <version>/"; take the newest.
	PF=$(cygpath -u "${PROGRAMFILES:-C:\\Program Files}" 2>/dev/null || echo "/c/Program Files")
	for c in "$PF"/Blender\ Foundation/*/blender.exe; do
		[ -f "$c" ] && BLENDER=$c
	done
fi
[ -n "${BLENDER:-}" ] || { echo "Blender not found: set BLENDER=/path/to/blender" >&2; exit 2; }

preview=0
do_import=1
names=()
for arg in "$@"; do
	case "$arg" in
		--preview) preview=1 ;;
		--no-import) do_import=0 ;;
		*) names+=("$arg") ;;
	esac
done
[ ${#names[@]} -eq 0 ] && names=('*')
expanded=()
for pat in "${names[@]}"; do
	found=0
	for f in "$ROOT"/tools/blender/models/$pat.py; do
		[ -f "$f" ] || continue
		expanded+=("$(basename "$f" .py)"); found=1
	done
	[ $found -eq 1 ] || expanded+=("$pat")
done

failed=0
built=()
for name in "${expanded[@]}"; do
	script="$ROOT/tools/blender/models/$name.py"
	[ -f "$script" ] || { echo "no such model: $name" >&2; failed=1; continue; }
	glb="${OUT_DIR:?}/${name:?}.glb"
	extra=()
	if [ $preview -eq 1 ]; then
		extra=(--preview "$PREVIEW_DIR/$name.png")
		mkdir -p "$PREVIEW_DIR" && touch "$PREVIEW_DIR/.gdignore"  # Godot does not import the sheets
	fi
	[ -f "$glb" ] && mv "$glb" "$glb.old"
	echo "== $name"
	# --background: no UI. --factory-startup: ignore the user's Blender prefs/add-ons.
	"$BLENDER" --background --factory-startup --python-exit-code 1 --python "$script" \
		-- --out "$glb" ${extra[@]+"${extra[@]}"} 2>&1 \
		| grep -E '^(PARTS|JOINT|BOUNDS|TRIS|MATERIALS|EXPORTED|PREVIEW|Error|Traceback|  File|[A-Za-z]+Error)' || true
	if [ -f "$glb" ]; then
		built+=("$glb")
		[ -f "$glb.old" ] && unlink "$glb.old"
	else
		echo "FAILED: $name" >&2; failed=1
		[ -f "$glb.old" ] && mv "$glb.old" "$glb"
	fi
done

if [ ${#built[@]} -gt 0 ] && [ -f "$ROOT/tools/dev/asset_check.py" ]; then
	echo "== model check"
	"$PYTHON" -I "$ROOT/tools/dev/asset_check.py" "${built[@]}" || true
fi
if [ $do_import -eq 1 ] && [ -n "${GODOT:-}" ]; then
	"$GODOT" --headless --audio-driver Dummy --path "$ROOT" --import > /dev/null 2>&1 || true
	echo "== Godot import done"
fi
exit $failed
