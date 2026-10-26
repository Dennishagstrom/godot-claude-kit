class_name PatchNotesPanel
extends Control
## "What's new": every release in data/patch_notes/releases.json, newest
## first, with New / Changes / Fixes sections. open_if_new() shows it once per
## new build (the seen build is kept in user://whats_new.cfg; headless runs
## never write it). Built in code with the project theme; every note line is
## its own translation key (Labels auto-translate).

signal closed

const SEEN_PATH: String = "user://whats_new.cfg"
const SEEN_SECTION: String = "patch_notes"
const SEEN_KEY: String = "seen_build"
const PANEL_SIZE: Vector2 = Vector2(720, 560)
const SPACING: int = 12
const TITLE: String = "What's new"
const EMPTY_TEXT: String = "No patch notes yet."
const HEADER_FORMAT: String = "Build %d  ·  Version %s  ·  %s"
const NEW_TAG: String = "New"
const CLOSE_TEXT: String = "Close"
const BULLET: String = "•"
const SECTION_TITLES: Dictionary = {
	PatchNotesData.KIND_NEW: "New",
	PatchNotesData.KIND_CHANGE: "Changes",
	PatchNotesData.KIND_FIX: "Fixes",
}

## Releases to show (PatchNotesData.load_releases() when left empty).
var releases: Array[Dictionary] = []
## Releases newer than this build get a "New" tag.
var seen_build: int = 0

var _list: VBoxContainer = null
var _close_button: Button = null


## Opens the panel under `parent` if the running build has notes the player has
## not seen, and marks them seen. Returns the panel, or null when nothing is new.
static func open_if_new(parent: Node, current_build: int = BuildInfo.NUMBER) -> PatchNotesPanel:
	var all: Array[Dictionary] = PatchNotesData.load_releases()
	var seen: int = load_seen_build()
	if PatchNotesData.unseen_build(all, current_build, seen) == 0:
		return null
	var panel := PatchNotesPanel.new()
	panel.releases = all
	panel.seen_build = seen
	parent.add_child(panel)
	save_seen_build(PatchNotesData.unseen_build(all, current_build, seen))
	return panel


static func load_seen_build() -> int:
	var cfg := ConfigFile.new()
	return int(cfg.get_value(SEEN_SECTION, SEEN_KEY, 0)) if cfg.load(SEEN_PATH) == OK else 0


## Headless runs (tests, servers) never write the player's file.
static func save_seen_build(build: int) -> void:
	if DisplayServer.get_name() == "headless":
		return
	var cfg := ConfigFile.new()
	cfg.load(SEEN_PATH)
	cfg.set_value(SEEN_SECTION, SEEN_KEY, build)
	cfg.save(SEEN_PATH)


func _ready() -> void:
	name = "PatchNotesPanel"
	set_anchors_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	if releases.is_empty():
		releases = PatchNotesData.load_releases()
	_build()
	_close_button.grab_focus.call_deferred()


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed(&"ui_cancel"):
		get_viewport().set_input_as_handled()
		close()


func close() -> void:
	closed.emit()
	queue_free()


## Number of release blocks shown (tests).
func release_count() -> int:
	return _list.get_child_count() if _list else 0


func _build() -> void:
	var center := CenterContainer.new()
	center.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(center)
	var panel := PanelContainer.new()
	panel.custom_minimum_size = PANEL_SIZE
	center.add_child(panel)
	var column := VBoxContainer.new()
	column.add_theme_constant_override(&"separation", SPACING)
	panel.add_child(column)
	var title := Label.new()
	title.text = TITLE
	title.theme_type_variation = &"HeaderLarge"
	column.add_child(title)
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	column.add_child(scroll)
	_list = VBoxContainer.new()
	_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_list.add_theme_constant_override(&"separation", SPACING)
	scroll.add_child(_list)
	if releases.is_empty():
		var empty := Label.new()
		empty.text = EMPTY_TEXT
		column.add_child(empty)
	for release: Dictionary in releases:
		_list.add_child(_release_block(release))
	_close_button = Button.new()
	_close_button.text = CLOSE_TEXT
	_close_button.size_flags_horizontal = Control.SIZE_SHRINK_END
	_close_button.pressed.connect(close)
	column.add_child(_close_button)


func _release_block(release: Dictionary) -> Control:
	var block := VBoxContainer.new()
	var header := Label.new()
	var build: int = int(release[PatchNotesData.F_BUILD])
	header.text = tr(HEADER_FORMAT) % [build, release[PatchNotesData.F_VERSION], release[PatchNotesData.F_DATE]]
	if build > seen_build and seen_build > 0:
		header.text += "  ·  " + tr(NEW_TAG)
	header.auto_translate_mode = Node.AUTO_TRANSLATE_MODE_DISABLED
	header.theme_type_variation = &"HeaderMedium"
	block.add_child(header)
	for kind: String in PatchNotesData.KINDS:
		var lines: Array = release[PatchNotesData.F_NOTES][kind]
		if lines.is_empty():
			continue
		var section := Label.new()
		section.text = SECTION_TITLES[kind]
		section.theme_type_variation = &"HeaderSmall"
		block.add_child(section)
		for line: Variant in lines:
			var row := HBoxContainer.new()
			var bullet := Label.new()
			bullet.text = BULLET
			bullet.auto_translate_mode = Node.AUTO_TRANSLATE_MODE_DISABLED
			row.add_child(bullet)
			var text := Label.new()
			text.text = str(line)
			text.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
			text.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			row.add_child(text)
			block.add_child(row)
	return block
