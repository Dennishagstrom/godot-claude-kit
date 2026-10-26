"""Example model: a banded wooden crate (about 1 m). Copy this file to start a new one.

    tools/blender/build.sh example_crate [--preview]
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import kit_base as kit  # noqa: E402

SIZE = 1.0
BAND_HEIGHT = 0.12
BAND_INSET = 0.02
BAND_HEIGHTS = (0.18, 0.82)
BEVEL = 0.03


def build():
    parts = [kit.box("body", (SIZE, SIZE, SIZE), loc=(0, 0, SIZE / 2), colour="wood", bevel=BEVEL)]
    for z in BAND_HEIGHTS:
        band = SIZE + BAND_INSET * 2
        parts.append(kit.box("band", (band, band, BAND_HEIGHT), loc=(0, 0, z * SIZE), colour="iron"))
    crate = kit.join("crate", parts)
    return [kit.pivot_to_floor(crate)]


kit.run(build)
