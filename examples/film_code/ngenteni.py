# Ngenteni Kabar: a rice village in Central Java. A father and his daughter wait at the corner shop phone every month
# for the mother's call from across the sea. The rice turns gold seven times. In the final chorus a minibus stops at the
# corner, she steps off, and the daughter runs to meet her. The village dances.
# The plate never moves. Footprints guard every path. Every walker faces the way that it moves.
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pixkit import INK, Captions, Occlusion, Sprite, bayer_field, contact_shadow, small_flame
from studio_paths import font_path

FIREFLY = (236, 240, 150)

BENCH_F, BENCH_A = (82, 262), (101, 263)
ASK = (122, 274)
ROAD = [(292, 180), (262, 200), (232, 222), (200, 240), (160, 258)]
BUS_STOP = (222, 230)
MEET_A, MEET_I = (142, 262), (184, 252)
DANCE = [("folk_k", "v_joget", 104, 270), ("folk_m", "v_joget_b", 124, 274), ("folk_k", "v_joget_b", 146, 272), ("folk_m", "v_joget", 178, 266)]
STROLL = [("folk_k", "v_walk_d", 0.0), ("folk_m", "v_walk_u", 0.45), ("folk_m", "v_walk_d", 0.7)]


def make(ctx):
    G, fps, brief, A, root = ctx["grid"], ctx["fps"], ctx["brief"], ctx["a"], ctx["root"]
    paper = np.array(brief["paper"], np.uint8)
    beats = np.array(A["beats"])
    rng = np.random.default_rng(7)
    bayer = bayer_field(G)
    Y, X = np.mgrid[:G, :G]
    caps = Captions(brief["lines"], paper, top_font=(font_path("msgothic.ttc"), 16), low_font=(font_path("simsun.ttc"), 12))
    shapes = json.loads((root / "occluders.json").read_text(encoding="utf-8"))

    def beat(t):
        return float(beats[np.argmin(np.abs(beats - t))])

    T_WAIT, T_ASK, T_WIPE, T_HOME, T_HIT, T_LETTER, T_NIGHT, T_FINAL, T_BUS, T_STEP, T_JOY = (
        beat(11.5), beat(23.0), beat(28.7), beat(34.4), brief["hit"], beat(62.9), beat(69.3), beat(83.0), beat(88.9), beat(94.5), beat(100.2))

    def plate(name, occ):
        d = np.asarray(Image.open(root / f"plates/{name}-360.png").convert("RGB")).copy()
        is_paper = (np.abs(d.astype(int) - paper.astype(int)).sum(axis=2) < 24) | (d.astype(int).sum(axis=2) > 720)
        d[is_paper] = paper
        return {"name": name, "day": d, "paper": is_paper, "occ": Occlusion(root, occ)}

    P = {n: plate(n, "desa") for n in ("desa", "desa_kuning", "desa_wengi")}
    P["omah"] = plate("omah", "omah")
    sprites = {}

    def S(folder, name):
        if (folder, name) not in sprites:
            sprites[(folder, name)] = Sprite(root, name, folder)
        return sprites[(folder, name)]

    # The minibus is a Tripo model, baked at the people's camera and scale. See props/bake_bus.py.
    bus_meta = json.loads((root / "props/bus.json").read_text())
    BUS = np.asarray(Image.open(root / "props/bus.png").convert("RGBA")).reshape(bus_meta["count"], bus_meta["size"], bus_meta["size"], 4)
    BUS_AX, BUS_AY = bus_meta["anchor"]
    BUS_G = bus_meta["groups"]

    def stamp(f, a, x0, y0, reveal=1.0):
        h, w = a.shape[:2]
        x0, y0 = int(x0), int(y0)
        ax0, ay0, ax1, ay1 = max(x0, 0), max(y0, 0), min(x0 + w, G), min(y0 + h, G)
        if ax0 >= ax1 or ay0 >= ay1:
            return
        part = a[ay0 - y0:ay1 - y0, ax0 - x0:ax1 - x0]
        solid = (part[..., 3] > 0) & (bayer[ay0:ay1, ax0:ax1] < reveal)
        f[ay0:ay1, ax0:ax1][solid] = part[..., :3][solid]

    def clearance(name, x, y):
        solids = [o["footprint"] for o in shapes.get(name, []) if "footprint" in o]
        return min((np.hypot((x - cx) / rx, (y - cy) / ry) for cx, cy, rx, ry in solids), default=9.0)

    def guard(name, pts):
        low = float(min(clearance(name, x, y) for x, y in pts))
        print(f"Footprint clearance on {name}, with 1.0 at the object edge:", round(low, 2), flush=True)
        if low < 1.0:
            raise SystemExit(f"A person stands inside a solid object on {name}: {low:.2f}")

    guard("desa", [BENCH_F, BENCH_A, ASK, MEET_A, MEET_I] + [(x, y) for _, _, x, y in DANCE])
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
                return points[k][0] + (points[k + 1][0] - points[k][0]) * v, points[k][1] + (points[k + 1][1] - points[k][1]) * v, sum(legs)
            d -= leg

    def person(f, spr, i, x, y, pl, grade=None, sh=(6, 2), reveal=1.0, light=None):
        contact_shadow(f, x, y, sh[0], sh[1], 0.8, bayer, ~pl["paper"], 2, occ=pl["occ"])
        spr.draw(f, i, x, y, occ=pl["occ"], grade=grade, bayer=bayer, reveal=reveal, light=light)

    def draw_all(f, people, pl, grade=None):
        for y, s, i, x, rev in sorted(people, key=lambda p: p[0]):
            person(f, s, i, x, y, pl, grade=grade, reveal=rev)

    def strollers(T, start):
        out = []
        for folder, name, ph in STROLL:
            s = S(folder, name)
            lap = int(ph + (T - start) * 0.05)
            u = (ph + (T - start) * 0.05) % 1.0
            down = name.endswith("_d")
            path = ROAD[::-1] if not down else ROAD
            x, y, total = along(path, u)
            heading(s, path[-1][0] - path[0][0], path[-1][1] - path[0][1])
            # Each lap walks a little to the side, so that the frozen check never sees two laps on one spot.
            side = (6 if down else -6) + (lap % 3) * 3
            out.append((y + (lap % 3), s, int(u * total / stride(s) * (s.n - 1)) % s.n, x + side, min(1.0, min(u, 1 - u) / 0.08)))
        return out

    # The rice ripens seven times across the chorus. Each harvest turns over on the beat through a dither.
    def seasons(T):
        u = (T - T_HIT) / (T_LETTER - 1.2 - T_HIT) * 7
        phase = u % 1.0
        gold = np.clip((0.5 - abs(phase - 0.5)) * 2.6, 0, 1)
        m = bayer < gold
        return np.where(m[..., None], P["desa_kuning"]["day"], P["desa"]["day"]).astype(np.uint8)

    def morning(T):
        pl = P["desa"]
        f = pl["day"].copy()
        people = strollers(T, 0)
        if T < 9.5:
            for k, (who, name, end) in enumerate((("hero", "f_walk_d", BENCH_F), ("anak", "a_walk_d", BENCH_A))):
                s = S(who, name)
                i, x, y = walk_between(s, (232 + k * 12, 222 + k * 4), end, 0.0, 9.5, T)
                people.append((y, s, i, x, min(1.0, T / 0.8)))
        else:
            people += bench(T)
        draw_all(f, people, pl)
        return f

    def bench(T, night=False):
        out = []
        f_name = "f_wipe" if T_WIPE <= T < T_HOME else "f_sit"
        s = S("hero", f_name)
        if f_name == "f_wipe":
            i = min(int((T - T_WIPE) * s.fps), 12) + (int((T - T_WIPE) * s.fps * 0.4) % 8 if T - T_WIPE > 0.5 else 0)
            i = min(i, s.n - 1)
        else:
            i = s.index(T, "pingpong")
        out.append((BENCH_F[1], s, i, BENCH_F[0], 1.0))
        if not night:
            if T_ASK <= T < T_WIPE:
                a = S("anak", "a_ask")
                out.append((ASK[1], a, a.index(T, "pingpong"), ASK[0], 1.0))
            else:
                a = S("anak", "a_sit")
                out.append((BENCH_A[1], a, a.index(T + 0.7, "pingpong"), BENCH_A[0], 1.0))
        return out

    def waiting(T):
        pl = P["desa"]
        f = pl["day"].copy()
        draw_all(f, strollers(T, 0) + bench(T), pl)
        return f

    def going_home(T):
        pl = P["desa_wengi"]
        f = pl["day"].copy()
        people = []
        for k, (who, name) in enumerate((("hero", "f_walk_u"), ("anak", "a_walk_u"))):
            s = S(who, name)
            i, x, y = walk_between(s, (BENCH_F[0] + 20 + k * 14, BENCH_F[1] - 2 + k * 3), (262 + k * 10, 200 + k * 4), T_HOME, T_HIT - 0.3, T)
            people.append((y, s, i, x, min(1.0, (T_HIT - 0.3 - T) / 0.8)))
        draw_all(f, people, pl, grade=(0.78, 0.8, 0.98))
        return f

    def chorus(T):
        pl = P["desa"]
        f = seasons(T)
        draw_all(f, strollers(T, T_HIT) + bench(T), pl)
        return f

    def letters(T):
        pl = P["omah"]
        f = pl["day"].copy()
        flick = 1 + np.sin(T * 9.1) * 0.03
        glow = (np.hypot(X - 186, (Y - 200) * 1.2) + bayer * 26 < 60) & ~pl["paper"]
        f[glow] = np.clip(f[glow] * flick * 1.06, 0, 255).astype(np.uint8)
        s = S("hero", "fo_read")
        i = min(int((T - T_LETTER) * s.fps), 12) + (int((T - T_LETTER) * s.fps * 0.4) % 8 if T - T_LETTER > 0.5 else 0)
        person(f, s, min(i, s.n - 1), 150, 264, pl, sh=(14, 4), light=(186, 205, 60, (1.15, 1.0, 0.8)))
        # The letter in his hands catches the lamp.
        hx, hy = s.point(min(i, s.n - 1), "right", 150, 264)
        f[int(hy) - 2:int(hy) + 2, int(hx) - 3:int(hx) + 3] = (236, 228, 204)
        return f

    def night_bench(T):
        pl = P["desa_wengi"]
        f = pl["day"].copy()
        dawn = float(np.clip((T - (T_FINAL - 3.5)) / 3.5, 0, 1))
        if dawn > 0:
            f = (f * (1 - dawn) + P["desa"]["day"] * dawn).astype(np.uint8)
        for k in range(14):
            x = int(120 + (k * 47 + T * (6 + k % 4)) % 200)
            y = int(200 + np.sin(T * 0.9 + k) * 18 + (k * 13) % 60)
            if (k + int(T * 3)) % 3 and not pl["paper"][y, x]:
                f[y, x] = FIREFLY
        draw_all(f, bench(T, night=True), pl, grade=(0.8, 0.82, 0.98))
        return f

    def homecoming(T):
        pl = P["desa"]
        f = pl["day"].copy()
        people = []
        if T < T_STEP:
            people += bench(T)
        else:
            # She steps down. The daughter runs to her, and they hold each other. The father comes after.
            i0 = S("ibu", "i_step")
            if T < T_STEP + 1.2:
                i, x, y = walk_between(i0, (BUS_STOP[0] + 12, BUS_STOP[1] + 10), MEET_I, T_STEP, T_STEP + 1.2, T)
                people.append((y, i0, i, x, min(1.0, (T - T_STEP) / 0.5)))
            else:
                h = S("ibu", "i_hug" if T < T_JOY + 3 else "i_joget")
                people.append((MEET_I[1], h, h.index(T - T_STEP, "pingpong"), MEET_I[0], 1.0))
            if T < T_STEP + 1.8:
                r = S("anak", "a_run")
                i, x, y = walk_between(r, BENCH_A, MEET_A, T_STEP, T_STEP + 1.8, T)
                people.append((y, r, i, x, 1.0))
            else:
                h = S("anak", "a_hug" if T < T_JOY + 3 else "a_joget")
                people.append((MEET_A[1], h, h.index(T - T_STEP, "pingpong"), MEET_A[0], 1.0))
            fa = S("hero", "f_walk_r")
            fx0, fy0, fx1, fy1 = BENCH_F[0], BENCH_F[1], MEET_A[0] - 22, MEET_A[1] + 4
            if T < T_STEP + 2.0:
                s = S("hero", "f_sit")
                people.append((BENCH_F[1], s, s.index(T, "pingpong"), BENCH_F[0], 1.0))
            elif T < T_STEP + 6.0:
                i, x, y = walk_between(fa, (fx0, fy0), (fx1, fy1), T_STEP + 2.0, T_STEP + 6.0, T)
                people.append((y, fa, i, x, 1.0))
            else:
                s = S("hero", "f_joget" if T >= T_JOY + 3 else "f_idle")
                people.append((fy1, s, s.index(T, "pingpong"), fx1, 1.0))
            if T >= T_JOY:
                for k, (folder, name, x, y) in enumerate(DANCE):
                    s = S(folder, name)
                    people.append((y, s, s.index(T + k * 0.6, "loop"), x, min(1.0, (T - T_JOY - k * 0.4) / 0.6)))
        if T < T_BUS - 1.0:
            draw_all(f, people, pl)
            return f
        bx, by, frame = bus_state(T)
        draw_all(f, [p for p in people if p[0] < by], pl)
        dust(f, T)
        stamp(f, BUS[frame], bx - BUS_AX, by - BUS_AY, reveal=min(1.0, (T - T_BUS + 1.0) / 0.9))
        draw_all(f, [p for p in people if p[0] >= by], pl)
        return f

    BUS_T = 3.0

    def bus_state(T):
        # The minibus pulls away from the shelter and brakes at the corner. It bobs on the road and idles when it stops.
        p = float(np.clip((T - T_BUS) / BUS_T, 0, 1))
        u = 1 - (1 - p) ** 2
        x = 270 + (BUS_STOP[0] - 270) * u
        y = 195 + (BUS_STOP[1] - 195) * u
        d0, d1 = BUS_G["drive"]
        b0, b1 = BUS_G["brake"]
        i0, i1 = BUS_G["idle"]
        stop = T_BUS + BUS_T
        if p < 1:
            frame = d0 + int(T * 10) % (d1 - d0)
        elif T < stop + (b1 - b0) / 12:
            frame = b0 + int((T - stop) * 12)
        elif T < T_JOY:
            frame = i0 + int(T * 12) % (i1 - i0)
        else:
            frame = b1 - 1
        return x, y, frame

    def puff(f, cx, cy, r, a, col):
        x0, y0, x1, y1 = int(cx - r), int(cy - r * 0.6), int(cx + r) + 1, int(cy + r * 0.6) + 1
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, G), min(y1, G)
        if x0 >= x1 or y0 >= y1:
            return
        yy, xx = np.mgrid[y0:y1, x0:x1]
        m = (((xx - cx) / r) ** 2 + ((yy - cy) / (r * 0.6)) ** 2 <= 1) & (bayer[y0:y1, x0:x1] < a)
        f[y0:y1, x0:x1][m] = col

    def dust(f, T):
        # Road dust trails the rear wheels while the bus moves. Small grey puffs leave the exhaust while it idles.
        for k in range(14):
            t0 = T_BUS - 0.6 + k * 0.25
            age = T - t0
            if not 0 <= age < 1.0 or t0 > T_BUS + BUS_T:
                continue
            x, y, _ = bus_state(t0)
            r = 2.0 + age * 5.0
            puff(f, x + 24 + age * 4, y - 3 - age * 3, r, 0.55 * (1 - age), (214, 196, 160))
        if T_BUS + BUS_T <= T < T_JOY:
            for k in range(3):
                age = ((T - T_BUS) * 1.2 + k / 3) % 1.0
                x, y, _ = bus_state(T)
                puff(f, x + 30 + age * 6, y - 6 - age * 5, 1.2 + age * 2.5, 0.45 * (1 - age), (150, 146, 140))

    title = Image.new("RGB", (240, 50), INK)
    d = ImageDraw.Draw(title)
    d.fontmode = "1"
    big, small = ImageFont.truetype(font_path("msgothic.ttc"), 22), ImageFont.truetype(font_path("simsun.ttc"), 14)
    d.text((120 - big.getlength(brief["title"]) / 2, 5), brief["title"], font=big, fill=tuple(int(v) for v in paper))
    d.text((120 - small.getlength(brief["title_zh"]) / 2, 31), brief["title_zh"], font=small, fill=(214, 208, 196))
    title = np.asarray(title)
    state = {"last": None, "scene": None, "at": 0.0}

    def scene_at(T):
        for end, name, fn in ((T_WAIT, "morning", morning), (T_HOME, "wait", waiting), (T_HIT, "home", going_home), (T_LETTER, "chorus", chorus),
                              (T_NIGHT, "letters", letters), (T_FINAL, "night", night_bench)):
            if T < end:
                return name, fn
        return "homecoming", homecoming

    def draw(i, t, T):
        name, builder = scene_at(T)
        f = builder(T)
        if name != state["scene"]:
            state["scene"], state["at"] = name, T
        u = (T - state["at"]) / 0.2
        if u < 1 and state["last"] is not None:
            hide = bayer > u
            f[hide] = state["last"][hide]
        if 1.0 <= T < 9.0:
            h, w, _ = title.shape
            x0 = (G - w) // 2
            keep = bayer[6:6 + h, x0:x0 + w] < min(1, (T - 1.0) / 0.3, (9.0 - T) / 0.3)
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
