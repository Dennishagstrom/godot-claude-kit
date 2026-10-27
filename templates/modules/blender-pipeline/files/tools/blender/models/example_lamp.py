"""Example jointed model: a lamp on an arm with two joints and a glowing bulb.
Copy this file for anything that moves in parts (doors, turrets, creatures, machines).

    tools/blender/build.sh example_lamp --preview

Each moving part has its origin at the joint it turns around (kit.origin_to) and hangs
under its parent (kit.attach), so in Godot `lamp_arm_lower.rotation.x` swings the whole
arm about the base joint. Part names are a contract with the model's *_visual.gd script
only; gameplay never reads them.

    lamp_base > lamp_arm_lower (BASE_JOINT) > lamp_arm_upper (ELBOW) > lamp_head (WRIST) > lamp_bulb
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import kit_base as kit  # noqa: E402
import kit_shapes as shapes  # noqa: E402
from mathutils import Vector  # noqa: E402

BASE_PROFILE = [(0.16, 0.0), (0.16, 0.025), (0.12, 0.05), (0.04, 0.07), (0.035, 0.1), (0.0, 0.1)]
BASE_JOINT = (0.0, 0.0, 0.1)
ELBOW = (0.0, -0.05, 0.42)
WRIST = (0.0, 0.18, 0.66)
ARM_RADIUS = 0.014
JOINT_RADIUS = 0.024
SHADE_PROFILE = [(0.0, 0.0), (0.04, 0.0), (0.05, -0.03), (0.09, -0.11), (0.1, -0.13)]
BULB_RADIUS = 0.032
BULB_DROP = 0.09
BULB_GLOW = "#FFD089"


def arm(name, start, end):
    """A rod from start to end with a joint ball at start; origin at start."""
    length = ((end[0] - start[0]) ** 2 + (end[1] - start[1]) ** 2 + (end[2] - start[2]) ** 2) ** 0.5
    rod = kit.cylinder(name, ARM_RADIUS, length, loc=(0, 0, length / 2), verts=10, colour="iron", metal=True)
    ball = kit.sphere(name + "_ball", JOINT_RADIUS, subdiv=2, colour="metal", metal=True)
    part = kit.join(name, [rod, ball])
    # Point the rod (built along +Z from the origin) from start towards end.
    rot = (Vector(end) - Vector(start)).to_track_quat("Z", "Y").to_euler()
    kit.place(part, start, tuple(math.degrees(a) for a in rot))
    return kit.origin_to(part, start)


def build():
    base = shapes.lathe("lamp_base", BASE_PROFILE, verts=24, colour="iron", metal=True)
    lower = arm("lamp_arm_lower", BASE_JOINT, ELBOW)
    upper = arm("lamp_arm_upper", ELBOW, WRIST)
    head = shapes.lathe("lamp_head", SHADE_PROFILE, verts=20, loc=WRIST, colour="red")
    kit.origin_to(head, WRIST)
    bulb = kit.glow(kit.sphere("lamp_bulb", BULB_RADIUS, loc=(WRIST[0], WRIST[1], WRIST[2] - BULB_DROP), subdiv=2),
                    BULB_GLOW)
    kit.origin_to(bulb, (WRIST[0], WRIST[1], WRIST[2] - BULB_DROP))
    kit.attach(bulb, head)
    kit.attach(head, upper)
    kit.attach(upper, lower)
    kit.attach(lower, base)
    return [base]


kit.run(build)
