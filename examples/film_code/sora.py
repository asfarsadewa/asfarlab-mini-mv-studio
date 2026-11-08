# 空まであと少し: a rural high school closes in spring. Its three-member rocket club launches all year from the school
# field. Every rocket fails: it topples, it fizzles, it breaks apart. They laugh and try again. On graduation dawn they
# launch one rocket built from every broken part. It climbs out of the frame, and its parachute drifts down onto the gate.
# The plates never move. Footprints guard every path. Every runner faces the way that it moves.
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage
from pixkit import INK, Captions, Occlusion, Sprite, bayer_field, contact_shadow
from studio_paths import font_path

RAIL = (173, 225)  # The foot of the rocket on the hub of the launch rail.
POS = {"hero": (156, 246), "b2": (118, 257), "b3": (186, 258)}
ROOM = {"hero": (150, 284), "b2": (200, 286), "b3": (252, 280)}
GATE = {"hero": (212, 249), "b2": (194, 258), "b3": (229, 237)}  # Just inside the field, left of the gate, all in view.
LAND = (251, 253)  # The parachute comes to rest on top of the gate bars.
TRIO = ["hero", "b2", "b3"]
SMOKE = (236, 232, 222)


def make(ctx):
    G, fps, brief, A, root = ctx["grid"], ctx["fps"], ctx["brief"], ctx["a"], ctx["root"]
    paper = np.array(brief["paper"], np.uint8)
    beats = np.array(A["beats"])
    bar = 4 * 60 / A["tempo"]
    rng = np.random.default_rng(5)
    bayer = bayer_field(G)
    Y, X = np.mgrid[:G, :G]
    caps = Captions(brief["lines"], paper, top_font=(font_path("msgothic.ttc"), 16), low_font=(font_path("msgothic.ttc"), 12))
    shapes = json.loads((root / "occluders.json").read_text(encoding="utf-8"))

    def beat(t):
        return float(beats[np.argmin(np.abs(beats - t))])

    T_LAUNCH1, T_FALL1, T_PICK, T_ROOM1, T_HIT, T_ROOM2, T_DAWN, T_STAND, T_FINAL, T_CHUTE, T_RUN, T_LAND = (
        beat(9.0), beat(12.6), beat(18.4), beat(24.34), brief["hit"], beat(48.0), beat(66.2), beat(73.0), beat(77.68), beat(81.14), beat(85.24), beat(90.5))
    SEASONS = [("kotei_natsu", "fizzle"), ("kotei_aki", "break"), ("kotei_fuyu", "tumble")]
    SEASON_LEN = 3 * bar

    def plate(name, occ):
        d = np.asarray(Image.open(root / f"plates/{name}-360.png").convert("RGB")).copy()
        # Pale pixels count as paper only where they connect to the frame edge. Bright snow inside the island stays snow.
        pale = (np.abs(d.astype(int) - paper.astype(int)).sum(axis=2) < 24) | (d.astype(int).sum(axis=2) > 720)
        lab, _ = ndimage.label(pale)
        edge = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
        is_paper = np.isin(lab, edge[edge > 0])
        d[is_paper] = paper
        return {"name": name, "day": d, "paper": is_paper, "occ": Occlusion(root, occ)}

    P = {n: plate(n, "kotei") for n in ("kotei", "kotei_natsu", "kotei_aki", "kotei_fuyu", "kotei_asa")}
    P["bushitsu"] = plate("bushitsu", "bushitsu")
    sprites = {}

    def S(folder, name):
        if (folder, name) not in sprites:
            sprites[(folder, name)] = Sprite(root, name, folder)
        return sprites[(folder, name)]

    # The rocket and the parachute come from one painted sheet. Each is the largest solid shape on its half.
    sheet = Image.open(root / "plates/roketto-raw.png").convert("RGBA")
    alpha = np.asarray(sheet.getchannel("A")) > 127
    lab, n = ndimage.label(alpha)
    boxes = sorted((ndimage.find_objects(lab)[k] for k in range(n)), key=lambda b: -(b[0].stop - b[0].start) * (b[1].stop - b[1].start))[:2]
    boxes.sort(key=lambda b: b[1].start)

    def prop(box, h=None, w=None):
        im = sheet.crop((box[1].start, box[0].start, box[1].stop, box[0].stop))
        size = (max(1, round(im.width * h / im.height)), h) if h else (w, max(1, round(im.height * w / im.width)))
        a = np.asarray(im.resize(size, Image.BOX)).copy()
        a[..., 3] = (a[..., 3] > 110) * 255
        return a

    ROCKET = prop(boxes[0], h=18)
    ROCKET_BIG = prop(boxes[0], h=44)
    CHUTE = prop(boxes[1], w=20)
    ROCKET_FLAT = np.rot90(ROCKET).copy()

    def stamp(f, a, x0, y0, reveal=1.0):
        h, w = a.shape[:2]
        x0, y0 = int(round(x0)), int(round(y0))
        ax0, ay0, ax1, ay1 = max(x0, 0), max(y0, 0), min(x0 + w, G), min(y0 + h, G)
        if ax0 >= ax1 or ay0 >= ay1:
            return
        part = a[ay0 - y0:ay1 - y0, ax0 - x0:ax1 - x0]
        solid = (part[..., 3] > 0) & (bayer[ay0:ay1, ax0:ax1] < reveal)
        f[ay0:ay1, ax0:ax1][solid] = part[..., :3][solid]

    def rocket_at(f, x, y, tilt=0.0):
        """Draws the rocket with its foot at x, y. A tilt of 1 lays it flat."""
        if tilt >= 0.75:
            stamp(f, ROCKET_FLAT, x - ROCKET_FLAT.shape[1] / 2, y - ROCKET_FLAT.shape[0])
            return
        a = ROCKET if tilt < 0.25 else np.asarray(Image.fromarray(ROCKET).rotate(-45 if tilt < 0.75 else -90, expand=True, resample=Image.NEAREST))
        stamp(f, a, x - a.shape[1] / 2, y - a.shape[0])

    def puff(f, cx, cy, r, a, col=SMOKE):
        x0, y0, x1, y1 = int(cx - r), int(cy - r), int(cx + r) + 1, int(cy + r) + 1
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, G), min(y1, G)
        if x0 >= x1 or y0 >= y1:
            return
        yy, xx = np.mgrid[y0:y1, x0:x1]
        m = (np.hypot(xx - cx, yy - cy) <= r) & (bayer[y0:y1, x0:x1] < a)
        f[y0:y1, x0:x1][m] = col

    def flame(f, x, y):
        for k, col in enumerate(((255, 236, 150), (255, 170, 60), (220, 90, 30))):
            if 0 <= int(y) + k < G:
                f[int(y) + k, int(x) - 1:int(x) + 1] = col

    def clearance(name, x, y):
        solids = [o["footprint"] for o in shapes.get(name, []) if "footprint" in o]
        return min((np.hypot((x - cx) / rx, (y - cy) / ry) for cx, cy, rx, ry in solids), default=9.0)

    def path_points(pts, step=3):
        out = []
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            n = max(int(np.hypot(x1 - x0, y1 - y0) / step), 1)
            out += [(x0 + (x1 - x0) * k / n, y0 + (y1 - y0) * k / n) for k in range(n + 1)]
        return out

    def guard(name, pts):
        low = float(min(clearance(name, x, y) for x, y in pts))
        print(f"Footprint clearance on {name}, with 1.0 at the object edge:", round(low, 2), flush=True)
        if low < 1.0:
            raise SystemExit(f"A person stands inside a solid object on {name}: {low:.2f}")

    guard("kotei", sum((path_points([POS[m], GATE[m]]) for m in TRIO), []))
    guard("bushitsu", list(ROOM.values()))
    checked = set()

    def heading(spr, dx, dy):
        """Stops the render if a clip runs against its path. A backward runner reads as a moonwalk."""
        if spr.name in checked or np.hypot(dx, dy) < 8:
            return
        p0, p1 = spr.path(0), spr.path(spr.n - 1)
        if (p1[0] - p0[0]) * dx + (p1[1] - p0[1]) * dy < 0:
            raise SystemExit(f"{spr.name} runs against its path. Bake it 180 degrees around.")
        checked.add(spr.name)

    def stride(spr):
        p0, p1 = spr.path(0), spr.path(spr.n - 1)
        return max(np.hypot(p1[0] - p0[0], p1[1] - p0[1]), 1.0)

    def person(f, spr, i, x, y, pl, sh=(4, 1), reveal=1.0):
        contact_shadow(f, x, y, sh[0], sh[1], 0.8, bayer, ~pl["paper"], 2, occ=pl["occ"])
        spr.draw(f, i, x, y, occ=pl["occ"], bayer=bayer, reveal=reveal)

    def draw_all(f, people, pl, sh=(4, 1)):
        for y, s, i, x in sorted(people, key=lambda p: p[0]):
            person(f, s, i, x, y, pl, sh=sh)

    def act(m, clip, T, t0=0.0, mode="loop", x=None, y=None):
        spr = S(m, clip)
        x0, y0 = POS[m] if x is None else (x, y)
        # A time before t0 wraps into the clip cycle, so a waiting person never holds frame 0.
        period = (spr.n if mode == "loop" else 2 * (spr.n - 1)) / spr.fps
        return (y0, spr, spr.index((T - t0) % period, mode), x0)

    # --- Petals and snow drift across the field. ---
    drift = [(rng.uniform(0, 360), rng.uniform(0, 360), rng.uniform(0.6, 1.4)) for _ in range(60)]

    def particles(f, pl, T, col, fall=14.0, sway=6.0):
        for x0, y0, v in drift:
            y = (y0 + T * fall * v) % 260 + 60
            x = int(x0 + np.sin(T * 1.3 * v + y0) * sway) % G
            if not pl["paper"][int(y), x]:
                f[int(y), x] = col

    def launch_people(T, t0, outcome_at):
        """The trio around a launch: the leader crouches at the rail, then stands. The others cheer, then laugh."""
        out = []
        out.append(act("hero", "f_crouch" if T < t0 - 0.2 else ("f_cheer" if T < outcome_at else "f_laugh"), T, t0))
        out.append(act("b2", "f_cheer" if t0 <= T < outcome_at else ("f_laugh" if T >= outcome_at else "f_idle"), T, t0))
        out.append(act("b3", "f_jump" if t0 <= T < outcome_at else ("f_point" if T >= outcome_at else "f_idle"), T, t0, mode="pingpong"))
        return out

    def flight(f, T, t0, outcome):
        """Draws one failed flight. Each failure has its own shape."""
        u = T - t0
        x, y = RAIL
        if u < 0:
            rocket_at(f, x, y)
            return
        if outcome == "topple":
            if u < 0.8:
                yy = y - 30 * u / 0.8
                rocket_at(f, x + 4 * u, yy)
                flame(f, x + 4 * u, yy)
                puff(f, x, y - 2, 3 + 6 * u, 0.6)
            elif u < 2.2:
                v = (u - 0.8) / 1.4
                rocket_at(f, x + 4 + 34 * v, y - 30 + 40 * v * v, tilt=min(1.0, v * 1.3))
            else:
                rocket_at(f, x + 38, y + 10, tilt=1.0)
            if u < 3.5:
                puff(f, x + 2, y - 6 - 4 * u, 4 + 2 * u, max(0.0, 0.55 - u * 0.15))
        elif outcome == "fizzle":
            hop = 6 * np.sin(min(u, 1.2) / 1.2 * np.pi)
            rocket_at(f, x, y - hop)
            for k in range(5):
                puff(f, x + np.sin(u * 3 + k) * 3, y - 4 - k * 4 - u * 5, 2 + k * 0.8 + u, max(0.0, 0.6 - u * 0.12))
        elif outcome == "break":
            if u < 1.2:
                yy = y - 110 * (u / 1.2) ** 1.5
                rocket_at(f, x, yy)
                flame(f, x, yy)
            else:
                v = u - 1.2
                for k in range(6):
                    px = x + (k - 2.5) * 6 * v
                    py = y - 110 + 30 * v * v + k * 2
                    if 0 <= py < G:
                        f[int(py):int(py) + 2, int(px):int(px) + 2] = (230, 226, 216) if k % 2 else (196, 60, 48)
                puff(f, x, y - 112, 4 + 8 * v, max(0.0, 0.7 - v * 0.3))
            for k in range(8):
                puff(f, x + np.sin(k) * 2, y - k * 13, 2 + u, max(0.0, 0.4 - u * 0.1))
        else:  # tumble
            if u < 1.0:
                yy = y - 70 * u
                rocket_at(f, x + 10 * u, yy)
                flame(f, x + 10 * u, yy)
            elif u < 2.4:
                v = (u - 1.0) / 1.4
                rocket_at(f, x + 10 + 30 * v, y - 70 + 82 * v * v, tilt=1.0 if int(u * 8) % 2 else 0.5)
            else:
                rocket_at(f, x + 40, y + 12, tilt=1.0)
            for k in range(6):
                puff(f, x + 2 * k, y - k * 12, 2 + u, max(0.0, 0.45 - u * 0.12))

    # --- Spring: the first failure. ---
    def spring(T):
        pl = P["kotei"]
        f = pl["day"].copy()
        flight(f, T, T_LAUNCH1, "topple")
        people = launch_people(T, T_LAUNCH1, T_FALL1)
        if T >= T_PICK:
            people = [act("hero", "f_pick", T, T_PICK, x=190, y=252), act("b2", "f_laugh", T, T_PICK), act("b3", "f_pick", T, T_PICK + 0.5, x=204, y=250)]
        draw_all(f, people, pl)
        particles(f, pl, T, (246, 196, 206))
        return f

    # --- The chorus: the seasons turn on the bar, and every launch fails in a new way. ---
    def seasons(T):
        k = min(int((T - T_HIT) / SEASON_LEN), 2)
        name, outcome = SEASONS[k]
        pl = P[name]
        f = pl["day"].copy()
        t0 = T_HIT + k * SEASON_LEN + bar * 0.5
        flight(f, T, t0, outcome)
        draw_all(f, launch_people(T, t0, t0 + 1.2), pl)
        if name == "kotei_fuyu":
            particles(f, pl, T, (250, 250, 252), fall=20.0)
        elif name == "kotei_aki":
            particles(f, pl, T, (214, 110, 50), fall=12.0, sway=10.0)
        return f

    # --- The club room: repairs, then the last rocket. ---
    def room(T):
        pl = P["bushitsu"]
        f = pl["day"].copy()
        winter = T >= T_ROOM2
        if winter:
            particles(f, pl, T, (250, 250, 252), fall=16.0)
        # The broken rocket lies on the bench. In winter the last rocket stands finished.
        if winter and T >= 61.0:
            stamp(f, ROCKET_BIG, 196 - ROCKET_BIG.shape[1] / 2, 214 - ROCKET_BIG.shape[0])
        else:
            flat = np.rot90(prop(boxes[0], h=40)).copy()
            stamp(f, flat, 190 - flat.shape[1] / 2, 216 - flat.shape[0])
        people = []
        start = T_ROOM2 if winter else T_ROOM1
        for m in TRIO:
            # Two of them work at the bench with their backs to us. The third turns round and laughs.
            if m == "b3":
                spr = S(m, "r_laugh")
                i = spr.index(T - start, "pingpong")
            else:
                spr = S(m, "r_work")
                k = (T - start) * spr.fps
                i = min(int(k) if k < 10 else 10 + int(k * 0.5) % 8, spr.n - 1)
            people.append((ROOM[m][1], spr, i, ROOM[m][0]))
        draw_all(f, people, pl, sh=(10, 3))
        return f

    # --- Graduation dawn: the last launch. ---
    def dawn(T):
        pl = P["kotei_asa"]
        f = pl["day"].copy()
        people = []
        if T < T_FINAL:
            rocket_at(f, *RAIL)
            people.append(act("hero", "f_crouch" if T < T_STAND else "f_idle", T, T_DAWN))
            people.append(act("b2", "f_point" if T >= T_STAND else "f_idle", T, T_DAWN, mode="pingpong"))
            people.append(act("b3", "f_idle", T, T_DAWN + 0.7))
        else:
            u = T - T_FINAL
            # The rocket climbs out of the frame. Its smoke column hangs, then thins.
            yy = RAIL[1] - 260 * (u / 1.6) ** 1.6
            if yy > -20:
                rocket_at(f, RAIL[0], yy)
                flame(f, RAIL[0], yy)
            for k in range(26):
                cy = RAIL[1] - 4 - k * 10
                if cy > yy:
                    puff(f, RAIL[0] + np.sin(k * 0.7 + u) * (1 + u * 0.6), cy, 2.5 + u * 0.7, max(0.0, 0.55 - u * 0.06))
            if T >= T_CHUTE:
                v = float(np.clip((T - T_CHUTE) / (T_LAND - T_CHUTE), 0, 1))
                cx = RAIL[0] + (LAND[0] - RAIL[0]) * v + np.sin(v * 9) * 10 * (1 - v)
                cy = 20 + (LAND[1] - 20) * v
                stamp(f, CHUTE, cx - CHUTE.shape[1] / 2, cy - CHUTE.shape[0])
                stamp(f, ROCKET, cx - ROCKET.shape[1] / 2, cy + 1)
            for m in TRIO:
                if T < T_CHUTE:
                    people.append(act(m, "f_cheer" if m != "b3" else "f_jump", T, T_FINAL + TRIO.index(m) * 0.15))
                elif T < T_RUN + TRIO.index(m) * 0.3:
                    people.append(act(m, "f_point" if m == "b2" else "f_cheer", T, T_CHUTE, mode="pingpong"))
                elif T < T_RUN + 3.0 + TRIO.index(m) * 0.3:
                    spr = S(m, "f_run")
                    a, b = POS[m], GATE[m]
                    heading(spr, b[0] - a[0], b[1] - a[1])
                    v = float(np.clip((T - T_RUN - TRIO.index(m) * 0.3) / 3.0, 0, 1))
                    d = v * np.hypot(b[0] - a[0], b[1] - a[1])
                    people.append((a[1] + (b[1] - a[1]) * v, spr, int(d / stride(spr) * (spr.n - 1)) % spr.n, a[0] + (b[0] - a[0]) * v))
                else:
                    clip = ["f_laugh", "f_cheer", "f_jump"][TRIO.index(m)] if T < 100 else "f_laugh"
                    people.append(act(m, clip, T, T_RUN + 3.0 + TRIO.index(m) * 0.3, x=GATE[m][0], y=GATE[m][1]))
        draw_all(f, people, pl)
        return f

    title = Image.new("RGB", (240, 50), INK)
    d = ImageDraw.Draw(title)
    d.fontmode = "1"
    big, small = ImageFont.truetype(font_path("msgothic.ttc"), 22), ImageFont.truetype(font_path("msgothic.ttc"), 12)
    d.text((120 - big.getlength(brief["title"]) / 2, 5), brief["title"], font=big, fill=tuple(int(v) for v in paper))
    d.text((120 - small.getlength(brief["title_id"]) / 2, 33), brief["title_id"], font=small, fill=(214, 208, 196))
    title = np.asarray(title)
    state = {"last": None, "scene": None, "at": 0.0}

    def scene_at(T):
        if T < T_ROOM1:
            return "spring", spring
        if T < T_HIT:
            return "room1", room
        if T < T_ROOM2:
            return "season" + str(min(int((T - T_HIT) / SEASON_LEN), 2)), seasons
        if T < T_DAWN:
            return "room2", room
        return "dawn", dawn

    def draw(i, t, T):
        name, builder = scene_at(T)
        f = builder(T)
        if name != state["scene"]:
            state["scene"], state["at"] = name, T
        u = (T - state["at"]) / 0.2
        if u < 1 and state["last"] is not None:
            hide = bayer > u
            f[hide] = state["last"][hide]
        if 0.8 <= T < 6.4:
            h, w, _ = title.shape
            x0 = (G - w) // 2
            keep = bayer[6:6 + h, x0:x0 + w] < min(1, (T - 0.8) / 0.3, (6.4 - T) / 0.3)
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
