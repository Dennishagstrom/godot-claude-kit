class_name PatchNotesData
extends RefCounted
## Player-facing patch notes for "What's new", read from
## data/patch_notes/releases.json (written by tools/patch_notes.py when
## tools/build_release.sh stamps a build; see docs/modules/build-release.md).
## export_presets.cfg includes "data/patch_notes/*.json", so exported
## builds read the same file from the pack with FileAccess.
##
## A release is {version: String, build: int, date: String,
## notes: {new: [String], change: [String], fix: [String]}}. load_releases()
## validates and sorts newest first; broken entries are skipped, never fatal.

const PATH: String = "res://data/patch_notes/releases.json"
const F_VERSION: String = "version"
const F_BUILD: String = "build"
const F_DATE: String = "date"
const F_NOTES: String = "notes"
## Note kinds in display order (the keys of `notes`).
const KIND_NEW: String = "new"
const KIND_CHANGE: String = "change"
const KIND_FIX: String = "fix"
const KINDS: Array[String] = [KIND_NEW, KIND_CHANGE, KIND_FIX]


## Every valid release in `path`, newest build first. Missing or broken
## file = [] (with a warning for a broken one).
static func load_releases(path: String = PATH) -> Array[Dictionary]:
	if not FileAccess.file_exists(path):
		return []
	return parse(FileAccess.get_file_as_string(path))


## Parses releases.json text into clean releases, newest build first.
static func parse(text: String) -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	var json := JSON.new()
	if json.parse(text) != OK:
		push_warning("PatchNotesData: releases.json line %d: %s" % [json.get_error_line(), json.get_error_message()])
		return result
	if not json.data is Array:
		push_warning("PatchNotesData: releases.json is not a JSON array")
		return result
	for entry: Variant in json.data:
		var release: Dictionary = _clean(entry)
		if not release.is_empty():
			result.append(release)
	result.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return int(a[F_BUILD]) > int(b[F_BUILD]))
	return result


## The newest release that is not newer than `current_build` ({} = none):
## the notes for the build the player is running.
static func current_release(releases: Array[Dictionary], current_build: int) -> Dictionary:
	for release: Dictionary in releases:
		if int(release[F_BUILD]) <= current_build:
			return release
	return {}


## Build whose notes should open by themselves (0 = nothing new): the
## current release when the player has not seen it yet.
static func unseen_build(releases: Array[Dictionary], current_build: int, seen_build: int) -> int:
	var release: Dictionary = current_release(releases, current_build)
	if release.is_empty():
		return 0
	var build: int = int(release[F_BUILD])
	return build if build > seen_build else 0


## Number of note lines in a release (all kinds).
static func note_count(release: Dictionary) -> int:
	var count: int = 0
	for kind: String in KINDS:
		count += (release[F_NOTES][kind] as Array).size()
	return count


static func _clean(entry: Variant) -> Dictionary:
	if not entry is Dictionary:
		return {}
	var raw: Dictionary = entry
	var build_value: Variant = raw.get(F_BUILD)
	if not (build_value is float or build_value is int) or int(build_value) <= 0:
		return {}
	var notes: Dictionary = {}
	var raw_notes: Variant = raw.get(F_NOTES, {})
	for kind: String in KINDS:
		var lines: Array[String] = []
		if raw_notes is Dictionary and (raw_notes as Dictionary).get(kind) is Array:
			for line: Variant in (raw_notes as Dictionary)[kind]:
				var text: String = str(line).strip_edges() if line is String else ""
				if not text.is_empty():
					lines.append(text)
		notes[kind] = lines
	return {
		F_VERSION: str(raw.get(F_VERSION, "")),
		F_BUILD: int(build_value),
		F_DATE: str(raw.get(F_DATE, "")),
		F_NOTES: notes,
	}
