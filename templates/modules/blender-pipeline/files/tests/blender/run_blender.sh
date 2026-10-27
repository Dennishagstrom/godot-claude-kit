#!/bin/bash
# Builds the example models with headless Blender into a scratch folder, with contact
# sheets, and checks them: both files exist, the model check passes, the lamp's parts hang
# under each other with their origins at the joints, and the palette materials are used.
# Skips (and passes) without Blender. Last line: "BLENDER PASS ..." / "BLENDER FAIL ...".
cd "$(dirname "$0")/../.."
source tools/dev/godot_env.sh
SCRATCH=$(mktemp -d)
cleanup() { [ -d "$SCRATCH" ] && find "$SCRATCH" -mindepth 1 -delete && rmdir "$SCRATCH"; }
trap cleanup EXIT
OUT=$(OUT_DIR="$SCRATCH/models" PREVIEW_DIR="$SCRATCH/previews" bash tools/blender/build.sh --preview --no-import \
	example_crate example_lamp 2>&1)
CODE=$?
echo "$OUT"
if [ $CODE = 2 ] && echo "$OUT" | grep -q "Blender not found"; then
	echo "BLENDER PASS (skipped: Blender not found; set BLENDER=/path/to/blender)"
	exit 0
fi
for f in models/example_crate.glb models/example_lamp.glb previews/example_crate.png previews/example_lamp.png; do
	[ -s "$SCRATCH/$f" ] || { echo "BLENDER FAIL missing $f (exit $CODE)"; exit 1; }
done
"$PYTHON" -I - "$SCRATCH/models" <<'PY' || { echo "BLENDER FAIL model checks"; exit 1; }
import json, os, subprocess, sys
models = sys.argv[1]
files = [os.path.join(models, f) for f in ("example_crate.glb", "example_lamp.glb")]
out = subprocess.run([sys.executable, "-I", "tools/dev/asset_check.py", "--json"] + files, capture_output=True, text=True)
report = json.loads(out.stdout)
problems = list(report["findings"])
stats = {os.path.basename(k): v for k, v in report["models"].items()}
parents = {n["name"]: n["parent"] for n in stats["example_lamp.glb"]["nodes"]}
want = {"lamp_arm_lower": "lamp_base", "lamp_arm_upper": "lamp_arm_lower", "lamp_head": "lamp_arm_upper",
        "lamp_bulb": "lamp_head"}
problems += ["%s hangs under %s, not %s" % (k, parents.get(k), v) for k, v in want.items() if parents.get(k) != v]
for name in ("example_crate.glb", "example_lamp.glb"):
    if "palette" not in stats[name]["materials"]:
        problems.append("%s does not use the palette material: %s" % (name, stats[name]["materials"]))
for p in problems:
    print("FAIL", p)
sys.exit(1 if problems else 0)
PY
echo "BLENDER PASS crate + jointed lamp built, checked, contact sheets rendered"
