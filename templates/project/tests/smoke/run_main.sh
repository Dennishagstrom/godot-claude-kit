#!/bin/bash
# Runs the game the way a player starts it: the main scene, real time (no test script,
# no --fixed-fps), for a few seconds, then a normal quit. Fails on script errors and on
# exit-time leaks ("leaked at exit", "resources still in use"), which only show on a
# clean shutdown of the real game. Last line: "MAIN PASS" / "MAIN FAIL ...".
cd "$(dirname "$0")/../.."
source tools/dev/godot_env.sh
FRAMES=${FRAMES:-180}
LOG=tests/smoke/out/main.log
mkdir -p tests/smoke/out
if ! grep -q '^run/main_scene=' project.godot; then
	echo "MAIN PASS (skipped: no main scene)"; exit 0
fi
perl -e 'alarm shift; exec @ARGV' 60 "$GODOT" --headless --audio-driver Dummy --path . --quit-after "$FRAMES" > "$LOG" 2>&1
CODE=$?
PROBLEMS=$(grep -E "SCRIPT ERROR|leaked at exit|still in use at exit|Pages in use exist at exit" "$LOG" | head -5)
if [ $CODE = 0 ] && [ -z "$PROBLEMS" ]; then
	echo "MAIN PASS ($FRAMES frames, clean exit)"
else
	echo "$PROBLEMS"
	echo "MAIN FAIL exit=$CODE (log: $LOG; exit leaks: docs/dev_reference.md \"Exit leaks\")"
	exit 1
fi
