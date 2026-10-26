#!/bin/bash
# Host + client in two headless Godot processes: the client joins, registers its
# name, and both sides must see the same server-authoritative roster.
# The last line is "NET PASS" or "NET FAIL ..." (tools/test_runner.py reads it).
cd "$(dirname "$0")/../.."
source tools/dev/godot_env.sh
PORT=${PORT:-7781}
D=tests/net
OUT=$D/out
mkdir -p $OUT
R=(--headless --audio-driver Dummy --path .)
"$GODOT" "${R[@]}" -s res://$D/net_host.gd -- --port=$PORT > $OUT/host.log 2>&1 &
HOST_PID=$!
sleep 1
"$GODOT" "${R[@]}" -s res://$D/net_client.gd -- --port=$PORT > $OUT/client.log 2>&1
CLIENT_CODE=$?
wait $HOST_PID
HOST_CODE=$?
ERRORS=$(cat $OUT/host.log $OUT/client.log | grep -c "SCRIPT ERROR")
grep -h "RESULT" $OUT/host.log $OUT/client.log
if [ "$HOST_CODE" = 0 ] && [ "$CLIENT_CODE" = 0 ] && [ "$ERRORS" = 0 ]; then
	echo "NET PASS"
else
	echo "NET FAIL host=$HOST_CODE client=$CLIENT_CODE script_errors=$ERRORS (logs: $OUT/)"
	exit 1
fi
