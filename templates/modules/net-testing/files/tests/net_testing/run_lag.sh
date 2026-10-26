#!/bin/bash
# The sync test with the client behind tools/lag_proxy.py (bad Wi-Fi / VPN:
# default 120 ms round trip, +-30 ms jitter, 1 % loss each way).
#   tests/net_testing/run_lag.sh [rtt_ms] [jitter_ms] [loss_pct]
# Host on 7793, proxy on 7794. Last line: "NET LAG PASS" / "NET LAG FAIL ...".
cd "$(dirname "$0")/../.."
source tools/dev/godot_env.sh
RTT=${1:-120}; JITTER=${2:-30}; LOSS=${3:-1}
HOST_PORT=7793; PROXY_PORT=7794
WALL_S=${WALL_S:-90}
# Fixed seed: the same packets are dropped on every run.
SEED=${SEED:-7}
source tests/net_testing/pair.sh
"$PYTHON" -I tools/lag_proxy.py --listen $PROXY_PORT --target 127.0.0.1:$HOST_PORT --rtt "$RTT" \
	--jitter "$JITTER" --loss "$LOSS" --seed "$SEED" --duration "$WALL_S" > "$OUT/lag.proxy.log" 2>&1 &
PROXY_PID=$!
echo "lag: rtt=${RTT}ms jitter=${JITTER}ms loss=${LOSS}%"
run_pair lag $HOST_PORT $PROXY_PORT "$WALL_S"
CODE=$?
kill $PROXY_PID 2>/dev/null; wait $PROXY_PID 2>/dev/null
tail -1 "$OUT/lag.proxy.log"
if [ $CODE = 0 ]; then echo "NET LAG PASS"; else echo "NET LAG FAIL (see $OUT/)"; fi
exit $CODE
