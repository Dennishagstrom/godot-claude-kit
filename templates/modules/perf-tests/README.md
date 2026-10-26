# Module: perf-tests

TL;DR: a performance budget as a test. `tests/perf/test_perf.gd` runs a scene
for N seconds and fails when average physics/process time, the 99th
percentile frame time or the number of hitches is over its limits. Plus an
in-game F3 overlay that logs every hitch.

## Suites

```
perf 120 perf,perf-tests,exclusive -s res://tests/perf/test_perf.gd -- --seconds=5
perf_level1 200 perf,exclusive -s res://tests/perf/test_perf.gd -- --scene=res://levels/level_01.tscn --host
```

- Without `--scene`: the main scene; without a main scene: a stress scene
  (200 physics bodies) so the budget is meaningful from day one.
- `--host` hosts first (multiplayer games simulate more on the host).
  `--report` prints the numbers and never fails (for measuring). So does `CI=true`
  (hosted CI runners are shared, slow machines).
- Limits are constants at the top (`MAX_AVG_PHYSICS_MS`, `MAX_AVG_PROCESS_MS`,
  `MAX_P99_FRAME_MS`, `SPIKE_MS`, `MAX_SPIKES`). Raise them on purpose, in a
  commit that says why.
- Tag `exclusive`: the runner runs it alone at the end, so parallel suites
  don't make it flaky. Headless frames are uncapped: frame time = CPU time.

## Overlay

`add_child(PerfOverlay.new())` once (e.g. main scene). F3 toggles FPS, frame,
physics and process time and the hitch count. Every frame over 33 ms prints
`[Perf] SPIKE <ms> (last input: ...)`, also in logs of headless runs: grep for
it when someone says "it stutters".

Why: a slow lookup in a hot path (e.g. reloading a resource per call) can
quietly cost tens of milliseconds per frame; a budget test catches it in the
round that introduced it instead of at the next playtest.
