# Bakes the Tripo hand cart with the same orthographic camera, sun and sky as the people.
# Usage: blender --background --python bake_bus.py -- <bis.glb> <out_dir> <ppu> sheet
#        blender --background --python bake_bus.py -- <bis.glb> <out_dir> <ppu> clip <heading_deg>
# "sheet" renders headings every 15 degrees. "clip" renders the roll, the stair climb and the stuck shake at one heading.
import json, math, os, sys
import bpy
from mathutils import Matrix, Vector

glb, out, ppu, mode = sys.argv[sys.argv.index("--") + 1:][:4]
ppu = float(ppu)
rest = sys.argv[sys.argv.index("--") + 5:]
os.makedirs(out, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
bpy.ops.import_scene.gltf(filepath=glb)
meshes = [o for o in scene.objects if o.type == "MESH"]
root = bpy.data.objects.new("Bus", None)
scene.collection.objects.link(root)
bpy.context.view_layer.update()
pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
# A heavy load cart with its handle, about 2.3 m long. The owner asked for a cart that reads clearly at phone size.
k = 2.3 / max(hi.x - lo.x, hi.y - lo.y)
centre = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
for o in meshes:
    o.matrix_world = Matrix.Scale(k, 4) @ Matrix.Translation(-centre) @ o.matrix_world
    o.parent = root
    o.matrix_parent_inverse = root.matrix_world.inverted()
print("SIZE", [round((hi - lo)[i] * k, 2) for i in range(3)])

el, canvas = math.radians(30), 4.4
view = Vector((0, -math.cos(el), math.sin(el)))
right = Vector((1, 0, 0))
up = view.cross(right).normalized()
if up.z < 0:
    up = -up
cam_data = bpy.data.cameras.new("Cam")
cam_data.type = "ORTHO"
cam_data.ortho_scale = canvas
cam_data.shift_y = 0.2
cam = bpy.data.objects.new("Cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
cam.rotation_euler = Matrix((right, up, view)).transposed().to_euler()
cam.location = view * 20
size = round(canvas * ppu)
r = scene.render
r.engine = "CYCLES"
scene.cycles.device = "GPU"
prefs = bpy.context.preferences.addons["cycles"].preferences
prefs.compute_device_type = "OPTIX"
prefs.get_devices()
for d in prefs.devices:
    d.use = d.type in ("OPTIX", "CUDA")
scene.cycles.samples = 12
scene.cycles.use_denoising = False
scene.cycles.pixel_filter_type = "BOX"
scene.cycles.filter_width = 0.01
scene.cycles.max_bounces = 2
r.resolution_x = r.resolution_y = size
r.film_transparent = True
r.image_settings.file_format = "PNG"
r.image_settings.color_mode = "RGBA"
scene.view_settings.view_transform = "Standard"
world = bpy.data.worlds.new("Ambient")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.75, 0.78, 0.86, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.55
scene.world = world
sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
scene.collection.objects.link(sun)
sun.data.energy = 3.4
sun.data.angle = 0.02
light = (view + right * -1.0 + Vector((0, 0, 0.7))).normalized()
sun.rotation_euler = light.to_track_quat("Z", "Y").to_euler()


def shot(name, heading, pitch=0.0, roll=0.0, lift=0.0):
    # The nose points to -Y, so pitch turns about X.
    root.rotation_euler = (math.radians(pitch), math.radians(roll), math.radians(heading))
    root.location = (0, 0, lift)
    r.filepath = f"{out}/{name}.png"
    bpy.ops.render.render(write_still=True)


anchor = [size / 2, size / 2 + 0.2 * size]
if mode == "sheet":
    for h in range(0, 360, 15):
        shot(f"h_{h:03d}", h)
else:
    h = float(rest[0])
    frames = []
    # Roll on the flat: a small bump as the wheels cross each paving joint.
    for i in range(4):
        frames.append(("roll", 0.0, 0.0, 0.008 * (i % 2)))
    # Climb: the nose tips up a step, then settles, four times.
    for i in range(8):
        frames.append(("climb", [14, 18, 14, 10][i % 4], 0.6 * (-1) ** i, 0.0))
    # Stuck: the load rocks against the step and does not move.
    for i in range(4):
        frames.append(("stuck", 16 + 2 * (i % 2), 1.2 * (-1) ** i, 0.0))
    for n, (_, p, ro, li) in enumerate(frames):
        shot(f"f_{n:04d}", h, -p, ro, li)
    json.dump({"size": size, "anchor": anchor, "ppu": ppu, "heading": h, "groups": {"roll": [0, 4], "climb": [4, 12], "stuck": [12, 16]}}, open(f"{out}/meta.json", "w"))
print("BAKED")
