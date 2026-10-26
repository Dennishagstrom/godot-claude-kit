#!/bin/bash
# Builds a release of {{GAME_NAME}} (Windows, optionally macOS) and smoke-tests it headless.
#
#   tools/build_release.sh            bump build number, stamp patch notes, export, zip, smoke-test
#   tools/build_release.sh --no-bump  rebuild with the current build number
#   tools/build_release.sh --mac      also export the "macOS" preset
#   tools/build_release.sh --no-smoke skip the headless smoke test
#   tools/build_release.sh --check    validate setup only (version, build number,
#                                     presets, patch notes, templates); exports nothing
#
# Version: application/config/version in project.godot. Build number:
# scripts/build_info.gd (BuildInfo.NUMBER, written here).{{#MULTIPLAYER}} Joining compares both
# (scripts/net/version_check.gd), so friends need the same zip.{{/MULTIPLAYER}}
# Output: the preset's export_path (export_presets.cfg) and
#         build/{{GAME_SLUG}}_<Preset>_<version>-b<build>.zip
# Headless only: never opens a window.
set -uo pipefail
cd "$(dirname "$0")/.."
source tools/dev/godot_env.sh

INFO=scripts/build_info.gd
PRESETS=export_presets.cfg
SLUG="{{GAME_SLUG}}"
# Seconds a smoke-test process may run before it is killed.
SMOKE_WALL_S=${SMOKE_WALL_S:-60}
# Frames to run when booting the pack (headless frames are not capped).
SMOKE_BOOT_FRAMES=${SMOKE_BOOT_FRAMES:-300}
{{#MULTIPLAYER}}SMOKE_PORT=${SMOKE_PORT:-7886}
SMOKE_HOST_FRAMES=${SMOKE_HOST_FRAMES:-3000}
SMOKE_CLIENT_FRAMES=${SMOKE_CLIENT_FRAMES:-1200}
SMOKE_FPS=60
{{/MULTIPLAYER}}BUMP=1; MAC=0; SMOKE=1; CHECK=0
for arg in "$@"; do
	case $arg in
		--no-bump) BUMP=0 ;;
		--mac) MAC=1 ;;
		--no-smoke) SMOKE=0 ;;
		--check) CHECK=1 ;;
		*) echo "unknown option $arg"; exit 2 ;;
	esac
done

with_timeout() { perl -e 'alarm shift; exec @ARGV' "$@"; }
preset_path() { # preset name -> export_path
	awk -v want="$1" -F'"' '/^name=/{name=$2} /^export_path=/{ if (name==want) print $2 }' "$PRESETS"
}
fail() { echo "RELEASE CHECK FAIL: $*"; exit 1; }

VERSION=$(sed -n 's/^config\/version="\(.*\)"/\1/p' project.godot)
OLD=$(sed -n 's/^const NUMBER: int = \([0-9]*\).*/\1/p' "$INFO")
GODOT_VERSION=$("$GODOT" --version 2>/dev/null | sed -E 's/^([0-9]+\.[0-9]+(\.[0-9]+)?)\.([a-z0-9]+).*/\1.\3/')
TEMPLATES_DIRS=("$HOME/Library/Application Support/Godot/export_templates" "$HOME/.local/share/godot/export_templates" "${APPDATA:-/nonexistent}/Godot/export_templates")
PRESET_LIST=(Windows)
[ $MAC -eq 1 ] && PRESET_LIST+=(macOS)

# --- checks (also the whole job of --check) ---
[ -n "$GODOT" ] || fail "Godot not found (set GODOT=/path/to/godot)"
[ -n "$VERSION" ] || fail "no application/config/version in project.godot"
[ -n "$OLD" ] || fail "no 'const NUMBER: int = N' in $INFO"
[ -f "$PRESETS" ] || fail "no $PRESETS (Project > Export in the editor, or the kit's template)"
for p in "${PRESET_LIST[@]}"; do
	[ -n "$(preset_path "$p")" ] || fail "no preset named \"$p\" with an export_path in $PRESETS"
done
grep -q '^run/main_scene=' project.godot || fail "no main scene (application/run/main_scene): the exported game would not start"
python3 -I tools/patch_notes.py --check > /dev/null || { python3 -I tools/patch_notes.py --check; fail "patch notes invalid"; }
TEMPLATES_OK=0
for d in "${TEMPLATES_DIRS[@]}"; do
	[ -d "$d/$GODOT_VERSION" ] && TEMPLATES_OK=1
done
if [ $CHECK -eq 1 ]; then
	[ $TEMPLATES_OK -eq 1 ] && echo "export templates: $GODOT_VERSION installed" \
		|| echo "export templates: $GODOT_VERSION NOT installed (Editor > Manage Export Templates)"
	echo "version $VERSION, build $OLD, presets: ${PRESET_LIST[*]}"
	echo "RELEASE CHECK PASS"
	exit 0
fi
[ $TEMPLATES_OK -eq 1 ] || fail "export templates for $GODOT_VERSION are not installed (Editor > Manage Export Templates)"

# --- bump + stamp (undone if the export fails) ---
BUILD=$OLD
NOTES_BAK=$(mktemp -d)
cp -R data/patch_notes "$NOTES_BAK/"
if [ $BUMP -eq 1 ]; then
	BUILD=$((OLD + 1))
	cp "$INFO" "$INFO.bak"
	STAMP=$(date '+%Y-%m-%d %H:%M')
	perl -pi -e "s/^const NUMBER: int = .*/const NUMBER: int = $BUILD/; s/^const TIME: String = .*/const TIME: String = \"$STAMP\"/" "$INFO"
	python3 -I tools/patch_notes.py --release "$VERSION" "$BUILD" > /dev/null || { mv "$INFO.bak" "$INFO"; fail "patch notes"; }
fi
restore() {
	if [ $BUMP -eq 1 ] && [ -f "$INFO.bak" ]; then mv "$INFO.bak" "$INFO"; echo "build number restored to $OLD"; fi
	rm -rf data/patch_notes && cp -R "$NOTES_BAK/patch_notes" data/ && echo "patch notes restored"
}
LABEL="v$VERSION (build $BUILD)"
echo "== Building $SLUG $LABEL"
# New class_names / assets must be in the import cache before exporting.
"$GODOT" --headless --audio-driver Dummy --path . --import > build_import.log 2>&1 || true
rm -f build_import.log

mkdir -p build
SMOKE_PACK=""
for p in "${PRESET_LIST[@]}"; do
	OUT=$(preset_path "$p")
	mkdir -p "$(dirname "$OUT")"
	rm -f "$OUT"
	LOG="build/export_$p.log"
	"$GODOT" --headless --audio-driver Dummy --path . --export-release "$p" "$OUT" > "$LOG" 2>&1
	if [ ! -s "$OUT" ] || grep -qE "SCRIPT ERROR|Parse Error|Export failed" "$LOG"; then
		echo "EXPORT FAILED: $p (see $LOG)"; grep -E "ERROR|error" "$LOG" | head -20
		restore; exit 1
	fi
	echo "exported $OUT ($(du -h "$OUT" | cut -f1))"
	ZIP="build/${SLUG}_${p}_${VERSION}-b${BUILD}.zip"
	rm -f "$ZIP"
	case "$OUT" in
		*.zip) cp "$OUT" "$ZIP" ;;
		*)
			STAGE=$(mktemp -d)
			mkdir -p "$STAGE/$SLUG"
			cp "$(dirname "$OUT")"/* "$STAGE/$SLUG/"
			printf '%s %s\n\nUnzip everything into one folder and start %s.\nEveryone who plays together needs this exact build.\n' \
				"$SLUG" "$LABEL" "$(basename "$OUT")" > "$STAGE/$SLUG/README.txt"
			(cd "$STAGE" && zip -qr - "$SLUG") > "$ZIP"
			rm -rf "${STAGE:?}"
			[ -z "$SMOKE_PACK" ] && SMOKE_PACK="$PWD/$OUT"
			;;
	esac
	echo "zipped $ZIP ($(du -h "$ZIP" | cut -f1))"
done
rm -f "$INFO.bak"
rm -rf "$NOTES_BAK"

[ $SMOKE -eq 1 ] || { echo "== DONE (no smoke test)"; exit 0; }
[ -n "$SMOKE_PACK" ] || { echo "== DONE (no pack to smoke-test)"; exit 0; }
echo "== Smoke test (headless, pack: $SMOKE_PACK)"
TMP=$(mktemp -d)
FAIL=0
R=(--headless --audio-driver Dummy --main-pack "$SMOKE_PACK")
# Run from an empty folder so only the pack is loaded, not the project.
(cd "$TMP" && with_timeout "$SMOKE_WALL_S" "$GODOT" "${R[@]}" --quit-after "$SMOKE_BOOT_FRAMES" > boot.log 2>&1)
if grep -qE "SCRIPT ERROR|Failed to load|Can't run project" "$TMP/boot.log"; then
	echo "boot: FAIL"; grep -E "SCRIPT ERROR|ERROR" "$TMP/boot.log" | head; FAIL=1
else
	echo "boot: ok"
fi
{{#MULTIPLAYER}}(cd "$TMP" && with_timeout "$SMOKE_WALL_S" "$GODOT" "${R[@]}" --max-fps $SMOKE_FPS --quit-after "$SMOKE_HOST_FRAMES" -- --host --port=$SMOKE_PORT --save=release_smoke > host.log 2>&1) &
HOST_PID=$!
sleep 3
(cd "$TMP" && with_timeout "$SMOKE_WALL_S" "$GODOT" "${R[@]}" --max-fps $SMOKE_FPS --quit-after "$SMOKE_CLIENT_FRAMES" -- --join=127.0.0.1 --port=$SMOKE_PORT --save=release_smoke_c > client.log 2>&1)
wait $HOST_PID
if grep -q "\[Network\] hosting" "$TMP/host.log" && ! grep -q "SCRIPT ERROR" "$TMP/host.log"; then echo "host: ok"; else echo "host: FAIL"; grep -E "SCRIPT ERROR|ERROR|Network" "$TMP/host.log" | head; FAIL=1; fi
if grep -q "\[Network\] joined" "$TMP/client.log" && ! grep -q "SCRIPT ERROR" "$TMP/client.log"; then echo "join: ok"; else echo "join: FAIL"; grep -E "SCRIPT ERROR|ERROR|Network" "$TMP/client.log" | head; FAIL=1; fi
{{/MULTIPLAYER}}rm -rf "${TMP:?}"
[ $FAIL -eq 0 ] && echo "== DONE $LABEL" || { echo "== SMOKE TEST FAILED"; exit 1; }
