extends SceneTree
## UI tokens: the theme builds with every variation, the components work
## (button variants, panel title/body, modal confirm + Esc), and no game
## script or scene hardcodes a colour or a font size / spacing number
## in a UI folder (ui/, hud/, menu/; outside scripts/ui/ui_tokens.gd).
## A line may opt out with "# ui-tokens: ok".

const SCAN_DIRS: Array[String] = ["res://scripts", "res://scenes", "res://autoload"]
const TOKENS_FILE: String = "res://scripts/ui/ui_tokens.gd"
const OPT_OUT: String = "# ui-tokens: ok"
## Only UI folders are scanned (gameplay may use colours for lights, VFX ...).
const UI_FOLDERS: Array[String] = ["/ui/", "/hud/", "/menu/", "/menus/"]
## Hardcoded colours or sizes in scripts.
const SCRIPT_PATTERNS: Array[String] = [
	"\\bColor8?\\s*\\(",
	"\\bColor\\.(html|from_hsv|from_rgba8|from_string)\\s*\\(",
	"\"#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?\"",
	"add_theme_(font_size|constant)_override\\s*\\([^,]+,\\s*-?\\d",
]
## Per-node overrides in scenes (colours / font sizes belong in the theme).
const SCENE_PATTERNS: Array[String] = ["^theme_override_colors/", "^theme_override_font_sizes/"]

var _fails: Array[String] = []
var _frame: int = 0
var _modal: UiModal = null
var _confirmed: bool = false
var _closed: bool = false


func _process(_delta: float) -> bool:
	_frame += 1
	if _frame == 1:
		_check_theme()
		_check_components()
		_scan_all()
		_modal = UiModal.confirm(root, "Leave?", "One sentence.", "Leave", "Stay")
		_modal.confirmed.connect(func() -> void: _confirmed = true)
		return false
	if _frame == 2:
		var esc := InputEventAction.new()
		esc.action = &"ui_cancel"
		esc.pressed = true
		Input.parse_input_event(esc)
		_modal.closed.connect(func() -> void: _closed = true)
		return false
	if _frame < 5:
		return false
	_check(_closed and not _confirmed, "Esc closes the modal without confirming")
	_finish()
	return true


func _check_theme() -> void:
	var t: Theme = UiTokens.build_theme()
	for v: StringName in [UiTokens.VAR_PRIMARY, UiTokens.VAR_DANGER, UiTokens.VAR_TITLE, UiTokens.VAR_MUTED]:
		_check(t.is_type_variation(v, &"Button") or t.is_type_variation(v, &"Label"), "theme has variation %s" % v)
	_check(t.get_font_size(&"font_size", UiTokens.VAR_TITLE) == UiTokens.FONT_TITLE, "title font size from tokens")
	_check(t.has_stylebox(&"focus", &"Button"), "buttons have a focus ring")


func _check_components() -> void:
	var holder := Control.new()
	holder.theme = UiTokens.theme()
	root.add_child(holder)
	var presses: Array[int] = [0]
	var button := UiButton.make("Play", func() -> void: presses[0] += 1, UiButton.Variant.PRIMARY)
	holder.add_child(button)
	button.pressed.emit()
	_check(presses[0] == 1 and button.theme_type_variation == UiTokens.VAR_PRIMARY, "UiButton variant + callback")
	var panel := UiPanel.make("Inventory", "Things you carry.")
	panel.body.add_child(UiText.label("Empty", UiText.MUTED))
	holder.add_child(panel)
	_check(panel.body.get_child_count() == 1 and panel.title == "Inventory", "UiPanel title + body")
	holder.queue_free()


func _scan_all() -> void:
	var script_res: Array[RegEx] = []
	for p: String in SCRIPT_PATTERNS:
		script_res.append(RegEx.create_from_string(p))
	var scene_res: Array[RegEx] = []
	for p: String in SCENE_PATTERNS:
		scene_res.append(RegEx.create_from_string(p))
	for dir: String in SCAN_DIRS:
		_scan(dir, script_res, scene_res)


func _scan(dir_path: String, script_res: Array[RegEx], scene_res: Array[RegEx]) -> void:
	var dir: DirAccess = DirAccess.open(dir_path)
	if dir == null:
		return
	for sub: String in dir.get_directories():
		_scan(dir_path.path_join(sub), script_res, scene_res)
	for file: String in dir.get_files():
		var path: String = dir_path.path_join(file)
		if path == TOKENS_FILE or not (file.ends_with(".gd") or file.ends_with(".tscn")):
			continue
		if not UI_FOLDERS.any(func(f: String) -> bool: return (path.get_base_dir() + "/").contains(f)):
			continue
		var patterns: Array[RegEx] = script_res if file.ends_with(".gd") else scene_res
		var lines: PackedStringArray = FileAccess.get_file_as_string(path).split("\n")
		for i: int in lines.size():
			var line: String = lines[i]
			if line.contains(OPT_OUT) or line.strip_edges().begins_with("#"):
				continue
			for re: RegEx in patterns:
				if re.search(line):
					_fails.append("%s:%d hardcodes a colour/size: %s (use UiTokens)" % [path, i + 1, line.strip_edges().left(100)])
					break


func _check(ok: bool, what: String) -> void:
	if not ok:
		_fails.append(what)


func _finish() -> void:
	if _fails.is_empty():
		print("RESULT PASS ui tokens")
		quit(0)
	else:
		for f: String in _fails:
			print("FAIL ", f)
		print("RESULT FAIL ui tokens: %d" % _fails.size())
		quit(1)
