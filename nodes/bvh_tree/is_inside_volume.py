
import sys
epsilon = sys.float_info.epsilon

import bpy
from random import random
from mathutils import Vector
from ... base_types.node import AnimationNode

# this is the initial random direction we'll try for raycasts...
random_direction = Vector((random(), random(), random())).normalized()

class IsInsideVolumeBVHTreeNode(bpy.types.Node, AnimationNode):
    bl_idname = "an_IsInsideVolumeBVHTreeNode"
    bl_label = "Is Inside Volume"

    def create(self):
        self.newInput("BVHTree", "BVHTree", "bvhTree")
        self.newInput("Vector", "Vector", "vector", defaultDrawType = "PROPERTY_ONLY")
        self.newOutput("Boolean", "Is Inside", "isInside")

    def execute(self, bvhTree, vector):
        # if the number of hits is odd, the point is inside a closed mesh
        return (self.countHits(bvhTree,vector,random_direction) % 2) == 1

    # NOTE: this is the best we can do with the API blender gives us for
    #       raycasts. Notably, after finding a hit, the only way to we coplanar
    #       find another is "nudge forward" and retry. This is not guaranteed
    #       to produce correct results in all cases.

    def countHits(self, bvhTree, start, direction):
        hits = 0
        cur = start.copy()
        last_face_idx = -1
        nudge_count = 0
        MAX_NUDGES = 1
        NUDGE_DISTANCE = 0.0001

        loc, normal, face_idx, distance = bvhTree.ray_cast(cur,direction)
        while face_idx != None:
            if nudge_count > MAX_NUDGES:
                # if we nudge too many times, we are coplanar with a face
                # pick a new direction and restart
                direction = Vector((random(), random(), random())).normalized()
                cur = start.copy()
                hits = 0
                nudge_count = 0
                last_face_idx = -1
            elif face_idx == last_face_idx:
                # we are hitting the same face, nudge forward
                cur += direction * NUDGE_DISTANCE
                nudge_count += 1
            elif face_idx != last_face_idx:
                # we hit a new face, count it and search again
                last_face_idx = face_idx
                hits += 1
                cur = loc.copy()

            loc, normal, face_idx, distance = bvhTree.ray_cast(cur,direction)

        return hits
