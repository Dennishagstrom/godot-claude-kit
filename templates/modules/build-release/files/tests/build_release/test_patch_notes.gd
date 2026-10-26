extends SceneTree
## Patch notes data + "What's new" panel: parsing (broken entries skipped,
## newest first), which build opens by itself, and that the panel shows every
## release and closes. Prints RESULT PASS/FAIL.

const SAMPLE: String = """[
	{"version": "0.1.0", "build": 1, "date": "2026-01-01", "notes": {"new": ["First playable"], "fix": []}},
	{"version": "0.2.0", "build": 3, "date": "2026-02-01", "notes": {"new": ["Second level"], "change": ["Faster menus"], "fix": ["Crash on quit"]}},
	{"version": "x", "build": 0, "notes": {}},
	"not a release"
]"""

var _fails: Array[String] = []


func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	var releases: Array[Dictionary] = PatchNotesData.parse(SAMPLE)
	_check(releases.size() == 2, "two valid releases (got %d)" % releases.size())
	_check(int(releases[0][PatchNotesData.F_BUILD]) == 3, "newest first")
	_check(PatchNotesData.note_count(releases[0]) == 3, "note count")
	_check(PatchNotesData.unseen_build(releases, 3, 1) == 3, "build 3 is new for a player who saw 1")
	_check(PatchNotesData.unseen_build(releases, 3, 3) == 0, "nothing new after seeing it")
	_check(PatchNotesData.unseen_build(releases, 2, 0) == 1, "build 2 shows the notes of build 1")
	_check(PatchNotesData.parse("{broken").is_empty(), "broken JSON = no releases")
	_check(PatchNotesData.load_releases() is Array, "releases.json loads")
	_check(BuildInfo.label("1.2.3", 0).contains("dev") and BuildInfo.label("1.2.3", 7).contains("7"), "build label")
	var panel := PatchNotesPanel.new()
	panel.releases = releases
	panel.seen_build = 1
	root.add_child(panel)
	await process_frame
	_check(panel.release_count() == 2, "panel shows both releases (%d)" % panel.release_count())
	var closed: Array[bool] = [false]
	panel.closed.connect(func() -> void: closed[0] = true)
	panel.close()
	await process_frame
	_check(closed[0] and not is_instance_valid(panel), "panel closes")
	if _fails.is_empty():
		print("RESULT PASS patch notes")
		quit(0)
	else:
		for f: String in _fails:
			print("FAIL ", f)
		print("RESULT FAIL patch notes: %d" % _fails.size())
		quit(1)


func _check(ok: bool, what: String) -> void:
	if not ok:
		_fails.append(what)
