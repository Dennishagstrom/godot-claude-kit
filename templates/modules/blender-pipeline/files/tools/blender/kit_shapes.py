"""Detail shapes on top of kit_base: what makes a scripted model look made, not assembled.

    import kit_base as kit, kit_shapes as shapes
    rng = shapes.jitter(7)                                   # fixed seed: the same model every build
    parts += shapes.plank_panel("side", 1.0, 0.8, 0.05, loc=(0, -0.5, 0.4), rng=rng)
    parts += shapes.band("band", (1.02, 1.02), z=0.2)
    post = shapes.lathe("post", [(0.08, 0), (0.06, 0.9), (0.09, 1.0), (0, 1.05)])

Silhouette first (lathe, extrude), then edges (bevels, planks, bands, rivets), then
colour (kit.paint shade, one glow accent). Everything follows kit_base's conventions:
metres, Z up, front -Y, painted with PALETTE colours.
"""

import math
import random

import bmesh
import bpy
from mathutils import Vector

import kit_base as kit

PLANK_GAP = 0.012
PLANK_BEVEL = 0.008
PLANK_WOBBLE = 0.012  # metres of seeded height/offset wobble per plank
PLANK_TILT_DEG = 0.8
BAND_THICKNESS = 0.03
BAND_HEIGHT = 0.07
RIVET_RADIUS = 0.022


def jitter(seed):
    """A seeded RNG so every rebuild gives the same 'hand-made' wobble."""
    return random.Random(seed)


def wobble(rng, amount):
    return rng.uniform(-amount, amount) if rng else 0.0


# --- Silhouettes -------------------------------------------------------------

def lathe(name, profile, verts=16, loc=(0, 0, 0), colour="wood", metal=False, shade=kit.SHADE):
    """Spins `profile` [(radius, z), ...] (bottom to top) around Z: posts, bottles, bowls, lamp shades.

    A radius of 0 at either end closes it to a point; otherwise the ends get a flat cap."""
    ox, oy, oz = loc
    coords, rings = [], []
    for r, z in profile:
        if r <= 0.0:
            rings.append([len(coords)])
            coords.append((ox, oy, oz + z))
            continue
        ring = []
        for i in range(verts):
            a = 2 * math.pi * i / verts
            ring.append(len(coords))
            coords.append((ox + r * math.cos(a), oy + r * math.sin(a), oz + z))
        rings.append(ring)
    faces = []
    for low, high in zip(rings, rings[1:]):
        if len(low) == 1 and len(high) == 1:
            continue
        for i in range(verts):
            j = (i + 1) % verts
            if len(low) == 1:
                faces.append((low[0], high[j], high[i]))
            elif len(high) == 1:
                faces.append((low[i], low[j], high[0]))
            else:
                faces.append((low[i], low[j], high[j], high[i]))
    if len(rings[0]) > 1:
        faces.append(tuple(reversed(rings[0])))
    if len(rings[-1]) > 1:
        faces.append(tuple(rings[-1]))
    return _shaped(name, coords, faces, colour, metal, shade)


def extrude(name, outline, depth, loc=(0, 0, 0), colour="wood", metal=False, bevel=0.0, shade=kit.SHADE):
    """A flat shape facing the front: `outline` [(x, z), ...] extruded `depth` along Y, centred on loc.

    Signs, blades, brackets, gables, leaves: anything with a drawn silhouette."""
    ox, oy, oz = loc
    n = len(outline)
    coords = [(ox + x, oy - depth / 2, oz + z) for x, z in outline] + \
             [(ox + x, oy + depth / 2, oz + z) for x, z in outline]
    faces = [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))]
    faces += [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    obj = _shaped(name, coords, faces, colour, metal, shade)
    if bevel > 0.0:
        _bevel(obj, bevel)
        kit.paint(obj, colour, shade, metal)
    return obj


# --- Edges and trim ----------------------------------------------------------

def plank_panel(name, width, height, thickness, loc=(0, 0, 0), planks=4, axis="z", rng=None, colour="wood",
                gap=PLANK_GAP):
    """A panel of boards facing -Y, centred on loc. axis "z" = upright boards, "x" = boards lying across.

    Each board is bevelled and, with an rng, a little uneven, so the panel reads as hand-made.
    Returns the parts (join them with the rest)."""
    ox, oy, oz = loc
    parts = []
    span = width if axis == "z" else height
    board = (span - gap * (planks - 1)) / planks
    for i in range(planks):
        c = -span / 2 + board / 2 + i * (board + gap)
        dz = -abs(wobble(rng, PLANK_WOBBLE))  # only ever shorter: boards never poke through a corner
        tilt = wobble(rng, PLANK_TILT_DEG)
        if axis == "z":
            size, at, rot = (board, thickness, height + dz), (ox + c, oy, oz + dz / 2), (0, tilt, 0)
        else:
            size, at, rot = (width + dz, thickness, board), (ox + dz / 2, oy, oz + c), (0, tilt, 0)
        parts.append(kit.box("%s_%d" % (name, i), size, loc=at, rot=rot, colour=colour, bevel=PLANK_BEVEL))
    return parts


def band(name, footprint, z, thickness=BAND_THICKNESS, height=BAND_HEIGHT, colour="iron", rivets_per_side=3,
         centre=(0, 0)):
    """A metal band around a box footprint (x, y) at height z, with rivets on the front and back."""
    fx, fy = footprint
    cx, cy = centre
    t = thickness
    parts = [kit.box(name + "_front", (fx + 2 * t, t, height), loc=(cx, cy - fy / 2 - t / 2, z), colour=colour,
                     metal=True),
             kit.box(name + "_back", (fx + 2 * t, t, height), loc=(cx, cy + fy / 2 + t / 2, z), colour=colour,
                     metal=True),
             kit.box(name + "_left", (t, fy, height), loc=(cx + fx / 2 + t / 2, cy, z), colour=colour, metal=True),
             kit.box(name + "_right", (t, fy, height), loc=(cx - fx / 2 - t / 2, cy, z), colour=colour, metal=True)]
    if rivets_per_side > 0:
        xs = [cx - fx / 2 + fx * (i + 0.5) / rivets_per_side for i in range(rivets_per_side)]
        parts += rivets(name + "_rivet", [(x, cy - fy / 2 - t, z) for x in xs], facing="-y", colour=colour)
        parts += rivets(name + "_rivet_back", [(x, cy + fy / 2 + t, z) for x in xs], facing="y", colour=colour)
    return parts


def rivets(name, points, radius=RIVET_RADIUS, facing="-y", colour="iron"):
    """Small domes at `points`, flattened against a surface that faces `facing` (-y, y, x, -x, z)."""
    flat = {"-y": (1, 0.45, 1), "y": (1, 0.45, 1), "x": (0.45, 1, 1), "-x": (0.45, 1, 1), "z": (1, 1, 0.45)}[facing]
    return [kit.sphere("%s_%d" % (name, i), radius, loc=p, scale=flat, subdiv=1, colour=colour, metal=True)
            for i, p in enumerate(points)]


# --- Natural shapes ----------------------------------------------------------

def rock(name, radius, loc=(0, 0, 0), seed=0, roughness=0.25, squash=0.7, subdiv=1, colour="stone"):
    """A faceted rock: an icosphere with seeded noise, flattened by `squash`, sitting on loc's z."""
    rng = jitter(seed)
    obj = kit.sphere(name, radius, loc=(0, 0, 0), subdiv=subdiv, colour=colour)
    for v in obj.data.vertices:
        v.co *= 1.0 + rng.uniform(-roughness, roughness)
        v.co.z *= squash
    lowest = min(v.co.z for v in obj.data.vertices)
    for v in obj.data.vertices:
        v.co += Vector(loc) - Vector((0, 0, lowest))
    _faceted(obj)
    return kit.paint(obj, colour)


def crystal(name, radius, height, loc=(0, 0, 0), sides=6, tip=0.3, lean=(0, 0), glow_hex=None, strength=2.5,
            colour="blue"):
    """A pointed prism standing on loc, leaning `lean` degrees (x, y). glow_hex makes it emissive."""
    obj = lathe(name, [(radius * 0.75, 0.0), (radius, height * (1 - tip)), (0.0, height)], verts=sides,
                colour=colour)
    kit.place(obj, loc, (lean[0], lean[1], 0))
    _faceted(obj)
    return kit.glow(obj, glow_hex, strength) if glow_hex else obj


def rounded(obj, levels=1):
    """Softens obj with subdivision (sacks, cushions, creatures). Colours are carried over."""
    mod = obj.modifiers.new("rounded", "SUBSURF")
    mod.levels = levels
    mod.render_levels = levels
    _select(obj)
    bpy.ops.object.modifier_apply(modifier=mod.name)
    return obj


def array(obj, count, offset, name=None):
    """obj plus count - 1 copies, each moved by `offset`, joined into one object."""
    copies = [obj]
    for i in range(1, count):
        c = obj.copy()
        c.data = obj.data.copy()
        bpy.context.collection.objects.link(c)
        for v in c.data.vertices:
            v.co += Vector(offset) * i
        copies.append(c)
    return kit.join(name or obj.name, copies)


# --- Private -----------------------------------------------------------------

def _shaped(name, coords, faces, colour, metal, shade):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(coords, [], faces)
    mesh.validate()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return kit.paint(obj, colour, shade, metal)


def _bevel(obj, width):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=width, segments=1, affect="EDGES", clamp_overlap=True)
    bm.to_mesh(obj.data)
    bm.free()


def _faceted(obj):
    """Every edge sharp: kit_base's smoothing keeps the facets flat."""
    for e in obj.data.edges:
        e.use_edge_sharp = True


def _select(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
