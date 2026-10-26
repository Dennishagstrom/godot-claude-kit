extends SceneTree
## Smoothness at a high refresh rate: drawn at 240 Hz with 60 Hz physics, a
## visual under a VisualSmoother (and the camera under it) must move on almost
## every drawn frame, not in 60 Hz steps, and stay within one physics tick of
## the body. Client mode (eases toward a transform that arrives in 60 Hz
## steps) must also move every frame, converge when the body stops, and snap
## on teleports.
##   godot --headless --audio-driver Dummy --path . --fixed-fps 240 -s res://tests/smooth/test_smooth.gd
## The suite is tagged exclusive: timing tests run alone.

## Frames to measure (at 240 fps = 0.5 s).
const FRAMES: int = 120
const WARMUP_FRAMES: int = 20
## A frame where the visual moved less than this counts as "still".
const STILL_EPSILON: float = 0.0001
## At most this share of frames may be still (60 Hz steps would be ~75 %).
const MAX_STILL_SHARE: float = 0.1
{{#3D}}const SPEED: float = 6.0
const TELEPORT: Vector3 = Vector3(50, 0, 0)
const CLIENT_MAX_LAG: float = 1.0
const CONVERGED: float = 0.01
{{/3D}}{{^3D}}const SPEED: float = 400.0
const TELEPORT: Vector2 = Vector2(5000, 0)
const CLIENT_MAX_LAG: float = 60.0
const CONVERGED: float = 0.5
{{/3D}}const SETTLE_FRAMES: int = 240
const GAP_SLACK: float = 1.05

var _fails: Array[String] = []

{{#3D}}
## Moves at constant speed in physics ticks, like a CharacterBody3D.
class Mover extends Node3D:
	var velocity: Vector3 = Vector3.ZERO

	func _physics_process(delta: float) -> void:
		position += velocity * delta


## A smoother that behaves like it runs on a client.
class ClientSmoother extends VisualSmoother:
	func _is_authority() -> bool:
		return false
{{/3D}}{{^3D}}
## Moves at constant speed in physics ticks, like a CharacterBody2D.
class Mover extends Node2D:
	var velocity: Vector2 = Vector2.ZERO

	func _physics_process(delta: float) -> void:
		position += velocity * delta


## A smoother that behaves like it runs on a client.
class ClientSmoother extends VisualSmoother2D:
	func _is_authority() -> bool:
		return false
{{/3D}}

func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	var tick_hz: int = Engine.physics_ticks_per_second
	await _host_case(tick_hz)
	await _client_case()
	if _fails.is_empty():
		print("RESULT PASS smooth motion")
		quit(0)
	else:
		for f: String in _fails:
			print("FAIL ", f)
		print("RESULT FAIL smooth motion: %d" % _fails.size())
		quit(1)


func _host_case(tick_hz: int) -> void:
	var mover := Mover.new()
	root.add_child(mover)
{{#3D}}	var smoother := VisualSmoother.new()
	mover.add_child(smoother)
	var camera := Camera3D.new()
	camera.position = Vector3(0, 2, 5)
	smoother.add_child(camera)
	camera.make_current()
	mover.velocity = Vector3(SPEED, 0, 0)
{{/3D}}{{^3D}}	var smoother := VisualSmoother2D.new()
	mover.add_child(smoother)
	var camera := Camera2D.new()
	smoother.add_child(camera)
	camera.make_current()
	mover.velocity = Vector2(SPEED, 0)
{{/3D}}	for i: int in WARMUP_FRAMES:
		await process_frame
	var still_visual: int = 0
	var still_camera: int = 0
	var max_gap: float = 0.0
	var last_v := smoother.global_position
	var last_c := camera.global_position
	# process_frame fires after this frame's physics but before _process, so the
	# visual we see belongs to the previous frame: compare it with the body then.
	var last_body := mover.global_position
	for i: int in FRAMES:
		await process_frame
		if smoother.global_position.distance_to(last_v) < STILL_EPSILON:
			still_visual += 1
		if camera.global_position.distance_to(last_c) < STILL_EPSILON:
			still_camera += 1
		max_gap = maxf(max_gap, smoother.global_position.distance_to(last_body))
		last_v = smoother.global_position
		last_c = camera.global_position
		last_body = mover.global_position
	var max_still: int = int(FRAMES * MAX_STILL_SHARE)
	var tick_gap: float = SPEED / float(tick_hz) * GAP_SLACK
	print("host: visual still %d/%d, camera still %d, max gap %.3f (one tick = %.3f)" % [
		still_visual, FRAMES, still_camera, max_gap, SPEED / float(tick_hz)])
	_check(still_visual <= max_still, "host visual moves every drawn frame (still %d/%d)" % [still_visual, FRAMES])
	_check(still_camera <= max_still, "camera under the smoother moves every drawn frame (still %d)" % still_camera)
	_check(max_gap <= tick_gap, "visual within one physics tick of the body (%.3f > %.3f)" % [max_gap, tick_gap])
	mover.queue_free()
	await process_frame


func _client_case() -> void:
	var mover := Mover.new()
	root.add_child(mover)
	var smoother := ClientSmoother.new()
	mover.add_child(smoother)
{{#3D}}	mover.velocity = Vector3(SPEED, 0, 0)
{{/3D}}{{^3D}}	mover.velocity = Vector2(SPEED, 0)
{{/3D}}	for i: int in WARMUP_FRAMES:
		await process_frame
	var still: int = 0
	var max_lag: float = 0.0
	var last := smoother.global_position
	for i: int in FRAMES:
		await process_frame
		if smoother.global_position.distance_to(last) < STILL_EPSILON:
			still += 1
		max_lag = maxf(max_lag, smoother.global_position.distance_to(mover.global_position))
		last = smoother.global_position
	print("client: still %d/%d, max lag %.3f" % [still, FRAMES, max_lag])
	_check(still <= int(FRAMES * MAX_STILL_SHARE), "client visual eases every frame (still %d/%d)" % [still, FRAMES])
	_check(max_lag <= CLIENT_MAX_LAG, "client lag stays small (%.3f)" % max_lag)
	mover.velocity *= 0.0
	for i: int in SETTLE_FRAMES:
		await process_frame
	var settled: float = smoother.global_position.distance_to(mover.global_position)
	_check(settled <= CONVERGED, "client converges when the body stops (%.4f)" % settled)
	mover.position += TELEPORT
	await process_frame
	await process_frame
	var after: float = smoother.global_position.distance_to(mover.global_position)
	_check(after <= CONVERGED, "client snaps on a teleport (%.3f)" % after)
	mover.queue_free()
	await process_frame


func _check(ok: bool, what: String) -> void:
	if not ok:
		_fails.append(what)
