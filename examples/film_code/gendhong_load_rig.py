"""Builds Mbok Tum's loaded rig: a rice sack on her back, held by a selendang tied across her chest.

Run with Blender's --background --python, then bake this folder with tools/bake_sprites.py.
Coordinates are in the standing character's space. Her back faces +Y.
"""
import math
from pathlib import Path

import bpy
from mathutils import Matrix

HERE = Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(HERE.parent / "mbok/hero.blend"))
rig = bpy.data.objects["Rig"]
rig.data.pose_position = "REST"
bpy.context.view_layer.update()
chest = rig.data.bones["mixamorig:Spine2"]


def bind_to_chest(obj):
    world = obj.matrix_world.copy()
    obj.parent = rig
    obj.parent_type = "BONE"
    obj.parent_bone = chest.name
    bpy.context.view_layer.update()
    obj.matrix_world = world
    bpy.context.view_layer.update()


def material(name, rgb, rough=0.9):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes.get("Principled BSDF")
    p.inputs["Base Color"].default_value = (*rgb, 1)
    p.inputs["Roughness"].default_value = rough
    return m


# The rice sack: a soft, slightly flattened ball on her upper back.
bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=16, location=(0, 0.34, 1.38))
sack = bpy.context.object
sack.name = "Rice sack"
sack.scale = (0.25, 0.15, 0.27)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
for v in sack.data.vertices:
    # The bottom sags and the top is tied tight.
    if v.co.z < 0:
        v.co.z *= 1.12
    else:
        v.co.x *= 1 - 0.35 * (v.co.z / 0.27)
for f in sack.data.polygons:
    f.use_smooth = True
sack.data.materials.append(material("Burlap", (0.24, 0.17, 0.09)))
bind_to_chest(sack)

# The selendang: a cloth band that runs over her right shoulder and around the sack to knot at her chest.
bpy.ops.mesh.primitive_torus_add(major_segments=40, minor_segments=6, location=(0, 0.12, 1.47),
                                 rotation=(0, math.radians(28), 0), major_radius=0.30, minor_radius=0.03)
band = bpy.context.object
band.name = "Selendang"
band.scale = (1.0, 0.82, 1.0)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
band.data.materials.append(material("Selendang batik", (0.42, 0.10, 0.12)))
bind_to_chest(band)

# The knot at the front of her chest.
bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=8, location=(0.05, -0.17, 1.50))
knot = bpy.context.object
knot.name = "Knot"
knot.scale = (0.05, 0.04, 0.05)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
knot.data.materials.append(material("Knot batik", (0.42, 0.10, 0.12)))
bind_to_chest(knot)

rig.data.pose_position = "POSE"
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(HERE / "hero.blend"), compress=True)
print("SAVED")
