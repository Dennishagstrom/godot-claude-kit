extends Node
## Save slots: every save file lives in user://saves/<slot>/. The slot is
## "default" for players, `--save=<slot>` picks another one (tests, tools,
## several worlds), and headless or `-s` script runs without --save use the
## throwaway "headless" slot, so tests never touch the player's saves.
## Writes are atomic (temp file + rename) and keep one .bak; a corrupt file
## falls back to its backup. No class_name on purpose (autoload).

const SAVES_DIR: String = "user://saves/"
const DEFAULT_SLOT: String = "default"
## Slot for headless and script runs that pass no --save=.
const TEST_SLOT: String = "headless"
const SAVE_ARG: String = "--save="
const TEMP_SUFFIX: String = ".tmp"
const BACKUP_SUFFIX: String = ".bak"
const JSON_INDENT: String = "\t"

## Current slot (folder name under SAVES_DIR).
var slot: String = DEFAULT_SLOT
## True for headless and `-s` script runs (tests, servers, tools).
var is_test_run: bool = false
## True when the slot came from --save= (an explicit choice).
var slot_forced: bool = false


func _init() -> void:
	var args: PackedStringArray = OS.get_cmdline_args()
	is_test_run = DisplayServer.get_name() == "headless" or args.has("-s") or args.has("--script")
	if is_test_run:
		slot = TEST_SLOT
	for arg: String in OS.get_cmdline_user_args():
		if arg.begins_with(SAVE_ARG):
			var wanted: String = arg.trim_prefix(SAVE_ARG)
			if is_valid_slot(wanted):
				slot = wanted
				slot_forced = true
			else:
				push_warning("SaveSlots: ignoring invalid slot name '%s'" % wanted)


static func is_valid_slot(slot_name: String) -> bool:
	return not slot_name.is_empty() and slot_name.is_valid_filename() and not slot_name.begins_with(".")


## Full path of a file in the current slot, e.g. path("world.json").
func path(file_name: String) -> String:
	return SAVES_DIR.path_join(slot).path_join(file_name)


func exists(file_name: String) -> bool:
	return FileAccess.file_exists(path(file_name))


## Writes `data` as JSON: temp file, then the old file becomes .bak, then rename.
func save_json(file_name: String, data: Variant) -> Error:
	var target: String = path(file_name)
	var err: Error = DirAccess.make_dir_recursive_absolute(target.get_base_dir())
	if err != OK and err != ERR_ALREADY_EXISTS:
		return err
	var temp: String = target + TEMP_SUFFIX
	var file: FileAccess = FileAccess.open(temp, FileAccess.WRITE)
	if file == null:
		return FileAccess.get_open_error()
	file.store_string(JSON.stringify(data, JSON_INDENT))
	file.close()
	if FileAccess.file_exists(target):
		DirAccess.rename_absolute(target, target + BACKUP_SUFFIX)
	return DirAccess.rename_absolute(temp, target)


## Reads JSON; a missing file gives `fallback`, a corrupt one its .bak (or fallback).
func load_json(file_name: String, fallback: Variant = null) -> Variant:
	var target: String = path(file_name)
	for candidate: String in [target, target + BACKUP_SUFFIX]:
		if not FileAccess.file_exists(candidate):
			continue
		var json := JSON.new()
		if json.parse(FileAccess.get_file_as_string(candidate)) == OK:
			if candidate != target:
				push_warning("SaveSlots: %s was unreadable, loaded its backup" % target)
			return json.data
	return fallback


func delete_file(file_name: String) -> void:
	for suffix: String in ["", BACKUP_SUFFIX, TEMP_SUFFIX]:
		if FileAccess.file_exists(path(file_name) + suffix):
			DirAccess.remove_absolute(path(file_name) + suffix)


## Slot folders that exist.
func list_slots() -> PackedStringArray:
	return DirAccess.get_directories_at(SAVES_DIR) if DirAccess.dir_exists_absolute(SAVES_DIR) else PackedStringArray()
