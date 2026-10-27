#!/bin/bash
# Host + client in two headless Godot processes. Default pair (net_host / net_client):
# the client joins, registers its name, and both sides must see the same
# server-authoritative roster. Other pairs: run_net.sh <host script> <client script> [port]
# (scripts in tests/net/, without .gd). Fails on any FAIL, SCRIPT ERROR or exit leak in
# either process. The last line is "NET PASS" or "NET FAIL ..." (tools/test_runner.py reads it).
cd "$(dirname "$0")/../.."
source tools/dev/godot_env.sh
HOST=${1:-net_host}
CLIENT=${2:-net_client}
PORT=${3:-${PORT:-7781}}
D=tests/net
OUT=$D/out
mkdir -p $OUT
R=(--headless --audio-driver Dummy --path .)
"$GODOT" "${R[@]}" -s res://$D/$HOST.gd -- --port=$PORT > $OUT/$HOST.log 2>&1 &
HOST_PID=$!
sleep 1
"$GODOT" "${R[@]}" -s res://$D/$CLIENT.gd -- --port=$PORT > $OUT/$CLIENT.log 2>&1
CLIENT_CODE=$?
wait $HOST_PID
HOST_CODE=$?
LOGS=($OUT/$HOST.log $OUT/$CLIENT.log)
ERRORS=$(cat "${LOGS[@]}" | grep -cE "SCRIPT ERROR|leaked at exit|still in use at exit")
grep -h "RESULT" "${LOGS[@]}"
if [ "$HOST_CODE" = 0 ] && [ "$CLIENT_CODE" = 0 ] && [ "$ERRORS" = 0 ]; then
	echo "NET PASS"
else
	echo "NET FAIL host=$HOST_CODE client=$CLIENT_CODE script_errors=$ERRORS (logs: $OUT/)"
	exit 1
fi
