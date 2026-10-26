#!/bin/bash
# Builds the example model with headless Blender into a scratch folder, with
# a preview PNG, and checks both files. Skips (and passes) without Blender.
# Last line: "BLENDER PASS ..." / "BLENDER FAIL ...".
cd "$(dirname "$0")/../.."
SCRATCH=$(mktemp -d)
cleanup() { [ -d "$SCRATCH" ] && find "$SCRATCH" -mindepth 1 -delete && rmdir "$SCRATCH"; }
trap cleanup EXIT
OUT=$(OUT_DIR="$SCRATCH/models" PREVIEW_DIR="$SCRATCH/previews" bash tools/blender/build.sh --preview --no-import example_crate 2>&1)
CODE=$?
echo "$OUT"
if [ $CODE = 2 ] && echo "$OUT" | grep -q "Blender not found"; then
	echo "BLENDER PASS (skipped: Blender not found; set BLENDER=/path/to/blender)"
	exit 0
fi
GLB="$SCRATCH/models/example_crate.glb"
PNG="$SCRATCH/previews/example_crate.png"
if [ $CODE = 0 ] && [ -s "$GLB" ] && [ -s "$PNG" ]; then
	echo "BLENDER PASS glb $(wc -c < "$GLB") bytes, preview $(wc -c < "$PNG") bytes"
else
	echo "BLENDER FAIL (exit $CODE)"
	exit 1
fi
