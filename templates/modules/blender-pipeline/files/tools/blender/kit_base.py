"""Shared helpers for building low-poly models in headless Blender.

Every script in tools/blender/models/ imports this module, builds its parts
with the primitives below and calls `run(build)`. Parts use a small shared
palette (one material per colour, shared by name), so models match each
other and Godot can batch them. Change PALETTE to restyle every model.

Conventions (Blender side):
    - Units are metres, Z is up; the model stands on z = 0, centred on x/y = 0
      (its pivot is at the bottom centre, see `pivot_to_floor`).
    - The front faces Blender -Y; the glTF exporter turns that into +Z in Godot.
    - Name parts that visuals may need, but game logic never depends on mesh names.

Run through tools/blender/build.sh, never with the Blender UI.
"""

import math
import os
import sys

import bpy
from mathutils import Vector

# name -> sRGB hex. Keep it small: a few colours used everywhere look intentional.
PALETTE = {
    "wood": "#9C6B3F", "wood_dark": "#6B4428", "stone": "#8A8A8F", "stone_dark": "#5A5A60",
    "metal": "#B8BEC6", "iron": "#4A4E55", "gold": "#E2B541", "red": "#C2463A",
    "green": "#5E9E4B", "blue": "#4A7FC1", "cream": "#EDE3CC", "black": "#1E1E22",
}
ROUGHNESS = 0.9
AUTO_SMOOTH_DEG = 35.0

PREVIEW_SIZE = int(os.environ.get("KIT_PREVIEW_SIZE", "512"))
PREVIEW_YAW_DEG = -35.0
PREVIEW_PITCH_DEG = 25.0
PREVIEW_LENS_MM = 50.0
PREVIEW_PADDING = 1.25
PREVIEW_BACKGROUND = (0.09, 0.08, 0.1)
PREVIEW_SUN_ENERGY = 3.0
PREVIEW_SUN_ROTATION_DEG = (50, 0, -30)
PREVIEW_WORLD_STRENGTH = 1.5
# Render engines to try for previews (names differ between Blender versions).
PREVIEW_ENGINES = ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "BLENDER_WORKBENCH")


# --- Scene / materials -------------------------------------------------------

def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def material(name):
    """The shared material for palette colour `name`."""
    mat = bpy.data.materials.get(name)
    if mat:
        return mat
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*_hex_to_linear(PALETTE[name]), 1.0)
    bsdf.inputs["Roughness"].default_value = ROUGHNESS
    return mat


def paint(obj, colour):
    obj.data.materials.clear()
    obj.data.materials.append(material(colour))
    return obj


# --- Primitives (transforms applied, painted) --------------------------------

def box(name, size, loc=(0, 0, 0), rot=(0, 0, 0), colour="wood", bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc, rotation=_rad(rot))
    obj = bpy.context.active_object
    obj.scale = size
    return _finish(obj, name, colour, bevel)


def cylinder(name, radius, depth, loc=(0, 0, 0), rot=(0, 0, 0), verts=12, colour="wood", radius_top=None):
    """A cylinder along local Z; `radius_top` makes a cone."""
    bpy.ops.mesh.primitive_cone_add(vertices=verts, radius1=radius,
                                    radius2=radius if radius_top is None else radius_top,
                                    depth=depth, location=loc, rotation=_rad(rot))
    return _finish(bpy.context.active_object, name, colour)


def sphere(name, radius, loc=(0, 0, 0), scale=(1, 1, 1), subdiv=1, colour="stone"):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=subdiv, radius=radius, location=loc)
    obj = bpy.context.active_object
    obj.scale = scale
    return _finish(obj, name, colour)


def torus(name, major, minor, loc=(0, 0, 0), rot=(0, 0, 0), colour="iron", segments=(12, 6)):
    bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor, major_segments=segments[0],
                                     minor_segments=segments[1], location=loc, rotation=_rad(rot))
    return _finish(bpy.context.active_object, name, colour)


def join(name, parts):
    """Merges parts into one object (one mesh, materials kept per face)."""
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


# --- Run / export / preview --------------------------------------------------

def run(build):
    """Entry point for model scripts. Args after "--": --out <file.glb> [--preview <file.png>]."""
    args = _parse_args()
    reset()
    roots = build()
    for obj in bpy.data.objects:
        if obj.type == "MESH":
            _smooth(obj)
    _report()
    export_glb(args["out"], roots)
    if args.get("preview"):
        render_preview(args["preview"])


def export_glb(path, roots):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    for root in roots:
        root.select_set(True)
        for child in root.children_recursive:
            child.select_set(True)
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_apply=True,
                              export_yup=True)
    print("EXPORTED", path)


def render_preview(path):
    """Renders a 3/4 view to a PNG file. Background mode: never opens a window."""
    scene = bpy.context.scene
    lo, hi = _bounds([o for o in bpy.data.objects if o.type == "MESH"])
    centre = (lo + hi) / 2
    radius = max((hi - lo).length / 2, 0.01) * PREVIEW_PADDING
    cam_data = bpy.data.cameras.new("preview_cam")
    cam_data.lens = PREVIEW_LENS_MM
    cam = bpy.data.objects.new("preview_cam", cam_data)
    scene.collection.objects.link(cam)
    fov = 2 * math.atan(cam_data.sensor_width / (2 * cam_data.lens))
    yaw, pitch = math.radians(PREVIEW_YAW_DEG), math.radians(PREVIEW_PITCH_DEG)
    offset = Vector((math.sin(yaw) * math.cos(pitch), -math.cos(yaw) * math.cos(pitch), math.sin(pitch)))
    cam.location = centre + offset * (radius / math.sin(fov / 2))
    cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam
    sun_data = bpy.data.lights.new("preview_sun", "SUN")
    sun_data.energy = PREVIEW_SUN_ENERGY
    sun = bpy.data.objects.new("preview_sun", sun_data)
    sun.rotation_euler = _rad(PREVIEW_SUN_ROTATION_DEG)
    scene.collection.objects.link(sun)
    world = bpy.data.worlds.new("preview_world")
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
    scene.render.resolution_x = PREVIEW_SIZE
    scene.render.resolution_y = PREVIEW_SIZE
    scene.view_settings.view_transform = "Standard"
    scene.render.filepath = os.path.abspath(path)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    bpy.ops.render.render(write_still=True)
    print("PREVIEW", path)


# --- Private -----------------------------------------------------------------

def _finish(obj, name, colour, bevel=0.0):
    obj.name = name
    obj.data.name = name
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    if bevel > 0.0:
        mod = obj.modifiers.new("bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 1
        bpy.ops.object.modifier_apply(modifier=mod.name)
    # Bake the location too, so every part's origin is the model origin.
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
    return paint(obj, colour)


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


def _report():
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    lo, hi = _bounds(meshes)
    tris = sum(len(p.vertices) - 2 for o in meshes for p in o.data.polygons)
    print("PARTS", ", ".join(o.name for o in meshes))
    print("BOUNDS size=(%.3f, %.3f, %.3f) m (Blender X, Y, Z-up)" % tuple(hi - lo))
    print("TRIS", tris)


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


def _hex_to_linear(hex_colour):
    rgb = [int(hex_colour.lstrip("#")[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb)


def _rad(deg):
    return tuple(math.radians(d) for d in deg)
