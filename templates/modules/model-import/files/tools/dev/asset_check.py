#!/usr/bin/env python3
"""Model check: every .glb/.gltf in the project, whatever made it (Blender scripts, Blender
by hand or over MCP, asset packs, generators), against the rules in tools/dev/asset_rules.json.
Pure Python, no Blender or Godot, about a second.

    python3 -I tools/dev/asset_check.py                    # whole project; exit 1 on findings
    python3 -I tools/dev/asset_check.py --report           # also a table: tris, size, materials, textures
    python3 -I tools/dev/asset_check.py a.glb --as assets/models/   # files anywhere, judged by that folder's rules
    python3 -I tools/dev/asset_check.py --json a.glb       # stats + node tree as JSON (tests, tools)
    python3 -I tools/dev/asset_check.py --root DIR         # another project (godot-analyse does this)

Rules (limits per folder in asset_rules.json; the longest matching folder wins, "files" overrides one file):
  tris              more triangles than max_tris (collision-only nodes not counted)
  size              largest side outside min_size_m..max_size_m: usually centimetres or
                    inches exported as metres (100x / 39x too big)
  pivot             "floor": the model does not stand on its origin (lowest point y = 0, origin
                    inside the footprint); "top": hangs from it (ceiling props); "center": the
                    origin is outside the model (projectiles, pickups); "any": not checked
  root-transform    a root node carries rotation or scale: an exporter's axis/unit fix-up that
                    Godot then applies to everything under it. Apply transforms before export.
  materials         more materials than max_materials (each one is a draw call per mesh)
  texture-size      an image larger than max_texture pixels on a side
  duplicate-texture the same image embedded in several models: Godot extracts one copy per
                    model (memory x N). Share one material/texture (docs/modules/model-import.md).
                    Not counted when the model's .import discards embedded images.
  name-suffix       a node name ends in a Godot import suffix (-col, _wheel, -rigid, -noimp ...):
                    Godot turns it into a physics body, wheel or nothing. Rename it, or set
                    "allow_suffixes": true for a folder that uses them on purpose (also off
                    when the model's .import has node type suffixes turned off).
  unreadable        not a valid glTF file
.blend files are listed as a note (not a failure): Godot imports them through Blender, so
every machine that imports the project needs Blender, CI too.
"""
import hashlib
import json
import math
import os
import re
import struct
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RULES_FILE = "tools/dev/asset_rules.json"
SKIP_DIRS = {".godot", ".git", ".claude", "build", "node_modules"}
DEFAULT_RULE = {"max_tris": 10000, "max_materials": 4, "max_texture": 2048, "min_size_m": 0.02,
                "max_size_m": 100.0, "pivot": "floor", "allow_suffixes": False}
# Godot's node type suffixes (resource_importer_scene.cpp): matched after "-", "_" or "$",
# ignoring case and Blender's ".001" duplicate numbers.
SUFFIXES = ("noimp", "col", "convcol", "colonly", "convcolonly", "navmesh", "occ", "occonly", "rigid", "vehicle",
            "wheel")
NOT_VISIBLE = ("colonly", "convcolonly", "navmesh", "occonly", "noimp")
SUFFIX = re.compile(r"[-_$](%s)$" % "|".join(SUFFIXES), re.I)
PIVOT_TOLERANCE = 0.1  # of the largest side: rocks and posts often sink a little into the floor
IDENTITY_EPS = 1e-4
GLB_MAGIC = b"glTF"


# --- glTF reading ----------------------------------------------------------------

def load_gltf(path):
    """(json, binary chunk or None) for a .glb or .gltf file. Raises ValueError."""
    with open(path, "rb") as f:
        data = f.read()
    if path.lower().endswith(".gltf"):
        return json.loads(data.decode("utf-8")), None
    if data[:4] != GLB_MAGIC or len(data) < 20:
        raise ValueError("not a glb file")
    length, kind = struct.unpack("<I4s", data[12:20])
    if kind != b"JSON":
        raise ValueError("first chunk is not JSON")
    doc = json.loads(data[20:20 + length].decode("utf-8"))
    rest = 20 + length
    binary = None
    if len(data) >= rest + 8:
        blen, bkind = struct.unpack("<I4s", data[rest:rest + 8])
        if bkind == b"BIN\x00":
            binary = data[rest + 8:rest + 8 + blen]
    return doc, binary


def image_bytes(doc, binary, image, base_dir):
    """(bytes, embedded) of one glTF image, or (None, False)."""
    if "bufferView" in image and binary is not None:
        view = doc["bufferViews"][image["bufferView"]]
        start = view.get("byteOffset", 0)
        return binary[start:start + view["byteLength"]], True
    uri = image.get("uri", "")
    if uri.startswith("data:"):
        import base64
        return base64.b64decode(uri.split(",", 1)[1]), True
    path = os.path.join(base_dir, uri)
    if uri and os.path.isfile(path):
        with open(path, "rb") as f:
            return f.read(), False
    return None, False


def image_size(data):
    """(width, height) of PNG/JPEG bytes, or None."""
    if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 24:
        return struct.unpack(">II", data[16:24])
    if data[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xC0, 0xC1, 0xC2):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return w, h
            i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
    return None


# --- Matrices (row-major 4x4 lists) ---------------------------------------------

def mat_mul(a, b):
    return [[sum(a[r][k] * b[k][c] for k in range(4)) for c in range(4)] for r in range(4)]


def node_matrix(node):
    if "matrix" in node:
        m = node["matrix"]  # column-major
        return [[m[c * 4 + r] for c in range(4)] for r in range(4)]
    tx, ty, tz = node.get("translation", (0, 0, 0))
    x, y, z, w = node.get("rotation", (0, 0, 0, 1))
    sx, sy, sz = node.get("scale", (1, 1, 1))
    rot = [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
           [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
           [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]
    return [[rot[0][0] * sx, rot[0][1] * sy, rot[0][2] * sz, tx],
            [rot[1][0] * sx, rot[1][1] * sy, rot[1][2] * sz, ty],
            [rot[2][0] * sx, rot[2][1] * sy, rot[2][2] * sz, tz],
            [0, 0, 0, 1]]


def apply(m, p):
    return [m[r][0] * p[0] + m[r][1] * p[1] + m[r][2] * p[2] + m[r][3] for r in range(3)]


def is_identity_rs(node):
    """True when the node has no rotation and no scale (translation is fine)."""
    m = node_matrix(node)
    return all(abs(m[r][c] - (1.0 if r == c else 0.0)) < IDENTITY_EPS for r in range(3) for c in range(3))


# --- Stats ------------------------------------------------------------------------

def primitive_tris(doc, prim):
    mode = prim.get("mode", 4)
    if "indices" in prim:
        count = doc["accessors"][prim["indices"]]["count"]
    else:
        count = doc["accessors"][prim["attributes"]["POSITION"]]["count"]
    if mode == 4:
        return count // 3
    if mode in (5, 6):
        return max(count - 2, 0)
    return 0


def suffix_of(name):
    m = SUFFIX.search(re.sub(r"[.\d]+$", "", name or ""))
    return m.group(1).lower() if m else ""


def stats(path):
    """Measurements of one glTF file (see --json)."""
    doc, binary = load_gltf(path)
    nodes = doc.get("nodes", [])
    scenes = doc.get("scenes", [])
    scene = scenes[doc.get("scene", 0)] if scenes else {"nodes": [i for i in range(len(nodes))
                                                                   if not any(i in n.get("children", []) for n in nodes)]}
    lo, hi = [math.inf] * 3, [-math.inf] * 3
    tris, used_materials, tree, roots_transformed = 0, set(), [], []

    def visit(index, parent_matrix, parent_name, depth):
        nonlocal tris
        node = nodes[index]
        name = node.get("name", "node%d" % index)
        world = mat_mul(parent_matrix, node_matrix(node))
        suffix = suffix_of(name)
        tree.append({"name": name, "parent": parent_name, "depth": depth, "suffix": suffix,
                     "translation": [round(v, 4) for v in node.get("translation", (0, 0, 0))]})
        if depth == 0 and not is_identity_rs(node):
            roots_transformed.append(name)
        if "mesh" in node:
            for prim in doc["meshes"][node["mesh"]].get("primitives", []):
                if "material" in prim:
                    used_materials.add(prim["material"])
                if suffix in NOT_VISIBLE:
                    continue
                tris += primitive_tris(doc, prim)
                acc = doc["accessors"][prim["attributes"]["POSITION"]]
                if "min" in acc and "max" in acc:
                    for corner in range(8):
                        p = [acc["max"][a] if corner >> a & 1 else acc["min"][a] for a in range(3)]
                        for a, v in enumerate(apply(world, p)):
                            lo[a], hi[a] = min(lo[a], v), max(hi[a], v)
        for child in node.get("children", []):
            visit(child, world, name, depth + 1)

    identity = [[1.0 if r == c else 0.0 for c in range(4)] for r in range(4)]
    for root in scene.get("nodes", []):
        visit(root, identity, None, 0)
    images = []
    for image in doc.get("images", []):
        data, embedded = image_bytes(doc, binary, image, os.path.dirname(path))
        if data is None:
            continue
        images.append({"name": image.get("name", ""), "embedded": embedded, "size": image_size(data),
                       "hash": hashlib.sha256(data).hexdigest()[:16]})
    has_bounds = lo[0] != math.inf
    return {
        "tris": tris,
        "min": [round(v, 4) for v in lo] if has_bounds else None,
        "max": [round(v, 4) for v in hi] if has_bounds else None,
        "size": [round(hi[a] - lo[a], 4) for a in range(3)] if has_bounds else None,
        "materials": sorted(doc["materials"][i].get("name", "material%d" % i) for i in used_materials),
        "double_sided": sorted(m.get("name", "") for m in doc.get("materials", []) if m.get("doubleSided")),
        "images": images,
        "nodes": tree,
        "root_transformed": roots_transformed,
    }


# --- Rules ------------------------------------------------------------------------

def load_rules(root):
    path = os.path.join(root, RULES_FILE)
    rules = {"folders": {"": {}}, "files": {}}
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            loaded = json.load(f)
        rules["folders"].update(loaded.get("folders", {}))
        rules["files"] = loaded.get("files", {})
        rules["ignore"] = loaded.get("ignore", [])
    return rules


def rule_for(rules, rel_path, as_folder=None):
    key = as_folder if as_folder is not None else rel_path
    rule = dict(DEFAULT_RULE)
    for folder in sorted(rules["folders"], key=len):
        if key.startswith(folder):
            rule.update(rules["folders"][folder])
    rule.update(rules["files"].get(rel_path, {}))
    return rule


def check_model(rel_path, st, rule):
    out = []

    def add(name, msg):
        out.append("%s: %s: %s" % (rel_path, name, msg))

    if st["tris"] > rule["max_tris"]:
        add("tris", "%d triangles > max_tris %d (decimate, or raise the limit for this file/folder)" % (
            st["tris"], rule["max_tris"]))
    if st["size"]:
        largest = max(st["size"])
        if largest > rule["max_size_m"] or largest < rule["min_size_m"]:
            add("size", "largest side %.3f m is outside %.2f..%.0f m (units: export in metres)" % (
                largest, rule["min_size_m"], rule["max_size_m"]))
        tol = max(largest * PIVOT_TOLERANCE, 1e-3)
        lo, hi = st["min"], st["max"]
        inside = all(lo[a] - tol <= 0.0 <= hi[a] + tol for a in (0, 2))  # origin within the footprint
        bounds = "bounds x %.2f..%.2f y %.2f..%.2f z %.2f..%.2f" % (lo[0], hi[0], lo[1], hi[1], lo[2], hi[2])
        if rule["pivot"] in ("floor", "top"):
            y = lo[1] if rule["pivot"] == "floor" else hi[1]
            if abs(y) > tol or not inside:
                add("pivot", "origin is not at the %s of the model, inside its footprint (%s)" % (
                    "bottom" if rule["pivot"] == "floor" else "top", bounds))
        elif rule["pivot"] == "center" and not (inside and lo[1] - tol <= 0.0 <= hi[1] + tol):
            add("pivot", "origin is outside the model (%s)" % bounds)
    for name in st["root_transformed"]:
        add("root-transform", "root node %s has rotation/scale; apply transforms before export" % name)
    if len(st["materials"]) > rule["max_materials"]:
        add("materials", "%d materials > max_materials %d (%s)" % (len(st["materials"]), rule["max_materials"],
                                                                  ", ".join(st["materials"])))
    for image in st["images"]:
        if image["size"] and max(image["size"]) > rule["max_texture"]:
            add("texture-size", "image %s is %dx%d > max_texture %d" % (image["name"] or "?", image["size"][0],
                                                                       image["size"][1], rule["max_texture"]))
    if not rule["allow_suffixes"]:
        for node in st["nodes"]:
            if node["suffix"]:
                add("name-suffix", "node %s ends in Godot's '%s' import suffix; rename it (or allow_suffixes)" % (
                    node["name"], node["suffix"]))
    return out


def import_params(path):
    """The [params] of Godot's <file>.import next to a model ({} before the first import)."""
    try:
        with open(path + ".import", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return {}
    return dict(re.findall(r"^([\w/]+)=(.*)$", text.split("[params]", 1)[-1], re.M))


def model_files(root):
    for base, dirs, names in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
        for n in sorted(names):
            if n.lower().endswith((".glb", ".gltf", ".blend")):
                yield os.path.relpath(os.path.join(base, n), root).replace(os.sep, "/")


def check(root, paths=None, as_folder=None):
    """(findings, notes, {rel path: stats}) for the project at root (or only `paths`)."""
    rules = load_rules(root)
    rels = [os.path.relpath(os.path.abspath(p), root).replace(os.sep, "/") for p in paths] if paths else \
        list(model_files(root))
    rels = [r for r in rels if not any(r.startswith(i) for i in rules.get("ignore", []))]
    findings, notes, all_stats, by_hash = [], [], {}, {}
    for rel in rels:
        full = os.path.join(root, rel)
        if rel.lower().endswith(".blend"):
            notes.append("%s: blend-source: Godot imports .blend through Blender: every machine (and CI) that "
                         "imports the project needs Blender; exporting .glb avoids that" % rel)
            continue
        try:
            st = stats(full)
        except (ValueError, KeyError, IndexError, OSError, UnicodeDecodeError, struct.error) as e:
            findings.append("%s: unreadable: %s" % (rel, e))
            continue
        all_stats[rel] = st
        imp = import_params(full)
        rule = rule_for(rules, rel, as_folder)
        if imp.get("nodes/use_node_type_suffixes") == "false":
            rule["allow_suffixes"] = True  # Godot keeps every node a plain node
        findings += check_model(rel, st, rule)
        if imp.get("gltf/embedded_image_handling") != "0":  # 0 = discarded on import (shared material instead)
            for image in st["images"]:
                if image["embedded"]:
                    by_hash.setdefault(image["hash"], []).append(rel)
    for digest, users in sorted(by_hash.items()):
        users = sorted(set(users))
        if len(users) > 1:
            findings.append("%s: duplicate-texture: the same image is embedded in %d models (%s%s); share one "
                            "material/texture" % (users[0], len(users), ", ".join(users[1:4]),
                                                  " ..." if len(users) > 4 else ""))
    return findings, notes, all_stats


def report(all_stats):
    lines = ["| model | tris | size x*y*z m | materials | images |", "|---|---|---|---|---|"]
    for rel, st in sorted(all_stats.items()):
        size = "*".join("%.2f" % v for v in st["size"]) if st["size"] else "-"
        imgs = ", ".join("%s%s" % ("x".join(map(str, i["size"])) if i["size"] else "?", "" if i["embedded"] else " ext")
                         for i in st["images"]) or "-"
        lines.append("| %s | %d | %s | %s | %s |" % (rel, st["tris"], size, ", ".join(st["materials"]) or "-", imgs))
    return lines


def main():
    args = sys.argv[1:]
    root, as_folder = ROOT, None
    for flag in ("--root", "--as"):
        if flag in args:
            i = args.index(flag)
            value = args[i + 1]
            del args[i:i + 2]
            if flag == "--root":
                root = os.path.abspath(value)
            else:
                as_folder = value
    want_report, want_json = "--report" in args, "--json" in args
    paths = [a for a in args if not a.startswith("--")]
    findings, notes, all_stats = check(root, paths, as_folder)
    if want_json:
        print(json.dumps({"findings": findings, "notes": notes, "models": all_stats}, indent=1))
        return 1 if findings else 0
    if want_report and all_stats:
        print("\n".join(report(all_stats)))
    for line in notes:
        print("NOTE " + line)
    for line in findings:
        print(line)
    if findings:
        print("RESULT FAIL assets: %d finding(s) in %d model(s); fix them or set limits in %s" % (
            len(findings), len(all_stats), RULES_FILE))
        return 1
    print("RESULT PASS assets (%d models)" % len(all_stats))
    return 0


if __name__ == "__main__":
    sys.exit(main())
