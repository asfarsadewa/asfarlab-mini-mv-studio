# Rigs a Tripo character to the Mixamo skeleton of PINOC clips, adds cloth, and bakes clips to sprite frames.
# Usage:
#   blender --background --python tools/hero.py -- rig <hero_dir>
#   blender --background --python tools/hero.py -- bake <hero_dir> <job.json>
# A job holds: clip, out, ppu, azimuth, elevation, cloth, torch, wind [x, y], gust, frames [start, end], step, canvas, tint.
import json, math, os, sys
import bpy
from mathutils import Matrix, Vector

SCALE_REF_HIP = 1.043  # Hip height of the PINOC rig.
JOINTS = {  # Fractions of hero height: x to the left of the hero, y to the back, z up.
    "Hips": (0, 0, 0.487), "Spine": (0, 0, 0.54), "Spine1": (0, 0, 0.60), "Spine2": (0, 0, 0.67),
    "Neck": (0, 0, 0.795), "Head": (0, -0.005, 0.825), "HeadTop_End": (0, -0.01, 1.0),
    "Shoulder": (0.04, 0, 0.765), "Arm": (0.095, 0, 0.76), "ForeArm": (0.25, 0, 0.76), "Hand": (0.365, 0, 0.755),
    "UpLeg": (0.055, 0, 0.47), "Leg": (0.08, 0, 0.285), "Foot": (0.10, 0, 0.09), "ToeBase": (0.10, -0.055, 0.02), "Toe_End": (0.10, -0.115, 0.01),
}
CHILD = {"Hips": "Spine", "Spine": "Spine1", "Spine1": "Spine2", "Spine2": "Neck", "Neck": "Head", "Head": "HeadTop_End",
         "Shoulder": "Arm", "Arm": "ForeArm", "ForeArm": "Hand", "UpLeg": "Leg", "Leg": "Foot", "Foot": "ToeBase", "ToeBase": "Toe_End"}
NO_DEFORM = {"HeadTop_End", "Toe_End"}
PFX = "mixamorig:"
XBOT_LEG = 0.975 - 0.087


def split(name):
    base = name.replace(PFX, "")
    for side in ("Left", "Right"):
        if base.startswith(side):
            return side, base[len(side):]
    return "", base


def target(name, S):
    side, joint = split(name)
    if joint not in JOINTS:
        return None
    x, y, z = JOINTS[joint]
    return Vector(((-x if side == "Right" else x) * S, y * S, z * S))


def sel(obj, *others):
    bpy.ops.object.select_all(action="DESELECT")
    for o in (obj,) + others:
        o.select_set(True)
    bpy.context.view_layer.objects.active = obj


def material(name, rgb):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    n = m.node_tree.nodes["Principled BSDF"]
    n.inputs["Base Color"].default_value = (*rgb, 1)
    n.inputs["Roughness"].default_value = 1
    return m


def grid(name, rows, cols, point):
    verts = [point(r / (rows - 1), c / (cols - 1)) for r in range(rows) for c in range(cols)]
    faces = [(r * cols + c, r * cols + c + 1, (r + 1) * cols + c + 1, (r + 1) * cols + c) for r in range(rows - 1) for c in range(cols - 1)]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def ring(name, rows, cols, point):
    """A closed cloth tube, such as a skirt. point takes the row and the angle fractions."""
    verts = [point(r / (rows - 1), c / cols) for r in range(rows) for c in range(cols)]
    faces = [(r * cols + c, r * cols + (c + 1) % cols, (r + 1) * cols + (c + 1) % cols, (r + 1) * cols + c) for r in range(rows - 1) for c in range(cols)]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def add_cloth(obj, rig, bone, pin_rows, cols, mass, bend, mat):
    obj.data.materials.append(mat)
    for p in obj.data.polygons:
        p.use_smooth = True
    obj.modifiers.new("Solid", "SOLIDIFY").thickness = 0.012
    group = obj.vertex_groups.new(name=PFX + bone)
    pin = obj.vertex_groups.new(name="pin")
    for r in range(pin_rows):
        ids = [r * cols + c for c in range(cols)]
        group.add(ids, 1.0, "REPLACE")
        pin.add(ids, 1.0, "REPLACE")
    arm = obj.modifiers.new("Armature", "ARMATURE")
    arm.object = rig
    cloth = obj.modifiers.new("Cloth", "CLOTH")
    s = cloth.settings
    s.quality, s.mass, s.air_damping, s.bending_stiffness = 10, mass, 1.5, bend
    s.tension_stiffness, s.compression_stiffness, s.shear_stiffness = 15, 15, 5
    s.vertex_group_mass = "pin"
    s.pin_stiffness = 1.0
    cloth.collision_settings.use_collision = True
    cloth.collision_settings.distance_min = 0.012
    # The armature runs first, so the pins follow the body. The solidify runs last, so the cloth stays a sheet.
    obj.modifiers.move(0, len(obj.modifiers) - 1)
    return obj


def clean_weights(hero, S):
    # Anatomy rules remove weight bleed. An arm bone cannot move the torso. A leg bone cannot move the upper body.
    # A head bone cannot move the shoulders. An orphan vertex copies its nearest weighted neighbour.
    names = {g.index: split(g.name)[1] for g in hero.vertex_groups}
    sides = {g.index: split(g.name)[0] for g in hero.vertex_groups}
    arm = {"Arm", "ForeArm", "Hand"}
    leg = {"UpLeg", "Leg", "Foot", "ToeBase"}
    removed = 0
    for v in hero.data.vertices:
        x, z = v.co.x / S, v.co.z / S
        for g in list(v.groups):
            joint, side = names[g.group], sides[g.group]
            bad = False
            if joint in arm or joint == "Shoulder":
                reach = {"Shoulder": 0.03, "Arm": 0.085, "ForeArm": 0.20, "Hand": 0.32}[joint]
                wrong_side = (x < 0) if side == "Left" else (x > 0)
                bad = wrong_side or abs(x) < reach or z < 0.68
            elif joint in leg:
                wrong_side = (x < -0.012) if side == "Left" else (x > 0.012)
                bad = z > 0.53 or wrong_side
            elif joint == "Head":
                bad = z < 0.76
            elif joint == "Neck":
                bad = z < 0.70
            elif joint.startswith("Spine") or joint == "Hips":
                bad = abs(x) > 0.15 or z < 0.33
            if bad:
                hero.vertex_groups[g.group].remove([v.index])
                removed += 1
    from mathutils.kdtree import KDTree
    weighted = [v for v in hero.data.vertices if any(g.weight > 0.01 for g in v.groups)]
    tree = KDTree(len(weighted))
    for i, v in enumerate(weighted):
        tree.insert(v.co, i)
    tree.balance()
    orphans = [v for v in hero.data.vertices if not any(g.weight > 0.01 for g in v.groups)]
    for v in orphans:
        _, i, _ = tree.find(v.co)
        for g in weighted[i].groups:
            hero.vertex_groups[g.group].add([v.index], g.weight, "REPLACE")
    sel(hero)
    bpy.ops.object.vertex_group_normalize_all(lock_active=False)
    print("CLEAN", json.dumps({"removed": removed, "orphans": len(orphans)}))


def motion_path(root, clip):
    """A film with two heroes keeps one motion library in hero/motions."""
    own = os.path.join(root, "motions", f"{clip}.glb")
    return own if os.path.exists(own) else os.path.join(os.path.dirname(root.rstrip("/\\")), "hero", "motions", f"{clip}.glb")


def outfit_of(root):
    """Cloth colours for this hero, from outfit.json beside the model."""
    path = os.path.join(root, "outfit.json")
    custom = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    # Optional keys hair, skirt and crown add those parts to the rig.
    return {"cloak": (0.10, 0.12, 0.20), "scarf": (0.62, 0.05, 0.03), **custom}


def add_bow(rig, hand_world, material_):
    """A bow is an arc in the XZ plane. Its belly points along the arm, so it stands upright in a raised hand."""
    curve = bpy.data.curves.new("BowCurve", "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = 0.03
    line = curve.splines.new("POLY")
    points = 13
    line.points.add(points - 1)
    for i in range(points):
        a = math.radians(-65 + 130 * i / (points - 1))
        line.points[i].co = (0.72 * math.cos(a) - 0.72, 0, 0.72 * math.sin(a), 1)
    curve.materials.append(material_)
    bow = bpy.data.objects.new("Bow", curve)
    bpy.context.scene.collection.objects.link(bow)
    return bow


def recolour_texture(rgb, low_limit=0.50, spread=0.17):
    """Moves pale neutral cloth in the base colour texture to a new colour. Skin, hair and gold trim keep their colour."""
    import numpy as np
    image = next(i for i in bpy.data.images if i.name.startswith("Color_"))
    w, h = image.size
    px = np.zeros(w * h * 4, np.float32)
    image.pixels.foreach_get(px)
    px = px.reshape(-1, 4)
    top, low = px[:, :3].max(axis=1), px[:, :3].min(axis=1)
    mask = (low > low_limit) & (top - low < spread)
    light = px[mask, :3].mean(axis=1, keepdims=True) / 0.85
    px[mask, :3] = np.clip(light * np.array(rgb, np.float32), 0, 1)
    image.pixels.foreach_set(px.ravel())
    image.update()
    image.pack()
    print("RECOLOUR", json.dumps({"share": round(float(mask.mean()), 3)}))


def paint_spots(count, radius, rgb=(0.72, 0.03, 0.04)):
    """Paints round spots on bare skin in the base colour texture. The spots stay on the body when it moves."""
    import numpy as np
    image = next(i for i in bpy.data.images if i.name.startswith("Color_"))
    w, h = image.size
    px = np.zeros(w * h * 4, np.float32)
    image.pixels.foreach_get(px)
    px = px.reshape(h, w, 4)
    r, g, b = px[..., 0], px[..., 1], px[..., 2]
    ratio_g, ratio_b = g / np.maximum(r, 0.01), b / np.maximum(r, 0.01)
    skin = (ratio_g > 0.45) & (ratio_g < 0.80) & (ratio_b > 0.27) & (ratio_b < 0.62) & (r > 0.25)
    ys, xs = np.nonzero(skin)
    rng = np.random.default_rng(11)
    picks = rng.integers(0, len(xs), count)
    yy, xx = np.mgrid[:h, :w]
    for k in picks:
        y0, y1, x0, x1 = max(ys[k] - radius, 0), ys[k] + radius + 1, max(xs[k] - radius, 0), xs[k] + radius + 1
        hit = (yy[y0:y1, x0:x1] - ys[k]) ** 2 + (xx[y0:y1, x0:x1] - xs[k]) ** 2 <= radius * radius
        px[y0:y1, x0:x1, :3][hit & skin[y0:y1, x0:x1]] = rgb
    image.pixels.foreach_set(px.ravel())
    image.update()
    print("SPOTS", json.dumps({"skin": round(float(skin.mean()), 3), "count": count}))


def rig_cmd(root):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=motion_path(root, "idle"))
    rig = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    for o in [o for o in bpy.data.objects if o.type == "MESH"]:
        bpy.data.objects.remove(o)
    for a in list(bpy.data.actions):
        bpy.data.actions.remove(a)
    rig.animation_data_clear()
    rig.name = "Rig"

    bpy.ops.import_scene.gltf(filepath=f"{root}/hero.glb")
    hero = next(o for o in bpy.data.objects if o.type == "MESH")
    hero.name = "Hero"
    if "recolour" in outfit_of(root):
        recolour_texture(outfit_of(root)["recolour"], *outfit_of(root).get("recolour_band", ()))
    S = SCALE_REF_HIP / JOINTS["Hips"][2]
    # The model faces +X. The rig faces -Y. The sole goes to z = 0.
    hero.matrix_world = Matrix.Translation((0, 0, 0.5 * S)) @ Matrix.Rotation(math.radians(-90), 4, "Z") @ Matrix.Scale(S, 4)
    sel(hero)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # Move the joints into the hero. Each bone keeps its direction, so clip rotations keep their meaning.
    sel(rig)
    bpy.ops.object.mode_set(mode="EDIT")
    inv = rig.matrix_world.inverted()
    bones = rig.data.edit_bones
    moved = {}
    for b in bones:
        t = target(b.name, S)
        if t is not None:
            moved[b.name] = (b.head.copy(), inv @ t, (b.tail - b.head).normalized(), b.length)
    for name, (old, new, direction, length) in moved.items():
        side, joint = split(name)
        child = CHILD.get(joint)
        size = length
        if child:
            c = PFX + side + child if side or joint == "Hips" else PFX + child
            c = c if c in moved else PFX + child
            if c in moved:
                size = max((moved[c][1] - new).length, 0.02)
        bones[name].use_connect = False
        bones[name].head, bones[name].tail = new, new + direction * size
    # Fingers follow the hand as a rigid group. The model has mitten hands, so they do not deform it.
    for b in bones:
        if b.name in moved:
            continue
        side, _ = split(b.name)
        hand = PFX + side + "Hand"
        if hand in moved:
            delta = moved[hand][1] - moved[hand][0]
            b.use_connect = False
            b.head += delta
            b.tail += delta
    bpy.ops.object.mode_set(mode="OBJECT")
    for b in rig.data.bones:
        b.use_deform = b.name in moved and split(b.name)[1] not in NO_DEFORM

    # Bone heat needs a watertight mesh, and a generated model is not one.
    # So the heat runs on a voxel copy, and the weights transfer back to the real surface.
    # Heat can fail outright at one voxel size on a thin model, so the solver tries others.
    for voxel in (0.022, 0.026, 0.018, 0.03, 0.015):
        solver = hero.copy()
        solver.data = hero.data.copy()
        solver.name = "Solver"
        bpy.context.scene.collection.objects.link(solver)
        remesh = solver.modifiers.new("Remesh", "REMESH")
        remesh.mode = "VOXEL"
        remesh.voxel_size = voxel
        remesh.use_smooth_shade = True
        sel(solver)
        bpy.ops.object.modifier_apply(modifier=remesh.name)
        sel(rig, solver)
        bpy.context.view_layer.objects.active = rig
        bpy.ops.object.parent_set(type="ARMATURE_AUTO")
        solved = sum(1 for v in solver.data.vertices if any(g.weight > 0.01 for g in v.groups))
        print("SOLVER", json.dumps({"voxel": voxel, "vertices": len(solver.data.vertices), "weighted": solved}))
        if solved > 0.9 * len(solver.data.vertices):
            break
        bpy.data.objects.remove(solver)
    else:
        raise SystemExit("Bone heat failed at each voxel size.")
    # The hero stays unparented. The rig object holds a 90 degree turn, and a parent would apply that turn twice.
    sel(hero)
    hero.modifiers.new("Armature", "ARMATURE").object = rig
    for g in solver.vertex_groups:
        hero.vertex_groups.new(name=g.name)
    transfer = hero.modifiers.new("Transfer", "DATA_TRANSFER")
    transfer.object = solver
    transfer.use_vert_data = True
    transfer.data_types_verts = {"VGROUP_WEIGHTS"}
    transfer.vert_mapping = "POLYINTERP_NEAREST"
    transfer.layers_vgroup_select_src = "ALL"
    transfer.layers_vgroup_select_dst = "NAME"
    bpy.ops.object.datalayout_transfer(modifier=transfer.name)
    bpy.ops.object.modifier_move_to_index(modifier=transfer.name, index=0)
    bpy.ops.object.modifier_apply(modifier=transfer.name)
    bpy.ops.object.vertex_group_limit_total(group_select_mode="ALL", limit=4)
    bpy.ops.object.vertex_group_normalize_all(lock_active=False)
    bpy.data.objects.remove(solver)
    clean_weights(hero, S)
    counts = [0] * len(hero.data.vertices)
    for v in hero.data.vertices:
        counts[v.index] = sum(1 for g in v.groups if g.weight > 0.01)
    empty = sum(1 for c in counts if c == 0)
    print("WEIGHTS", json.dumps({"vertices": len(counts), "unweighted": empty, "groups": len(hero.vertex_groups)}))

    outfit = outfit_of(root)
    cloak_mat = material("Cloak", tuple(outfit["cloak"]))
    scarf_mat = material("Scarf", tuple(outfit["scarf"]))
    top, low = 0.775 * S, 0.27 * S
    CR, CC = 19, 13

    def cloak_point(r, c):
        wide = 0.26 + r * 0.26
        return Vector(((c - 0.5) * 2 * wide, 0.15 + r * 0.05 - 0.05 * (1 - abs(c - 0.5) * 2) * (1 - r), top + (low - top) * r))

    add_cloth(grid("Cloak", CR, CC, cloak_point), rig, "Spine2", 2, CC, 0.25, 2.0, cloak_mat)
    neck = 0.79 * S

    def ribbon(offset):
        return lambda r, c: Vector((offset + (c - 0.5) * 0.18, 0.10 + r * 0.02, neck - r * 1.0))

    add_cloth(grid("ScarfA", 15, 3, ribbon(-0.04)), rig, "Neck", 1, 3, 0.05, 0.3, scarf_mat)
    add_cloth(grid("ScarfB", 12, 3, ribbon(0.06)), rig, "Neck", 1, 3, 0.05, 0.3, scarf_mat)

    if "hair" in outfit:
        # Long hair is three tapered ribbons in different golds, pinned at the back of the head. It reads as strands.
        def hair_point(offset, half, length, depth):
            def point(r, c):
                wide = half * (1 - 0.72 * r)
                return Vector((offset + (c - 0.5) * 2 * wide, depth + r * 0.05, 0.90 * S - r * length))
            return point

        gold = tuple(outfit["hair"])
        for name, offset, half, length, depth, shade in (("HairB", -0.11, 0.09, 1.08, 0.13, 0.72), ("HairC", 0.11, 0.09, 1.0, 0.13, 0.82), ("Hair", 0.0, 0.13, 1.22, 0.15, 1.0)):
            add_cloth(grid(name, 20, 5, hair_point(offset, half, length, depth)), rig, "Head", 2, 5, 0.07, 1.2, material(name, tuple(v * shade for v in gold)))
    if "skirt" in outfit:
        # A gown is a closed tube bound softly to the hips and legs. The legs carry it, and the cloth adds only the sway.
        def skirt_point(r, c):
            # A job-free option: "skirt_shape" sets the waist radius and the flare, for a narrow wrap skirt.
            radius = outfit.get("skirt_shape", (0.19, 0.32))[0] + r * outfit.get("skirt_shape", (0.19, 0.32))[1]
            a = c * 2 * math.pi
            return Vector((math.cos(a) * radius, math.sin(a) * radius * 0.9, 0.53 * S - r * (0.53 * S - 0.05)))

        rows, cols = 13, 24
        skirt = ring("Skirt", rows, cols, skirt_point)
        skirt.data.materials.append(material("Skirt", tuple(outfit["skirt"])))
        for poly in skirt.data.polygons:
            poly.use_smooth = True
        skirt.modifiers.new("Solid", "SOLIDIFY").thickness = 0.012
        groups = {n: skirt.vertex_groups.new(name=PFX + n) for n in ("Hips", "LeftUpLeg", "RightUpLeg", "LeftLeg", "RightLeg")}
        pin = skirt.vertex_groups.new(name="pin")
        for r in range(rows):
            u = r / (rows - 1)
            for c in range(cols):
                i = r * cols + c
                left = min(1.0, max(0.0, 0.5 + math.cos(c / cols * 2 * math.pi) * 1.1))
                upper, lower = max(0.0, 1 - abs(u - 0.45) * 2.2), max(0.0, (u - 0.45) * 1.8)
                hips = max(0.0, 1 - u * 2.2)
                for name, weight in (("Hips", hips), ("LeftUpLeg", left * upper), ("RightUpLeg", (1 - left) * upper), ("LeftLeg", left * lower), ("RightLeg", (1 - left) * lower)):
                    if weight > 0:
                        groups[name].add([i], weight, "REPLACE")
                # The hem keeps a soft goal, so it sways without flying up.
                pin.add([i], 1.0 - 0.72 * u, "REPLACE")
        arm_mod = skirt.modifiers.new("Armature", "ARMATURE")
        arm_mod.object = rig
        cloth = skirt.modifiers.new("Cloth", "CLOTH")
        st = cloth.settings
        st.quality, st.mass, st.air_damping, st.bending_stiffness = 10, 0.25, 2.0, 2.0
        st.tension_stiffness, st.compression_stiffness, st.shear_stiffness = 15, 15, 5
        st.vertex_group_mass = "pin"
        st.pin_stiffness = 0.6
        cloth.collision_settings.use_collision = False
        skirt.modifiers.move(0, len(skirt.modifiers) - 1)
    extras = []
    if "crown" in outfit:
        bpy.ops.mesh.primitive_torus_add(major_radius=0.13, minor_radius=0.028, location=(0, -0.01, 0.955 * S))
        crown = bpy.context.object
        crown.name = "Crown"
        crown.data.materials.append(material("Crown", tuple(outfit["crown"])))
        extras.append((crown, Matrix.Translation((0, -0.01, 0.955 * S)), "Head"))

    if "pillow" in outfit:
        # A held pillow rides in front of the chest. A job shows it with "pillow": true.
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -0.34, 0.60 * S))
        pillow = bpy.context.object
        pillow.name = "Pillow"
        pillow.scale = (0.46, 0.20, 0.30)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        pillow.modifiers.new("Round", "BEVEL").width = 0.06
        pillow.data.materials.append(material("Pillow", tuple(outfit["pillow"])))
        extras.append((pillow, Matrix.Translation((0, -0.34, 0.60 * S)), "Spine2"))

    if "mic" in outfit:
        # A microphone in the right hand. A job shows it with "mic": true.
        grip = target(PFX + "RightHand", S) + Vector((-0.07, -0.04, 0.0))
        tilt = Matrix.Rotation(math.radians(20), 4, "Y")
        bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.05, depth=0.30, location=(0, 0, 0))
        handle = bpy.context.object
        handle.name = "MicHandle"
        handle.data.materials.append(material("MicHandle", tuple(outfit["mic"])))
        extras.append((handle, Matrix.Translation(grip + Vector((0, 0, 0.08))) @ tilt, "RightHand"))
        bpy.ops.mesh.primitive_uv_sphere_add(segments=10, ring_count=8, radius=0.085, location=(0, 0, 0))
        ball = bpy.context.object
        ball.name = "MicHead"
        ball.data.materials.append(material("MicHead", (0.75, 0.76, 0.80)))
        extras.append((ball, Matrix.Translation(grip + Vector((0.08, 0, 0.27))), "RightHand"))

    if "glasses" in outfit:
        # Painted glasses vanish at small sizes. Thick rims and pale lenses stay readable. They ride on the head bone.
        eye = outfit["glasses"] * S
        front = min(v.co.y for v in hero.data.vertices if abs(v.co.x) < 0.09 and abs(v.co.z - eye) < 0.05) - 0.012
        rim, lens = material("Rim", (0.01, 0.01, 0.012)), material("Lens", (0.86, 0.94, 1.0))
        # The lens glows a little, so it stays pale in shade and keeps its place in a small palette.
        shader = lens.node_tree.nodes["Principled BSDF"]
        shader.inputs["Emission Color"].default_value = (0.9, 0.96, 1.0, 1)
        shader.inputs["Emission Strength"].default_value = 0.9
        turn = Matrix.Rotation(math.radians(90), 4, "X")
        for k, x in (("L", 0.058), ("R", -0.058)):
            bpy.ops.mesh.primitive_torus_add(major_radius=0.052, minor_radius=0.015, location=(0, 0, 0))
            ring_obj = bpy.context.object
            ring_obj.name = "Rim" + k
            ring_obj.data.materials.append(rim)
            extras.append((ring_obj, Matrix.Translation((x, front, eye)) @ turn, "Head"))
            bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.040, depth=0.006, location=(0, 0, 0))
            glass = bpy.context.object
            glass.name = "Lens" + k
            glass.data.materials.append(lens)
            extras.append((glass, Matrix.Translation((x, front, eye)) @ turn, "Head"))

    # The wrap around the neck is rigid, so it follows the neck bone.
    bpy.ops.mesh.primitive_torus_add(major_radius=0.105, minor_radius=0.05, location=(0, 0.01, neck))
    wrap = bpy.context.object
    wrap.name = "Wrap"
    wrap.data.materials.append(scarf_mat)

    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.05, depth=0.72, location=(0, 0, 0))
    torch = bpy.context.object
    torch.name = "Torch"
    torch.data.materials.append(material("TorchWood", (0.13, 0.07, 0.03)))
    hand = target(PFX + "RightHand", S)
    left_hand = target(PFX + "LeftHand", S)
    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.035, depth=2.3, location=(0, 0, 0))
    staff = bpy.context.object
    staff.name = "Staff"
    staff.data.materials.append(material("StaffGreen", (0.18, 0.42, 0.20)))
    bow = add_bow(rig, left_hand, material("BowWood", (0.20, 0.09, 0.03)))

    rig.data.pose_position = "REST"
    bpy.context.view_layer.update()
    for obj, world, bone in ((wrap, Matrix.Translation((0, 0.01, neck)), "Neck"),
                             # The torch leans 45 degrees out from the T-pose, so it reads upward on a low and a raised arm.
                             (torch, Matrix.Translation(hand + Vector((-0.16, 0, 0.14))) @ Matrix.Rotation(math.radians(-45), 4, "Y"), "RightHand"),
                             (staff, Matrix.Translation(hand + Vector((-0.04, 0, 0.0))), "RightHand"),
                             (bow, Matrix.Translation(left_hand + Vector((0.10, 0, 0.0))), "LeftHand"), *extras):
        obj.parent = rig
        obj.parent_type = "BONE"
        obj.parent_bone = PFX + bone
        bpy.context.view_layer.update()
        obj.matrix_world = world
    rig.data.pose_position = "POSE"

    # The collision body is a light copy of the hero. It follows the same armature.
    proxy = hero.copy()
    proxy.data = hero.data.copy()
    proxy.name = "Proxy"
    bpy.context.scene.collection.objects.link(proxy)
    dec = proxy.modifiers.new("Decimate", "DECIMATE")
    dec.ratio = 0.06
    proxy.modifiers.new("Collision", "COLLISION")
    proxy.collision.thickness_outer = 0.03
    proxy.hide_render = True

    bpy.ops.object.empty_add(location=(0, 0, 1.2))
    wind = bpy.context.object
    wind.name = "Wind"
    bpy.ops.object.forcefield_toggle()
    wind.field.type = "WIND"
    wind.field.flow = 0.6
    bpy.ops.object.empty_add(location=(0, 0, 1.2))
    gust = bpy.context.object
    gust.name = "Gust"
    bpy.ops.object.forcefield_toggle()
    gust.field.type = "TURBULENCE"
    gust.field.size = 0.5
    gust.field.flow = 0.5

    bpy.ops.wm.save_as_mainfile(filepath=f"{root}/hero.blend")
    print("RIG", json.dumps({"scale": round(S, 3), "leg_ratio": round(leg_ratio(S), 3)}))


def leg_ratio(S):
    return (JOINTS["UpLeg"][2] - JOINTS["Foot"][2]) * S / XBOT_LEG


def fcurves_of(action):
    out = []
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                out.extend(bag.fcurves)
    return out


def load_clip(root, clip, rig, S):
    keep = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=motion_path(root, clip))
    action = next(o.animation_data.action for o in bpy.data.objects if o not in keep and o.type == "ARMATURE" and o.animation_data)
    action.use_fake_user = True
    slot = next(o.animation_data.action_slot for o in bpy.data.objects if o not in keep and o.type == "ARMATURE" and o.animation_data)
    for o in [o for o in bpy.data.objects if o not in keep]:
        bpy.data.objects.remove(o)
    # Scale root travel by the leg ratio, so a planted foot stays planted on the shorter leg.
    k = leg_ratio(S)
    for fc in fcurves_of(action):
        if fc.data_path == f'pose.bones["{PFX}Hips"].location':
            for point in fc.keyframe_points:
                point.co.y *= k
                point.handle_left.y *= k
                point.handle_right.y *= k
            fc.update()
    rig.animation_data_create()
    rig.animation_data.action = action
    rig.animation_data.action_slot = slot
    return action


def bake_cmd(root, job_path):
    job = json.load(open(job_path, encoding="utf-8"))
    bpy.ops.wm.open_mainfile(filepath=f"{root}/hero.blend")
    scene = bpy.context.scene
    rig = bpy.data.objects["Rig"]
    S = SCALE_REF_HIP / JOINTS["Hips"][2]
    action = load_clip(root, job["clip"], rig, S)
    first, last = (int(v) for v in action.frame_range)
    if job.get("frames"):
        first, last = max(first, job["frames"][0]), min(last, job["frames"][1])
    step = job.get("step", 1)

    # Optional IK pins a hand to a point relative to the chest, on top of the clip.
    # The target rides on Spine2, so the body motion of the clip still carries the arm.
    if job.get("ik"):
        rig.data.pose_position = "REST"
        bpy.context.view_layer.update()
        chest = rig.matrix_world @ rig.data.bones[PFX + "Spine2"].head_local
        for side, offset in job["ik"].items():
            goal = bpy.data.objects.new(f"Goal{side}", None)
            scene.collection.objects.link(goal)
            goal.parent = rig
            goal.parent_type = "BONE"
            goal.parent_bone = PFX + "Spine2"
            bpy.context.view_layer.update()
            goal.matrix_world = Matrix.Translation(chest + Vector(offset))
            ik = rig.pose.bones[PFX + side + "ForeArm"].constraints.new("IK")
            ik.target = goal
            ik.chain_count = 2
            if job.get("ik_ramp"):
                # The IK eases in over these frames, so the pose grows out of the clip.
                ik.influence = 0
                ik.keyframe_insert("influence", frame=job["ik_ramp"][0])
                ik.influence = 1
                ik.keyframe_insert("influence", frame=job["ik_ramp"][1])
        rig.data.pose_position = "POSE"
        bpy.context.view_layer.update()

    cloths = [bpy.data.objects[n] for n in ("Cloak", "ScarfA", "ScarfB", "Hair", "HairB", "HairC", "Skirt") if n in bpy.data.objects]
    wrap, torch = bpy.data.objects["Wrap"], bpy.data.objects["Torch"]
    use_cloth = job.get("cloth", True)
    for o in cloths + [wrap]:
        show = job.get("outfit", True) and (use_cloth or o is wrap)
        if o.name == "Cloak" and not job.get("cloak", True):
            show = False
        if o.name in ("ScarfA", "ScarfB", "Wrap") and not job.get("scarf", True):
            show = False
        o.hide_render = not show
        o.hide_viewport = not show
    # A walk that travels across the screen drags light hair flat. A job can lower the air drag on the hair.
    if "hair_drag" in job:
        for o in cloths:
            if o.name.startswith("Hair"):
                next(m for m in o.modifiers if m.type == "CLOTH").settings.air_damping = job["hair_drag"]
    torch.hide_render = not job.get("torch", False)
    if "Pillow" in bpy.data.objects:
        bpy.data.objects["Pillow"].hide_render = not job.get("pillow", False)
    for name in ("MicHandle", "MicHead"):
        if name in bpy.data.objects:
            bpy.data.objects[name].hide_render = not job.get("mic", False)
    if job.get("spots"):
        paint_spots(*job["spots"])
    if "Crown" in bpy.data.objects:
        bpy.data.objects["Crown"].hide_render = not job.get("outfit", True)
    staff, bow = bpy.data.objects["Staff"], bpy.data.objects["Bow"]
    staff.hide_render = not job.get("staff", False)
    bow.hide_render = not job.get("bow", False)
    tint = job.get("tint")
    if tint:
        tree = bpy.data.objects["Hero"].material_slots[0].material.node_tree
        principled = tree.nodes["Principled BSDF"]
        source = principled.inputs["Base Color"].links[0].from_socket
        mix = tree.nodes.new("ShaderNodeVectorMath")
        mix.operation = "MULTIPLY"
        mix.inputs[1].default_value = tint
        tree.links.new(source, mix.inputs[0])
        tree.links.new(mix.outputs[0], principled.inputs["Base Color"])

    # Camera axes stay fixed. The camera follows a smoothed root, and the bake records that path.
    az, el = math.radians(job.get("azimuth", 45)), math.radians(job.get("elevation", 30))
    view = Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))
    right = Vector((math.cos(az), math.sin(az), 0))
    up = view.cross(right).normalized()
    if up.z < 0:
        up = -up

    hips = rig.pose.bones[PFX + "Hips"]
    for o in cloths:
        o.modifiers["Cloth"].show_viewport = False
    raw = []
    for f in range(first, last + 1):
        scene.frame_set(f)
        raw.append(rig.matrix_world @ hips.head)
    base = raw[0].copy()
    # Measure the real contact height of the posed mesh. Some clips do not touch z = 0.
    scene.frame_set(first)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    posed = bpy.data.objects["Hero"].evaluated_get(depsgraph).to_mesh()
    ground = min(v.co.z for v in posed.vertices)
    bpy.data.objects["Hero"].evaluated_get(depsgraph).to_mesh_clear()
    win = 24 if job.get("travel") else 10 ** 6
    smooth = []
    for i in range(len(raw)):
        a, b = max(0, i - win // 2), min(len(raw), i + win // 2 + 1)
        c = sum((raw[j] for j in range(a, b)), Vector()) / (b - a)
        smooth.append(Vector((c.x, c.y, c.z)) if job.get("travel") else Vector((base.x, base.y, ground)))
    if job.get("travel"):
        lift = smooth[0].z - ground
        smooth = [s - Vector((0, 0, lift)) for s in smooth]
    for o in cloths:
        o.modifiers["Cloth"].show_viewport = True

    # Wind lifts cloth a little. In still air set wind_z to 0, or the lift beats gravity.
    wind_vec = Vector((*job.get("wind", (-3, 2)), job.get("wind_z", 0.25)))
    wind = bpy.data.objects["Wind"]
    wind.field.strength = wind_vec.length * 12
    wind.rotation_euler = wind_vec.to_track_quat("Z", "Y").to_euler()
    bpy.data.objects["Gust"].field.strength = job.get("gust", 8)
    bpy.data.objects["Wind"].location = bpy.data.objects["Gust"].location = (base.x, base.y, 1.2)

    cam_data = bpy.data.cameras.new("Cam")
    cam_data.type = "ORTHO"
    canvas_u = job.get("canvas", 3.6)
    cam_data.ortho_scale = canvas_u
    cam_data.shift_y = 0.28  # The anchor sits below the centre of the canvas.
    cam = bpy.data.objects.new("Cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    # Build the camera from its axes, so it has no roll: X is screen right, Y is screen up, Z points back at the camera.
    cam.rotation_euler = Matrix((right, up, view)).transposed().to_euler()
    size = max(16, round(canvas_u * job["ppu"]))
    anchor_px = (size / 2, size / 2 + 0.28 * size)

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
    scene.view_settings.look = "None"

    world = bpy.data.worlds.new("Ambient")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.75, 0.78, 0.86, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.55
    scene.world = world
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    scene.collection.objects.link(sun)
    sun.data.energy = 3.4
    sun.data.angle = 0.02
    # Hard shadows fall to the screen right, as in ANU.
    light = (view + right * -1.0 + Vector((0, 0, 0.7))).normalized()
    sun.rotation_euler = light.to_track_quat("Z", "Y").to_euler()

    os.makedirs(job["out"], exist_ok=True)
    meta = {"clip": job["clip"], "fps": scene.render.fps / step, "ppu": job["ppu"], "size": size, "anchor": anchor_px, "frames": []}
    pre = 24 if use_cloth else 0
    scene.frame_start = first - pre
    scene.frame_end = last
    for o in cloths:
        o.modifiers["Cloth"].point_cache.frame_start = first - pre
        o.modifiers["Cloth"].point_cache.frame_end = last + 1
    bone_r, bone_l = rig.pose.bones[PFX + "RightHand"], rig.pose.bones[PFX + "LeftHand"]

    def to_px(point, ref):
        d = point - ref
        return [round(anchor_px[0] + d.dot(right) * job["ppu"], 1), round(anchor_px[1] - d.dot(up) * job["ppu"], 1)]

    for f in range(first - pre, first):
        scene.frame_set(f)
    index = 0
    for f in range(first, last + 1):
        scene.frame_set(f)
        ref = smooth[f - first]
        cam.location = ref + view * 20
        bpy.context.view_layer.update()
        if (f - first) % step == 0:
            r.filepath = f"{job['out']}/f_{index:04d}.png"
            bpy.ops.render.render(write_still=True)
            delta = ref - smooth[0]
            tip = (staff.matrix_world @ Vector((0, 0, 1.15))) if job.get("staff") else (torch.matrix_world @ Vector((0, 0, 0.36)))
            meta["frames"].append({
                "path": [round(delta.dot(right) * job["ppu"], 2), round(-delta.dot(up) * job["ppu"], 2)],
                "right": to_px(rig.matrix_world @ bone_r.head, ref), "left": to_px(rig.matrix_world @ bone_l.head, ref), "tip": to_px(tip, ref),
            })
            index += 1
    json.dump(meta, open(f"{job['out']}/meta.json", "w"))
    print("BAKED", job["out"], index, "frames at", size, "px")


args = sys.argv[sys.argv.index("--") + 1:]
if args[0] == "rig":
    rig_cmd(args[1])
elif args[0] == "bake":
    bake_cmd(args[1], args[2])
