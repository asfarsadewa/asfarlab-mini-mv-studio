# This Fire: a wildfire comes over the ridge toward a valley city. A forest warden burns his own village to stop it.
# He lights his own house first, climbs ahead of his fire, and the two fronts close around him on the key change.
# Each pixel holds the moment that it catches. The living plate and the burnt plate share one layout.
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pixkit import FIRE, INK, Captions, Fire, Occlusion, Sprite, bayer_field, contact_shadow, small_flame
from studio_paths import font_path

GLOW = np.array([1.5, 0.95, 0.55])
NIGHT = (0.72, 0.74, 0.95)
ASH_NIGHT = np.array([0.42, 0.38, 0.46])
SPARK = (255, 196, 96)
SMOKE = (52, 46, 50)
FLAKE = (206, 200, 196)

STAND = (180, 268)
DOORSTEP = (180, 240)
ALONG = (232, 252)
PATH = [(196, 171), (232, 160), (208, 142), (250, 128)]
RIDGE = (232, 133)
CROWD = [("folk_a", "f_acc_b", 132, 256), ("folk_b", "f_acc_b", 154, 250), ("folk_a", "f_acc_a", 208, 250), ("folk_b", "f_acc_a", 230, 256),
         ("folk_b", "f_acc_d", 134, 280), ("folk_a", "f_acc_c", 228, 280), ("folk_a", "f_acc_d", 158, 288), ("folk_b", "f_acc_c", 204, 288)]
STROLL = [("c_walk_r", 92, 262, 0.0), ("c_walk_l", 190, 256, 1.1), ("c_walk_r", 110, 272, 2.2), ("c_walk_l", 176, 270, 0.6)]
PARTY = [(96, 262), (120, 250), (146, 244), (108, 274), (136, 262), (164, 254), (130, 280), (158, 272), (184, 264), (174, 282)]


def in_square(x, y):
    """The open threshing square, as measured on the plate."""
    return np.hypot((x - 180) / 86, (y - 268) / 30) <= 1.0


def make(ctx):
    G, fps, brief, A, root = ctx["grid"], ctx["fps"], ctx["brief"], ctx["a"], ctx["root"]
    paper = np.array(brief["paper"], np.uint8)
    beats = np.array(A["beats"])
    rng = np.random.default_rng(41)
    bayer = bayer_field(G)
    Y, X = np.mgrid[:G, :G]
    caps = Captions(brief["lines"], paper, top_font=(font_path("simsun.ttc"), 16), low_font=(font_path("msgothic.ttc"), 12))
    shapes = json.loads((root / "occluders.json").read_text(encoding="utf-8"))

    def beat(t):
        return float(beats[np.argmin(np.abs(beats - t))])

    T_NIGHT, T_CITY1, T_COUNT, T_GATE, T_CURSE, T_DOOR, T_LEAVE = beat(12.9), beat(16.2), beat(19.3), beat(25.4), beat(31.8), beat(38.0), beat(44.5)
    T_LAST_WALK, T_HIT, T_CITY2, T_CLIMB, T_LOOK, T_MEET = beat(51.0), brief["hit"], beat(74.4), beat(78.2), beat(88.8), beat(94.7)
    T_SAFE, T_BLAME, T_TURN, T_KNEEL, T_PARTY, T_ALONE = beat(101.0), beat(104.0), beat(107.3), beat(109.5), beat(112.4), beat(117.2)

    def plate(name, occ):
        d = np.asarray(Image.open(root / f"plates/{name}-360.png").convert("RGB")).copy()
        is_paper = (np.abs(d.astype(int) - paper.astype(int)).sum(axis=2) < 24) | (d.astype(int).sum(axis=2) > 720)
        d[is_paper] = paper
        return {"name": name, "day": d, "paper": is_paper, "occ": Occlusion(root, occ)}

    P = {n: plate(n, "cun") for n in ("cun", "cun_night", "cun_ash")}
    P.update({n: plate(n, "kota") for n in ("kota", "kota_dawn")})
    P.update({n: plate(n, "rumah") for n in ("rumah", "rumah_open")})

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

    BUNDLE = prop("baoguo", 6)
    NIGHT_BUNDLE = BUNDLE.copy()
    NIGHT_BUNDLE[..., :3] = np.clip(BUNDLE[..., :3] * np.array(NIGHT) * 0.8, 0, 255).astype(np.uint8)

    def stamp(f, a, x0, y0):
        h, w = a.shape[:2]
        x0, y0 = int(x0), int(y0)
        ax0, ay0, ax1, ay1 = max(x0, 0), max(y0, 0), min(x0 + w, G), min(y0 + h, G)
        if ax0 >= ax1 or ay0 >= ay1:
            return
        part = a[ay0 - y0:ay1 - y0, ax0 - x0:ax1 - x0]
        solid = part[..., 3] > 0
        f[ay0:ay1, ax0:ax1][solid] = part[..., :3][solid]

    def clearance(name, x, y):
        solids = [o["footprint"] for o in shapes.get(name, []) if "footprint" in o]
        return min((np.hypot((x - cx) / rx, (y - cy) / ry) for cx, cy, rx, ry in solids), default=9.0)

    def guard(name, pts):
        low = float(min(clearance(name, x, y) for x, y in pts))
        print(f"Footprint clearance on {name}, with 1.0 at the object edge:", round(low, 2), flush=True)
        if low < 1.0:
            raise SystemExit(f"A person stands inside a solid object on {name}: {low:.2f}")
        off = [p for p in pts if not in_square(*p)]
        if off:
            raise SystemExit(f"A person leaves the square on {name}: {off[0]}")

    guard("cun", [STAND, DOORSTEP, ALONG] + [(c[2], c[3]) for c in CROWD])

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

    FLAME = np.array([(255, 250, 222), (255, 226, 120), (255, 170, 58), (236, 98, 34), (176, 52, 30)], np.uint8)

    def torch_flame(f, x, y, T, size):
        """A wrapped torch head with a teardrop flame on it. The flame tapers to a point at both ends."""
        r = max(1.0, size / 6)
        hx0, hx1, hy0, hy1 = int(x - r - 1), int(x + r + 2), int(y - r - 1), int(y + r + 2)
        for py in range(max(hy0, 0), min(hy1, G)):
            for px in range(max(hx0, 0), min(hx1, G)):
                d = np.hypot(px - x, (py - y) * 1.2)
                if d <= r + 0.3:
                    f[py, px] = (58, 38, 26) if d > r - 0.8 else (92, 62, 38)
        height = size * (1.0 + 0.12 * np.sin(T * 11) + 0.08 * np.sin(T * 17.3))
        base = y - r * 0.6
        for k in range(int(height)):
            u = k / height
            w = size * 0.3 * np.sin(np.pi * min(1.0, (u + 0.12) ** 0.8)) + 0.4
            lean = np.sin(T * 9 + k * 0.7) * u * size * 0.12
            py = int(base - k)
            if not 0 <= py < G:
                continue
            for px in range(int(x + lean - w), int(x + lean + w) + 1):
                if not 0 <= px < G:
                    continue
                edge = abs(px - x - lean) / max(w, 0.5)
                if u > 0.55 and bayer[py, px] < (u - 0.55) * 1.6 * edge + (u - 0.7) * 1.2:
                    continue
                level = u * 2.6 + edge * 1.8 + (bayer[py, px] - 0.5) * 0.9
                f[py, px] = FLAME[int(np.clip(level, 0, len(FLAME) - 1))]

    def torch(f, spr, i, x, y, T, size=7):
        """A wooden handle from the hand to the flame, so that the flame never floats."""
        tx, ty = spr.point(i, "tip", x, y)
        hx, hy = spr.point(i, "right", x, y)
        n = int(max(abs(tx - hx), abs(ty - hy), 1))
        for k in range(n + 1):
            px, py = int(hx + (tx - hx) * k / n), int(hy + (ty - hy) * k / n)
            if 0 <= px < G and 0 <= py < G:
                f[py, px] = (96, 64, 40)
                if size > 9 and px + 1 < G:
                    f[py, px + 1] = (72, 48, 30)
        torch_flame(f, tx, ty, T, size)

    # The moment that each pixel catches. His fire runs out from his house, then climbs slowly behind him.
    # The wildfire comes down from the top. They meet at one row on the ridge, on the key change.
    MEET_ROW = 135

    def burn_map():
        d = np.hypot(X - 180, (Y - 205) * 1.6)
        back = T_HIT + d / 150 * 14
        up = T_HIT + 14 + np.clip(175 - Y, 0, None) / (175 - MEET_ROW) * (T_MEET - T_HIT - 14)
        back = np.where(Y < 175, up, back)
        wild = T_MEET - np.clip(MEET_ROW - Y, 0, None) / (MEET_ROW - 85) * (T_MEET - 72)
        m = np.where(Y < MEET_ROW, wild, back)
        wob = np.sin(X / 17.0 + Y / 29.0) * np.sin(X / 31.0 - Y / 13.0) * 1.4
        return m + wob + rng.random((G, G)) * 1.1

    BURN = burn_map()
    ground = ~P["cun_night"]["paper"]
    night = P["cun_night"]["day"]
    ash = np.clip(P["cun_ash"]["day"] * ASH_NIGHT, 0, 255).astype(np.uint8)
    ash[P["cun_ash"]["paper"]] = paper
    FIRE_PX = np.array(FIRE, np.uint8)

    def burning(T):
        since = T - BURN
        f = night.copy()
        # Light comes before the fire.
        near = (since > -3.2) & (since < 0) & ground
        k = (1 + since[near] / 3.2)[..., None] * (GLOW - 1) + 1
        f[near] = np.clip(f[near] * k, 0, 255).astype(np.uint8)
        done = since >= 0
        f[done] = ash[done]
        # The fire front, then embers that die away.
        front = (since >= 0) & (since < 0.8) & ground
        idx = np.clip(((0.8 - since) / 0.8 * (len(FIRE) - 1) + (bayer - 0.5) * 8).astype(int), 0, len(FIRE) - 1)
        keep = front & (bayer < 0.62)
        f[keep] = FIRE_PX[idx][keep]
        ember = (since >= 0.8) & (since < 7) & ground & (np.roll(speck, int(T * 3), axis=1) > 0.988 + since * 0.0015)
        f[ember] = SPARK
        return f

    speck = rng.random((G, G))

    # Flames stand on the houses and through the forest. Each one burns for a few seconds when its pixel catches.
    def flame_sites():
        out = []
        for x, y in [(180, 212), (152, 214), (208, 214), (108, 224), (252, 222), (78, 240), (292, 246), (98, 278), (268, 278)]:
            out.append((x, y, 62, 44, 7.5))
        pts = np.argwhere(ground & (Y < 200) & (Y > 86))
        for k in rng.choice(len(pts), 46, replace=False):
            y, x = pts[k]
            out.append((int(x), int(y), 40, 26, 4.5))
        out.sort(key=lambda s: s[1])
        return [{"x": x, "y": y, "at": float(BURN[y, x]), "life": life, "fire": Fire(rng, height=h, width=w)} for x, y, h, w, life in out]

    SITES = flame_sites()
    WILD = [{"x": x, "y": y, "fire": Fire(rng, height=38, width=30)} for x, y in [(206, 106), (232, 92), (262, 84), (290, 104), (316, 134)]]
    WALL = [{"x": x, "y": MEET_ROW + (k % 3) * 5, "fire": Fire(rng, height=92, width=56)} for k, x in enumerate(range(116, 322, 29))]
    smoke = []
    sparks = []
    last_t = {"t": -1.0}

    def advance_air(T, sources):
        dt = 1 / fps
        for x, y in sources:
            if rng.random() < 0.3:
                smoke.append([x + rng.uniform(-6, 6), y - 18, rng.uniform(2, 7), rng.uniform(-20, -12), 2.0, rng.uniform(2.0, 3.6)])
            if rng.random() < 0.5:
                sparks.append([x + rng.uniform(-8, 8), y - 12, rng.uniform(3, 14), rng.uniform(-34, -14), rng.uniform(0.5, 1.4)])
        for s in smoke:
            s[0] += s[2] * dt
            s[1] += s[3] * dt
            s[4] += dt * 3.8
            s[5] -= dt
        for s in sparks:
            s[0] += s[2] * dt
            s[1] += s[3] * dt
            s[4] -= dt
        smoke[:] = [s for s in smoke if s[5] > 0 and s[1] > -12][-170:]
        sparks[:] = [s for s in sparks if s[4] > 0]

    def draw_air(f):
        for x, y, _, _, r, life in smoke:
            x0, x1, y0, y1 = max(int(x - r), 0), min(int(x + r) + 1, G), max(int(y - r), 0), min(int(y + r) + 1, G)
            if x0 >= x1 or y0 >= y1:
                continue
            yy, xx = np.mgrid[y0:y1, x0:x1]
            dist = np.hypot(xx - x, yy - y) / max(r, 1)
            m = bayer[y0:y1, x0:x1] + speck[y0:y1, x0:x1] * 0.35 < (1 - dist) * min(0.7, life / 2.2)
            f[y0:y1, x0:x1][m] = SMOKE
        for x, y, _, _, _ in sparks:
            if 0 <= x < G and 0 <= y < G:
                f[int(y), int(x)] = SPARK

    def fire_draw(fire, f, ox, oy, band=9):
        """Draws a flame with a ragged base. The flame thins into the burning ground. It never ends in a flat line."""
        h, w = fire.v.shape
        x0, x1, y0, y1 = max(ox - w // 2, 0), min(ox - w // 2 + w, G), max(oy - h, 0), min(oy, G)
        if x0 >= x1 or y0 >= y1:
            return
        tmp = f[y0:y1, x0:x1].copy()
        fire.draw(f, ox, oy)
        drawn = (f[y0:y1, x0:x1] != tmp).any(axis=2)
        rows = np.arange(y0, y1)[:, None]
        cols = np.arange(x0, x1)[None, :]
        rise = (oy - rows) / band + (1 - np.abs(cols - ox) / (w / 2)) * 0.35
        keep = bayer[y0:y1, x0:x1] + speck[y0:y1, x0:x1] * 0.3 < rise
        back = drawn & ~keep
        f[y0:y1, x0:x1][back] = tmp[back]

    def flames(f, T, heat_scale=1.0, below=None, above=None):
        """Draws the flames that are burning now, in row order."""
        sources = []
        for s in SITES:
            age = T - s["at"]
            if 0 <= age < s["life"] + 1.5:
                if below is not None and s["y"] > below or above is not None and s["y"] <= above:
                    continue
                heat = 34 * heat_scale if age < s["life"] else 0
                s["fire"].step(int(heat), 3)
                fire_draw(s["fire"], f, s["x"], s["y"])
                sources.append((s["x"], s["y"]))
        return sources

    def wild_fire(f, T):
        """The wildfire stands on the ridge before it comes down."""
        heat = int(np.clip((T - T_NIGHT) / 6, 0.3, 1) * 30)
        for s in WILD:
            s["fire"].step(heat, 3)
            fire_draw(s["fire"], f, s["x"], s["y"])
        if T > T_NIGHT:
            fade = np.clip(1 - np.hypot(X - 256, (Y - 96) * 1.3) / 74, 0, 1)
            halo = (bayer + speck * 0.2 < fade * 0.5) & P["cun_night"]["paper"]
            f[halo] = (236, 150, 92)
        return [(s["x"], s["y"]) for s in WILD]

    def walkers(f, T, pl, grade=None):
        for k, (folder, name, a, b, t0, dur) in enumerate(VILLAGE):
            s = S(folder, name)
            u = ((T + t0) % dur) / dur
            i, x, y = walk_between(s, a, b, 0, 1, u)
            person(f, s, i, x, y, pl, grade=grade, reveal=min(1.0, min(u, 1 - u) / 0.06))

    VILLAGE = [("folk_a", "f_walk_r", (112, 262), (246, 262), 0.0, 13.0), ("folk_b", "f_walk_l", (250, 276), (116, 276), 4.0, 12.0), ("folk_a", "f_walk_l", (240, 252), (118, 252), 8.0, 12.0)]

    def dusk(T):
        pl = P["cun"]
        f = pl["day"].copy()
        walkers(f, T, pl)
        s = S("hero", "h_walk_r")
        if T < 7.4:
            i, x, y = walk_between(s, (126, 268), (188, 268), 0.0, 7.4, T)
            person(f, s, i, x, y, pl)
        else:
            b = S("hero", "h_back")
            person(f, b, b.index(T, "pingpong"), 188, 268, pl)
        # A thin smoke far behind the ridge.
        if T > 7.0:
            advance_air(T, [(262, 84)] if rng.random() < 0.25 else [])
            draw_air(f)
        return f

    def night_watch(T):
        pl = P["cun_night"]
        f = night.copy()
        src = wild_fire(f, T)
        advance_air(T, src)
        draw_air(f)
        walkers(f, T, pl, grade=NIGHT)
        b = S("hero", "h_back")
        person(f, b, b.index(T, "pingpong"), 188, 268, pl, grade=NIGHT)
        return f

    def counting(T):
        # He walks one way, then the other. There is no way out.
        pl = P["cun_night"]
        f = night.copy()
        src = wild_fire(f, T)
        advance_air(T, src)
        draw_air(f)
        mid = T_COUNT + (T_GATE - T_COUNT) / 2
        if T < mid:
            s = S("hero", "h_walk_l")
            i, x, y = walk_between(s, (188, 268), (126, 268), T_COUNT, mid, T)
        else:
            s = S("hero", "h_walk_r")
            i, x, y = walk_between(s, (126, 268), (216, 268), mid, T_GATE, T)
        person(f, s, i, x, y, pl, grade=NIGHT)
        return f

    def city(T):
        pl = P["kota"]
        f = pl["day"].copy()
        for name, x, y, ph in STROLL:
            s = S("folk_c", name)
            u = ((T + ph) % 7.0) / 7.0
            d = 60 if "_r" in name else -60
            i, px, py = walk_between(s, (x, y), (x + d, y), 0, 1, u)
            person(f, s, i, px, py, pl, sh=(4, 1), reveal=min(1.0, min(u, 1 - u) / 0.08))
        # The sparks from the mountain cross above the town.
        for k in range(26):
            sx = int((T * (18 + k % 7) + k * 37) % G)
            sy = int(60 + (k * 53) % 90 + np.sin(T + k) * 6)
            f[sy, sx] = SPARK
        return f

    def gate(T):
        pl = P["rumah"]
        f = pl["day"].copy()
        s = S("hero", "hz_idle")
        i = s.index(T, "pingpong")
        person(f, s, i, 180, 276, pl, sh=(16, 5), light=(180, 232, 40, (1.15, 0.98, 0.76)))
        torch(f, s, i, 180, 276, T, 15)
        return f

    def door(T):
        s = S("hero", "hz_door")
        u = (T - T_DOOR) * s.fps
        i = min(int(u), s.n - 1)
        pl = P["rumah_open"] if i > s.n * 0.42 else P["rumah"]
        f = pl["day"].copy()
        person(f, s, i if u < s.n else s.n - 1 - int(u - s.n) % 8, 180, 268, pl, sh=(16, 5), light=(180, 232, 40, (1.15, 0.98, 0.76)))
        torch(f, s, i, 180, 268, T, 15)
        return f

    def cursing(T):
        pl = P["cun_night"]
        f = night.copy()
        src = wild_fire(f, T)
        advance_air(T, src)
        draw_air(f)
        order = sorted(CROWD + [("hero", "ht_front", STAND[0], STAND[1])], key=lambda c: c[3])
        for k, (folder, name, x, y) in enumerate(order):
            s = S(folder, name)
            if folder == "hero":
                i = s.index(T, "pingpong")
                person(f, s, i, x, y, pl, grade=NIGHT, light=(x, y - 22, 16, (1.2, 1.0, 0.78)))
                torch(f, s, i, x, y, T)
            else:
                person(f, s, s.index(T + k * 0.53, "pingpong"), x, y, pl, grade=NIGHT)
        return f

    def leaving(T):
        pl = P["cun_night"]
        f = night.copy()
        src = wild_fire(f, T)
        advance_air(T, src)
        draw_air(f)
        h = S("hero", "ht_idle")
        i = h.index(T, "pingpong")
        person(f, h, i, *STAND, pl, grade=NIGHT)
        torch(f, h, i, *STAND, T)
        for k, (folder, _, x, y) in enumerate(CROWD):
            name = "f_carry_a" if x > 180 else "f_carry_b"
            s = S(folder, name)
            # Everyone moves from the first frame. A longer way out makes a later exit.
            t0 = T_LEAVE
            t1 = t0 + np.hypot(x - 180, y - 296) / 16 + k * 0.3
            if T >= t1:
                continue
            i2, px, py = walk_between(s, (x, y), (180 + (k - 4) * 2, 296), t0, t1, T)
            person(f, s, i2, px, py, pl, grade=NIGHT, reveal=min(1.0, (t1 - T) / 0.5))
            hx, hy = s.point(i2, "left", px, py)
            stamp(f, NIGHT_BUNDLE, hx - 3, hy - 2)
        return f

    def last_walk(T):
        pl = P["cun_night"]
        f = night.copy()
        src = wild_fire(f, T)
        advance_air(T, src)
        draw_air(f)
        s = S("hero", "ht_walk")
        t1 = T_HIT - 0.8
        if T < t1:
            i, x, y = walk_between(s, STAND, DOORSTEP, T_LAST_WALK, t1, T)
            person(f, s, i, x, y, pl, grade=NIGHT)
            torch(f, s, i, x, y, T)
        else:
            c = S("hero", "ht_crouch")
            i = c.index(T - t1, "pingpong")
            person(f, c, i, *DOORSTEP, pl, grade=NIGHT)
            torch(f, c, i, *DOORSTEP, T)
        return f

    def hero_in_fire(f, T):
        pl = P["cun_night"]
        light = None
        if T < T_HIT + 6.4:
            s = S("hero", "ht_crouch")
            i = s.index(T - T_HIT, "pingpong")
            x, y = DOORSTEP
        elif T < T_HIT + 12:
            s = S("hero", "ht_walk_r")
            i, x, y = walk_between(s, DOORSTEP, ALONG, T_HIT + 6.4, T_HIT + 12, T)
        elif T < T_CITY2:
            s = S("hero", "ht_idle")
            i = s.index(T, "pingpong")
            x, y = ALONG
        elif T < T_LOOK:
            # He climbs just ahead of his own fire.
            legs = [np.hypot(PATH[k + 1][0] - PATH[k][0], PATH[k + 1][1] - PATH[k][1]) for k in range(3)]
            legs.append(np.hypot(RIDGE[0] - PATH[3][0], RIDGE[1] - PATH[3][1]))
            total, walked, stops = sum(legs), (T - T_CLIMB) / (T_LOOK - T_CLIMB), PATH + [RIDGE]
            walked = float(np.clip(walked, 0, 1)) * total
            k = 0
            while k < 3 and walked > legs[k]:
                walked -= legs[k]
                k += 1
            s = S("hero", "ht_up_r" if stops[k + 1][0] > stops[k][0] else "ht_up_l")
            i, x, y = walk_between(s, stops[k], stops[k + 1], 0, legs[k], walked)
        else:
            s = S("hero", "ht_idle")
            i = s.index(T, "pingpong")
            x, y = RIDGE
        return s, i, x, y

    def fire_scene(T):
        pl = P["cun_night"]
        f = burning(T)
        s, i, x, y = hero_in_fire(None, T)
        src = flames(f, T, below=y) + wild_fire(f, T)
        contact_shadow(f, x, y, 6, 2, 0.8, bayer, ground, 2)
        s.draw(f, i, x, y, grade=(1.3, 1.08, 0.86), bayer=bayer, occ=pl["occ"] if y > 200 else None)
        torch(f, s, i, x, y, T)
        src += flames(f, T, above=y)
        advance_air(T, src[:24])
        draw_air(f)
        return f

    def collide(T):
        # The fronts meet. A wall stands along the ridge, and he is inside it.
        f = burning(T)
        age = T - T_MEET
        heat = int(np.clip(36 - max(age - 3.2, 0) * 12, 0, 36))
        src = []
        for s in WALL:
            s["fire"].step(heat, 2 if age < 3.2 else 4)
            fire_draw(s["fire"], f, s["x"], s["y"])
            src.append((s["x"], s["y"] - 40))
        src += flames(f, T)
        advance_air(T, src[:18])
        draw_air(f)
        if age < 0.7:
            flash = bayer < 1 - age / 0.7
            f[flash] = (255, 236, 196)
        return f

    def blame(T):
        pl = P["cun_ash"]
        f = pl["day"].copy()
        falling(f, T, 30)
        h = S("hero", "h_front")
        items = sorted(CROWD + [("hero", "h_front", STAND[0], STAND[1])], key=lambda c: c[3])
        for k, (folder, name, x, y) in enumerate(items):
            s = S(folder, name)
            if folder == "hero":
                person(f, s, s.index(T, "pingpong"), x, y, pl)
            elif T < T_TURN:
                person(f, s, s.index(T + k * 0.53, "pingpong"), x, y, pl)
            else:
                c = S(folder, "f_carry_a" if x > 180 else "f_carry_b")
                t1 = T_TURN + np.hypot(x - 180, y - 296) / 16
                if T < t1:
                    i, px, py = walk_between(c, (x, y), (180, 296), T_TURN, t1, T)
                    person(f, c, i, px, py, pl, reveal=min(1.0, (t1 - T) / 0.5))
        return f

    def kneeling(T):
        pl = P["cun_ash"]
        f = pl["day"].copy()
        falling(f, T, 44)
        s = S("hero", "h_kneel")
        i = int((T - T_KNEEL) * s.fps)
        last = s.n - 1
        hold = i if i < last else last - int((i - last) / 2) % 24
        person(f, s, hold, *STAND, pl)
        return f

    def blame_kneel(T):
        if T < T_KNEEL:
            return blame(T)
        f = blame(T)
        # The crowd is still leaving behind him when his knees go.
        pl = P["cun_ash"]
        clean = kneeling(T)
        return clean if T > T_TURN + 3.4 else f

    def party(T):
        pl = P["kota_dawn"]
        f = pl["day"].copy()
        for k, (x, y) in enumerate(PARTY):
            s = S("folk_c", "c_cheer" if k % 2 else "c_da")
            person(f, s, s.index(T + k * 0.4, "loop"), x, y, pl, sh=(4, 1))
        return f

    flakes = [[rng.uniform(0, G), rng.uniform(40, 330), rng.uniform(5, 13), rng.uniform(0, 6)] for _ in range(70)]

    def falling(f, T, n):
        for x, y, speed, ph in flakes[:n]:
            py = int(40 + (y + T * speed) % 300)
            px = int((x + np.sin(T * 0.8 + ph) * 8 + T * 3) % G)
            f[py, px] = FLAKE if not (f[py, px] == paper).all() else (176, 170, 168)

    title = Image.new("RGB", (210, 52), INK)
    d = ImageDraw.Draw(title)
    d.fontmode = "1"
    big, small = ImageFont.truetype(font_path("simsun.ttc"), 26), ImageFont.truetype(font_path("msgothic.ttc"), 12)
    d.text((105 - big.getlength(brief["title"]) / 2, 5), brief["title"], font=big, fill=tuple(int(v) for v in paper))
    d.text((105 - small.getlength(brief["title_id"]) / 2, 35), brief["title_id"], font=small, fill=(214, 208, 196))
    title = np.asarray(title)
    state = {"last": None, "scene": None, "at": 0.0}

    def scene_at(T):
        for end, name, fn in ((T_NIGHT, "dusk", dusk), (T_CITY1, "watch", night_watch), (T_COUNT, "city", city), (T_GATE, "count", counting), (T_CURSE, "gate", gate), (T_DOOR, "curse", cursing), (T_LEAVE, "door", door), (T_LAST_WALK, "leave", leaving), (T_HIT, "walk", last_walk), (T_CITY2, "fire", fire_scene), (T_CLIMB, "city2", city), (T_MEET, "fire2", fire_scene), (T_SAFE, "collide", collide), (T_BLAME, "safe", city), (T_PARTY, "blame", blame_kneel), (T_ALONE, "party", party)):
            if T < end:
                return name, fn
        return "alone", kneeling

    def draw(i, t, T):
        name, builder = scene_at(T)
        f = builder(T)
        if name != state["scene"]:
            state["scene"], state["at"] = name, T
        u = (T - state["at"]) / 0.2
        if u < 1 and state["last"] is not None:
            hide = bayer > u
            f[hide] = state["last"][hide]
        if 1.2 <= T < 8.0:
            h, w, _ = title.shape
            x0 = (G - w) // 2
            keep = bayer[6:6 + h, x0:x0 + w] < min(1, (T - 1.2) / 0.3, (8.0 - T) / 0.3)
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
