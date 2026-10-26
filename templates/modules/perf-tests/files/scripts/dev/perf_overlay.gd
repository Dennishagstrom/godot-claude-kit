class_name PerfOverlay
extends CanvasLayer
## Dev overlay (F3): FPS, frame time, physics/process time and hitch count, so
## "it feels choppy" can be measured instead of guessed. Every frame longer
## than SPIKE_MS is logged as "[Perf] SPIKE <ms>" with the last input, which
## makes hitches easy to find in logs (also in headless tests).
## Add it once, e.g. in the main scene: add_child(PerfOverlay.new()).
## F3 is read directly because this is a developer tool, not a game action.

const TOGGLE_KEY: Key = KEY_F3
## A frame longer than this (ms) is a hitch (33 ms = a dropped frame at 30 fps).
const SPIKE_MS: float = 33.0
const LAYER: int = 120
const MARGIN: Vector2 = Vector2(16, 16)
const MS_PER_S: float = 1000.0
const US_PER_MS: float = 1000.0

## Hitches since start (or reset()).
var spikes: int = 0
## Longest frame seen (ms).
var worst_ms: float = 0.0

var _label: Label = null
var _last_frame_us: int = 0
var _last_input: String = "-"
var _last_input_us: int = 0


func _ready() -> void:
	layer = LAYER
	visible = false
	process_mode = Node.PROCESS_MODE_ALWAYS
	_label = Label.new()
	_label.position = MARGIN
	_label.auto_translate_mode = Node.AUTO_TRANSLATE_MODE_DISABLED
	add_child(_label)


func _input(event: InputEvent) -> void:
	if event is InputEventMouseButton or event is InputEventKey:
		_last_input = event.as_text() + (" down" if event.is_pressed() else " up")
		_last_input_us = Time.get_ticks_usec()
	if event is InputEventKey and event.pressed and not event.echo and event.physical_keycode == TOGGLE_KEY:
		visible = not visible


func _process(_delta: float) -> void:
	var now: int = Time.get_ticks_usec()
	if _last_frame_us > 0:
		record_frame((now - _last_frame_us) / US_PER_MS)
	_last_frame_us = now
	if visible:
		var fps: float = Engine.get_frames_per_second()
		_label.text = "FPS %d (%.1f ms)  physics %.1f ms  process %.1f ms  hitches>%d ms: %d (worst %.0f ms)" % [
			fps, MS_PER_S / maxf(fps, 1.0), Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS) * MS_PER_S,
			Performance.get_monitor(Performance.TIME_PROCESS) * MS_PER_S, int(SPIKE_MS), spikes, worst_ms]


## Counts one frame; public so tests can feed frame times.
func record_frame(frame_ms: float) -> void:
	worst_ms = maxf(worst_ms, frame_ms)
	if frame_ms <= SPIKE_MS:
		return
	spikes += 1
	var since_input: float = (Time.get_ticks_usec() - _last_input_us) / US_PER_MS if _last_input_us > 0 else -1.0
	print("[Perf] SPIKE %.0f ms  (last input: %s, %.0f ms before)  fps=%d" % [
		frame_ms, _last_input, since_input, Engine.get_frames_per_second()])


func reset() -> void:
	spikes = 0
	worst_ms = 0.0
