extends SceneTree
## Localization check: player-visible text must go through translation.
## Controls translate plain text by themselves (auto-translate), so the
## mistakes this finds are the ones that slip past it:
## - code that builds UI text by formatting or concatenation without tr()
##   (`label.text = "Score: %d" % n`, `title = "Hi " + name`, `text += "x"`),
##   because the formatted string is never a translation key;
## - .tscn nodes with auto-translate turned off that still show text.
## Allowed exceptions: tests/l10n/l10n_allowlist.gd. Also checks at runtime
## that tr() and Control auto-translate really translate (test locale).
##   godot --headless --audio-driver Dummy --path . -s res://tests/l10n/check_strings.gd
## Prints "RESULT PASS/FAIL l10n" (exit 0 / 1).

const Allowlist := preload("res://tests/l10n/l10n_allowlist.gd")
const SKIP_DIRS: Array[String] = ["res://tests", "res://addons", "res://tools", "res://.godot", "res://.claude",
	"res://build"]
## Assignments of these properties show text to the player.
const TEXT_PROPERTIES: String = "text|tooltip_text|placeholder_text|title|dialog_text|ok_button_text|cancel_button_text"
## Calls whose first argument is shown to the player.
const TEXT_CALLS: String = "set_text|set_tooltip_text|add_item|add_check_item|add_radio_check_item|add_tab|set_item_text|set_tab_title|add_button|add_cancel_button"
const TRANSLATE_CALLS: Array[String] = ["tr(", "atr(", "tr_n(", "atr_n(", "translate("]
const AUTO_TRANSLATE_DISABLED: String = "auto_translate_mode = 2"
const TEST_LOCALE: String = "x-l10n-test"

var _assign_re: RegEx = RegEx.create_from_string("(?:^|[\\s.(])(?:%s)\\s*(\\+?=)\\s*(.+)$" % TEXT_PROPERTIES)
var _call_re: RegEx = RegEx.create_from_string("\\b(?:%s)\\s*\\((.+)$" % TEXT_CALLS)
var _literal_re: RegEx = RegEx.create_from_string("(?<![&^])\"((?:[^\"\\\\]|\\\\.)*)\"")
var _letter_re: RegEx = RegEx.create_from_string("[A-Za-z\\p{L}]")
## Format specifiers (%d, %.1f, %s, {0}, {name}) are not words.
var _spec_re: RegEx = RegEx.create_from_string("%[-+ 0#]*\\d*(?:\\.\\d+)?[a-zA-Z%]|\\{\\w*\\}|\\\\[ntr]")
var _failures: Array[String] = []
var _scanned: int = 0
var _done: bool = false


func _initialize() -> void:
	_self_test()
	_scan("res://")


func _process(_delta: float) -> bool:
	# Translation of Controls needs the tree, so this runs in the first frame.
	if _done:
		return true
	_done = true
	_check_pipeline()
	for line: String in _failures:
		print(line)
	if _failures.is_empty():
		print("RESULT PASS l10n (%d files scanned)" % _scanned)
		quit(0)
	else:
		print("RESULT FAIL l10n: %d problem(s) in %d files" % [_failures.size(), _scanned])
		quit(1)
	return true


## Returns a reason if one line of GDScript builds player text without tr(), else "".
func check_line(line: String) -> String:
	var code: String = _strip_comment(line)
	var rhs: String = ""
	var appends: bool = false
	var m: RegExMatch = _assign_re.search(code)
	if m:
		appends = m.get_string(1) == "+="
		rhs = m.get_string(2)
	else:
		var c: RegExMatch = _call_re.search(code)
		if c == null:
			return ""
		rhs = c.get_string(1)
	for lit: RegExMatch in _literal_re.search_all(rhs):
		var value: String = lit.get_string(1)
		if not has_words(value) or Allowlist.STRINGS.has(value) or _translated(rhs, lit.get_start()):
			continue
		var after: String = rhs.substr(lit.get_end()).strip_edges()
		var before: String = rhs.substr(0, lit.get_start()).strip_edges()
		if appends:
			return "appends untranslated text \"%s\" (build the whole string with tr() first)" % value
		if after.begins_with("%") or after.begins_with(".format(") or after.begins_with("+") or before.ends_with("+"):
			return "formats/concatenates \"%s\" without tr() (use tr(\"...\") %% args)" % value
	return ""


## True if the text has letters outside format specifiers.
func has_words(value: String) -> bool:
	return _letter_re.search(_spec_re.sub(value, "", true)) != null


func _translated(rhs: String, literal_start: int) -> bool:
	var before: String = rhs.substr(0, literal_start).strip_edges()
	for call: String in TRANSLATE_CALLS:
		if before.ends_with(call):
			return true
	return false


func _strip_comment(line: String) -> String:
	var in_string: bool = false
	for i: int in line.length():
		var ch: String = line[i]
		if ch == "\"" and (i == 0 or line[i - 1] != "\\"):
			in_string = not in_string
		elif ch == "#" and not in_string:
			return line.substr(0, i)
	return line


func _scan(dir_path: String) -> void:
	if SKIP_DIRS.has(dir_path.trim_suffix("/")) or Allowlist.PATHS.any(func(p: String) -> bool: return (dir_path.trim_suffix("/") + "/").begins_with(p)):
		return
	var dir: DirAccess = DirAccess.open(dir_path)
	if dir == null:
		return
	for sub: String in dir.get_directories():
		if not sub.begins_with("."):
			_scan(dir_path.path_join(sub))
	for file: String in dir.get_files():
		var path: String = dir_path.path_join(file)
		if Allowlist.PATHS.has(path):
			continue
		if file.ends_with(".gd"):
			_scan_script(path)
		elif file.ends_with(".tscn"):
			_scan_scene(path)


func _scan_script(path: String) -> void:
	_scanned += 1
	var lines: PackedStringArray = FileAccess.get_file_as_string(path).split("\n")
	for i: int in lines.size():
		var reason: String = check_line(lines[i])
		if not reason.is_empty():
			_failures.append("%s:%d: %s" % [path, i + 1, reason])


## Nodes with auto-translate disabled that still carry text.
func _scan_scene(path: String) -> void:
	_scanned += 1
	var node_header: String = ""
	var node_line: int = 0
	var disabled: bool = false
	var text_value: String = ""
	var lines: PackedStringArray = FileAccess.get_file_as_string(path).split("\n")
	for i: int in lines.size() + 1:
		var line: String = lines[i] if i < lines.size() else "["
		if line.begins_with("["):
			if disabled and has_words(text_value) and not Allowlist.STRINGS.has(text_value):
				_failures.append("%s:%d: %s shows \"%s\" with auto-translate disabled" % [path, node_line, node_header, text_value])
			node_header = line.strip_edges()
			node_line = i + 1
			disabled = false
			text_value = ""
		elif line.strip_edges() == AUTO_TRANSLATE_DISABLED:
			disabled = true
		elif line.begins_with("text = \""):
			text_value = line.trim_prefix("text = \"").trim_suffix("\"")


## tr() and a Control's auto-translate must use a registered translation.
func _check_pipeline() -> void:
	var translation := Translation.new()
	translation.locale = TEST_LOCALE
	translation.add_message("Play", "Spielen")
	translation.add_message("Score: %d", "Punkte: %d")
	TranslationServer.add_translation(translation)
	var previous: String = TranslationServer.get_locale()
	TranslationServer.set_locale(TEST_LOCALE)
	var label := Label.new()
	root.add_child(label)
	_expect(label.atr("Play") == "Spielen", "Control auto-translate does not translate (%s)" % label.atr("Play"))
	_expect(root.tr("Score: %d") % 3 == "Punkte: 3", "tr() with format arguments")
	_expect(root.tr("Unknown key") == "Unknown key", "unknown keys fall back to the source text")
	label.queue_free()
	TranslationServer.set_locale(previous)
	TranslationServer.remove_translation(translation)


## The checker itself: known good and bad lines.
func _self_test() -> void:
	var bad: Array[String] = [
		'label.text = "Score: %d" % score',
		'title = "Welcome, " + player_name',
		'status.text += " (ready)"',
		'button.set_text("Level " + str(level))',
		'menu.add_item("Volume %d%%" % vol)',
	]
	var good: Array[String] = [
		'label.text = "Play"',
		'label.text = tr("Score: %d") % score',
		'title = tr("Welcome, %s") % player_name',
		'label.text = TITLE',
		'label.text = str(score)',
		'# label.text = "Score: %d" % score',
		'var path: String = "res://a/%s.tscn" % id',
		'label.text = "%d / %d" % [a, b]',
		'node.name = "Spawn_%d" % i',
	]
	for line: String in bad:
		_expect(not check_line(line).is_empty(), "self-test: should flag: %s" % line)
	for line: String in good:
		_expect(check_line(line).is_empty(), "self-test: should pass: %s (%s)" % [line, check_line(line)])


func _expect(ok: bool, what: String) -> void:
	if not ok:
		_failures.append("CHECK: " + what)
