#!/bin/bash
# Every model in the project against tools/dev/asset_rules.json (tools/dev/asset_check.py):
# no Godot or Blender needed, about a second.
cd "$(dirname "$0")/../.."
source tools/dev/godot_env.sh
"$PYTHON" -I tools/dev/asset_check.py
