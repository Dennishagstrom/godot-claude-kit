#!/bin/bash
# Static checks (tools/dev/lint.py): no Godot needed, about a second.
cd "$(dirname "$0")/../.."
source tools/dev/godot_env.sh
"$PYTHON" -I tools/dev/lint.py
