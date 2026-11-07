# Brother, Go First: June 1950. Two friends from one village walk south with the refugees, in rain and fog.
# At a rope bridge the younger one stays. His hyung crosses last, and he cuts the bridge down behind him.
# When the rain stops he walks back into the fog. The film ends on the promise: the two of them walking home.
# The plate never moves. Footprints guard every path. No person holds one frame.
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pixkit import INK, Captions, Occlusion, Sprite, bayer_field, contact_shadow
from studio_paths import font_path

RAIN = (196, 204, 212)
FOG = np.array([214, 216, 214])
FOAM = (230, 234, 228)
LAMP = (255, 214, 140)
WET = (0.86, 0.88, 0.94)
DAWN = (1.04, 1.0, 0.96)

# The road of the first scene, from the back to the front.
ROAD = [(306, 172), (262, 192), (214, 220), (166, 240), (110, 258), (52, 274)]
BRIDGE_NEAR, BRIDGE_FAR, FAR_PATH = (180, 250), (178, 172), (190, 128)
STAY = (180, 268)
POST = (165, 258)
HY_FAR = (196, 150)
HY_WAIT = (164, 264)
HOME_A, HOME_B = (76, 270), (232, 190)
BLUE, RED = np.array([52, 82, 150]), np.array([166, 46, 38])
# The two sides stand on the two banks. Nobody acts, and the rifles stay on their backs.
FAR_LINE = [(122, 170), (142, 165), (222, 165), (244, 170), (262, 176)]
FAR_FLAG = (232, 158)
NEAR_LINE = [(118, 286), (140, 289), (206, 289), (228, 287), (250, 283)]
NEAR_FLAG = (100, 284)
BANK_ROW = 166


def make(ctx):
    G, fps, brief, A, root = ctx["grid"], ctx["fps"], ctx["brief"], ctx["a"], ctx["root"]
    paper = np.array(brief["paper"], np.uint8)
    beats = np.array(A["beats"])
    rng = np.random.default_rng(1950)
    bayer = bayer_field(G)
    Y, X = np.mgrid[:G, :G]
    caps = Captions(brief["lines"], paper, top_font=(font_path("malgun.ttf"), 16), low_font=(font_path("msgothic.ttc"), 12))
    shapes = json.loads((root / "occluders.json").read_text(encoding="utf-8"))

    def beat(t):
        return float(beats[np.argmin(np.abs(beats - t))])

    T_FOG, T_BARN, T_BRIDGE, T_HIT, T_GUARD, T_GO, T_LIVE = beat(20.8), beat(33.4), beat(45.4), brief["hit"], beat(55.4), beat(62.2), beat(69.0)
    T_RICE, T_STAY, T_KEY, T_RAIN_STOP, T_HOME = beat(75.6), beat(89.4), beat(104.6), beat(117.1), beat(123.8)

    def plate(name, occ):
        d = np.asarray(Image.open(root / f"plates/{name}-360.png").convert("RGB")).copy()
        is_paper = (np.abs(d.astype(int) - paper.astype(int)).sum(axis=2) < 24) | (d.astype(int).sum(axis=2) > 720)
        d[is_paper] = paper
        return {"name": name, "day": d, "paper": is_paper, "occ": Occlusion(root, occ)}

    P = {"gil": plate("gil", "gil"), "dari": plate("dari", "dari"), "dari_cut": plate("dari_cut", "dari"), "bam": plate("bam", "bam"), "gohyang": plate("gohyang", "gohyang")}

    def graded(pl, k):
        out = np.clip(pl["day"] * np.array(k), 0, 255).astype(np.uint8)
        out[pl["paper"]] = paper
        return out

    sprites = {}

    def S(folder, name):
        key = (folder, name)
        if key not in sprites:
            sprites[key] = Sprite(root, name, folder)
        return sprites[key]

    def clearance(name, x, y):
        solids = [o["footprint"] for o in shapes.get(name, []) if "footprint" in o]
        return min((np.hypot((x - cx) / rx, (y - cy) / ry) for cx, cy, rx, ry in solids), default=9.0)

    def guard(name, pts):
        low = float(min(clearance(name, x, y) for x, y in pts))
        print(f"Footprint clearance on {name}, with 1.0 at the object edge:", round(low, 2), flush=True)
        if low < 1.0:
            raise SystemExit(f"A person stands inside a solid object on {name}: {low:.2f}")

    guard("dari", [STAY, POST, BRIDGE_NEAR, HY_WAIT])
    guard("bam", [(146, 264), (216, 260)])

    checked = set()

    def heading(spr, dx, dy):
        """Stops the render if a clip walks against its path. A backward walker reads as a moonwalk."""
        if spr.name in checked or np.hypot(dx, dy) < 8:
            return
        p0, p1 = spr.path(0), spr.path(spr.n - 1)
        if (p1[0] - p0[0]) * dx + (p1[1] - p0[1]) * dy < 0:
            raise SystemExit(f"{spr.name} walks against its path. Bake it 180 degrees around.")
        checked.add(spr.name)

    def walk_between(spr, a, b, t0, t1, T):
        """Plays a clip along a path. The frame follows the distance, so that the feet keep pace with the ground."""
        heading(spr, b[0] - a[0], b[1] - a[1])
        u = float(np.clip((T - t0) / (t1 - t0), 0, 1))
        p0, p1 = spr.path(0), spr.path(spr.n - 1)
        stride = max(np.hypot(p1[0] - p0[0], p1[1] - p0[1]), 1.0)
        walked = u * np.hypot(b[0] - a[0], b[1] - a[1])
        return int(walked / stride * (spr.n - 1)) % spr.n, a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u

    def along(points, u):
        """A point at fraction u of a polyline."""
        legs = [np.hypot(points[k + 1][0] - points[k][0], points[k + 1][1] - points[k][1]) for k in range(len(points) - 1)]
        d = u * sum(legs)
        for k, leg in enumerate(legs):
            if d <= leg or k == len(legs) - 1:
                v = min(d / max(leg, 1e-6), 1.0)
                return points[k][0] + (points[k + 1][0] - points[k][0]) * v, points[k][1] + (points[k + 1][1] - points[k][1]) * v, sum(legs)
            d -= leg

    def person(f, spr, i, x, y, pl, grade=None, sh=(6, 2), reveal=1.0, light=None, occ=True):
        if sh:
            contact_shadow(f, x, y, sh[0], sh[1], 0.8, bayer, ~pl["paper"], 2, occ=pl["occ"] if occ else None)
        spr.draw(f, i, x, y, occ=pl["occ"] if occ else None, grade=grade, bayer=bayer, reveal=reveal, light=light)

    # Rain falls on everything, and over the paper too. It slants to screen right like the shadows.
    drops = rng.random((150, 3))

    def rain(f, T, amount=1.0):
        n = int(150 * amount)
        for k in range(n):
            x0, y0, sp = drops[k]
            y = (y0 * 420 + T * (300 + sp * 160)) % 420 - 40
            x = (x0 * 420 + y * 0.35) % 380 - 10
            for s in range(5):
                px, py = int(x + s * 0.35), int(y + s)
                if 0 <= px < G and 0 <= py < G:
                    f[py, px] = RAIN

    # Soft fog: a slow cloud field that blends with the plate. It never forms a dither lattice.
    cloud = np.asarray(Image.fromarray((rng.random((10, 20)) * 255).astype(np.uint8)).resize((G * 2, G), Image.BICUBIC)).astype(np.float32) / 255
    band = np.clip(1.15 - np.abs(Y - 220) / 150, 0.35, 1)

    def fog(f, density, drift=0.0, ground=None):
        if density <= 0:
            return
        x0 = int(drift) % G
        field = cloud[:, x0:x0 + G] if x0 + G <= 2 * G else np.roll(cloud, -x0, axis=1)[:, :G]
        a = np.clip(density * (0.45 + field * 1.1) * band, 0, 0.85)
        if ground is not None:
            a = a * ground
        f[:] = (f * (1 - a[..., None]) + FOG * a[..., None]).astype(np.uint8)

    # The column of refugees on the road. Everyone walks from the first frame.
    COLUMN = [("folk_a", "f_carry_45", 0.00), ("folk_b", "f_walk_45", 0.11), ("folk_a", "f_walk_45", 0.23), ("folk_b", "f_carry_45", 0.37),
              ("folk_a", "f_carry_45", 0.52), ("folk_b", "f_walk_45", 0.64), ("folk_a", "f_walk_45", 0.78), ("folk_b", "f_carry_45", 0.9)]

    def column(f, T, pl, grade, speed=0.034):
        people = []
        for folder, name, ph in COLUMN:
            u = (ph + T * speed) % 1.0
            x, y, total = along(ROAD, u)
            s = S(folder, name)
            heading(s, ROAD[-1][0] - ROAD[0][0], ROAD[-1][1] - ROAD[0][1])
            p0, p1 = s.path(0), s.path(s.n - 1)
            stride = max(np.hypot(p1[0] - p0[0], p1[1] - p0[1]), 1.0)
            i = int(u * total / stride * (s.n - 1)) % s.n
            people.append((y, s, i, x, min(1.0, min(u, 1 - u) / 0.07)))
        return people

    def friends_on_road(T, start):
        u = 0.28 + (T - start) * 0.03
        out = []
        for folder, name, off in (("hero", "y_walk_45", 0.0), ("hero_hy", "h_walk_45", 0.035)):
            x, y, total = along(ROAD, min(u + off, 0.97))
            s = S(folder, name)
            p0, p1 = s.path(0), s.path(s.n - 1)
            stride = max(np.hypot(p1[0] - p0[0], p1[1] - p0[1]), 1.0)
            out.append((y + 4, s, int((u + off) * total / stride * (s.n - 1)) % s.n, x + 4, 1.0))
        return out

    def banner(f, spr, i, x, y, T, colour, grade):
        """A plain cloth banner on a pole, held in the right hand. It carries no emblem."""
        hx, hy = spr.point(i, "right", x, y)
        hx, hy = int(hx), int(hy)
        for py in range(hy - 24, hy + 9):
            if 0 <= py < G and 0 <= hx < G:
                f[py, hx] = (70, 52, 36)
        g = np.array(grade)
        for cx in range(11):
            wave = np.sin(T * 6.0 - cx * 0.7) * (cx / 11) * 2.0
            for cy in range(7):
                px, py = hx + 1 + cx, int(hy - 24 + cy + wave)
                if 0 <= px < G and 0 <= py < G:
                    shade = 0.78 + 0.22 * np.sin(T * 6.0 - cx * 0.7 + 1.2)
                    f[py, px] = np.clip(colour * g * shade, 0, 255).astype(np.uint8)

    def soldiers_line(T, folder, stand, flag, spots, flag_spot, colour, start, grade, fade=1.0):
        people = []
        rev = min(1.0, max(0.0, (T - start) / 1.6)) * fade
        if rev <= 0:
            return people
        for k, (x, y) in enumerate(spots):
            s = S(folder, stand)
            people.append((y, s, s.index(T + k * 0.7, "pingpong"), x, rev, None))
        s = S(folder, flag)
        people.append((flag_spot[1], s, s.index(T, "pingpong"), flag_spot[0], rev, colour))
        return people

    def road_column(T):
        """A column of soldiers marches north, against the refugees going south."""
        out = []
        s = S("soldier_a", "s_march_225")
        heading(s, ROAD[0][0] - ROAD[-1][0], ROAD[0][1] - ROAD[-1][1])
        p0, p1 = s.path(0), s.path(s.n - 1)
        stride = max(np.hypot(p1[0] - p0[0], p1[1] - p0[1]), 1.0)
        for k in range(6):
            u = 1.0 - ((k * 0.09 + T * 0.03) % 1.0)
            x, y, total = along(ROAD, u)
            i = int((1 - u) * total / stride * (s.n - 1)) % s.n
            out.append((y - 6, s, i, x + 12, min(1.0, min(u, 1 - u) / 0.07)))
        return out

    def road(T):
        pl = P["gil"]
        f = graded(pl, WET)
        dens = 0.12 if T < T_FOG else float(np.clip(0.12 + (T - T_FOG) / 4 * 0.45, 0, 0.57))
        fog(f, dens, T * 4, ~pl["paper"])
        people = column(f, T, pl, WET) + (friends_on_road(T, 7.3) if T >= 7.3 else []) + (road_column(T) if T < T_FOG + 6 else [])
        for y, s, i, x, rev in sorted(people, key=lambda p: p[0]):
            person(f, s, i, x, y, pl, grade=WET, reveal=rev)
        fog(f, dens * 0.45, T * 4, ~pl["paper"])
        rain(f, T)
        return f

    def barn(T, give=False):
        pl = P["bam"]
        f = pl["day"].copy()
        flick = 1 + np.sin(T * 9.3) * 0.03
        glow = (np.hypot(X - 181, (Y - 212) * 1.2) + bayer * 30 < 70) & ~pl["paper"]
        f[glow] = np.clip(f[glow] * flick * 1.08, 0, 255).astype(np.uint8)
        light = (181, 212, 70, (1.12, 1.0, 0.82))
        if give:
            y, h = S("hero", "y_give"), S("hero_hy", "h_crouch")
        else:
            y, h = S("hero", "y_crouch"), S("hero_hy", "h_reach")
        start = T_RICE if give else T_BARN
        yi = min(int((T - start) * y.fps), 20) + (int((T - start) * y.fps) % 12 if T - start > 1 else 0) if give else y.index(T, "pingpong")
        hi = h.index(T + 0.4, "pingpong") if give else min(int((T - start) * h.fps), 20) + (int((T - start) * h.fps * 0.5) % 10 if T - start > 1 else 0)
        person(f, y, min(yi, y.n - 1), 146, 264, pl, sh=(16, 5), light=light)
        person(f, h, min(hi, h.n - 1), 216, 260, pl, sh=(16, 5), light=light)
        return f

    # The bridge falls when he cuts the rope. The deck drops in order from the near end, then hits the water.
    deck = (np.abs(P["dari"]["day"].astype(int) - P["dari_cut"]["day"].astype(int)).sum(axis=2) > 40) & (X > 136) & (X < 224) & (Y > 160) & (Y < 252)
    deck_px = P["dari"]["day"][deck]
    deck_y, deck_x = np.nonzero(deck)

    def bridge_fall(f, T):
        t = T - T_KEY
        delay = (250 - deck_y) / 90 * 0.9
        tt = np.clip(t - delay, 0, None)
        dy = (180 * tt * tt).astype(int)
        ny = deck_y + dy
        alive = (ny < 236) & (tt < 1.2)
        f[ny[alive], deck_x[alive]] = deck_px[alive]
        hit = (tt > 0) & (ny >= 214) & (ny < 238) & (rng.random(len(ny)) < 0.06)
        f[np.clip(ny[hit] - 2, 0, G - 1), deck_x[hit]] = FOAM

    def river_scene(T):
        cut = T >= T_KEY
        pl = P["dari_cut"] if cut else P["dari"]
        dawn = float(np.clip((T - T_RAIN_STOP) / 3.0, 0, 1))
        k = np.array(WET) * (1 - dawn) + np.array(DAWN) * dawn
        f = graded(pl, k)
        if cut and T < T_KEY + 2.2:
            bridge_fall(f, T)
        fdens = 0.16 + (0.18 if T_STAY <= T < T_KEY else 0) - dawn * 0.12
        fog(f, fdens, T * 4, ~pl["paper"])
        people = []
        if T < T_GO:
            # The last of the column crosses before his hyung.
            for n, (folder, name) in enumerate((("folk_a", "f_carry_up"), ("folk_b", "f_up"), ("folk_a", "f_up"), ("folk_b", "f_carry_up"))):
                t0 = T_BRIDGE - 1.0 + n * 3.4
                t1 = t0 + 8.0
                if t0 <= T < t1:
                    # They pass on his right, then step onto the middle of the deck.
                    s = S(folder, name)
                    u = (T - t0) / (t1 - t0)
                    x, y, total = along([(208, 304), (200, 266), (182, 246), FAR_PATH], u)
                    p0, p1 = s.path(0), s.path(s.n - 1)
                    i = int(u * total / max(np.hypot(p1[0] - p0[0], p1[1] - p0[1]), 1.0) * (s.n - 1)) % s.n
                    people.append((y, s, i, x, min(1.0, (t1 - T) / 0.6, (T - t0) / 0.6), y > 200))
        # His hyung waits on the near end of the bridge, then crosses, looks back once and goes on.
        hy_end = T_LIVE + 4.6
        if T < T_GO:
            s = S("hero_hy", "h_idle")
            people.append((HY_WAIT[1], s, s.index(T, "pingpong"), HY_WAIT[0], 1.0, True))
        elif T < T_LIVE - 1.4:
            s = S("hero_hy", "h_walk_up")
            u = (T - T_GO) / (T_LIVE - 1.4 - T_GO)
            x, y, total = along([HY_WAIT, BRIDGE_NEAR, BRIDGE_FAR], u)
            p0, p1 = s.path(0), s.path(s.n - 1)
            i = int(u * total / max(np.hypot(p1[0] - p0[0], p1[1] - p0[1]), 1.0) * (s.n - 1)) % s.n
            people.append((y, s, i, x, 1.0, False))
        elif T < T_LIVE + 0.6:
            s = S("hero_hy", "h_idle")
            people.append((BRIDGE_FAR[1], s, s.index(T, "pingpong"), BRIDGE_FAR[0], 1.0, False))
        elif T < hy_end:
            s = S("hero_hy", "h_walk_up")
            i, x, y = walk_between(s, BRIDGE_FAR, FAR_PATH, T_LIVE + 0.6, hy_end, T)
            people.append((y, s, i, x, min(1.0, (hy_end - T) / 0.8), False))
        elif cut:
            # On the far bank, after the bridge falls.
            s = S("hero_hy", "h_wave" if T > beat(113.0) else "h_idle")
            people.append((HY_FAR[1], s, s.index(T, "pingpong"), HY_FAR[0], min(1.0, (T - T_KEY) / 0.8), False))
        # The younger one.
        if T < T_GUARD:
            s = S("hero", "y_wave_b" if T >= T_HIT else "y_back")
            people.append((STAY[1], s, s.index(T, "pingpong"), STAY[0], 1.0, True))
        elif T < T_STAY:
            s = S("hero", "y_back" if T_GO <= T < T_LIVE + 4 else "y_idle")
            people.append((STAY[1], s, s.index(T, "pingpong"), STAY[0], 1.0, True))
        elif T < T_STAY + 2.0:
            s = S("hero", "y_walk_l")
            i, x, y = walk_between(s, STAY, POST, T_STAY, T_STAY + 2.0, T)
            people.append((y, s, i, x, 1.0, True))
        elif T < T_KEY:
            s = S("hero", "y_saw")
            people.append((POST[1], s, s.index(T, "loop"), POST[0], 1.0, True))
        elif T < T_RAIN_STOP + 1.0:
            s = S("hero", "y_back")
            people.append((POST[1], s, s.index(T, "pingpong"), POST[0], 1.0, True))
        else:
            s = S("hero", "y_walk_d")
            t1 = T_HOME - 0.2
            i, x, y = walk_between(s, POST, (172, 292), T_RAIN_STOP + 1.0, t1, T)
            people.append((y, s, i, x, min(1.0, (t1 - T) / 1.4), True))
        # The far-bank column marches behind the crossing in the first chorus.
        if T_HIT <= T < T_RICE:
            s = S("soldier_a", "s_march_r")
            heading(s, 1, 0)
            for n in range(5):
                u = ((T - T_HIT) * 0.045 + n * 0.11) % 1.0
                x = 30 + u * 300
                y = BANK_ROW + np.sin(u * 3.1) * 2
                i = int(u * 300 / 98 * (s.n - 1)) % s.n
                people.append((y, s, i, x, min(1.0, min(u, 1 - u) / 0.08), False))
        # The near line comes out of the fog while he cuts the rope. The far line waits around his hyung.
        if T >= T_STAY + 5:
            fade = 1.0 if T < T_RAIN_STOP else 1.0
            for y, s, i, x, rev, col in soldiers_line(T, "soldier_b", "s_stand_b", "s_flag_b", NEAR_LINE, NEAR_FLAG, RED, T_STAY + 5, k):
                people.append((y, s, i, x, rev * (0.55 if T < T_KEY else 1.0), ("flag", col) if col is not None else True))
        if cut:
            for y, s, i, x, rev, col in soldiers_line(T, "soldier_a", "s_stand_f", "s_flag_f", FAR_LINE, FAR_FLAG, BLUE, T_KEY + 0.8, k):
                people.append((y, s, i, x, rev, ("flag", col) if col is not None else False))
        for y, s, i, x, rev, occ in sorted(people, key=lambda p: p[0]):
            flag = occ if isinstance(occ, tuple) else None
            occ_on = bool(occ) if flag is None else y > 200
            person(f, s, i, x, y, pl, grade=tuple(k), reveal=rev, occ=occ_on, sh=(6, 2) if occ_on or y < 200 else None)
            if flag is not None and rev > 0.5:
                banner(f, s, i, x, y, T, flag[1], k)
        fog(f, fdens * 0.35, T * 4, ~pl["paper"])
        rain(f, T, 1.0 - dawn)
        return f

    def home(T):
        pl = P["gohyang"]
        f = pl["day"].copy()
        for folder, name, off in (("hero", "y_walk_h", (-6, 4)), ("hero_hy", "h_walk_h", (6, -2))):
            s = S(folder, name)
            a = (HOME_A[0] + off[0], HOME_A[1] + off[1])
            b = (HOME_B[0] + off[0], HOME_B[1] + off[1])
            i, x, y = walk_between(s, a, b, T_HOME, T_HOME + 16, T)
            person(f, s, i, x, y, pl)
        return f

    title = Image.new("RGB", (220, 54), INK)
    d = ImageDraw.Draw(title)
    d.fontmode = "1"
    big, small = ImageFont.truetype(font_path("malgun.ttf"), 22), ImageFont.truetype(font_path("msgothic.ttc"), 12)
    d.text((110 - big.getlength(brief["title"]) / 2, 4), brief["title"], font=big, fill=tuple(int(v) for v in paper))
    d.text((110 - small.getlength(brief["title_id"]) / 2, 36), brief["title_id"], font=small, fill=(214, 208, 196))
    title = np.asarray(title)
    state = {"last": None, "scene": None, "at": 0.0}

    def scene_at(T):
        for end, name, fn in ((T_BARN, "road", road), (T_BRIDGE, "barn", barn), (T_RICE, "river", river_scene), (T_STAY, "rice", lambda t: barn(t, True)), (T_HOME, "river2", river_scene)):
            if T < end:
                return name, fn
        return "home", home

    def draw(i, t, T):
        name, builder = scene_at(T)
        f = builder(T)
        if name != state["scene"]:
            state["scene"], state["at"] = name, T
        u = (T - state["at"]) / 0.2
        if u < 1 and state["last"] is not None:
            hide = bayer > u
            f[hide] = state["last"][hide]
        if 1.2 <= T < 7.0:
            h, w, _ = title.shape
            x0 = (G - w) // 2
            keep = bayer[6:6 + h, x0:x0 + w] < min(1, (T - 1.2) / 0.3, (7.0 - T) / 0.3)
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
