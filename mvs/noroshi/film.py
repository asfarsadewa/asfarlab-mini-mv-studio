# Noroshi: a person hides an ember in an ash town, climbs to a beacon, lights it on the chorus, and the world answers.
# The plates are painted. All motion is baked 3D sprites plus code. Depth comes from the occlusion maps.
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pixkit import BAYER4, FIRE, INK, Captions, Fire, Occlusion, Sprite, bayer_field, contact_shadow, disc, small_flame
from studio_paths import font_path

BRAZIER = (163, 158)
CAIRNS = [(200, 103), (72, 112), (287, 122)]
HORIZON = 146
SWAY = [(72, 136, 151, 172), (245, 292, 200, 222)]
SUMMIT = (191, 190)  # Where the hero stands beside the brazier.
# The climb is one continuous journey: lower flight, landing turn, upper flight. Each leg names the view to show.
CLIMB_LEGS = [((186, 246), (179, 238), "climb"), ((179, 238), (181, 234), "climb_b"), ((181, 234), (195, 208), "climb_r")]
PIVOT = 0.3
DOOR = (198, 216)  # The doorway that the hero leaves.
ROOM_SPOT = (178, 226)
ROOFS = [(118, 168), (280, 210), (140, 287)]
ARCH = [(175, 127), (90, 70), (282, 78), (57, 190), (311, 193), (97, 268), (259, 273), (60, 17), (303, 17), (185, 13)]
ARCH_SEAT_CENTRE = 132
DUSK = np.array([0.27, 0.31, 0.43])
FOLK_DUSK = (0.56, 0.57, 0.70)
FIRE_LIT = (1.12, 0.92, 0.72)


def make(ctx):
    G, fps, brief, A, root = ctx["grid"], ctx["fps"], ctx["brief"], ctx["a"], ctx["root"]
    paper = np.array(brief["paper"], np.uint8)
    hit = brief["hit"]
    beats = np.array(A["beats"])
    rng = np.random.default_rng(7)
    bayer = bayer_field(G)
    Y, X = np.mgrid[:G, :G]
    caps = Captions(brief["lines"], paper)

    def plate(name):
        d = np.asarray(Image.open(root / f"plates/{name}-360.png").convert("RGB")).copy()
        return {
            "day": d, "paper": (d == paper).all(axis=2),
            "dusk": np.clip(d * DUSK + np.array([6, 8, 16]), 0, 255).astype(np.uint8),
            "warm_day": np.clip(d * np.array([1.16, 1.02, 0.80]), 0, 255).astype(np.uint8),
            "warm_dusk": np.clip(d * np.array([0.82, 0.54, 0.38]) + np.array([12, 6, 4]), 0, 255).astype(np.uint8),
            "occ": Occlusion(root, name),
        }

    town, room, island, arch = plate("town"), plate("room"), plate("island"), plate("archipelago")
    S = {n: Sprite(root, n) for n in ("walk", "crouch", "cradle", "climb", "climb_b", "climb_r", "walk_up", "pivot_180", "pivot_135", "pivot_90", "strike", "stance", "stance_small", "folk_a", "folk_b", "folk_c", "folk_d")}

    def band(name, T):
        v = A[name]
        return v[min(int(T * fps), len(v) - 1)]

    def since_beat(T):
        past = beats[beats <= T]
        return T - past[-1] if len(past) else 9.0

    def beat_after(t, n):
        return beats[min(int(np.argmin(np.abs(beats - t))) + n, len(beats) - 1)]

    # Scene edges sit on beats.
    T_ROOM = 22.84
    T_ISLAND = float(beats[np.argmin(np.abs(beats - 29.73))])
    T_TOWN2 = float(beats[np.argmin(np.abs(beats - 50.33))])
    T_ARCH = float(beats[np.argmin(np.abs(beats - 56.96))])
    T_CROUCH = float(beats[np.argmin(np.abs(beats - 16.03))])

    # The walk ends where the crouch starts, behind the well. Its length comes from the real root path.
    walk = S["walk"]
    steps = next(i for i in range(walk.n) if walk.path(i)[0] <= -46)
    T_WALK = T_CROUCH - steps / walk.fps
    CROUCH_AT = (DOOR[0] + walk.path(steps)[0], DOOR[1] + walk.path(steps)[1])

    # The chorus hit lands on the frame where the torch tip comes closest to the rim of the brazier.
    strike = S["strike"]
    rim_point = (176, 156)
    gaps = [np.hypot(*(np.array(strike.point(i, "tip", *SUMMIT)) - rim_point)) for i in range(strike.n)]
    thrust = 30 + int(np.argmin(gaps[30:]))
    ctx["strike_report"] = (thrust, round(gaps[thrust], 1))
    print("Strike: frame", thrust, "of", strike.n, "tip to rim", round(gaps[thrust], 1), "px", flush=True)
    T_STRIKE0 = hit - thrust / strike.fps
    T_STANCE = T_STRIKE0 + (strike.n - 1) / strike.fps

    # Work back from the torch: pivot, then the plaza walk, then the climb fills the time from the start of the scene.
    walk_up = S["walk_up"]
    plaza = np.hypot(CLIMB_LEGS[-1][1][0] - SUMMIT[0], CLIMB_LEGS[-1][1][1] - SUMMIT[1])
    plaza_frames = next((i for i in range(walk_up.n) if np.hypot(*walk_up.path(i)) >= plaza), walk_up.n - 1)
    T_PIVOT = T_STRIKE0 - PIVOT
    T_PLAZA = T_PIVOT - plaza_frames / walk_up.fps
    leg_lengths = [np.hypot(b[0] - a[0], b[1] - a[1]) for a, b, _ in CLIMB_LEGS]
    climb_total = sum(leg_lengths)
    print("Climb: plays at", round(S["climb"].n / S["climb"].fps / (T_PLAZA - T_ISLAND), 2), "x speed.", flush=True)

    def hero_on_island(T):
        """The hero clip and its feet for this moment. Each moment continues from the one before it."""
        if T < T_PLAZA:
            u = (T - T_ISLAND) / (T_PLAZA - T_ISLAND)
            i = min(int(u * S["climb"].n), S["climb"].n - 1)
            s = u * climb_total
            for (a, b, view), length in zip(CLIMB_LEGS, leg_lengths):
                if s <= length:
                    break
                s -= length
            k = min(s / length, 1)
            return S[view], i, a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k
        if T < T_PIVOT:
            i = min(int((T - T_PLAZA) * walk_up.fps), plaza_frames)
            k = i / max(plaza_frames, 1)
            top = CLIMB_LEGS[-1][1]
            return walk_up, i, top[0] + (SUMMIT[0] - top[0]) * k, top[1] + (SUMMIT[1] - top[1]) * k
        if T < T_STRIKE0:
            view = (180, 135, 90)[min(int((T - T_PIVOT) / PIVOT * 3), 2)]
            return S[f"pivot_{view}"], 0, SUMMIT[0], SUMMIT[1]
        if T < T_STANCE:
            return strike, strike.index(T - T_STRIKE0, "hold"), SUMMIT[0], SUMMIT[1]
        return S["stance"], S["stance"].index(T - T_STANCE, "pingpong"), SUMMIT[0], SUMMIT[1]

    FOLK = [("folk_a", 139, 222, 2), ("folk_b", 150, 233, 3), ("folk_c", 192, 226, 4), ("folk_d", 201, 240, 5), ("folk_b", 128, 233, 6),
            ("folk_c", 214, 218, 7), ("folk_a", 188, 239, 8), ("folk_d", 118, 222, 9), ("folk_a", 176, 203, 10), ("folk_c", 150, 246, 11)]

    # A person must never stand inside a solid object. Stop the render if a path or a position does.
    solids = [o["footprint"] for o in json.loads((root / "occluders.json").read_text(encoding="utf-8"))["town"] if "footprint" in o]

    def clearance(x, y):
        return min(np.hypot((x - cx) / rx, (y - cy) / ry) for cx, cy, rx, ry in solids)

    walk_points = [(DOOR[0] + walk.path(i)[0], DOOR[1] + walk.path(i)[1]) for i in range(steps + 1)]
    spots = {"walk": min(clearance(x, y) for x, y in walk_points), "crouch": clearance(*CROUCH_AT)}
    spots.update({f"{n}@{x},{y}": clearance(x, y) for n, x, y, _ in FOLK + [("hero", 147, 232, 0)]})
    inside = {k: round(v, 2) for k, v in spots.items() if v < 1.0}
    print("Footprint clearance: lowest", round(min(spots.values()), 2), "with 1.0 at the object edge", flush=True)
    if inside:
        raise SystemExit(f"A person stands inside a solid object: {inside}")

    font_title = ImageFont.truetype(font_path("msgothic.ttc"), 32)
    font_small = ImageFont.truetype(font_path("msgothic.ttc"), 12)
    title = Image.new("RGB", (130, 56), INK)
    d = ImageDraw.Draw(title)
    d.fontmode = "1"
    d.text((65 - font_title.getlength("のろし") / 2, 5), "のろし", font=font_title, fill=tuple(int(v) for v in paper))
    d.text((65 - font_small.getlength("Suar") / 2, 40), "Suar", font=font_small, fill=(214, 208, 196))
    title = np.asarray(title)

    ash = [[rng.uniform(0, G), rng.uniform(0, G), rng.uniform(9, 22), rng.uniform(0, 6)] for _ in range(120)]
    fire = Fire(rng)
    puffs, embers, thin = [], [], []
    state = {"burst": False, "last": None, "scene": None, "scene_at": 0.0}

    def smoke_and_embers(f, T, level, mid, high, emit_x, emit_y):
        for p in puffs:
            p["age"] += 1 / fps
            p["y"] -= (34 + 14 * level) / fps
            p["x"] += (10 + 16 * mid + 5 * np.sin(p["age"] * 2 + p["seed"])) / fps
            r = 3 + p["age"] * 4.6
            o = max(0.0, 0.95 - p["age"] * 0.13)
            disc(f, p["x"], p["y"], r, o, (64, 60, 66), bayer)
            disc(f, p["x"] + r * 0.3, p["y"] - r * 0.3, r * 0.55, o * 0.8, (128, 120, 120), bayer)
        puffs[:] = [p for p in puffs if p["y"] > -30 and p["age"] < 8]
        for _ in range(int(1 + high * 6)):
            embers.append([emit_x + rng.uniform(-10, 10), emit_y, rng.uniform(4, 30), rng.uniform(-90, -40), rng.uniform(0.8, 2.4)])
        for e in embers:
            e[0] += e[2] / fps
            e[1] += e[3] / fps
            e[2] += 10 / fps
            e[3] *= 0.985
            e[4] -= 1 / fps
            x, y = int(e[0]), int(e[1])
            if 0 <= x < G and 0 <= y < G and e[4] > 0:
                f[y, x] = FIRE[6] if e[4] > 0.6 else FIRE[3]
        embers[:] = [e for e in embers if e[4] > 0]

    def beacon(f, x, y, T, at, size, column, k=0):
        """A far fire with a thin signal column and a ring when it lights."""
        age = T - at
        if age < 0:
            return
        for j in range(column):
            row = y - size - j
            cx = x + int(j * 0.25 + np.sin(T * 3 + j * 0.18 + k) * 1.5)
            if 0 <= row < G and 0 <= cx < G - 2 and bayer[row, cx] < 0.95 - j * (0.8 / max(column, 1)) and age * 36 > j:
                f[row, cx:cx + 2 + j // 18] = (112, 106, 112)
        small_flame(f, x, y, T, size)
        if age < 0.45:
            disc(f, x, y - 3, 3 + age * 44, 0.5 * (1 - age / 0.45), tuple(int(v) for v in FIRE[5]), bayer)

    def town_night(T, level, bass, mid, high):
        f = town["dusk"].copy()
        for a in ash:
            a[1] += (a[2] + bass * 26) / fps
            a[0] += (6 + 10 * np.sin(T * 0.7 + a[3])) / fps
            if a[1] > G:
                a[1], a[0] = 0.0, rng.uniform(0, G)
            f[int(a[1]) % G, int(a[0]) % G] = (176, 180, 194)
        ground = ~town["paper"]
        if T >= T_CROUCH:
            x, y = CROUCH_AT
            contact_shadow(f, x, y, 7, 2.5, 0.8, bayer, ground, 1, occ=town["occ"])
            S["crouch"].draw(f, S["crouch"].index(T - T_CROUCH, "pingpong"), x, y, occ=town["occ"], grade=FOLK_DUSK, bayer=bayer)
        elif T >= T_WALK:
            i = walk.index(T - T_WALK, "hold")
            dx, dy = walk.path(i)
            x, y = DOOR[0] + dx, DOOR[1] + dy
            contact_shadow(f, x, y, 6, 2, 0.8, bayer, ground, 1, occ=town["occ"])
            walk.draw(f, i, x, y, occ=town["occ"], grade=FOLK_DUSK, reveal=min(1, (T - T_WALK) / 0.35), bayer=bayer)
        if 6.6 <= T < 11.6:
            h, w, _ = title.shape
            hide = bayer[50:50 + h, (G - w) // 2:(G + w) // 2] > min(1, (T - 6.6) / 0.25, (11.6 - T) / 0.25)
            part = f[50:50 + h, (G - w) // 2:(G + w) // 2]
            part[~hide] = title[~hide]
        return f

    def room_scene(T, level, bass, mid, high):
        f = room["dusk"].copy()
        spr = S["cradle"]
        t = T - T_ROOM
        i = spr.index(t, "hold")
        x, y = ROOM_SPOT
        hx = (spr.point(i, "left", x, y)[0] + spr.point(i, "right", x, y)[0]) / 2
        hy = (spr.point(i, "left", x, y)[1] + spr.point(i, "right", x, y)[1]) / 2
        radius = 24 + t * 6 + level * 14
        lit = (np.hypot(X - hx, Y - hy) + bayer * 14 < radius) & ~room["paper"]
        f[lit] = room["warm_dusk"][lit]
        contact_shadow(f, x, y, 22, 7, 0.9, bayer, ~room["paper"], 2, occ=room["occ"])
        spr.draw(f, i, x, y, occ=room["occ"], grade=(0.42, 0.44, 0.56), bayer=bayer, light=(hx, hy, radius * 0.8, (0.98, 0.76, 0.58)))
        # The ember sits in the hands, in front of the chest.
        small = 2 + int(level * 2)
        disc(f, hx, hy, small + 1, 0.9, tuple(int(v) for v in FIRE[3]), bayer)
        disc(f, hx, hy, small, 1.0, tuple(int(v) for v in FIRE[6]), bayer)
        return f

    def island_base(T, mid, bob):
        xmap, ymap = X.copy(), Y.copy()
        for x0, x1, y0, y1 in SWAY:
            for y in range(y0, y1):
                shift = int(round(np.sin(T * 2.6 + y * 0.12) * (y1 - y) / (y1 - y0) * (1.2 + 1.4 * mid)))
                xmap[y, x0:x1] = np.clip(X[y, x0:x1] - shift, 0, G - 1)
        if bob:
            ymap[HORIZON:] = np.clip(Y[HORIZON:] - bob, 0, G - 1)
        return xmap, ymap

    def wind_streaks(f, T, mid, lit):
        count = int((10 + 26 * mid) if not lit else 6 + 8 * mid)
        for k in range(count):
            y = int((k * 47 + 13) % 300) + 10
            x = int((k * 83 + T * (150 + k * 9)) % (G + 60)) - 40
            n = 8 + k % 18
            if x + n <= 0:
                continue
            row = f[y, max(x, 0):min(x + n, G)]
            # Wind shows only against open sky. A dash across the painted rock reads as a glitch.
            sky = island["paper"][y, max(x, 0):min(x + n, G)]
            row[((np.arange(len(row)) + y) % 3 != 0) & sky] = (120, 128, 150) if not lit else (222, 216, 206)

    def island_scene(T, level, bass, mid, high):
        after = T - hit
        lit = after >= 0
        bob = -int(round(2 * np.exp(-since_beat(T) * 7))) if lit else 0
        xmap, ymap = island_base(T, mid, bob)
        src_day, src_dusk = island["day"][ymap, xmap], island["dusk"][ymap, xmap]
        src_warm, src_wd = island["warm_day"][ymap, xmap], island["warm_dusk"][ymap, xmap]
        src_paper = island["paper"][ymap, xmap]
        occ = island["occ"]
        dist = np.hypot(X - BRAZIER[0], Y - BRAZIER[1])
        front = 900 * after if lit else -1
        f = np.where((dist + bayer * 40 < front)[..., None], src_day, src_dusk)
        grade = None if lit else FOLK_DUSK

        # Choose the hero clip for this moment.
        spr, i, x, y = hero_on_island(T)
        y = y + bob
        tip = spr.point(i, "tip", x, y)

        if lit:
            radius = (58 + 26 * (0.7 + 0.5 * bass)) * min(1, after / 0.5)
            glow = (dist + bayer * 22 < radius) & ~src_paper & (Y >= HORIZON)
            f[glow] = src_warm[glow]
        else:
            pool = (np.hypot(X - tip[0], Y - tip[1]) + bayer * 8 < 18 + 5 * level) & ~src_paper & (Y >= HORIZON)
            f[pool] = src_wd[pool]
        wind_streaks(f, T, mid, lit)

        if lit and int(T * fps) % 3 == 0:
            puffs.append({"x": BRAZIER[0] + rng.uniform(-4, 4), "y": BRAZIER[1] - 22, "age": 0.0, "seed": rng.uniform(0, 6)})
        smoke_mid = mid
        heat = 0
        if lit:
            heat = 36 if after < 0.5 else int(24 + 12 * bass)
        fire.step(heat, 2 if lit and after < 0.5 else 3 + int((1 - level) * 2))

        contact_shadow(f, x, y, 11, 3.5, 0.85, bayer, ~src_paper & (Y >= HORIZON), 2, occ=occ, lift=bob)
        # The hero stands in front of the brazier, and any nearer rock hides the hero. Firelight warms the near side.
        if lit:
            light = (BRAZIER[0], BRAZIER[1] + 10, 40 + 14 * bass, FIRE_LIT)
        else:
            light = (tip[0], tip[1], 20 + 4 * level, (0.92, 0.70, 0.56))
        spr.draw(f, i, x, y, occ=occ, lift=bob, grade=grade, bayer=bayer, light=light)
        small_flame(f, int(tip[0]), int(tip[1]), T, 5 + 2 * level)

        # The flame stays inside the bowl: the front of the brazier masks it.
        fire.draw(f, BRAZIER[0], BRAZIER[1] + bob, blocked=occ.blocks(170, bob))
        if lit:
            smoke_and_embers(f, T, level, smoke_mid, high, BRAZIER[0], BRAZIER[1] - 14)
            if not state["burst"]:
                state["burst"] = True
                for _ in range(90):
                    a, s = rng.uniform(0, 2 * np.pi), rng.uniform(30, 130)
                    embers.append([BRAZIER[0], BRAZIER[1] - 8, np.cos(a) * s, np.sin(a) * s - 40, rng.uniform(0.7, 1.8)])
            for k, (cx, cy) in enumerate(CAIRNS):
                beacon(f, cx, cy, T, beat_after(hit, 2 * (k + 1)), int(7 + 2 * bass), 44, k)
            if after < 0.4:
                amount = 3 * np.exp(-after * 8)
                f = np.roll(f, (int(round(amount * np.sin(after * 70))), int(round(amount * np.cos(after * 55)))), axis=(0, 1))
        return f

    def town_day(T, level, bass, mid, high):
        f = town["day"].copy()
        t = T - T_TOWN2
        occ = town["occ"]
        ground = ~town["paper"]
        for k, (rx, ry) in enumerate(ROOFS):
            beacon(f, rx, ry, T, beat_after(T_TOWN2, 2 * k), int(11 + 3 * bass), 70, k)
        # Depth order on screen: draw far people first, so nearer people overlap them.
        people = sorted(FOLK + [("hero", 147, 232, 0)], key=lambda p: p[2])
        for name, x, y, n in people:
            at = beat_after(T_TOWN2, n)
            if T < at:
                continue
            spr = S["stance_small"] if name == "hero" else S[name]
            i = spr.index(T - at + n * 0.13, "pingpong")
            bob = 0 if name == "hero" else -int(round(1.5 * np.exp(-since_beat(T) * 7)))
            contact_shadow(f, x, y, 6, 2, 0.8, bayer, ground, 1, occ=occ)
            spr.draw(f, i, x, y + bob, occ=occ, reveal=min(1, (T - at) / 0.25), bayer=bayer)
            if name == "hero":
                tip = spr.point(i, "tip", x, y)
                small_flame(f, int(tip[0]), int(tip[1]), T, 5 + 2 * level)
        return f

    def arch_scene(T, level, bass, mid, high):
        f = arch["day"].copy()
        order = sorted(range(len(ARCH)), key=lambda k: np.hypot(ARCH[k][0] - ARCH[0][0], ARCH[k][1] - ARCH[0][1]))
        for n, k in enumerate(order):
            x, y = ARCH[k]
            big = k == 0
            size = int((14 if big else 7) + (5 if big else 2) * bass)
            seat = ARCH_SEAT_CENTRE if big else y + 2
            sub = f.copy() if big else None
            beacon(f, x, seat, T, T_ARCH if big else beat_after(T_ARCH, 2 + n), size, 90 if big else 46, k)
            if big:
                # Re-stamp the front of the centre brazier over its flame.
                front = arch["occ"].blocks(135)
                f[front] = arch["day"][front]
        return f

    def draw(i, t, T):
        level, bass, mid, high = band("level", T), band("bass", T), band("mid", T), band("high", T)
        if T < T_ROOM:
            name, f = "town_night", town_night(T, level, bass, mid, high)
        elif T < T_ISLAND:
            name, f = "room", room_scene(T, level, bass, mid, high)
        elif T < T_TOWN2:
            name, f = "island", island_scene(T, level, bass, mid, high)
        elif T < T_ARCH:
            name, f = "town_day", town_day(T, level, bass, mid, high)
        else:
            name, f = "arch", arch_scene(T, level, bass, mid, high)

        # Cut on the beat with a short Bayer dissolve from the last frame.
        if name != state["scene"]:
            state["scene"], state["scene_at"] = name, T
        u = (T - state["scene_at"]) / 0.17
        if u < 1 and state["last"] is not None:
            hide = bayer > u
            f[hide] = state["last"][hide]
        caps.draw(f, T)
        # Open from flat dusk. Close by dissolving to paper when the last chord ends.
        if T < 0.5:
            hide = bayer > T / 0.5
            f[hide] = town["dusk"][0, 0]
        left = ctx["end"] - T
        if left < 0.7:
            hide = bayer > left / 0.7
            f[hide] = paper
        state["last"] = np.array(f, np.uint8)
        return f.astype(np.uint8)

    return draw
