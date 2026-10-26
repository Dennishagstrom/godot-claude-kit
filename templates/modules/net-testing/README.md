# Module: net-testing

TL;DR: host + client tests in two headless Godot processes, with the client's
input simulated by `Input.action_press`, and a UDP lag proxy to run the same
test over a bad connection. `python3 -I tools/test_runner.py net`.

## Files

- `tests/net_testing/net_test_base.gd`: base for test scripts (`extends "res://tests/net_testing/net_test_base.gd"`).
  Parses `-- --role=host|client --port=N`, connects in the first frame (never in
  `_initialize()`: autoloads don't exist yet), times out, prints `RESULT PASS/FAIL`.
  Override `_step(elapsed) -> bool`. Helpers: `network()`, `instantiate_main_scene()`,
  `press()`, `release()`, `press_for(action, seconds)`, `finish(ok, text)`.
- `tests/net_testing/sync_fixture.gd`: a tiny server-authoritative object
  (client input by validated RPC, `MultiplayerSynchronizer` built in code).
- `sync_host.gd` / `sync_client.gd`: the example test; `pair.sh` runs a pair.
- `run_sync.sh`: the pair on localhost (suite `net_sync`, port 7791).
- `run_lag.sh [rtt jitter loss]`: the pair with the client behind the proxy
  (suite `net_lag`, ports 7793/7794, default 120 ms, ±30 ms, 1 %).
- `tools/lag_proxy.py`: stdlib UDP proxy (`--rtt --jitter --loss --up/--down --seed --duration`).
  Play over it by hand too: `python3 -I tools/lag_proxy.py --listen 7778 --target 127.0.0.1:7777 --rtt 150`
  and join port 7778.

## Writing a game test

1. Copy `sync_host.gd`/`sync_client.gd`. In `_step`, call `instantiate_main_scene()`
   on the first frame if you need the real game, wait on **state** (player node
   exists, value reached), never on frame counts.
2. Simulate the player with `press_for(&"move_right", 1.0)` (real input actions).
3. Assert what the *other* peer sees (the client reads synced state, the host
   reads authoritative state).
4. Give the suite its own port (`--port=` / `PORT=`) and add it to
   `tests/integration/suites.txt` with the `net` tag.
5. Run it once over lag: `tests/net_testing/run_lag.sh 200 50 3` style.

Why: netcode bugs (missing validation, deltas instead of full state, RPC order)
show up only with two processes, and timing bugs only with latency and loss.
