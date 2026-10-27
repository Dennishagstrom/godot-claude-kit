#!/bin/bash
# Host + client in two headless Godot processes, both running the real main scene:
# the client joins, both see both players, and the client's input moves its player
# on the server and back. The last line is "NET PASS" or "NET FAIL ...".
cd "$(dirname "$0")/../.."
source tools/dev/godot_env.sh
PORT=${PORT:-7784}
D=tests/starter
OUT=$D/out
mkdir -p $OUT
R=(--headless --audio-driver Dummy --path . -s res://$D/starter_peer.gd)
"$GODOT" "${R[@]}" -- --role=host --port=$PORT > $OUT/host.log 2>&1 &
HOST_PID=$!
sleep 1
"$GODOT" "${R[@]}" -- --role=client --port=$PORT > $OUT/client.log 2>&1
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
