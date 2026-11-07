# Reports what the hero model and each motion clip contain, as JSON lines.
# Usage: blender --background --python tools/blender_inspect.py -- <hero.glb> <motions_dir>
import glob, json, os, sys
import bpy
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]
hero, motions = args[0], args[1]


def clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)


clear()
bpy.ops.import_scene.gltf(filepath=hero)
meshes = [o for o in bpy.data.objects if o.type == "MESH"]
corners = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
print("HERO", json.dumps({
    "meshes": [o.name for o in meshes], "faces": sum(len(o.data.polygons) for o in meshes),
    "materials": [m.name for m in bpy.data.materials], "images": [[i.name, list(i.size)] for i in bpy.data.images],
    "min": [round(min(c[k] for c in corners), 3) for k in range(3)], "max": [round(max(c[k] for c in corners), 3) for k in range(3)],
    "armatures": [o.name for o in bpy.data.objects if o.type == "ARMATURE"],
}))

for path in sorted(glob.glob(os.path.join(motions, "*.glb"))):
    clear()
    bpy.ops.import_scene.gltf(filepath=path)
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    act = bpy.data.actions[0]
    start, end = (int(v) for v in act.frame_range)
    scene = bpy.context.scene
    bones = arm.pose.bones
    hips = next(b for b in bones if b.name.lower().endswith("hips"))
    foot_l = next(b for b in bones if b.name.lower().endswith("leftfoot"))
    foot_r = next(b for b in bones if b.name.lower().endswith("rightfoot"))
    head = next(b for b in bones if b.name.lower().endswith("head"))

    def at(f, b):
        scene.frame_set(f)
        return arm.matrix_world @ b.head

    h0, h1 = at(start, hips), at(end, hips)
    low = min(min(at(f, foot_l).z, at(f, foot_r).z) for f in range(start, end + 1, 3))
    tops = [at(f, head).z for f in range(start, end + 1, 3)]
    info = {"clip": os.path.basename(path), "fps": scene.render.fps, "frames": [start, end], "bones": len(bones),
            "rest_head_z": round(at(start, head).z, 3), "hips_start": [round(v, 2) for v in h0], "hips_end": [round(v, 2) for v in h1],
            "foot_low_z": round(low, 2), "head_z": [round(min(tops), 2), round(max(tops), 2)]}
    if path.endswith("walking.glb"):
        info["bone_names"] = [b.name for b in bones][:12]
    print("CLIP", json.dumps(info))
