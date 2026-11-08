# 거울 속 우리: Seoul, 2011. A small dance academy closes tomorrow. Five trainees who never debuted come back at night
# for one last run of their routine. They dance before the mirror wall, then on the rooftop over the city. At dawn they
# walk off in five directions, and the mirror in the empty room shows them dancing for one more beat.
# The plates never move. Footprints guard every path. Every walker faces the way that it moves.
# The mirror shows the front view of each dancer, flipped and set back to the mirrored depth.
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pixkit import INK, Captions, Occlusion, Sprite, bayer_field, contact_shadow
from studio_paths import font_path

MEMBERS = ["m1", "m2", "m3", "m4", "m5"]
DOOR = (112, 257)
CORNER = (128, 214)  # The lane turns here behind the academy building, so the building hides a walker.
LANE = (155, 226)
FRONT = (153, 261)  # In front of the building corner, so a walker never cuts behind it.
LEAVE = {"m1": [FRONT, LANE, CORNER], "m2": [(226, 286)], "m3": [(214, 270)], "m4": [(72, 281)], "m5": [(138, 290)]}
LEAVE_CLIPS = {"m1": ["g_out", "g_out", "g_ul"], "m2": ["g_out"], "m3": ["g_out"], "m4": ["g_out"], "m5": ["g_out"]}
MIRROR = (88, 185, 238, 245)  # x0, y0, x1, floor row of the mirror
FORM_A = {"m1": (163, 251), "m2": (143, 257), "m4": (183, 257), "m3": (123, 264), "m5": (203, 264)}
FORM_B = {"m1": (163, 267), "m2": (140, 260), "m4": (186, 260), "m3": (118, 253), "m5": (208, 253)}
RAP = {"m3": (190, 254), "m1": (150, 234), "m2": (175, 229), "m4": (205, 229), "m5": (230, 234)}
FINAL = {"m1": (190, 264), "m2": (165, 249), "m4": (215, 249), "m3": (140, 235), "m5": (240, 235)}
SPOT_ORDER = ["m1", "m2", "m4", "m3", "m5"]


def make(ctx):
    G, fps, brief, A, root = ctx["grid"], ctx["fps"], ctx["brief"], ctx["a"], ctx["root"]
    paper = np.array(brief["paper"], np.uint8)
    beats = np.array(A["beats"])
    bar = 4 * 60 / A["tempo"]
    rng = np.random.default_rng(11)
    bayer = bayer_field(G)
    Y, X = np.mgrid[:G, :G]
    caps = Captions(brief["lines"], paper, top_font=(font_path("malgun.ttf"), 15), low_font=(font_path("msgothic.ttc"), 12))
    shapes = json.loads((root / "occluders.json").read_text(encoding="utf-8"))

    def beat(t):
        return float(beats[np.argmin(np.abs(beats - t))])

    T_ROOM, T_HIT, T_SWAP, T_ROOF, T_BRIDGE, T_FINAL, T_RIPPLE, T_DAWN, T_EMPTY = (
        beat(27.87), brief["hit"], beat(45.07), beat(54.13), beat(66.1), beat(70.47), beat(80.14), beat(89.0), beat(99.4))
    T_FADE = 106.4  # The mirror lets them go on the last word.

    def plate(name, occ):
        d = np.asarray(Image.open(root / f"plates/{name}-360.png").convert("RGB")).copy()
        is_paper = (np.abs(d.astype(int) - paper.astype(int)).sum(axis=2) < 24) | (d.astype(int).sum(axis=2) > 720)
        d[is_paper] = paper
        return {"name": name, "day": d, "paper": is_paper, "occ": Occlusion(root, occ)}

    P = {"golmok": plate("golmok", "golmok"), "golmok_asa": plate("golmok_asa", "golmok"), "yeonseupsil": plate("yeonseupsil", "yeonseupsil"),
         "yeonseupsil_asa": plate("yeonseupsil_asa", "yeonseupsil"), "oksang": plate("oksang", "oksang")}
    sprites = {}

    def S(folder, name):
        if (folder, name) not in sprites:
            sprites[(folder, name)] = Sprite(root, name, folder)
        return sprites[(folder, name)]

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

    guard("golmok", path_points([CORNER, LANE, FRONT, DOOR]) + sum((path_points([DOOR] + LEAVE[m]) for m in MEMBERS), []))
    guard("yeonseupsil", list(FORM_A.values()) + list(FORM_B.values()))
    guard("oksang", list(RAP.values()) + list(FINAL.values()))
    checked = set()

    def heading(spr, dx, dy):
        """Stops the render if a clip walks against its path. A backward walker reads as a moonwalk."""
        key = spr.name
        if key in checked or np.hypot(dx, dy) < 8:
            return
        p0, p1 = spr.path(0), spr.path(spr.n - 1)
        if (p1[0] - p0[0]) * dx + (p1[1] - p0[1]) * dy < 0:
            raise SystemExit(f"{spr.name} walks against its path. Bake it 180 degrees around.")
        checked.add(key)

    def stride(spr):
        p0, p1 = spr.path(0), spr.path(spr.n - 1)
        return max(np.hypot(p1[0] - p0[0], p1[1] - p0[1]), 1.0)

    def follow(folder, clips, pts, t0, t1, T):
        """Moves one walker along a polyline at an even speed. The frame follows the distance walked."""
        legs = [np.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:])]
        d = float(np.clip((T - t0) / (t1 - t0), 0, 1)) * sum(legs)
        done = 0.0
        for k, leg in enumerate(legs):
            if d <= done + leg or k == len(legs) - 1:
                a, b = pts[k], pts[k + 1]
                spr = S(folder, clips[k])
                heading(spr, b[0] - a[0], b[1] - a[1])
                v = min((d - done) / max(leg, 1e-6), 1.0)
                return spr, int(d / stride(spr) * (spr.n - 1)) % spr.n, a[0] + (b[0] - a[0]) * v, a[1] + (b[1] - a[1]) * v
            done += leg

    def person(f, spr, i, x, y, pl, grade=None, sh=(6, 2), reveal=1.0, light=None):
        contact_shadow(f, x, y, sh[0], sh[1], 0.8, bayer, ~pl["paper"], 2, occ=pl["occ"])
        spr.draw(f, i, x, y, occ=pl["occ"], grade=grade, bayer=bayer, reveal=reveal, light=light)

    def draw_all(f, people, pl, grade=None):
        for y, s, i, x, rev, light in sorted(people, key=lambda p: p[0]):
            person(f, s, i, x, y, pl, grade=grade, reveal=rev, light=light)

    def dance(spr, T, t0, lag=0.0):
        """Plays a dance clip from a beat. Every member shares the start, so the group moves as one."""
        return int(max(T - t0 - lag, 0) * spr.fps) % spr.n

    BEAT = 60 / A["tempo"]
    CHAIN = [16, 52, 88, 124, 160]  # The first frame of each of the five moves. The hook clip has 193 frames at 24 fps.

    def chained(spr, T, t0, tc, order):
        """The domino chain. On beat k of the chain, member k plays move k. The others hold their poses."""
        k = order
        if T < tc:
            return dance(spr, T, t0)
        if T >= tc + 5 * BEAT:
            # All five snap back into the hook together, in sync with the music.
            return dance(spr, T, t0)
        start, n = CHAIN[k], int(BEAT * spr.fps)
        breath = int(T / 0.15) % 2
        if T < tc + k * BEAT:
            return min(start + breath, spr.n - 1)
        if T < tc + (k + 1) * BEAT:
            return min(start + int((T - tc - k * BEAT) * spr.fps), spr.n - 1)
        return min(start + n - 1 - breath, spr.n - 1)

    SENT = np.array([1, 2, 3], np.uint8)

    def reflect(f, folder, clip, i, x, y, strength):
        """Draws the front view in the mirror. It stands at the mirrored depth, flipped left to right."""
        x0, y0, x1, floor = MIRROR
        yr = 2 * floor - y
        c = np.empty((G, G, 3), np.uint8)
        c[:] = SENT
        S(folder, clip).draw(c, i, G - 1 - x, yr)
        c = c[:, ::-1]
        m = (c != SENT).any(axis=2)
        m[:y0], m[floor:], m[:, :x0], m[:, x1:] = False, False, False, False
        m &= bayer < strength
        f[m] = (c[m] * 0.78 + f[m] * 0.22).astype(np.uint8)

    def pool(f, pl, x, y, r, gain):
        m = (np.hypot(X - x, (Y - y) * 2.2) + bayer * 6 < r) & ~pl["paper"]
        f[m] = np.clip(f[m].astype(np.float32) * gain, 0, 255).astype(np.uint8)

    # --- The rainy alley: they arrive one by one and go in. ---
    rain = [(rng.uniform(20, 340), rng.uniform(40, 330), rng.uniform(0, 1)) for _ in range(140)]

    def raining(f, pl, T, amount=1.0):
        for k, (x0, y0, ph) in enumerate(rain[:int(len(rain) * amount)]):
            y = (y0 + (T * 260 + ph * 300)) % 300 + 30
            x = int(x0 - (y - 30) * 0.12) % G
            for d in range(4):
                yy, xx = int(y) + d, x - d // 3
                if 0 <= yy < G and 0 <= xx < G and not pl["paper"][yy, xx]:
                    f[yy, xx] = np.clip(f[yy, xx].astype(int) + 46, 0, 255)
            # A ripple where the drop lands.
            if k % 3 == 0 and (T * 5 + ph) % 1 < 0.25:
                gx, gy = int(x0), int(250 + (y0 % 30))
                if 0 <= gy < G and 0 <= gx < G - 2 and not pl["paper"][gy, gx]:
                    f[gy, gx - 1:gx + 2] = np.clip(f[gy, gx - 1:gx + 2].astype(int) + 30, 0, 255)

    ARRIVE = {"m1": 1.6, "m2": 6.1, "m3": 10.6, "m4": 15.1, "m5": 15.8}

    def alley(T):
        pl = P["golmok"]
        f = pl["day"].copy()
        # The academy sign flickers.
        if (int(T * 7) * 37 % 11) == 3:
            sign = (X > 74) & (X < 104) & (Y > 156) & (Y < 182) & ~pl["paper"]
            f[sign] = (f[sign] * 0.62).astype(np.uint8)
        people = []
        for k, m in enumerate(MEMBERS):
            t0 = ARRIVE[m]
            if t0 <= T < t0 + 3.6:
                off = 8 if m == "m5" else 0
                # Each member walks out from behind the academy building, so the building reveals him.
                pts = [(CORNER[0] + off // 2, CORNER[1] + off // 2), (LANE[0] + off, LANE[1] + off // 2), (FRONT[0] + off, FRONT[1] + off // 3), DOOR]
                spr, i, x, y = follow(m, ["g_dr", "g_in", "g_door"], pts, t0, t0 + 3.6, T)
                fade = min(1.0, (t0 + 3.6 - T) / 0.4)
                people.append((y, spr, i, x, fade, None))
        draw_all(f, people, pl, grade=(0.86, 0.88, 1.0))
        raining(f, pl, T)
        return f

    # --- The practice room: they dance before the mirror. ---
    def formation(T):
        if T < T_SWAP + 5 * BEAT:
            return dict(FORM_A)
        u = float(np.clip((T - T_SWAP - 5 * BEAT) / BEAT, 0, 1))
        return {m: (FORM_A[m][0] + (FORM_B[m][0] - FORM_A[m][0]) * u, FORM_A[m][1] + (FORM_B[m][1] - FORM_A[m][1]) * u) for m in MEMBERS}

    def room(T):
        pl = P["yeonseupsil"]
        f = pl["day"].copy()
        clip, t0 = ("count", T_ROOM) if T < T_HIT else ("hook", T_HIT)
        form = formation(T)
        lead = SPOT_ORDER[int((T - T_HIT) / bar) % 5] if T >= T_HIT else None
        for m in sorted(MEMBERS, key=lambda m: -form[m][1]):
            x, y = form[m]
            spr = S(m, "f_" + clip)
            i = chained(spr, T, t0, T_SWAP, SPOT_ORDER.index(m)) if clip == "hook" else dance(spr, T, t0)
            reflect(f, m, "f_" + clip, i, x, y, 0.9)
        people = []
        for m in MEMBERS:
            x, y = form[m]
            spr = S(m, "r_" + clip)
            i = chained(spr, T, t0, T_SWAP, SPOT_ORDER.index(m)) if clip == "hook" else dance(spr, T, t0)
            light = None
            if m == lead:
                pool(f, pl, x, y, 16, 1.25)
                light = (x, y - 20, 40, (1.18, 1.14, 1.06))
            people.append((y, spr, i, x, 1.0, light))
        draw_all(f, people, pl)
        return f

    # --- The rooftop: the rap, the bridge and the final chorus. ---
    bulbs = None

    def roof(T):
        nonlocal bulbs
        pl = P["oksang"]
        f = pl["day"].copy()
        if bulbs is None:
            warm = (f[..., 0].astype(int) > 215) & (f[..., 1].astype(int) > 185) & (f[..., 2].astype(int) < 170) & ~pl["paper"] & (Y < 200)
            bulbs = np.argwhere(warm)
        if len(bulbs):
            flick = bulbs[(np.arange(len(bulbs)) * 7 + int(T * 4)) % 9 == 0]
            f[flick[:, 0], flick[:, 1]] = (f[flick[:, 0], flick[:, 1]] * 0.7).astype(np.uint8)
        people = []
        if T < T_BRIDGE:
            for m in MEMBERS:
                x, y = RAP[m]
                spr = S(m, "o_move")
                light = (x, y - 20, 40, (1.15, 1.12, 1.05)) if m == "m3" else None
                if m == "m3":
                    pool(f, pl, x, y, 15, 1.2)
                people.append((y, spr, dance(spr, T, T_ROOF), x, 1.0, light))
            draw_all(f, people, pl, grade=(0.95, 0.95, 1.0))
        elif T < T_FINAL:
            # The beat drops. One tenor stands in the light. The others wait in the dark.
            dark = ~pl["paper"]
            f[dark] = (f[dark] * 0.72).astype(np.uint8)
            x, y = RAP["m2"]
            pool(f, pl, x, y, 18, 1.5)
            for m in MEMBERS:
                x, y = RAP[m]
                # The bridge moves in slow motion. The tenor reaches out slowly. The others sway at half speed.
                spr = S(m, "o_hook" if m == "m2" else "o_move")
                speed = 0.4 if m == "m2" else 0.5
                i = int((T - T_BRIDGE) * spr.fps * speed + (30 if m == "m2" else 0)) % spr.n
                light = (x, y - 20, 40, (1.3, 1.25, 1.12)) if m == "m2" else None
                people.append((y, spr, i, x, 1.0, light))
            draw_all(f, people, pl, grade=(0.8, 0.82, 0.95))
            for y, s, i, x, rev, light in people:
                if light:
                    person(f, s, i, x, y, pl, light=light)
        else:
            u = float(np.clip((T - T_FINAL) / (60 / A["tempo"]), 0, 1))
            lead = SPOT_ORDER[int((T - T_FINAL) / bar) % 5]
            for m in MEMBERS:
                x = RAP[m][0] + (FINAL[m][0] - RAP[m][0]) * u
                y = RAP[m][1] + (FINAL[m][1] - RAP[m][1]) * u
                spr = S(m, "o_hook")
                light = None
                if m == lead:
                    pool(f, pl, x, y, 15, 1.2)
                    light = (x, y - 20, 40, (1.15, 1.12, 1.05))
                people.append((y, spr, chained(spr, T, T_FINAL, T_RIPPLE, SPOT_ORDER.index(m)), x, 1.0, light))
            draw_all(f, people, pl)
        return f

    # --- Dawn: they lock up and walk off in five directions. ---
    LEAVE_AT = {m: T_DAWN + 0.6 + k * 1.1 for k, m in enumerate(MEMBERS)}

    def dawn(T):
        pl = P["golmok_asa"]
        f = pl["day"].copy()
        raining(f, pl, T, amount=float(np.clip(1 - (T - T_DAWN) / 2.0, 0, 1)) * 0.3)
        people = []
        for m in MEMBERS:
            t0 = LEAVE_AT[m]
            if t0 <= T < t0 + 4.0:
                spr, i, x, y = follow(m, LEAVE_CLIPS[m], [DOOR] + LEAVE[m], t0, t0 + 4.0, T)
                # The member who takes the lane walks back behind the building. The building hides him.
                fade = min(1.0, (T - t0) / 0.5) if m == "m1" else min(1.0, (T - t0) / 0.5, (t0 + 4.0 - T) / 0.8)
                people.append((y, spr, i, x, fade, None))
        draw_all(f, people, pl)
        return f

    # --- The empty room at dawn: the mirror remembers them for one more beat. ---
    def empty_room(T):
        pl = P["yeonseupsil_asa"]
        f = pl["day"].copy()
        strength = float(np.clip(min((T - T_EMPTY) / 1.2, (T_FADE - T) / 2.4), 0, 0.85))
        if strength > 0:
            for m in sorted(MEMBERS, key=lambda m: -FORM_A[m][1]):
                x, y = FORM_A[m]
                reflect(f, m, "f_hook", dance(S(m, "f_hook"), T, T_EMPTY), x, y, strength)
        return f

    title = Image.new("RGB", (240, 50), INK)
    d = ImageDraw.Draw(title)
    d.fontmode = "1"
    big, small = ImageFont.truetype(font_path("malgun.ttf"), 22), ImageFont.truetype(font_path("msgothic.ttc"), 12)
    d.text((120 - big.getlength(brief["title"]) / 2, 3), brief["title"], font=big, fill=tuple(int(v) for v in paper))
    d.text((120 - small.getlength(brief["title_id"]) / 2, 33), brief["title_id"], font=small, fill=(214, 208, 196))
    title = np.asarray(title)
    state = {"last": None, "scene": None, "at": 0.0}

    def scene_at(T):
        for end, name, fn in ((T_ROOM, "alley", alley), (T_ROOF, "room", room), (T_DAWN, "roof", roof), (T_EMPTY, "dawn", dawn)):
            if T < end:
                return name, fn
        return "empty", empty_room

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
