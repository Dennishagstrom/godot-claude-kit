class_name CsvResourceBuilder
extends RefCounted
## Turns a CSV table into one Resource (.tres) per row. The column types come
## from the Resource class itself (its exported properties), so the CSV stays
## a plain spreadsheet and the class is the schema. Used by
## tools/data/build_resources.gd; see docs/modules/data-pipeline.md.
##
## A table starts with a directive line, then the header:
##   # class=res://scripts/data/example_item_data.gd out=res://data/example_items/
##   id,display_name,rarity,value,tags,tint
## Cells: int/float/bool/String/StringName, enums by name (case-insensitive),
## Color (#rrggbb), Vector2/3 ("x;y;z"), typed arrays ("a;b;c"), resources by
## res:// path. An empty cell keeps the class default. The `id` column names
## the file (<out>/<id>.tres). Files whose content is unchanged are not rewritten.

const ID_COLUMN: String = "id"
const DIRECTIVE_PREFIX: String = "#"
const LIST_SEPARATOR: String = ";"
const KEY_CLASS: String = "class"
const KEY_OUT: String = "out"
const TRUE_WORDS: Array[String] = ["true", "yes", "1", "y"]
const FALSE_WORDS: Array[String] = ["false", "no", "0", "n"]

var errors: Array[String] = []
var warnings: Array[String] = []
var written: int = 0
var unchanged: int = 0
var pruned: int = 0


## Builds every row of `csv_path`. check_only validates without writing;
## prune deletes .tres files in the out folder whose id is not in the table.
## out_override replaces the table's out= folder (tests). Returns the resources.
func build(csv_path: String, check_only: bool = false, prune: bool = false, out_override: String = "") -> Array[Resource]:
	var result: Array[Resource] = []
	var file: FileAccess = FileAccess.open(csv_path, FileAccess.READ)
	if file == null:
		errors.append("%s: cannot open" % csv_path)
		return result
	var directives: Dictionary = {}
	var header: PackedStringArray = PackedStringArray()
	var line_no: int = 0
	while not file.eof_reached() and header.is_empty():
		var line: PackedStringArray = file.get_csv_line()
		line_no += 1
		var first: String = line[0].strip_edges() if not line.is_empty() else ""
		if first.begins_with(DIRECTIVE_PREFIX):
			directives.merge(_parse_directive(",".join(line)))
		elif not first.is_empty():
			header = line
	var script: Script = load(str(directives.get(KEY_CLASS, ""))) as Script if directives.has(KEY_CLASS) else null
	var out_dir: String = out_override if not out_override.is_empty() else str(directives.get(KEY_OUT, ""))
	if script == null:
		errors.append("%s: needs a directive line '# class=res://path/to/resource.gd out=res://folder/'" % csv_path)
		return result
	if out_dir.is_empty():
		errors.append("%s: no out= folder" % csv_path)
		return result
	var props: Dictionary = _properties(script)
	for column: String in header:
		if not props.has(column.strip_edges()):
			errors.append("%s: column '%s' is not an exported property of %s" % [csv_path, column, script.resource_path])
	if not header.has(ID_COLUMN):
		errors.append("%s: missing column '%s'" % [csv_path, ID_COLUMN])
	if not errors.is_empty():
		return result
	var ids: Dictionary = {}
	while not file.eof_reached():
		var cells: PackedStringArray = file.get_csv_line()
		line_no += 1
		if cells.is_empty() or (cells.size() == 1 and cells[0].strip_edges().is_empty()):
			continue
		if cells[0].strip_edges().begins_with(DIRECTIVE_PREFIX):
			continue
		var where: String = "%s:%d" % [csv_path.get_file(), line_no]
		var res: Resource = _row_to_resource(script, header, cells, props, where)
		if res == null:
			continue
		var row_id: String = str(res.get(ID_COLUMN))
		if row_id.is_empty() or not row_id.is_valid_identifier():
			errors.append("%s: invalid id '%s'" % [where, row_id])
			continue
		if ids.has(row_id):
			errors.append("%s: duplicate id '%s'" % [where, row_id])
			continue
		ids[row_id] = true
		result.append(res)
		if not check_only:
			_save(res, out_dir.path_join(row_id + ".tres"), header)
	_report_extra_files(out_dir, ids, check_only, prune)
	return result


## Converts one cell for a property (from Object.get_property_list()).
## Returns {ok: bool, value: Variant, error: String}.
static func convert_cell(text: String, prop: Dictionary, current: Variant = null) -> Dictionary:
	var value: String = text.strip_edges()
	var type: int = prop["type"]
	match type:
		TYPE_BOOL:
			if TRUE_WORDS.has(value.to_lower()):
				return _ok(true)
			if FALSE_WORDS.has(value.to_lower()):
				return _ok(false)
			return _bad("'%s' is not a bool" % value)
		TYPE_INT:
			if int(prop["hint"]) == PROPERTY_HINT_ENUM:
				return _enum_value(value, str(prop["hint_string"]))
			return _ok(value.to_int()) if value.is_valid_int() else _bad("'%s' is not an int" % value)
		TYPE_FLOAT:
			return _ok(value.to_float()) if value.is_valid_float() else _bad("'%s' is not a number" % value)
		TYPE_STRING:
			return _ok(value)
		TYPE_STRING_NAME:
			return _ok(StringName(value))
		TYPE_COLOR:
			return _ok(Color.html(value)) if Color.html_is_valid(value) else _bad("'%s' is not a colour" % value)
		TYPE_VECTOR2, TYPE_VECTOR3:
			var parts: PackedStringArray = value.split(LIST_SEPARATOR)
			var size: int = 2 if type == TYPE_VECTOR2 else 3
			if parts.size() != size or Array(parts).any(func(p: String) -> bool: return not p.strip_edges().is_valid_float()):
				return _bad("'%s' needs %d numbers separated by '%s'" % [value, size, LIST_SEPARATOR])
			if size == 2:
				return _ok(Vector2(parts[0].to_float(), parts[1].to_float()))
			return _ok(Vector3(parts[0].to_float(), parts[1].to_float(), parts[2].to_float()))
		TYPE_ARRAY:
			return _array_value(value, str(prop["hint_string"]), current)
		TYPE_PACKED_STRING_ARRAY:
			return _ok(PackedStringArray(Array(value.split(LIST_SEPARATOR, false)).map(func(s: String) -> String: return s.strip_edges())))
		TYPE_OBJECT:
			if not value.begins_with("res://") or not ResourceLoader.exists(value):
				return _bad("'%s' is not an existing res:// resource" % value)
			return _ok(load(value))
	return _bad("type %s is not supported in CSV" % type_string(type))


func _row_to_resource(script: Script, header: PackedStringArray, cells: PackedStringArray, props: Dictionary,
		where: String) -> Resource:
	var res: Resource = script.new() as Resource
	var ok: bool = true
	for i: int in header.size():
		var column: String = header[i].strip_edges()
		var cell: String = cells[i] if i < cells.size() else ""
		if cell.strip_edges().is_empty():
			continue
		var converted: Dictionary = convert_cell(cell, props[column], res.get(column))
		if not converted["ok"]:
			errors.append("%s column '%s': %s" % [where, column, converted["error"]])
			ok = false
			continue
		res.set(column, converted["value"])
	return res if ok else null


func _save(res: Resource, path: String, header: PackedStringArray) -> void:
	if ResourceLoader.exists(path):
		var old: Resource = ResourceLoader.load(path, "", ResourceLoader.CACHE_MODE_IGNORE)
		if old != null and old.get_script() == res.get_script() and _same(old, res, header):
			unchanged += 1
			return
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var err: Error = ResourceSaver.save(res, path)
	if err != OK:
		errors.append("%s: cannot save (%s)" % [path, error_string(err)])
		return
	written += 1


static func _same(a: Resource, b: Resource, header: PackedStringArray) -> bool:
	for column: String in header:
		var name: String = column.strip_edges()
		if a.get(name) != b.get(name):
			return false
	return true


func _report_extra_files(out_dir: String, ids: Dictionary, check_only: bool, prune: bool) -> void:
	if not DirAccess.dir_exists_absolute(out_dir):
		return
	for file_name: String in DirAccess.get_files_at(out_dir):
		if not file_name.ends_with(".tres") or ids.has(file_name.get_basename()):
			continue
		if prune and not check_only:
			DirAccess.remove_absolute(out_dir.path_join(file_name))
			pruned += 1
		else:
			warnings.append("%s is not in the table (kept; --prune deletes it)" % out_dir.path_join(file_name))


## Exported script properties: name -> property dictionary.
static func _properties(script: Script) -> Dictionary:
	var out: Dictionary = {}
	for prop: Dictionary in script.get_script_property_list():
		if int(prop["usage"]) & PROPERTY_USAGE_STORAGE and int(prop["usage"]) & PROPERTY_USAGE_SCRIPT_VARIABLE:
			out[str(prop["name"])] = prop
	return out


static func _parse_directive(line: String) -> Dictionary:
	var out: Dictionary = {}
	for token: String in line.trim_prefix(DIRECTIVE_PREFIX).replace(",", " ").split(" ", false):
		if token.contains("="):
			out[token.get_slice("=", 0)] = token.get_slice("=", 1)
	return out


static func _enum_value(value: String, hint_string: String) -> Dictionary:
	var wanted: String = _norm(value)
	var index: int = 0
	for entry: String in hint_string.split(","):
		var label: String = entry.get_slice(":", 0)
		var number: int = entry.get_slice(":", 1).to_int() if entry.contains(":") else index
		if _norm(label) == wanted:
			return _ok(number)
		index += 1
	return _bad("'%s' is not one of %s" % [value, hint_string])


static func _array_value(value: String, hint_string: String, current: Variant) -> Dictionary:
	var element: String = hint_string.get_slice(":", hint_string.get_slice_count(":") - 1)
	var arr: Array = (current as Array).duplicate() if current is Array else []
	arr.clear()
	for raw: String in value.split(LIST_SEPARATOR, false):
		var item: String = raw.strip_edges()
		match element:
			"int":
				if not item.is_valid_int():
					return _bad("'%s' is not an int" % item)
				arr.append(item.to_int())
			"float":
				if not item.is_valid_float():
					return _bad("'%s' is not a number" % item)
				arr.append(item.to_float())
			"StringName":
				arr.append(StringName(item))
			_:
				arr.append(item)
	return _ok(arr)


static func _norm(text: String) -> String:
	return text.strip_edges().to_lower().replace("_", "").replace(" ", "")


static func _ok(value: Variant) -> Dictionary:
	return {"ok": true, "value": value, "error": ""}


static func _bad(message: String) -> Dictionary:
	return {"ok": false, "value": null, "error": message}
