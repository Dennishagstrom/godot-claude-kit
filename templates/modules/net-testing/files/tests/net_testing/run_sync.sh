#!/bin/bash
# Host + client in two headless Godot processes: the client holds an input
# action, the server moves a synced value, the client sees it come back.
# Last line: "NET SYNC PASS" or "NET SYNC FAIL ..." (read by tools/test_runner.py).
#   tests/net_testing/run_sync.sh            (PORT=7791 by default)
cd "$(dirname "$0")/../.."
source tools/dev/godot_env.sh
PORT=${PORT:-7791}
WALL_S=${WALL_S:-60}
source tests/net_testing/pair.sh
run_pair sync "$PORT" "$PORT" "$WALL_S"
