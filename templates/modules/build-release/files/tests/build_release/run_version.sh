#!/bin/bash
# Join handshake: a client on the same build joins; a client on another build
# is refused with a reason and never connects. Ports 7795, 7796.
# Last line: "RELEASE VERSION PASS" / "RELEASE VERSION FAIL ...".
cd "$(dirname "$0")/../.."
source tools/dev/godot_env.sh
D=tests/build_release
OUT=$D/out
mkdir -p $OUT
R=(--headless --audio-driver Dummy --path .)
WALL_S=40
FAIL=0
pair() { # name port expect client_extra...
	local name=$1 port=$2 expect=$3; shift 3
	perl -e 'alarm shift; exec @ARGV' $WALL_S "$GODOT" "${R[@]}" -s res://$D/version_peer.gd -- --role=host --port=$port --expect=$expect > $OUT/$name.host.log 2>&1 &
	local hp=$!
	sleep 1
	perl -e 'alarm shift; exec @ARGV' $WALL_S "$GODOT" "${R[@]}" -s res://$D/version_peer.gd -- --role=client --port=$port --expect=$expect "$@" > $OUT/$name.client.log 2>&1
	local cc=$?
	wait $hp; local hc=$?
	local errs=$(cat $OUT/$name.*.log | grep -c "SCRIPT ERROR")
	grep -h RESULT $OUT/$name.*.log
	if [ $hc != 0 ] || [ $cc != 0 ] || [ $errs != 0 ]; then FAIL=1; echo "$name: host=$hc client=$cc errors=$errs"; fi
}
pair match 7795 ok
pair mismatch 7796 reject --fake-build=999
[ $FAIL = 0 ] && echo "RELEASE VERSION PASS" || { echo "RELEASE VERSION FAIL (logs: $OUT/)"; exit 1; }
