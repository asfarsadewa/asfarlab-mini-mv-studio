"""Builds Mbok Tum carrying Sekar on her back in the selendang.

Sekar's own model is posed for a piggyback, baked into a still mesh at the size of a six-year-old,
and bound to her grandmother's chest bone. One bake then shows them as one shape.
Run with Blender's --background --python, then bake this folder with tools/bake_sprites.py.
Coordinates are in the standing character's space. Faces look along -Y, so a back faces +Y.
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix

HERE = Path(__file__).resolve().parent
P = "mixamorig:"
CHILD = 0.72                      # A six-year-old against her grandmother.
SEAT = (0.0, 0.34, 0.55)          # Where Sekar's model origin goes after the scale.

bpy.ops.wm.open_mainfile(filepath=str(HERE.parent / "mbok/hero.blend"))
gran = bpy.data.objects["Rig"]
gran.data.pose_position = "REST"
bpy.context.view_layer.update()
chest = gran.data.bones[P + "Spine2"]

with bpy.data.libraries.load(str(HERE.parent / "sekar/hero.blend"), link=False) as (src, dst):
    dst.objects = [n for n in src.objects if n in ("Rig", "Hero")]
kid_rig = next(o for o in dst.objects if o.type == "ARMATURE")
kid_body = next(o for o in dst.objects if o.type == "MESH")
for o in (kid_rig, kid_body):
    bpy.context.scene.collection.objects.link(o)

# The piggyback pose: thighs forward and apart around her waist, shins hanging, arms over her shoulders.
kid_rig.data.pose_position = "POSE"
pose = {
    "LeftUpLeg": (75, 0, 28), "RightUpLeg": (75, 0, -28),
    "LeftLeg": (-85, 0, 0), "RightLeg": (-85, 0, 0),
    "LeftArm": (0, 0, 62), "RightArm": (0, 0, -62),
    "LeftForeArm": (0, 0, 35), "RightForeArm": (0, 0, -35),
    "Spine": (12, 0, 0), "Neck": (8, 0, 0), "Head": (6, 0, 12),
}
for name, (x, y, z) in pose.items():
    pb = kid_rig.pose.bones.get(P + name)
    if pb:
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = (math.radians(x), math.radians(y), math.radians(z))
bpy.context.view_layer.update()

foot = kid_rig.matrix_world @ kid_rig.pose.bones[P + "LeftFoot"].head
hand = kid_rig.matrix_world @ kid_rig.pose.bones[P + "LeftHand"].head
print("POSED foot", [round(v, 2) for v in foot], "hand", [round(v, 2) for v in hand])

# Bake the pose into a still mesh, then drop the child's rig.
deps = bpy.context.evaluated_depsgraph_get()
still = bpy.data.meshes.new_from_object(kid_body.evaluated_get(deps), preserve_all_data_layers=True, depsgraph=deps)
sekar = bpy.data.objects.new("Sekar riding", still)
bpy.context.scene.collection.objects.link(sekar)
sekar.matrix_world = Matrix.Translation(SEAT) @ Matrix.Scale(CHILD, 4) @ kid_body.matrix_world
bpy.data.objects.remove(kid_body)
bpy.data.objects.remove(kid_rig)


def bind_to_chest(obj):
    world = obj.matrix_world.copy()
    obj.parent = gran
    obj.parent_type = "BONE"
    obj.parent_bone = chest.name
    bpy.context.view_layer.update()
    obj.matrix_world = world
    bpy.context.view_layer.update()


def material(name, rgb):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes.get("Principled BSDF")
    p.inputs["Base Color"].default_value = (*rgb, 1)
    p.inputs["Roughness"].default_value = 0.9
    return m


bind_to_chest(sekar)

# The selendang: a sling that holds Sekar's seat against her back and ties over her right shoulder to the chest.
bpy.ops.mesh.primitive_torus_add(major_segments=40, minor_segments=6, location=(0, 0.16, 1.36),
                                 rotation=(0, math.radians(30), 0), major_radius=0.34, minor_radius=0.035)
band = bpy.context.object
band.name = "Selendang"
band.scale = (1.0, 0.95, 1.0)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
band.data.materials.append(material("Selendang batik", (0.42, 0.10, 0.12)))
bind_to_chest(band)

gran.data.pose_position = "POSE"
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(HERE / "hero.blend"), compress=True)
print("SAVED")
