#!/bin/bash
# Sourced by the net_testing scripts: run_pair <name> <host_port> <client_port> <wall_s>
# starts sync_host.gd and sync_client.gd headless (client on <client_port>, which
# is the lag proxy's port in run_lag.sh), waits for both and prints one result line.
D=tests/net_testing
OUT=$D/out
mkdir -p "$OUT"
R=(--headless --audio-driver Dummy --path .)
# Kills a process after N seconds (portable: no coreutils `timeout` on macOS).
with_timeout() { # seconds cmd...
	local s=$1; shift
	perl -e 'alarm shift; exec @ARGV' "$s" "$@"
}
run_pair() {
	local name=$1 hp=$2 cp=$3 wall=$4
	with_timeout "$wall" "$GODOT" "${R[@]}" -s res://$D/sync_host.gd -- --role=host --port="$hp" > "$OUT/$name.host.log" 2>&1 &
	local host_pid=$!
	# The host needs a moment to open the port; the client retries via its own timeout anyway.
	sleep 1
	with_timeout "$wall" "$GODOT" "${R[@]}" -s res://$D/sync_client.gd -- --role=client --port="$cp" > "$OUT/$name.client.log" 2>&1
	local client_code=$?
	wait $host_pid
	local host_code=$?
	local errors
	errors=$(cat "$OUT/$name.host.log" "$OUT/$name.client.log" | grep -c "SCRIPT ERROR")
	grep -h "RESULT" "$OUT/$name.host.log" "$OUT/$name.client.log"
	local label
	label=$(echo "$name" | tr '[:lower:]' '[:upper:]')
	if [ "$host_code" = 0 ] && [ "$client_code" = 0 ] && [ "$errors" = 0 ]; then
		echo "NET $label PASS"
		return 0
	fi
	echo "NET $label FAIL host=$host_code client=$client_code script_errors=$errors (logs: $OUT/)"
	return 1
}
