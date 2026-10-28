extends SceneTree
## Performance budget: runs a scene for N seconds and fails when the average
## physics or process time, the 99th percentile frame time or the number of
## hitches is over the limits below. Tagged `exclusive` in suites.txt so the
## runner runs it alone (other suites would steal CPU).
##   godot --headless --audio-driver Dummy --path . -s res://tests/perf/test_perf.gd \
##       -- [--scene=res://levels/level_01.tscn] [--seconds=5] [--host] [--report]
## Without --scene it measures the main scene, and without a main scene a
## built-in stress scene (many physics bodies) so the budget means something
## from day one. --report prints numbers but never fails.
## Headless frames are not capped, so frame time here is CPU time per frame.
## The run seed is fixed (`--seed=N` overrides it): with a random seed the scene gets
## other rooms, enemies and events every run, and the numbers swing so much (3–11 ms
## measured on one game) that a real regression and noise look the same.

const MAX_AVG_PHYSICS_MS: float = 8.0
const MAX_AVG_PROCESS_MS: float = 8.0
const MAX_P99_FRAME_MS: float = 33.0
## A frame longer than this (ms) is a hitch.
const SPIKE_MS: float = 50.0
const MAX_SPIKES: int = 2
const DEFAULT_SECONDS: float = 5.0
## Loading, shader and first-physics work is not measured.
const WARMUP_SECONDS: float = 1.0
const PERCENTILE: float = 0.99
const MS_PER_S: float = 1000.0
const US_PER_MS: float = 1000.0
const PERF_PORT: int = 7797
const PERF_SEED: int = 1234
## Set by tools/test_runner.py for suites that run beside others.
const PARALLEL_ENV: String = "{{GAME_ENV}}_PARALLEL"
## Built-in stress scene.
const STRESS_BODIES: int = 200
const STRESS_COLUMNS: int = 10
{{#3D}}const STRESS_SPACING: float = 1.2
const STRESS_FLOOR_SIZE: Vector3 = Vector3(60, 1, 60)
{{/3D}}{{^3D}}const STRESS_SPACING: float = 24.0
const STRESS_FLOOR_SIZE: Vector2 = Vector2(2000, 40)
const STRESS_BODY_RADIUS: float = 8.0
{{/3D}}
var _seconds: float = DEFAULT_SECONDS
var _scene_path: String = ""
var _host: bool = false
var _report_only: bool = false
var _seed: int = PERF_SEED
var _physics_ms: Array[float] = []
var _process_ms: Array[float] = []
var _frame_ms: Array[float] = []


func _initialize() -> void:
	for arg: String in OS.get_cmdline_user_args():
		if arg.begins_with("--seconds="):
			_seconds = arg.get_slice("=", 1).to_float()
		elif arg.begins_with("--scene="):
			_scene_path = arg.get_slice("=", 1)
		elif arg == "--host":
			_host = true
		elif arg == "--report":
			_report_only = true
		elif arg.begins_with(Rng.SEED_ARG):
			_seed = arg.trim_prefix(Rng.SEED_ARG).to_int()
	# Beside other suites (not exclusive) CPU timings mean little: report only.
	if OS.get_environment(PARALLEL_ENV) == "1":
		_report_only = true
		print("[PERF] %s=1: running beside other suites, limits are reported, not asserted" % PARALLEL_ENV)
	# Hosted CI runners are shared, slow VMs: a budget there measures the neighbours.
	if OS.get_environment("CI") == "true":
		_report_only = true
		print("[PERF] CI=true: shared CI machine, limits are reported, not asserted")
	_run.call_deferred()


func _run() -> void:
	if not _overlay_counts_spikes():
		_finish(["PerfOverlay did not count an injected hitch"], "")
		return
	Rng.reseed(_seed)
	seed(_seed)  # also code that still uses the global randf()
	var label: String = _load_scene()
	if _host and root.has_node(^"Network"):
		root.get_node(^"Network").call(&"host_game", PERF_PORT)
	var start: int = Time.get_ticks_msec()
	var warm_end: int = start + int(WARMUP_SECONDS * MS_PER_S)
	var end: int = warm_end + int(_seconds * MS_PER_S)
	var last_us: int = Time.get_ticks_usec()
	while Time.get_ticks_msec() < end:
		await process_frame
		var now_us: int = Time.get_ticks_usec()
		if Time.get_ticks_msec() >= warm_end:
			_frame_ms.append((now_us - last_us) / US_PER_MS)
			_physics_ms.append(Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS) * MS_PER_S)
			_process_ms.append(Performance.get_monitor(Performance.TIME_PROCESS) * MS_PER_S)
		last_us = now_us
	var avg_physics: float = _average(_physics_ms)
	var avg_process: float = _average(_process_ms)
	var p99: float = _percentile(_frame_ms, PERCENTILE)
	var spikes: int = _frame_ms.filter(func(ms: float) -> bool: return ms > SPIKE_MS).size()
	var summary: String = "%s (seed %d): %d frames in %.0f s, physics %.2f ms, process %.2f ms, p99 frame %.1f ms, hitches>%d ms: %d, nodes %d" % [
		label, _seed, _frame_ms.size(), _seconds, avg_physics, avg_process, p99, int(SPIKE_MS), spikes,
		Performance.get_monitor(Performance.OBJECT_NODE_COUNT)]
	var fails: Array[String] = []
	if avg_physics > MAX_AVG_PHYSICS_MS:
		fails.append("average physics %.2f ms > %.1f" % [avg_physics, MAX_AVG_PHYSICS_MS])
	if avg_process > MAX_AVG_PROCESS_MS:
		fails.append("average process %.2f ms > %.1f" % [avg_process, MAX_AVG_PROCESS_MS])
	if p99 > MAX_P99_FRAME_MS:
		fails.append("p99 frame %.1f ms > %.1f" % [p99, MAX_P99_FRAME_MS])
	if spikes > MAX_SPIKES:
		fails.append("%d hitches > %d" % [spikes, MAX_SPIKES])
	if _frame_ms.is_empty():
		fails.append("no frames measured")
	if _report_only:
		fails.clear()
	_finish(fails, summary)


## Loads --scene, else the main scene, else the stress scene. Returns a label.
func _load_scene() -> String:
	var path: String = _scene_path
	if path.is_empty():
		path = ProjectSettings.get_setting("application/run/main_scene", "")
	if not path.is_empty():
		root.add_child((load(path) as PackedScene).instantiate())
		return path
	root.add_child(_stress_scene())
	return "stress scene (%d bodies)" % STRESS_BODIES


func _stress_scene() -> Node:
{{#3D}}	var scene := Node3D.new()
	var floor_body := StaticBody3D.new()
	var floor_shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = STRESS_FLOOR_SIZE
	floor_shape.shape = box
	floor_body.add_child(floor_shape)
	scene.add_child(floor_body)
	var body_shape := BoxShape3D.new()
	for i: int in STRESS_BODIES:
		var body := RigidBody3D.new()
		var shape := CollisionShape3D.new()
		shape.shape = body_shape
		body.add_child(shape)
		body.position = Vector3(i % STRESS_COLUMNS, 2 + floori(float(i) / STRESS_COLUMNS), 0) * STRESS_SPACING
		scene.add_child(body)
{{/3D}}{{^3D}}	var scene := Node2D.new()
	var floor_body := StaticBody2D.new()
	var floor_shape := CollisionShape2D.new()
	var rect := RectangleShape2D.new()
	rect.size = STRESS_FLOOR_SIZE
	floor_shape.shape = rect
	floor_body.add_child(floor_shape)
	scene.add_child(floor_body)
	var circle := CircleShape2D.new()
	circle.radius = STRESS_BODY_RADIUS
	for i: int in STRESS_BODIES:
		var body := RigidBody2D.new()
		var shape := CollisionShape2D.new()
		shape.shape = circle
		body.add_child(shape)
		body.position = Vector2(i % STRESS_COLUMNS, -2 - floori(float(i) / STRESS_COLUMNS)) * STRESS_SPACING
		scene.add_child(body)
{{/3D}}	return scene


## The overlay must notice a long frame (fed directly: no real stall needed).
func _overlay_counts_spikes() -> bool:
	var overlay := PerfOverlay.new()
	root.add_child(overlay)
	overlay.record_frame(PerfOverlay.SPIKE_MS * 0.5)
	overlay.record_frame(PerfOverlay.SPIKE_MS * 3.0)
	var ok: bool = overlay.spikes == 1
	overlay.queue_free()
	return ok


func _average(values: Array[float]) -> float:
	var total: float = 0.0
	for v: float in values:
		total += v
	return total / maxf(values.size(), 1.0)


func _percentile(values: Array[float], q: float) -> float:
	if values.is_empty():
		return 0.0
	var sorted: Array[float] = values.duplicate()
	sorted.sort()
	return sorted[mini(int(q * sorted.size()), sorted.size() - 1)]


func _finish(fails: Array[String], summary: String) -> void:
	print("[PERF] " + summary)
	for f: String in fails:
		print("FAIL ", f)
	print("RESULT %s perf" % ("PASS" if fails.is_empty() else "FAIL"))
	quit(0 if fails.is_empty() else 1)
