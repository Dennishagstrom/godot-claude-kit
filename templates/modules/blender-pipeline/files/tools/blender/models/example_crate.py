"""Example model: a wooden crate of planks with metal bands and rivets (about 1 m).
Copy this file to start a new prop.

    tools/blender/build.sh example_crate --preview

Silhouette (a bevelled core), then edges (planks with a seeded wobble, bands, rivets),
then colour (palette shading). Constants on top, no magic numbers in the parts.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import kit_base as kit  # noqa: E402
import kit_shapes as shapes  # noqa: E402

SEED = 7
SIZE = 1.0
CORE_INSET = 0.04
CORE_BEVEL = 0.02
PLANK_THICKNESS = 0.05
PLANKS = 4
LID_PLANKS = 5
BAND_HEIGHTS = (0.16, 0.84)


def build():
    rng = shapes.jitter(SEED)
    half = SIZE / 2
    parts = [kit.box("core", (SIZE - CORE_INSET, SIZE - CORE_INSET, SIZE - CORE_INSET), loc=(0, 0, half),
                     colour="wood_dark", bevel=CORE_BEVEL)]
    face = half - PLANK_THICKNESS / 2
    # Front and back: upright boards. Sides: boards lying across. Lid: boards along X.
    for y, tag in ((-face, "front"), (face, "back")):
        parts += shapes.plank_panel(tag, SIZE, SIZE, PLANK_THICKNESS, loc=(0, y, half), planks=PLANKS, rng=rng)
    for x, tag in ((face, "left"), (-face, "right")):
        side = shapes.plank_panel(tag, SIZE - 2 * PLANK_THICKNESS, SIZE, PLANK_THICKNESS, loc=(0, 0, half),
                                  planks=PLANKS, axis="x", rng=rng)
        parts += [kit.place(p, (x, 0, 0), (0, 0, 90)) for p in side]  # turned to face +-X
    lid = shapes.plank_panel("lid", SIZE, SIZE, PLANK_THICKNESS, loc=(0, 0, 0), planks=LID_PLANKS, rng=rng,
                             colour="wood_light")
    parts += [kit.place(p, (0, 0, SIZE - PLANK_THICKNESS / 2), (90, 0, 0)) for p in lid]  # laid flat on top
    for i, z in enumerate(BAND_HEIGHTS):
        parts += shapes.band("band%d" % i, (SIZE, SIZE), z * SIZE)
    crate = kit.join("crate", parts)
    return [kit.pivot_to_floor(crate)]


kit.run(build)
