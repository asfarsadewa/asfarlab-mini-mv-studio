# Sound the Bugle: autumn 1934, southern Jiangxi. A boy's mother weaves straw sandals for the passing column.
# At the village gate he decides. He becomes the column's bugler, and each chorus is his call that gathers them on.
# At dawn on a snow pass he sounds the call, and the column rises past him. His mother waits at the empty gate.
# The plate never moves. Footprints guard every path. Every walker faces the way that it moves.
import json
import numpy as np
from scipy import ndimage
from PIL import Image, ImageDraw, ImageFont
from pixkit import INK, Captions, Occlusion, Sprite, bayer_field, contact_shadow, small_flame
from studio_paths import font_path

RED = np.array([186, 44, 36])
LEAF = [(196, 64, 36), (222, 120, 40), (232, 170, 60)]
SNOW = (236, 240, 248)
NIGHT = (0.62, 0.66, 0.9)
DAWN = (1.0, 0.9, 0.94)
DUSK = (1.02, 0.86, 0.74)

# The village road, from the hill at the back to the gate at the front.
ROAD = [(300, 140), (272, 168), (262, 190), (240, 210), (200, 228), (150, 240), (112, 250), (84, 262)]
PLAZA = (150, 242)
# The snow trail, from the foot of the pass to the saddle.
TRAIL = [(120, 252), (175, 232), (140, 220), (195, 205), (155, 188), (205, 172), (165, 158), (190, 145)]
SADDLE = (190, 140)
SUMMIT = [(160, 150), (176, 146), (206, 146), (222, 152), (150, 160), (234, 160)]
MOTHER_SEAT, BOY_GATE, ARCH = (118, 252), (204, 258), (178, 222)


def make(ctx):
    G, fps, brief, A, root = ctx["grid"], ctx["fps"], ctx["brief"], ctx["a"], ctx["root"]
    paper = np.array(brief["paper"], np.uint8)
    beats = np.array(A["beats"])
    rng = np.random.default_rng(1934)
    bayer = bayer_field(G)
    Y, X = np.mgrid[:G, :G]
    caps = Captions(brief["lines"], paper, top_font=(font_path("simsun.ttc"), 16), low_font=(font_path("msgothic.ttc"), 12))
    shapes = json.loads((root / "occluders.json").read_text(encoding="utf-8"))

    def beat(t):
        return float(beats[np.argmin(np.abs(beats - t))])

    T_GATE, T_TURN, T_HIT, T_RUN, T_SNOW, T_KNEEL, T_NIGHT, T_HOME1, T_CLIMB, T_FINAL, T_TOGETHER, T_END = (
        beat(25.4), beat(32.2), brief["hit"], beat(39.1), beat(49.6), beat(63.3), beat(69.6), beat(75.8), beat(80.2), beat(84.1), beat(96.6), beat(99.8))

    def plate(name):
        d = np.asarray(Image.open(root / f"plates/{name}-360.png").convert("RGB")).copy()
        # Pale pixels count as paper only where they connect to the frame edge. Bright snow inside the island stays snow.
        pale = (np.abs(d.astype(int) - paper.astype(int)).sum(axis=2) < 24) | (d.astype(int).sum(axis=2) > 720)
        lab, _ = ndimage.label(pale)
        edge = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
        is_paper = np.isin(lab, edge[edge > 0])
        d[is_paper] = paper
        return {"name": name, "day": d, "paper": is_paper, "occ": Occlusion(root, name)}

    P = {n: plate(n) for n in ("cun", "men", "xue")}

    def graded(pl, k):
        out = np.clip(pl["day"] * np.array(k), 0, 255).astype(np.uint8)
        out[pl["paper"]] = paper
        return out

    sprites = {}

    def S(folder, name):
        if (folder, name) not in sprites:
            sprites[(folder, name)] = Sprite(root, name, folder)
        return sprites[(folder, name)]

    raw = Image.open(root / "plates/laba-raw.png").convert("RGBA")
    raw = raw.crop(raw.getchannel("A").point(lambda v: 255 if v > 127 else 0).getbbox())

    def bugle_prop(width):
        a = np.asarray(raw.resize((width, max(2, int(raw.height * width / raw.width))), Image.BOX)).copy()
        a[..., 3] = (a[..., 3] > 110) * 255
        return a

    BUGLE_S, BUGLE_L = bugle_prop(9), bugle_prop(22)

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

    guard("men", [MOTHER_SEAT, BOY_GATE, ARCH])
    guard("cun", [PLAZA])
    checked = set()

    def heading(spr, dx, dy):
        """Stops the render if a clip walks against its path. A backward walker reads as a moonwalk."""
        if spr.name in checked or np.hypot(dx, dy) < 8:
            return
        p0, p1 = spr.path(0), spr.path(spr.n - 1)
        if (p1[0] - p0[0]) * dx + (p1[1] - p0[1]) * dy < 0:
            raise SystemExit(f"{spr.name} walks against its path. Bake it 180 degrees around.")
        checked.add(spr.name)

    def stride(spr):
        p0, p1 = spr.path(0), spr.path(spr.n - 1)
        return max(np.hypot(p1[0] - p0[0], p1[1] - p0[1]), 1.0)

    def walk_between(spr, a, b, t0, t1, T):
        heading(spr, b[0] - a[0], b[1] - a[1])
        u = float(np.clip((T - t0) / (t1 - t0), 0, 1))
        walked = u * np.hypot(b[0] - a[0], b[1] - a[1])
        return int(walked / stride(spr) * (spr.n - 1)) % spr.n, a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u

    def along(points, u):
        legs = [np.hypot(points[k + 1][0] - points[k][0], points[k + 1][1] - points[k][1]) for k in range(len(points) - 1)]
        d = u * sum(legs)
        for k, leg in enumerate(legs):
            if d <= leg or k == len(legs) - 1:
                v = min(d / max(leg, 1e-6), 1.0)
                return points[k][0] + (points[k + 1][0] - points[k][0]) * v, points[k][1] + (points[k + 1][1] - points[k][1]) * v, k, sum(legs)
            d -= leg

    def person(f, spr, i, x, y, pl, grade=None, sh=(5, 2), reveal=1.0, light=None, occ=True):
        if sh:
            contact_shadow(f, x, y, sh[0], sh[1], 0.8, bayer, ~pl["paper"], 2, occ=pl["occ"] if occ else None)
        spr.draw(f, i, x, y, occ=pl["occ"] if occ else None, grade=grade, bayer=bayer, reveal=reveal, light=light)

    def flag(f, spr, i, x, y, T, grade):
        """A plain red flag on a pole in the right hand. It carries no emblem."""
        hx, hy = spr.point(i, "right", x, y)
        hx, hy = int(hx), int(hy)
        for py in range(hy - 22, hy + 8):
            if 0 <= py < G and 0 <= hx < G:
                f[py, hx] = (74, 54, 38)
        for cx in range(11):
            wave = np.sin(T * 6.0 - cx * 0.7) * (cx / 11) * 2.0
            for cy in range(7):
                px, py = hx + 1 + cx, int(hy - 22 + cy + wave)
                if 0 <= px < G and 0 <= py < G:
                    shade = 0.78 + 0.22 * np.sin(T * 6.0 - cx * 0.7 + 1.2)
                    f[py, px] = np.clip(RED * np.array(grade) * shade, 0, 255).astype(np.uint8)

    def blow(f, spr, i, x, y, big=False):
        """The bugle at his mouth. It points to screen right, toward the light."""
        hx, hy = spr.point(i, "right", x, y)
        a = BUGLE_L if big else BUGLE_S
        stamp(f, a, hx - 2, hy - a.shape[0] / 2 - (6 if big else 2))

    def blown(T, t0):
        """He holds the call on the beat and lowers it between phrases."""
        return (T - t0) % 3.7 < 2.8

    # A column marches along a path. Each soldier walks with the frames that his distance needs.
    def column(T, path, names, speed, n, flags, grade, start=0.0, pl=None, spacing=0.09):
        out = []
        for k in range(n):
            u = (start + T * speed - k * spacing) % 1.0
            x, y, leg, total = along(path, u)
            a, b = path[leg], path[leg + 1]
            right = b[0] >= a[0]
            name = names[(1 if k in flags else 0) * 2 + (0 if right else 1)] if len(names) == 4 else names[1 if k in flags else 0]
            s = S("soldier", name)
            heading(s, b[0] - a[0], b[1] - a[1])
            i = int(u * total / stride(s) * (s.n - 1)) % s.n
            out.append((y, s, i, x, min(1.0, min(u, 1 - u) / 0.06), k in flags))
        return out

    leaves = [[rng.uniform(0, G), rng.uniform(40, 330), rng.uniform(5, 11), rng.uniform(0, 6), k % 3] for k in range(46)]

    def falling_leaves(f, T, n):
        for x, y, sp, ph, c in leaves[:n]:
            py = int(60 + (y + T * sp) % 270)
            px = int((x + np.sin(T * 0.9 + ph) * 10 + T * 4) % G)
            f[py, px] = LEAF[c]

    flakes = [[rng.uniform(0, G), rng.uniform(30, 320), rng.uniform(8, 18), rng.uniform(0, 6)] for _ in range(90)]

    def snowfall(f, T, n):
        for x, y, sp, ph in flakes[:n]:
            py = int(30 + (y + T * sp) % 290)
            px = int((x + np.sin(T * 1.3 + ph) * 6 + T * 9) % G)
            f[py, px] = SNOW

    def draw_people(f, people, pl, grade, T):
        for y, s, i, x, rev, has_flag in sorted(people, key=lambda p: p[0]):
            person(f, s, i, x, y, pl, grade=grade, reveal=rev)
            if has_flag and rev > 0.5:
                flag(f, s, i, x, y, T, grade)

    # The village in autumn. The column comes over the hill and through the village.
    def village(T):
        pl = P["cun"]
        f = pl["day"].copy()
        falling_leaves(f, T, 30)
        people = []
        for k, (name, a, b, ph) in enumerate((("a_walk_r", (128, 244), (216, 226), 0.0), ("a_walk_l", (226, 214), (140, 238), 3.0))):
            s = S("folk_a", name)
            span = 9.0
            u = ((T + ph) % span) / span
            i, x, y = walk_between(s, a, b, 0, 1, u)
            people.append((y, s, i, x, min(1.0, min(u, 1 - u) / 0.08), False))
        if T >= 19.0:
            people += column(T - 19.0, ROAD, ["s_march", "s_flag"], 0.028, 6, {0, 4}, (1, 1, 1), spacing=0.1)
        draw_people(f, people, pl, (1, 1, 1), T)
        return f

    def gate(T):
        pl = P["men"]
        f = pl["day"].copy()
        falling_leaves(f, T, 22)
        light = None
        m = S("folk_b", "m_crouch" if T < 28.6 else ("m_give" if T < T_TURN + 0.6 else "m_idle"))
        mi = m.index(T, "pingpong") if m.name.endswith("m_crouch") or m.name.endswith("m_idle") else min(int((T - 28.6) * m.fps), 18) + int((T - 28.6) * m.fps * 0.4) % 6
        person(f, m, min(mi, m.n - 1), *MOTHER_SEAT, pl, sh=(14, 4))
        if T < T_TURN:
            b = S("hero", "y_take" if T >= 29.6 else "y_front30")
            bi = min(int((T - 29.6) * b.fps), 18) + int((T - 29.6) * b.fps * 0.4) % 6 if T >= 29.6 else b.index(T, "pingpong")
            person(f, b, min(bi, b.n - 1), *BOY_GATE, pl, sh=(14, 4))
        else:
            b = S("hero", "y_gate")
            t1 = T_HIT - 0.3
            i, x, y = walk_between(b, BOY_GATE, ARCH, T_TURN, t1, T)
            person(f, b, i, x, y, pl, sh=(14, 4), reveal=min(1.0, (t1 - T) / 0.8))
        return f

    def chorus(T):
        pl = P["cun"]
        f = pl["day"].copy()
        falling_leaves(f, T, 30)
        people = column(T - 19.0, ROAD, ["s_march", "s_flag"], 0.028, 6, {0, 4}, (1, 1, 1), spacing=0.1)
        if T < T_RUN:
            s = S("hero", "y_bugle")
            i = min(int((T - T_HIT) * s.fps), 8) + (int((T - T_HIT) * s.fps * 0.5) % 10 if T - T_HIT > 0.4 else 0)
            person(f, s, min(i, s.n - 1), *PLAZA, pl)
            if blown(T, T_HIT):
                blow(f, s, min(i, s.n - 1), *PLAZA)
        else:
            # He runs to the tail of the column, then marches with it out of the gate.
            tail_u = ((T - 19.0) * 0.028 - 5 * 0.1) % 1.0 - 0.1
            x_t, y_t, _, total = along(ROAD, max(tail_u, 0.0))
            if T < T_RUN + 2.4:
                s = S("hero", "y_run")
                i, x, y = walk_between(s, PLAZA, (x_t, y_t), T_RUN, T_RUN + 2.4, T)
            else:
                s = S("hero", "y_march")
                u = max(tail_u, 0.0)
                x, y = x_t, y_t
                i = int(u * total / stride(s) * (s.n - 1)) % s.n
            people.append((y, s, i, x, min(1.0, max(0.0, (88 - 0) / 1)), False))
        draw_people(f, people, pl, (1, 1, 1), T)
        return f

    def snow(T, night=0.0, dawn=0.0):
        pl = P["xue"]
        k = np.array((1, 1, 1)) * (1 - night - dawn) + np.array(NIGHT) * night + np.array(DAWN) * dawn
        f = graded(pl, k)
        return f, pl, tuple(k)

    def pass_climb(T):
        f, pl, k = snow(T)
        snowfall(f, T, 60)
        people = column(T - T_SNOW, TRAIL, ["s_up_r", "s_up_l", "s_flag_up_r", "s_flag_up_l"], 0.022, 6, {1}, k, start=0.55, spacing=0.11)
        # The boy walks among them. He falls to his knees once, and the column passes him.
        u = (0.55 + (T - T_SNOW) * 0.022 - 3.5 * 0.11)
        if T_KNEEL <= T < T_KNEEL + 4.2:
            u = 0.55 + (T_KNEEL - T_SNOW) * 0.022 - 3.5 * 0.11
            x, y, leg, total = along(TRAIL, u % 1.0)
            s = S("hero", "y_kneel")
            people.append((y, s, min(int((T - T_KNEEL) * s.fps), s.n - 1), x, 1.0, False))
        else:
            if T >= T_KNEEL + 4.2:
                u -= 4.2 * 0.022
            x, y, leg, total = along(TRAIL, u % 1.0)
            a, b = TRAIL[leg], TRAIL[leg + 1]
            s = S("hero", "y_up_r" if b[0] >= a[0] else "y_up_l")
            heading(s, b[0] - a[0], b[1] - a[1])
            people.append((y, s, int(u * total / stride(s) * (s.n - 1)) % s.n, x, 1.0, False))
        draw_people(f, people, pl, k, T)
        return f

    def camp(T):
        f, pl, k = snow(T, night=1.0)
        snowfall(f, T, 30)
        fire = (176, 214)
        glow = (np.hypot(X - fire[0], (Y - fire[1]) * 1.3) + bayer * 18 < 40) & ~pl["paper"]
        f[glow] = np.clip(f[glow] * np.array([1.5, 1.2, 0.85]), 0, 255).astype(np.uint8)
        people = []
        for n, (x, y) in enumerate(((204, 210), (150, 206), (196, 226))):
            s = S("soldier", "s_sit")
            people.append((y, s, s.index(T + n, "pingpong"), x, 1.0, False))
        s = S("hero", "y_sit")
        people.append((216, s, s.index(T, "pingpong"), 156, 1.0, False))
        for y, sp, i, x, rev, _ in sorted(people, key=lambda p: p[0]):
            person(f, sp, i, x, y, pl, grade=k, light=(fire[0], fire[1] - 6, 30, (1.35, 1.1, 0.8)))
        small_flame(f, fire[0], fire[1], T, 9)
        return f

    def mother_alone(T, end=False):
        pl = P["men"]
        f = graded(pl, DUSK)
        falling_leaves(f, T, 36)
        m = S("folk_b", "m_back")
        x, y = (150, 250) if end else MOTHER_SEAT
        person(f, m, m.index(T, "pingpong"), x, y, pl, grade=DUSK, sh=(14, 4))
        return f

    def summit(T):
        dawn = float(np.clip((T - T_CLIMB) / 4.0, 0, 1))
        f, pl, k = snow(T, night=max(0.0, 1 - dawn) * 0.6, dawn=dawn)
        snowfall(f, T, 20)
        people = []
        if T < T_FINAL:
            s = S("hero", "y_up_r")
            i, x, y = walk_between(s, (165, 158), SADDLE, T_CLIMB, T_FINAL - 0.2, T)
            people.append((y, s, i, x, 1.0, False))
        else:
            # He sounds the call on the saddle. The column rises past him, and then gathers.
            if T < T_TOGETHER:
                people += column(T - T_FINAL, TRAIL[3:] + [SADDLE], ["s_up_r", "s_up_l", "s_flag_up_r", "s_flag_up_l"], 0.05, 6, {0, 3}, k, spacing=0.12)
            else:
                for n, (x, y) in enumerate(SUMMIT):
                    s = S("soldier", "s_flag_stand" if n in (1, 4) else "s_stand")
                    people.append((y, s, s.index(T + n * 0.6, "pingpong"), x, min(1.0, (T - T_TOGETHER) / 0.8), n in (1, 4)))
            s = S("hero", "y_bugle_x")
            i = min(int((T - T_FINAL) * s.fps), 8) + (int((T - T_FINAL) * s.fps * 0.5) % 10 if T - T_FINAL > 0.4 else 0)
            people.append((SADDLE[1], s, min(i, s.n - 1), SADDLE[0], 1.0, ("bugle", blown(T, T_FINAL))))
        for y, sp, i, x, rev, extra in sorted(people, key=lambda p: p[0]):
            person(f, sp, i, x, y, pl, grade=k, reveal=rev)
            if extra is True and rev > 0.5:
                flag(f, sp, i, x, y, T, k)
            if isinstance(extra, tuple) and extra[1]:
                blow(f, sp, i, x, y)
        return f

    title = Image.new("RGB", (220, 54), INK)
    d = ImageDraw.Draw(title)
    d.fontmode = "1"
    big, small = ImageFont.truetype(font_path("simsun.ttc"), 24), ImageFont.truetype(font_path("msgothic.ttc"), 12)
    d.text((110 - big.getlength(brief["title"]) / 2, 5), brief["title"], font=big, fill=tuple(int(v) for v in paper))
    d.text((110 - small.getlength(brief["title_id"]) / 2, 36), brief["title_id"], font=small, fill=(214, 208, 196))
    title = np.asarray(title)
    state = {"last": None, "scene": None, "at": 0.0}

    def scene_at(T):
        for end, name, fn in ((T_GATE, "village", village), (T_HIT, "gate", gate), (T_SNOW, "chorus", chorus), (T_NIGHT, "pass", pass_climb), (T_HOME1, "camp", camp), (T_CLIMB, "mother", mother_alone), (T_END, "summit", summit)):
            if T < end:
                return name, fn
        return "end", lambda t: mother_alone(t, True)

    def draw(i, t, T):
        name, builder = scene_at(T)
        f = builder(T)
        if name != state["scene"]:
            state["scene"], state["at"] = name, T
        u = (T - state["at"]) / 0.2
        if u < 1 and state["last"] is not None:
            hide = bayer > u
            f[hide] = state["last"][hide]
        if 1.2 <= T < 9.0:
            h, w, _ = title.shape
            x0 = (G - w) // 2
            keep = bayer[6:6 + h, x0:x0 + w] < min(1, (T - 1.2) / 0.3, (9.0 - T) / 0.3)
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
