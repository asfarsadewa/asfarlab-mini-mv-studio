# Damar ing Dhasar Banyu: a dam drowns a river town. A ferryman steers home by the lamp in his wife's window.
# They leave it burning when the water comes. Forty years later he lowers her lamp on a line from his boat.
# On the final chorus the drowned windows light one by one, and the whole town dances under the water.
# The plates share one layout, so the water can sweep from one to the next. Footprints guard every path.
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pixkit import INK, Captions, Occlusion, Sprite, bayer_field, contact_shadow
from studio_paths import font_path

AMBER = (255, 190, 96)
GLOW = (255, 226, 150)
FOAM = (222, 240, 232)
BUBBLE = (150, 220, 216)
ROPE = (196, 182, 150)
POLE = (92, 66, 44)
NIGHT = (0.74, 0.76, 0.96)
UNDER = (0.60, 0.80, 0.92)
UNDER_WARM = (0.98, 0.84, 0.66)

LANDING = (162, 283)
MEET_H, MEET_W = (168, 232), (184, 232)
DOOR = (182, 217)
TOP_STAIR = (288, 154)
STAIR_BASE = (250, 205)
HOVER = (184, 146)
LAMP_END = 184
TALL = (159, 183, 203, 230)
# Each drowned window with its lit pool, in the order that the light spreads from the tall house.
WINDOWS = [TALL, (128, 196, 151, 225), (209, 195, 237, 225), (103, 207, 128, 234), (242, 208, 264, 234), (71, 189, 88, 209), (253, 236, 280, 264), (86, 225, 112, 252), (56, 229, 84, 257)]
# Folder, x, y and the beat offset of each dancer. The heroes stand at the front.
DANCERS = [("folk_k", 124, 228, 1), ("folk_d", 150, 224, 3), ("folk_m", 212, 224, 2), ("folk_k", 238, 228, 5), ("folk_d", 112, 242, 4), ("folk_m", 136, 240, 6), ("folk_k", 222, 240, 3), ("folk_d", 244, 240, 7), ("folk_m", 196, 228, 5), ("folk_k", 168, 226, 2)]
LEAVERS = [("folk_k", 214, 226, 0.0), ("folk_d", 232, 234, 0.6), ("folk_m", 196, 244, 1.1), ("folk_d", 156, 236, 1.5), ("folk_k", 134, 244, 2.2), ("folk_m", 218, 246, 3.0)]


def in_plaza(x, y):
    """The open square, as measured on the plate."""
    return 216 <= y <= 254 and 100 + max(0, 238 - y) * 0.9 <= x <= 250


def make(ctx):
    G, fps, brief, A, root = ctx["grid"], ctx["fps"], ctx["brief"], ctx["a"], ctx["root"]
    paper = np.array(brief["paper"], np.uint8)
    beats = np.array(A["beats"])
    rng = np.random.default_rng(23)
    bayer = bayer_field(G)
    Y, X = np.mgrid[:G, :G]
    caps = Captions(brief["lines"], paper, top_font=(font_path("msgothic.ttc"), 16), low_font=(font_path("simsun.ttc"), 12))
    shapes = json.loads((root / "occluders.json").read_text(encoding="utf-8"))

    def beat(t):
        return float(beats[np.argmin(np.abs(beats - t))])

    T_OMAH1, T_BACK, T_GARIS, T_OMAH2, T_HIT = beat(11.0), beat(14.2), beat(23.6), beat(30.4), beat(33.68)
    T_DUSK, T_OLD, T_LOWER, T_FINAL, T_CLOSE, T_WIDE, T_FADE = beat(50.6), beat(55.2), beat(61.86), beat(72.58), beat(79.6), beat(86.8), beat(99.2)

    def plate(name, occ):
        d = np.asarray(Image.open(root / f"plates/{name}-360.png").convert("RGB")).copy()
        is_paper = (np.abs(d.astype(int) - paper.astype(int)).sum(axis=2) < 24) | (d.astype(int).sum(axis=2) > 720)
        d[is_paper] = paper
        return {"name": name, "day": d, "paper": is_paper, "occ": Occlusion(root, occ)}

    P = {n: plate(n, "desa") for n in ("desa", "desa_night", "garis", "lelep", "lelep_night", "lelep_lit")}
    P.update({n: plate(n, "omah") for n in ("omah", "omah_lelep")})

    sprites = {}

    def S(folder, name):
        key = (folder, name)
        if key not in sprites:
            sprites[key] = Sprite(root, name, folder)
        return sprites[key]

    def prop(name, width):
        raw = Image.open(root / f"plates/{name}-raw.png").convert("RGBA")
        raw = raw.crop(raw.getchannel("A").point(lambda v: 255 if v > 127 else 0).getbbox())
        small = np.asarray(raw.resize((width, max(2, int(raw.height * width / raw.width))), Image.BOX)).copy()
        small[..., 3] = (small[..., 3] > 110) * 255
        return small

    HULL = prop("prau", 74)
    LAMP = prop("damar", 11)
    SILL_LAMP = prop("damar", 12)

    def stamp(f, a, x0, y0, rows=None):
        h, w = a.shape[:2]
        x0, y0 = int(x0), int(y0)
        ax0, ay0, ax1, ay1 = max(x0, 0), max(y0, 0), min(x0 + w, G), min(y0 + h, G)
        if ax0 >= ax1 or ay0 >= ay1:
            return
        part = a[ay0 - y0:ay1 - y0, ax0 - x0:ax1 - x0]
        solid = part[..., 3] > 0
        if rows is not None:
            solid = solid & (np.arange(ay0 - y0, ay1 - y0)[:, None] >= rows)
        f[ay0:ay1, ax0:ax1][solid] = part[..., :3][solid]

    def line(f, a, b, colour):
        n = int(max(abs(b[0] - a[0]), abs(b[1] - a[1]), 1))
        xs = np.clip(np.linspace(a[0], b[0], n + 1).astype(int), 0, G - 1)
        ys = np.clip(np.linspace(a[1], b[1], n + 1).astype(int), 0, G - 1)
        f[ys, xs] = colour

    def grade_plate(pl, k):
        out = np.clip(pl["day"] * np.array(k), 0, 255).astype(np.uint8)
        out[pl["paper"]] = paper
        return out

    def clearance(name, x, y):
        solids = [o["footprint"] for o in shapes.get(name, []) if "footprint" in o]
        return min((np.hypot((x - cx) / rx, (y - cy) / ry) for cx, cy, rx, ry in solids), default=9.0)

    def guard(name, pts, plaza=True):
        low = float(min(clearance(name, x, y) for x, y in pts))
        print(f"Footprint clearance on {name}, with 1.0 at the object edge:", round(low, 2), flush=True)
        if low < 1.0:
            raise SystemExit(f"A person stands inside a solid object on {name}: {low:.2f}")
        off = [p for p in pts if plaza and not in_plaza(*p)]
        if off:
            raise SystemExit(f"A person leaves the square on {name}: {off[0]}")

    def walk_between(spr, a, b, t0, t1, T):
        """Plays a clip along a path. The frame follows the distance, so that the feet keep pace with the ground."""
        u = float(np.clip((T - t0) / (t1 - t0), 0, 1))
        p0, p1 = spr.path(0), spr.path(spr.n - 1)
        stride = max(np.hypot(p1[0] - p0[0], p1[1] - p0[1]), 1.0)
        walked = u * np.hypot(b[0] - a[0], b[1] - a[1])
        return int(walked / stride * (spr.n - 1)) % spr.n, a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u

    def person(f, spr, i, x, y, pl, grade=None, sh=(6, 2), reveal=1.0, light=None, occ=True):
        if sh:
            contact_shadow(f, x, y, sh[0], sh[1], 0.8, bayer, ~pl["paper"], 2, occ=pl["occ"] if occ else None)
        spr.draw(f, i, x, y, occ=pl["occ"] if occ else None, grade=grade, bayer=bayer, reveal=reveal, light=light)

    # The boat. The hull draws twice, so that its near side hides the feet of the people in it.
    def boat_back(f, x, y, T, wake=True):
        h, w = HULL.shape[:2]
        stamp(f, HULL, x - w / 2, y - h + 5)
        if wake:
            for k in range(7):
                wx = int(x + 40 + k * 5 + np.sin(T * 3 + k) * 2)
                wy = int(y + 3 + (k % 3))
                if 0 <= wx < G and 0 <= wy < G and not (f[wy, wx] == paper).all():
                    f[wy, wx] = FOAM

    def boat_front(f, x, y):
        h, w = HULL.shape[:2]
        stamp(f, HULL, x - w / 2, y - h + 5, rows=int(h * 0.52))

    def poler(f, spr, T, x, y, pl, grade=None, light=None):
        i = spr.index(T, "pingpong")
        boat_back(f, x, y, T)
        fx, fy = x + 8, y - 5
        spr.draw(f, i, fx, fy, grade=grade, bayer=bayer, light=light)
        hx, hy = spr.point(i, "right", fx, fy)
        lean = np.sin(T * 1.7) * 5
        line(f, (hx + 5 + lean * 0.4, hy - 16), (hx - 6 - lean, y + 6), POLE)
        boat_front(f, x, y)

    def materialise(f, draw, x, u):
        """A boat forms on the water, from the bow back to the stern. It never slides in from past the island."""
        if u >= 1:
            draw(f)
            return
        if u <= 0:
            return
        temp = f.copy()
        draw(temp)
        # The edge crosses the boat. Behind it the pixels arrive through a wide dither band.
        edge = x - 60 + u * 130
        show = bayer < np.clip((edge - X) / 34, 0, 1)
        f[show] = temp[show]

    bubbles = [[rng.uniform(20, 340), rng.uniform(130, 300), rng.uniform(3, 11), rng.uniform(0, 6)] for _ in range(60)]

    def rise_bubbles(f, T, n, top=132, bottom=292):
        span = bottom - top
        if span < 8:
            return
        for x, y, speed, ph in bubbles[:n]:
            py = int(bottom - ((bottom - y) + T * speed) % span)
            px = int(x + np.sin(T * 1.3 + ph) * 3)
            if 0 <= px < G and not (f[py, px] == paper).all():
                f[py, px] = BUBBLE

    # The window that they leave burning, copied from the lit plates.
    def warm_mask(pl_lit, pl_dark, box):
        x0, y0, x1, y1 = box
        m = np.zeros((G, G), bool)
        m[y0:y1, x0:x1] = (pl_lit["day"][y0:y1, x0:x1].astype(int)[..., 0] - pl_dark["day"][y0:y1, x0:x1].astype(int)[..., 0]) > 18
        return m

    WARM = [warm_mask(P["lelep_lit"], P["lelep_night"], b) for b in WINDOWS]
    DRY_WARM = warm_mask(P["desa_night"], P["desa"], (160, 186, 204, 232)) & (P["desa_night"]["day"][..., 0].astype(int) > 120)

    def lit_window(f, T, dry=False):
        flick = 0.5 + 0.5 * np.sin(T * 9.1) * np.sin(T * 5.3)
        m = DRY_WARM if dry else WARM[0]
        src = P["desa_night"]["day"] if dry else P["lelep_lit"]["day"]
        f[m & (bayer < 0.86 + 0.14 * flick)] = src[m & (bayer < 0.86 + 0.14 * flick)]

    # The flood follows the method of the ANU water: low ground goes first, shallow water is a dithered
    # mirror over the ground, deep water hides it, and foam marks the moving edge. Each pixel has the flood
    # progress at which the water reaches it.
    def poly_mask(points):
        im = Image.new("1", (G, G))
        ImageDraw.Draw(im).polygon(points, fill=1)
        return np.asarray(im)

    def flood_map():
        noise = rng.random((G, G)) * 0.012
        # Above the banks, the water climbs by row. The far corners of the block rise with it.
        m = 0.32 + np.clip(256 - Y, 0, None) / 156 * 0.62 - np.abs(X - 180) * 0.0012
        # The outer wall of the island is not ground, so it never shows the shallow mirror.
        m[Y >= 256] = -1.0
        # A slow wobble keeps the line of the water from reading as a straight wipe.
        wob = np.sin(X / 23.0 + Y / 41.0) * np.sin(X / 37.0 - Y / 19.0) * 0.025
        m = m + wob * (m > 0)
        # The steps overflow first. The water then spreads flat across the square, away from the steps.
        steps = poly_mask([(136, 256), (196, 256), (188, 282), (146, 282)])
        m[steps] = 0.08 + np.clip(282 - Y[steps], 0, None) / 26 * 0.09
        plaza = poly_mask([(122, 218), (250, 216), (250, 236), (236, 254), (186, 256), (182, 262), (140, 262), (136, 254), (100, 252), (100, 238)])
        m[plaza] = 0.17 + np.hypot(X[plaza] - 164, (Y[plaza] - 258) * 2.0) / 150 * 0.15
        river = poly_mask([(12, 262), (140, 262), (150, 280), (182, 280), (190, 262), (345, 262), (345, 272), (290, 298), (180, 312), (80, 300), (30, 285)])
        m[river] = 0.0
        return m + noise, river, plaza, steps

    FLOOD, RIVER, PLAZA, STEPS = flood_map()
    # By day the window burns, and its pool is only a thin dither on the teal.
    DAY_GLOW = WARM[0] & ((Y < 199) | (bayer < 0.3))
    SHALLOW = 0.07
    MIRROR = np.array([[92, 152, 150], [122, 178, 170], [158, 204, 194], [196, 226, 216]], np.uint8)
    rip = np.array([[np.sin(x / 64 * 6.283 * 3 + np.sin(y / 64 * 6.283 * 2) * 1.2) * 0.45 + np.sin((x + y) / 64 * 6.283 * 4 + np.cos(x / 64 * 6.283) * 1.4) * 0.35 + np.sin((y - x) / 64 * 6.283 * 7) * 0.2 for x in range(64)] for y in range(64)])
    speck = rng.random((G, G))
    SURFACE = (Y < 150 + (170 - 150) * (1 - np.abs(X - 180) / 170)) & ~P["lelep"]["paper"]

    def ripple(T):
        tick = int(T * 10)
        return rip[(Y - (tick >> 1)) % 64, (X + tick) % 64]

    def glint(f, T, mask, colour=FOAM):
        tick = int(T * 10)
        on = mask & (ripple(T) > 0.8) & (np.roll(speck, tick >> 2, axis=0) > 0.8)
        f[on] = colour

    def flood_progress(T):
        return float(np.clip((T - T_HIT) / (T_DUSK - 0.5 - T_HIT), 0, 1)) * 1.04

    def water(T):
        p = flood_progress(T)
        wet = FLOOD <= p
        f = P["garis"]["day"].copy()
        lit_window(f, T, dry=True)
        deep = wet & (p - FLOOD > SHALLOW)
        f[deep] = P["lelep"]["day"][deep]
        lit = DAY_GLOW & deep
        f[lit] = P["lelep_lit"]["day"][lit]
        # Shallow water: the ground shows through the dither, and more of it hides as the water deepens.
        shallow = wet & ~deep & ~P["garis"]["paper"]
        r = ripple(T)
        idx = np.clip((1.5 + r * 1.7 + (bayer - 0.5) * 0.8).astype(int), 0, 3)
        cover = (bayer < 0.28 + (p - FLOOD) / SHALLOW * 0.72) & shallow
        f[cover] = MIRROR[idx][cover]
        # Foam marks the moving edge, and it flecks the steps where the river spills over.
        edge = wet & (p - FLOOD < 0.012) & ~P["garis"]["paper"] & ~RIVER
        f[edge] = FOAM
        tick = int(T * 12)
        if p < 0.24:
            f[STEPS & wet & (np.roll(speck, -tick, axis=0) > 0.9)] = FOAM
        glint(f, T, deep & (FLOOD < 0.05))
        return f, p

    def boat_row(p):
        return 285.0 - 135.0 * float(np.clip((p - 0.05) / 0.9, 0, 1))

    def couple(f, x, y, T, grade=None):
        boat_back(f, x, y, T)
        h, w = S("hero", "h_idle_l"), S("hero_wife", "w_idle_l")
        w.draw(f, w.index(T + 0.6, "pingpong"), x - 8, y - 5, grade=grade, bayer=bayer)
        h.draw(f, h.index(T, "pingpong"), x + 12, y - 5, grade=grade, bayer=bayer)
        boat_front(f, x, y)

    # The scenes.
    guard("desa", [MEET_H, MEET_W, DOOR if in_plaza(*DOOR) else MEET_W] + [(d[1], d[2]) for d in DANCERS] + [(l[1], l[2]) for l in LEAVERS] + [(176, 240), (192, 240)])

    night_base = grade_plate(P["desa_night"], (1, 1, 1))

    def night_river(T):
        f = night_base.copy()
        glint(f, T, RIVER, (168, 186, 214))
        # The boat crosses the night, then the hero walks up to his wife.
        H = S("hero", "h_pole")
        glow = (182, 196, 30, (1.2, 1.05, 0.8))
        if T < T_OMAH1:
            x = 274 - (274 - 244) * (T / T_OMAH1)
            materialise(f, lambda g: poler(g, H, T, x, 284, P["desa_night"], grade=NIGHT), x, (T - 0.8) / 3.6)
        else:
            u = min(1.0, (T - T_BACK) / 5.0)
            if u < 1:
                poler(f, H, T, 236 - (236 - LANDING[0]) * u, 284, P["desa_night"], grade=NIGHT)
            else:
                boat_back(f, *LANDING, T, wake=False)
                boat_front(f, *LANDING)
                t0, t1 = T_BACK + 5.0, T_BACK + 5.0 + 3.4
                up = S("hero", "h_walk_up")
                if T < t1:
                    i, x, y = walk_between(up, (160, 276), MEET_H, t0, t1, T)
                    person(f, up, i, x, y, P["desa_night"], grade=NIGHT, light=(x, y - 24, 16, (1.1, 1.0, 0.85)))
                else:
                    idle = S("hero", "h_idle")
                    person(f, idle, idle.index(T, "pingpong"), *MEET_H, P["desa_night"], grade=NIGHT, light=(MEET_H[0] + 10, MEET_H[1] - 16, 20, (1.15, 1.0, 0.82)))
                wd = S("hero_wife", "w_walk_d")
                t2, t3 = T_BACK + 6.4, T_BACK + 7.9
                if T < t2:
                    pass
                elif T < t3:
                    i, x, y = walk_between(wd, DOOR, MEET_W, t2, t3, T)
                    person(f, wd, i, x, y, P["desa_night"], grade=NIGHT, reveal=min(1.0, (T - t2) / 0.4))
                else:
                    w = S("hero_wife", "w_idle")
                    person(f, w, w.index(T, "pingpong"), *MEET_W, P["desa_night"], grade=NIGHT, light=(MEET_W[0], MEET_W[1] - 16, 20, (1.15, 1.0, 0.82)))
        return f

    def room(T, first):
        pl = P["omah"]
        f = pl["day"].copy()
        spot = (146, 256)
        start = T_OMAH1 if first else T_OMAH2
        lit = T - start > 1.1
        s = S("hero_wife", "wb_light")
        if first or T - start < 1.7:
            i = min(int((T - start) * s.fps), 18) + (int((T - start) * s.fps * 0.5) % 6 if T - start > 0.6 else 0)
            person(f, s, min(i, s.n - 1), *spot, pl, sh=(16, 5))
        else:
            b = S("hero_wife", "wb_front")
            person(f, b, b.index(T, "pingpong"), *spot, pl, sh=(16, 5))
        stamp(f, SILL_LAMP, 110, 231 - SILL_LAMP.shape[0])
        if lit or not first:
            pool = np.hypot(X - 116, (Y - 222) * 1.2) + bayer * 22 < 36
            k = 1.28 + np.sin(T * 8.3) * 0.03
            f[pool & ~pl["paper"]] = np.clip(f[pool & ~pl["paper"]] * np.array([k, k * 0.92, k * 0.72]), 0, 255).astype(np.uint8)
            stamp(f, SILL_LAMP, 110, 231 - SILL_LAMP.shape[0])
        return f

    def leaving(T):
        # The red line runs along the walls. The town carries its life to the stair.
        edge = (T - T_GARIS) / 2.4 * (G + 40) - 20
        f = np.where((X < edge)[..., None], P["garis"]["day"], P["desa"]["day"]).astype(np.uint8)
        glint(f, T, RIVER)
        pl = P["garis"]
        for folder, x, y, delay in LEAVERS:
            # Everyone walks from the first frame. A longer way to the stair makes a later arrival.
            t0 = T_GARIS - delay
            t1 = t0 + np.hypot(STAIR_BASE[0] - x, STAIR_BASE[1] - y) / 20 + delay
            t2 = t1 + 4.2
            if T < t1:
                c = S(folder, "f_carry")
                i, px, py = walk_between(c, (x, y), STAIR_BASE, t0, t1, T)
                person(f, c, i, px, py, pl)
            elif T < t2:
                c = S(folder, "f_stair")
                i, px, py = walk_between(c, STAIR_BASE, TOP_STAIR, t1, t2, T)
                person(f, c, i, px, py, pl, sh=None, reveal=min(1.0, (t2 - T) / 0.5), occ=False)
        h, w = S("hero", "h_idle"), S("hero_wife", "w_idle")
        person(f, h, h.index(T, "pingpong"), *MEET_H, pl)
        person(f, w, w.index(T, "pingpong"), *MEET_W, pl)
        return f

    def flood(T):
        f, p = water(T)
        u = float(np.clip((T - T_HIT) / (T_DUSK + 2.2 - T_HIT), 0, 1))
        x = 232 - 170 * u
        leave = (T_DUSK + 2.2 - T) / 2.8
        materialise(f, lambda g: couple(g, x, boat_row(p), T), x, leave)
        rise_bubbles(f, T, 26, top=max(int(322 - 220 * p), 132))
        return f

    def dusk(T):
        u = (T - T_DUSK) / (T_OLD - T_DUSK)
        # The years pass as one slow change of light, with no dither lattice.
        f = (P["lelep"]["day"] * (1 - u) + P["lelep_night"]["day"] * u).astype(np.uint8)
        glow = DAY_GLOW if u < 0.5 else WARM[0]
        f[glow] = P["lelep_lit"]["day"][glow]
        rise_bubbles(f, T, 14)
        glint(f, T, SURFACE, (176, 196, 222))
        if T < T_DUSK + 2.2:
            x = 232 - 170 * float(np.clip((T - T_HIT) / (T_DUSK + 2.2 - T_HIT), 0, 1))
            materialise(f, lambda g: couple(g, x, 150, T), x, (T_DUSK + 2.2 - T) / 2.8)
        return f

    def old_row(T):
        f = P["lelep_night"]["day"].copy()
        lit_window(f, T)
        glint(f, T, SURFACE, (176, 196, 222))
        O = S("hero_old", "o_pole")
        u = float(np.clip((T - T_OLD) / (T_LOWER - T_OLD), 0, 1))
        x = 272 - (272 - HOVER[0]) * u
        y = 140 + (HOVER[1] - 140) * u
        materialise(f, lambda g: poler(g, O, T, x, y, P["lelep_night"], grade=NIGHT), x, (T - T_OLD) / 2.6)
        rise_bubbles(f, T, 14)
        return f

    def kneeler(f, T, lamp_y):
        x, y = HOVER
        boat_back(f, x, y, T, wake=False)
        k = S("hero_old", "o_kneel")
        i = k.index(T, "pingpong")
        fx, fy = x + 6, y - 4
        k.draw(f, i, fx, fy, grade=NIGHT, bayer=bayer)
        hx, hy = k.point(i, "right", fx, fy)
        boat_front(f, x, y)
        if lamp_y is not None:
            line(f, (hx, hy), (HOVER[0] - 2, lamp_y - 6), ROPE)
            h, w = LAMP.shape[:2]
            stamp(f, LAMP, HOVER[0] - 2 - w / 2, lamp_y - 6)
            glow = np.hypot(X - HOVER[0] + 2, Y - lamp_y) + bayer * 8 < 9
            f[glow] = np.clip(f[glow] * np.array([1.5, 1.25, 0.9]), 0, 255).astype(np.uint8)
            stamp(f, LAMP, HOVER[0] - 2 - w / 2, lamp_y - 6)

    def lowering(T):
        f = P["lelep_night"]["day"].copy()
        lit_window(f, T)
        glint(f, T, SURFACE, (176, 196, 222))
        u = float(np.clip((T - T_LOWER) / (T_FINAL - T_LOWER), 0, 1))
        kneeler(f, T, 156 + (LAMP_END - 156) * u)
        rise_bubbles(f, T, 14)
        return f

    def lights_at(f, T, order=1):
        beat_len = 0.8
        for k, m in enumerate(WARM):
            if order > 0:
                u = (T - (T_FINAL + k * beat_len)) / 0.4
            else:
                u = ((T_FADE + (len(WARM) - 1 - k) * 0.28) - T) / 0.3 if k else 1.0
            if u > 0:
                keep = m & (bayer < min(u, 1.0))
                f[keep] = P["lelep_lit"]["day"][keep]

    def under_dance(f, T, fade=1.0):
        pl = P["lelep_lit"]
        for n, (folder, x, y, off) in enumerate(DANCERS):
            on = T_FINAL + (n % 8) * 0.8 + 0.2
            if T < on:
                continue
            spr = S(folder, "f_da" if n % 2 else "f_db")
            t = (T - on) + off * 0.4
            person(f, spr, spr.index(t, "loop"), x, y, pl, grade=UNDER, reveal=min(fade, (T - on) / 0.5), light=(x, y - 12, 22, UNDER_WARM))
        for folder, name, spot, off in (("hero", "h_da", (176, 240), 0), ("hero_wife", "w_da", (192, 240), 0)):
            spr = S(folder, name)
            t = (T - T_FINAL) + off
            person(f, spr, spr.index(t, "loop"), *spot, pl, grade=UNDER, reveal=min(fade, (T - T_FINAL) / 0.5), light=(spot[0], spot[1] - 12, 26, (1.05, 0.95, 0.82)))

    def final_wide(T):
        f = P["lelep_night"]["day"].copy()
        lights_at(f, T)
        glint(f, T, SURFACE, (176, 196, 222))
        under_dance(f, T)
        rise_bubbles(f, T, 40)
        if T < T_WIDE:
            line_y = None
            kneeler(f, T, LAMP_END)
        else:
            x, y = HOVER
            boat_back(f, x, y, T, wake=False)
            o = S("hero_old", "o_wave")
            o.draw(f, o.index(T, "pingpong"), x + 6, y - 5, grade=NIGHT, bayer=bayer)
            boat_front(f, x, y)
        return f

    def under_room(T):
        pl = P["omah_lelep"]
        f = pl["day"].copy()
        spot = (146, 256)
        glow = (118, 218, 60, (1.15, 0.98, 0.78))
        s = S("hero_wife", "wu_wave") if T >= beat(83.42) else S("hero_wife", "wu_front")
        person(f, s, s.index(T - T_CLOSE, "pingpong"), *spot, pl, grade=(0.72, 0.9, 0.96), sh=(16, 5), light=glow)
        stamp(f, SILL_LAMP, 110, 231 - SILL_LAMP.shape[0])
        rise_bubbles(f, T, 40, top=100, bottom=280)
        return f

    def last(T):
        f = P["lelep_night"]["day"].copy()
        lights_at(f, T, order=-1)
        u = max(0.0, 1 - (T - T_FADE) / 1.8)
        if u > 0:
            under_dance(f, T, fade=u)
        rise_bubbles(f, T, 10)
        kneeler(f, T, None)
        return f

    title = Image.new("RGB", (250, 50), INK)
    d = ImageDraw.Draw(title)
    d.fontmode = "1"
    big, small = ImageFont.truetype(font_path("msgothic.ttc"), 18), ImageFont.truetype(font_path("simsun.ttc"), 14)
    d.text((125 - big.getlength(brief["title"]) / 2, 7), brief["title"], font=big, fill=tuple(int(v) for v in paper))
    d.text((125 - small.getlength(brief["title_zh"]) / 2, 30), brief["title_zh"], font=small, fill=(214, 208, 196))
    title = np.asarray(title)
    state = {"last": None, "scene": None, "at": 0.0}

    def scene_at(T):
        if T < T_OMAH1:
            return "night", night_river
        if T < T_BACK:
            return "room1", lambda t: room(t, True)
        if T < T_GARIS:
            return "night", night_river
        if T < T_OMAH2:
            return "leaving", leaving
        if T < T_HIT:
            return "room2", lambda t: room(t, False)
        if T < T_DUSK:
            return "flood", flood
        if T < T_OLD:
            return "dusk", dusk
        if T < T_LOWER:
            return "old", old_row
        if T < T_FINAL:
            return "lower", lowering
        if T < T_CLOSE:
            return "final", final_wide
        if T < T_WIDE:
            return "under", under_room
        if T < T_FADE:
            return "final", final_wide
        return "last", last

    def draw(i, t, T):
        name, builder = scene_at(T)
        f = builder(T)
        if name != state["scene"]:
            state["scene"], state["at"] = name, T
        u = (T - state["at"]) / 0.2
        if u < 1 and state["last"] is not None:
            hide = bayer > u
            f[hide] = state["last"][hide]
        if 1.2 <= T < 7.2:
            h, w, _ = title.shape
            x0 = (G - w) // 2
            keep = bayer[6:6 + h, x0:x0 + w] < min(1, (T - 1.2) / 0.3, (7.2 - T) / 0.3)
            f[6:6 + h, x0:x0 + w][keep] = title[keep]
        caps.draw(f, T)
        if T < 0.6:
            f[bayer > T / 0.6] = paper
        left = ctx["end"] - T
        if left < 1.2:
            f[bayer > left / 1.2] = paper
        state["last"] = np.array(f, np.uint8)
        return f.astype(np.uint8)

    return draw
