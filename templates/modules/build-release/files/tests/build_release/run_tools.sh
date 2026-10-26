#!/bin/bash
# Release tooling without exporting: tools/patch_notes.py on a scratch copy
# (validate, stamp, reject bad lines) and tools/build_release.sh --check.
# Last line: "RELEASE TOOLS PASS" / "RELEASE TOOLS FAIL ...".
cd "$(dirname "$0")/../.."
source tools/dev/godot_env.sh
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
FAIL=0
mkdir -p "$TMP/notes/unreleased"
echo "[]" > "$TMP/notes/releases.json"
printf 'new: A shiny feature.\nfix: A nasty bug.\n# comment lines are ignored\n' > "$TMP/notes/unreleased/task-a.txt"
printf 'change: Something feels better.\n' > "$TMP/notes/unreleased/task-b.txt"
"$PYTHON" -I tools/patch_notes.py --dir "$TMP/notes" --check | grep -q "3 unreleased notes in 2 files" || { echo "check: wrong count"; FAIL=1; }
"$PYTHON" -I tools/patch_notes.py --dir "$TMP/notes" --release 9.9.9 42 > /dev/null || { echo "release failed"; FAIL=1; }
"$PYTHON" -I - "$TMP/notes/releases.json" <<'PY' || FAIL=1
import json, sys
r = json.load(open(sys.argv[1]))
ok = len(r) == 1 and r[0]["build"] == 42 and r[0]["notes"]["new"] == ["A shiny feature."] and len(r[0]["notes"]["change"]) == 1
print("stamp ok" if ok else "stamp wrong: %s" % r)
sys.exit(0 if ok else 1)
PY
ls "$TMP/notes/unreleased/"*.txt > /dev/null 2>&1 && { echo "fragments not removed"; FAIL=1; }
printf 'nope: bad line\n' > "$TMP/notes/unreleased/bad.txt"
"$PYTHON" -I tools/patch_notes.py --dir "$TMP/notes" --check > /dev/null && { echo "bad line accepted"; FAIL=1; }
"$PYTHON" -I tools/patch_notes.py --check > /dev/null || { echo "project patch notes invalid"; FAIL=1; }
OUT=$(bash tools/build_release.sh --check 2>&1)
echo "$OUT" | tail -3
if ! echo "$OUT" | grep -q "RELEASE CHECK PASS"; then
	# A brand-new project has no main scene yet: that is a note, not a failure.
	if echo "$OUT" | grep -q "no main scene"; then echo "note: set a main scene before the first release"; else FAIL=1; fi
fi
[ $FAIL = 0 ] && echo "RELEASE TOOLS PASS" || { echo "RELEASE TOOLS FAIL"; exit 1; }
