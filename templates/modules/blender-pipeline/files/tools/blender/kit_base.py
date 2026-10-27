"""Shared helpers for building models in headless Blender.

Every script in tools/blender/models/ imports this module, builds its parts with the
primitives below (and the shapes in kit_shapes.py) and calls `run(build)`.

Look: one shared palette. `paint()` gives a part a PALETTE colour as vertex colours,
lighter at its top and darker at its bottom (SHADE), which reads as soft top light
without any texture. All painted parts use ONE material ("palette", or "palette_metal"
for metal=True); Godot swaps it for assets/materials/<name>.tres on import
(tools/import/shared_materials.gd), so every model shares one material and batches.
`glow()` gives a part its own emissive material (lamps, crystals, fire).

Conventions (Blender side):
    - Units are metres, Z is up; the model stands on z = 0, centred on x/y = 0.
    - The front faces Blender -Y; the glTF exporter turns that into +Z in Godot.
    - Parts that move get their origin at the joint they turn around (`origin_to`) and
      hang under their parent (`attach`): Godot then rotates the node about the joint.
    - Name parts that visuals need (animation, swapping); game logic never depends on them.
    - No Godot import suffixes in names (-col, _wheel, -rigid ...): tools/dev/asset_check.py.

Run through tools/blender/build.sh, never with the Blender UI.
"""

import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

# name -> sRGB hex. Keep it small: a few colours used everywhere look intentional.
PALETTE = {
    "wood": "#9C6B3F", "wood_dark": "#6B4428", "wood_light": "#C49A6C", "stone": "#8A8A8F",
    "stone_dark": "#5A5A60", "metal": "#B8BEC6", "iron": "#4A4E55", "gold": "#E2B541", "red": "#C2463A",
    "green": "#5E9E4B", "blue": "#4A7FC1", "cream": "#EDE3CC", "cloth": "#B9A27E", "black": "#1E1E22",
}
# Brightness at a part's top and bottom (x the colour): soft light from above.
SHADE = (1.12, 0.72)
ROUGHNESS = 0.9
METAL_ROUGHNESS = 0.45
METAL_METALLIC = 0.6
MATERIAL = "palette"
METAL_MATERIAL = "palette_metal"
COLOR_LAYER = "Col"
AUTO_SMOOTH_DEG = 35.0

# Previews: a contact sheet of front | side / top | three-quarter views. The orthographic
# views show a grey reference figure (the player's height) beside the model for scale; the
# three-quarter view shows the model alone, large, for detail. Rendered to a file, no window.
PREVIEW_SIZE = int(os.environ.get("KIT_PREVIEW_SIZE", "512"))  # one cell
REFERENCE_HEIGHT = float(os.environ.get("KIT_REFERENCE_HEIGHT", "1.75"))
REFERENCE_GAP = 0.3
PREVIEW_PADDING = 1.15
PREVIEW_LENS_MM = 50.0
PREVIEW_YAW_DEG = -35.0
PREVIEW_PITCH_DEG = 25.0
PREVIEW_BACKGROUND = (0.09, 0.08, 0.1)
PREVIEW_SUN_ENERGY = 3.0
PREVIEW_SUN_ROTATION_DEG = (50, 0, -30)
PREVIEW_FILL_ENERGY = 1.0
PREVIEW_FILL_ROTATION_DEG = (65, 0, 150)
PREVIEW_WORLD_STRENGTH = 1.2
PREVIEW_SAMPLES = 16
# Render engines to try for previews (names differ between Blender versions).
PREVIEW_ENGINES = ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "BLENDER_WORKBENCH")
SHEET_VIEWS = ("front", "side", "top", "three_quarter")  # left to right, top to bottom


# --- Scene / materials -------------------------------------------------------

def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def material(metal=False):
    """The shared palette material: base colour from the vertex colours."""
    name = METAL_MATERIAL if metal else MATERIAL
    mat = bpy.data.materials.get(name)
    if mat:
        return mat
    mat = _new_material(name)
    nodes = mat.node_tree.nodes
    bsdf = nodes["Principled BSDF"]
    attr = nodes.new("ShaderNodeVertexColor")
    attr.layer_name = COLOR_LAYER
    mat.node_tree.links.new(attr.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = METAL_ROUGHNESS if metal else ROUGHNESS
    bsdf.inputs["Metallic"].default_value = METAL_METALLIC if metal else 0.0
    return mat


def paint(obj, colour, shade=SHADE, metal=False):
    """Colours every vertex of obj with PALETTE[colour], shade[0] x at its top to shade[1] x at its bottom.

    Pass the same value twice for a flat colour. Returns obj."""
    base = _hex_to_srgb(PALETTE[colour])
    mesh = obj.data
    attr = mesh.color_attributes.get(COLOR_LAYER) or mesh.color_attributes.new(COLOR_LAYER, "BYTE_COLOR", "CORNER")
    mesh.color_attributes.active_color = attr
    mesh.color_attributes.render_color_index = mesh.color_attributes.active_color_index
    zs = [v.co.z for v in mesh.vertices] or [0.0]
    z_min, height = min(zs), max(max(zs) - min(zs), 1e-6)
    for loop in mesh.loops:
        t = (mesh.vertices[loop.vertex_index].co.z - z_min) / height
        k = shade[1] + (shade[0] - shade[1]) * t
        attr.data[loop.index].color_srgb = (*(min(c * k, 1.0) for c in base), 1.0)
    mesh.materials.clear()
    mesh.materials.append(material(metal))
    return obj


def glow(obj, hex_colour, strength=3.0):
    """Gives obj its own emissive material (exported as glTF emissive), shared by colour + strength."""
    name = "glow_%s_%d" % (hex_colour.lstrip("#").lower(), round(strength * 10))
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = _new_material(name)
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        colour = (*_hex_to_linear(hex_colour), 1.0)
        bsdf.inputs["Base Color"].default_value = colour
        bsdf.inputs["Emission Color"].default_value = colour
        bsdf.inputs["Emission Strength"].default_value = strength
        bsdf.inputs["Roughness"].default_value = 0.6
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    return obj


# --- Primitives (transforms applied, painted) --------------------------------

def box(name, size, loc=(0, 0, 0), rot=(0, 0, 0), colour="wood", bevel=0.0, segments=1, metal=False):
    """A box of `size` (x, y, z) centred on loc. bevel = edge width in metres, segments > 1 rounds it."""
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc, rotation=_rad(rot))
    obj = bpy.context.active_object
    obj.scale = size
    return _finish(obj, name, colour, bevel, segments, metal)


def cylinder(name, radius, depth, loc=(0, 0, 0), rot=(0, 0, 0), verts=12, colour="wood", radius_top=None,
             bevel=0.0, segments=1, metal=False):
    """A cylinder along local Z; `radius_top` makes a cone."""
    bpy.ops.mesh.primitive_cone_add(vertices=verts, radius1=radius,
                                    radius2=radius if radius_top is None else radius_top,
                                    depth=depth, location=loc, rotation=_rad(rot))
    return _finish(bpy.context.active_object, name, colour, bevel, segments, metal)


def sphere(name, radius, loc=(0, 0, 0), scale=(1, 1, 1), subdiv=1, colour="stone", metal=False):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=subdiv, radius=radius, location=loc)
    obj = bpy.context.active_object
    obj.scale = scale
    return _finish(obj, name, colour, 0.0, 1, metal)


def torus(name, major, minor, loc=(0, 0, 0), rot=(0, 0, 0), colour="iron", segments=(12, 6), metal=False):
    bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor, major_segments=segments[0],
                                     minor_segments=segments[1], location=loc, rotation=_rad(rot))
    return _finish(bpy.context.active_object, name, colour, 0.0, 1, metal)


def mesh_object(name, verts, faces, colour="stone", metal=False):
    """An object from raw vertices and faces (kit_shapes builds on this)."""
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    mesh.validate()
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return paint(obj, colour, metal=metal)


# --- Editing -----------------------------------------------------------------

def join(name, parts):
    """Merges parts into one object (one mesh, colours and materials kept per face)."""
    bpy.ops.object.select_all(action="DESELECT")
    for part in parts:
        part.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    obj = bpy.context.active_object
    obj.name = name
    obj.data.name = name
    return obj


def mirror_x(obj, name=None):
    """A painted copy of obj mirrored across x = 0."""
    copy = obj.copy()
    copy.data = obj.data.copy()
    copy.name = name or obj.name + "_mirror"
    bpy.context.collection.objects.link(copy)
    for v in copy.data.vertices:
        v.co.x = -v.co.x
    copy.data.flip_normals()
    return copy


def pivot_to_floor(obj):
    """Moves the geometry so the object's origin is its bottom centre, standing on z = 0."""
    lo, hi = _bounds([obj])
    offset = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
    for v in obj.data.vertices:
        v.co -= offset
    obj.location = (0, 0, 0)
    return obj


def place(obj, loc=(0, 0, 0), rot=(0, 0, 0)):
    """Rotates obj by `rot` degrees (about its origin), moves it by `loc` and bakes both into the mesh."""
    obj.rotation_euler = _rad(rot)
    obj.location = loc
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return obj


def origin_to(obj, point):
    """Puts obj's origin at `point` (world) without moving its geometry: the joint it turns around."""
    point = Vector(point)
    shift = point - _world(obj)
    for v in obj.data.vertices:
        v.co -= shift
    obj.location += shift
    return obj


def attach(child, parent):
    """Hangs child under parent, keeping where it is (parts have no rotation/scale of their own)."""
    world = _world(child)
    child.parent = parent
    child.matrix_parent_inverse.identity()
    child.location = world - _world(parent)
    return child


# --- Run / export / preview --------------------------------------------------

def run(build):
    """Entry point for model scripts. Args after "--": --out <file.glb> [--preview <file.png>]."""
    args = _parse_args()
    reset()
    roots = build()
    bpy.context.view_layer.update()
    for obj in bpy.data.objects:
        if obj.type == "MESH":
            _smooth(obj)
    _report(roots)
    export_glb(args["out"], roots)
    if args.get("preview"):
        render_sheet(args["preview"])


def export_glb(path, roots):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    for root in roots:
        root.select_set(True)
        for child in root.children_recursive:
            child.select_set(True)
    options = dict(filepath=path, export_format="GLB", use_selection=True, export_apply=True, export_yup=True,
                   export_image_format="NONE")
    try:
        bpy.ops.export_scene.gltf(export_vertex_color="ACTIVE", **options)
    except TypeError:  # Blender < 4.2: colours are exported when present
        bpy.ops.export_scene.gltf(**options)
    print("EXPORTED", path)


def render_sheet(path):
    """Renders front, side, top and three-quarter views into one PNG (2 x 2 cells). Never opens a window."""
    import numpy as np
    scene = bpy.context.scene
    model = [o for o in bpy.data.objects if o.type == "MESH"]
    _, m_hi = _bounds(model)
    figure = _reference_figure()
    _preview_setup(scene)
    cells = []
    for view in SHEET_VIEWS:
        # Beside the model as the camera sees it: +X, or +Y in the side view (seen from +X).
        for part in figure:
            part.location = (0, m_hi.y + REFERENCE_GAP, 0) if view == "side" else (m_hi.x + REFERENCE_GAP, 0, 0)
            part.hide_render = view == "three_quarter"
        bpy.context.view_layer.update()
        lo, hi = _bounds(model if view == "three_quarter" else model + figure)
        cam = _camera(scene, view, lo, hi)
        scene.camera = cam
        scene.render.filepath = os.path.abspath(path) + ".%s.png" % view
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images.load(scene.render.filepath)
        px = np.empty(PREVIEW_SIZE * PREVIEW_SIZE * 4, dtype=np.float32)
        img.pixels.foreach_get(px)
        cells.append(px.reshape(PREVIEW_SIZE, PREVIEW_SIZE, 4))
        bpy.data.images.remove(img)
        os.remove(scene.render.filepath)
    # Blender images start at the bottom row: the top pair goes last.
    sheet = np.concatenate([np.concatenate(cells[2:4], axis=1), np.concatenate(cells[0:2], axis=1)], axis=0)
    out = bpy.data.images.new("sheet", PREVIEW_SIZE * 2, PREVIEW_SIZE * 2, alpha=True)
    out.pixels.foreach_set(sheet.ravel())
    out.filepath_raw = os.path.abspath(path)
    out.file_format = "PNG"
    out.save()
    print("PREVIEW %s (front | side / top | three-quarter; grey figure = %.2f m)" % (path, REFERENCE_HEIGHT))


# --- Private -----------------------------------------------------------------

def _new_material(name):
    mat = bpy.data.materials.new(name)
    if mat.node_tree is None:  # Blender < 5 creates materials without nodes
        mat.use_nodes = True
    mat.use_backface_culling = True  # glTF doubleSided off: Godot culls back faces
    return mat


def _world(obj):
    """obj's origin in world space, from locations alone (matrix_world lags until a scene update)."""
    loc = obj.location.copy()
    while obj.parent:
        obj = obj.parent
        loc += obj.location
    return loc


def _finish(obj, name, colour, bevel=0.0, segments=1, metal=False):
    obj.name = name
    obj.data.name = name
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    if bevel > 0.0:
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=segments, affect="EDGES",
                        profile=0.5, clamp_overlap=True)
        bm.to_mesh(obj.data)
        bm.free()
    # Bake the location too, so every part's origin is the model origin (origin_to moves it).
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
    return paint(obj, colour, metal=metal)


def _smooth(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(AUTO_SMOOTH_DEG), keep_sharp_edges=True)


def _bounds(objects):
    lo, hi = Vector((math.inf,) * 3), Vector((-math.inf,) * 3)
    for obj in objects:
        for corner in obj.bound_box:
            p = obj.matrix_world @ Vector(corner)
            lo = Vector(map(min, lo, p))
            hi = Vector(map(max, hi, p))
    return lo, hi


def _report(roots):
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    lo, hi = _bounds(meshes)
    tris = sum(len(p.vertices) - 2 for o in meshes for p in o.data.polygons)
    mats = sorted({m.name for o in meshes for m in o.data.materials if m})
    print("PARTS", ", ".join(o.name for o in meshes))
    for obj in meshes:
        if obj.parent:
            print("JOINT %s under %s at (%.3f, %.3f, %.3f)" % (obj.name, obj.parent.name,
                                                               *obj.matrix_world.translation))
    print("BOUNDS size=(%.3f, %.3f, %.3f) m (Blender X, Y, Z-up)" % tuple(hi - lo))
    print("TRIS", tris)
    print("MATERIALS", ", ".join(mats))


def _reference_figure():
    """A grey stand-in for the player, standing on z = 0 (added after the export, so never exported)."""
    mat = _new_material("preview_reference")
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.35, 0.35, 0.38, 1.0)
    h = REFERENCE_HEIGHT
    head = h * 0.07
    radius = h * 0.1
    parts = []
    for add, kw, z in ((bpy.ops.mesh.primitive_cylinder_add, {"radius": radius, "depth": h - head * 2},
                        (h - head * 2) / 2), (bpy.ops.mesh.primitive_uv_sphere_add, {"radius": head}, h - head)):
        add(location=(0, 0, 0), **kw)
        part = bpy.context.active_object
        part.name = "preview_reference"
        for v in part.data.vertices:  # geometry relative to an origin at the figure's near side
            v.co += Vector((radius, radius, z))
        part.data.materials.append(mat)
        parts.append(part)
    return parts


def _preview_setup(scene):
    sun_data = bpy.data.lights.new("preview_sun", "SUN")
    sun_data.energy = PREVIEW_SUN_ENERGY
    sun = bpy.data.objects.new("preview_sun", sun_data)
    sun.rotation_euler = _rad(PREVIEW_SUN_ROTATION_DEG)
    scene.collection.objects.link(sun)
    fill_data = bpy.data.lights.new("preview_fill", "SUN")
    fill_data.energy = PREVIEW_FILL_ENERGY
    fill = bpy.data.objects.new("preview_fill", fill_data)
    fill.rotation_euler = _rad(PREVIEW_FILL_ROTATION_DEG)
    scene.collection.objects.link(fill)
    world = bpy.data.worlds.new("preview_world")
    if world.node_tree is None:
        world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (*PREVIEW_BACKGROUND, 1.0)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = PREVIEW_WORLD_STRENGTH
    scene.world = world
    for engine in PREVIEW_ENGINES:
        try:
            scene.render.engine = engine
            break
        except TypeError:
            continue
    if scene.render.engine == "BLENDER_WORKBENCH":
        scene.display.shading.color_type = "VERTEX"
    elif hasattr(scene, "eevee"):
        scene.eevee.taa_render_samples = PREVIEW_SAMPLES
    scene.render.resolution_x = PREVIEW_SIZE
    scene.render.resolution_y = PREVIEW_SIZE
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "Standard"


def _camera(scene, view, lo, hi):
    """An orthographic camera for front/side/top, a perspective one for the three-quarter view."""
    centre = (lo + hi) / 2
    size = hi - lo
    data = bpy.data.cameras.new("preview_" + view)
    cam = bpy.data.objects.new("preview_" + view, data)
    scene.collection.objects.link(cam)
    far = size.length * 2 + 1.0
    data.clip_end = far * 4
    if view == "three_quarter":
        data.lens = PREVIEW_LENS_MM
        fov = 2 * math.atan(data.sensor_width / (2 * data.lens))
        yaw, pitch = math.radians(PREVIEW_YAW_DEG), math.radians(PREVIEW_PITCH_DEG)
        offset = Vector((math.sin(yaw) * math.cos(pitch), -math.cos(yaw) * math.cos(pitch), math.sin(pitch)))
        cam.location = centre + offset * (size.length / 2 * PREVIEW_PADDING / math.sin(fov / 2))
    else:
        data.type = "ORTHO"
        direction, extent = {"front": (Vector((0, -1, 0)), max(size.x, size.z)),
                             "side": (Vector((1, 0, 0)), max(size.y, size.z)),
                             "top": (Vector((0, 0, 1)), max(size.x, size.y))}[view]
        data.ortho_scale = max(extent, 0.01) * PREVIEW_PADDING
        cam.location = centre + direction * far
    if view == "top":
        cam.rotation_euler = (0, 0, 0)  # looks down; the model's front (-Y) at the bottom of the cell
    else:
        cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", "Y").to_euler()
    return cam


def _parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    args, i = {}, 0
    while i < len(argv):
        if argv[i] in ("--out", "--preview") and i + 1 < len(argv):
            args[argv[i][2:]] = argv[i + 1]
            i += 2
        else:
            i += 1
    if "out" not in args:
        sys.exit("kit_base.run: missing --out <file.glb>")
    return args


def _hex_to_srgb(hex_colour):
    return tuple(int(hex_colour.lstrip("#")[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def _hex_to_linear(hex_colour):
    return tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in _hex_to_srgb(hex_colour))


def _rad(deg):
    return tuple(math.radians(d) for d in deg)
