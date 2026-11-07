# Layangan Pedhot, her side of the sea: he sings that her letters stopped.
# We see her in the far city, asleep each night over a letter she cannot finish.
# On Sunday the women dance in the park. On the roof she lets her own kite go.
# In the outro her kite crosses his in the middle of the paper, and neither knows.
# The plate never moves. Footprints guard every path. No person holds one frame.
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pixkit import INK, Captions, Occlusion, Sprite, bayer_field, contact_shadow
from studio_paths import font_path

STRING = (112, 92, 72)
MOTE = (255, 226, 120)
LAMP = (255, 222, 150)
NIGHT_PAPER = (24, 26, 48)
T_STREET, T_PARK, T_ALONE, T_ROOF, T_SEA = 31.2, 41.6, 62.7, 75.7, 97.0
T_HIT, T_LET = 41.8, 89.0
DAY = np.array([1.0, 1.0, 0.98])
DUSK = np.array([0.74, 0.70, 0.88])
NIGHT = np.array([0.60, 0.60, 0.80])
GOLDEN = np.array([1.05, 0.96, 0.86])
SPR_DUSK = (0.86, 0.82, 0.94)
SPR_NIGHT = (0.76, 0.74, 0.92)
SPR_GOLD = (1.04, 0.96, 0.88)

SINK = (150, 258)
TABLE = (206, 254)
ALONE = (186, 252)
PIN = (270, 142)
PILE = (248, 201)
WINDOW = (186, 128, 240, 172)
BOX_SPOT = (124, 262)
SLOT = (103, 236)
HER_PARK = (178, 250)
FRIEND = (205, 252)
PARK_CROWD = [
    ("w", 96, 226), ("f", 132, 216), ("p", 170, 210), ("w", 210, 212), ("f", 248, 218), ("p", 284, 228),
    ("p", 74, 244), ("w", 112, 248), ("f", 146, 240), ("w", 236, 244), ("p", 268, 250), ("f", 300, 246),
    ("f", 128, 268), ("p", 160, 278), ("w", 200, 280), ("f", 234, 270),
]
ARRIVALS = [("p", "se", 106, 254), ("w", "se", 58, 232), ("f", "se", 180, 226), ("w", "sw", 276, 244), ("p", "sw", 228, 228), ("f", "sw", 318, 234)]
SITTERS = [("w", 44, 218), ("f", 70, 214), ("p", 312, 218), ("w", 268, 248), ("f", 66, 236)]
ROOF_FROM = (92, 208)
LINES_ROOF = [((292, 196), (335, 199)), ((280, 208), (327, 212)), ((268, 221), (317, 228))]
SHIRTS = [(0, 0.3, (232, 226, 210)), (0, 0.7, (150, 170, 196)), (1, 0.4, (214, 196, 170)), (1, 0.8, (232, 226, 210)), (2, 0.35, (170, 190, 170)), (2, 0.72, (226, 214, 196))]
HEADLAND = (92, 261)
TOWER_TOP = (306, 107)


def key_props(path):
    arr = np.asarray(Image.open(path).convert("RGB")).astype(np.int32)
    keep = ~((arr[..., 0] > 170) & (arr[..., 2] > 170) & (arr[..., 1] < 110))
    h, w = keep.shape
    out = {}
    for name, (x0, x1, y0, y1) in {"kite": (0, int(w * 0.41), 0, h // 2), "letter": (0, int(w * 0.41), h // 2, h)}.items():
        part = keep[y0:y1, x0:x1]
        ys, xs = np.nonzero(part.sum(axis=1) > 2)[0], np.nonzero(part.sum(axis=0) > 2)[0]
        box = (x0 + xs.min(), y0 + ys.min(), x0 + xs.max() + 1, y0 + ys.max() + 1)
        out[name] = np.dstack([arr[box[1]:box[3], box[0]:box[2]], keep[box[1]:box[3], box[0]:box[2]] * 255]).astype(np.uint8)
    return out


def scaled(prop, width):
    img = Image.fromarray(prop, "RGBA")
    k = width / img.width
    small = np.asarray(img.resize((max(2, int(img.width * k)), max(2, int(img.height * k))), Image.BOX)).copy()
    small[..., 3] = (small[..., 3] > 110) * 255
    return small


def stamp(f, a, x0, y0):
    G = f.shape[0]
    h, w = a.shape[:2]
    x0, y0 = int(x0), int(y0)
    ax0, ay0, ax1, ay1 = max(x0, 0), max(y0, 0), min(x0 + w, G), min(y0 + h, G)
    if ax0 >= ax1 or ay0 >= ay1:
        return
    part = a[ay0 - y0:ay1 - y0, ax0 - x0:ax1 - x0]
    solid = part[..., 3] > 0
    f[ay0:ay1, ax0:ax1][solid] = part[..., :3][solid]


def load_birds(path):
    raw = Image.open(path).convert("RGBA")
    cw, ch = raw.width // 4, raw.height // 2
    frames = []
    for row in range(2):
        for col in range(4):
            cell = raw.crop((col * cw, row * ch, (col + 1) * cw, (row + 1) * ch))
            frames.append(cell.crop(cell.getchannel("A").point(lambda v: 255 if v > 127 else 0).getbbox()))
    return frames


def make(ctx):
    G, fps, brief, A, root = ctx["grid"], ctx["fps"], ctx["brief"], ctx["a"], ctx["root"]
    paper = np.array(brief["paper"], np.uint8)
    beats = np.array(A["beats"])
    rng = np.random.default_rng(53)
    bayer = bayer_field(G)
    Y, X = np.mgrid[:G, :G]
    caps = Captions(brief["lines"], paper, top_font=(font_path("msgothic.ttc"), 16), low_font=(font_path("simsun.ttc"), 12))
    shapes = json.loads((root / "occluders.json").read_text(encoding="utf-8"))

    def plate(name):
        d = np.asarray(Image.open(root / f"plates/{name}-360.png").convert("RGB")).copy()
        is_paper = (np.abs(d.astype(int) - paper.astype(int)).sum(axis=2) < 24) | (d.astype(int).sum(axis=2) > 720)
        d[is_paper] = paper
        return {"name": name, "day": d, "paper": is_paper, "occ": Occlusion(root, name)}

    P = {n: plate(n) for n in ("dapur", "pos", "taman", "atap", "seberang")}

    def graded(pl, k):
        out = np.clip(pl["day"] * k, 0, 255).astype(np.uint8)
        out[pl["paper"]] = paper
        return out

    def loader(folder):
        out = {}
        for n in json.loads((root / folder / "jobs.json").read_text()):
            if (root / folder / "sprites" / f"{n}.png").exists():
                out[n] = Sprite(root, n, folder)
        return out

    W, V, Fr, C, H = loader("hero_her"), loader("hero_folk2"), loader("hero_friend"), loader("hero_city"), loader("hero_him")

    # Half of the friends wear another colour, so the crowd is not one blue shirt.
    for name, spr in Fr.items():
        if name.startswith("fp_"):
            frames = spr.frames.copy()
            rgb = frames[..., :3].astype(np.float32)
            blue = (rgb[..., 2] > rgb[..., 0] * 1.12) & (rgb[..., 2] > rgb[..., 1] * 1.02) & (frames[..., 3] > 0)
            light = (rgb.mean(axis=-1) / 120.0)[..., None]
            rgb = np.where(blue[..., None], np.clip(light * np.array([196, 150, 112], np.float32), 0, 255), rgb)
            frames[..., :3] = rgb.astype(np.uint8)
            spr.frames = frames

    props = key_props(root / "plates/props-raw.png")
    prop_cache = {}

    def prop(name, width):
        if (name, width) not in prop_cache:
            prop_cache[(name, width)] = scaled(props[name], width)
        return prop_cache[(name, width)]

    birds = load_birds(root / "plates/egret-raw.png")
    bird_cache = {}

    def flock(f, T, n, height, speed, width, offset=0.0):
        for k in range(n):
            x = ((T + offset) * speed - k * width * 1.4) % (G + 160) - 80
            frame = int((T / 0.75 + k * 0.37) * 8) % 8
            if (width, frame) not in bird_cache:
                bird_cache[(width, frame)] = scaled(np.asarray(birds[frame]), width)
            a = bird_cache[(width, frame)]
            stamp(f, a, x - a.shape[1] / 2, height + (k % 3) * width * 0.5 + np.sin(T * 1.1 + k) * 2)

    def since_beat(T):
        past = beats[beats <= T]
        return T - past[-1] if len(past) else 9.0

    def beat_at(t, n=0):
        return float(beats[min(int(np.argmin(np.abs(beats - t))) + n, len(beats) - 1)])

    BEAT = float(np.median(np.diff(beats)))

    def hop(T):
        return -int(since_beat(T) < 0.07)

    def dance_rate(spr):
        y = np.array([fr["right"][1] for fr in spr.meta["frames"]], float)
        y = y - y.mean()
        spectrum = np.abs(np.fft.rfft(y * np.hanning(len(y))))
        spectrum[:2] = 0
        period = len(y) / max(int(np.argmax(spectrum)), 1) / spr.fps
        best = min((1, 2, 4, 8, 16), key=lambda m: abs(period / (BEAT * m) - 1))
        return float(np.clip(period / (BEAT * best), 0.75, 1.35))

    def breathing(spr, t, first):
        i = int(max(t, 0) * spr.fps)
        if i < first:
            return i
        span = max(spr.n - 1 - first, 1)
        j = (i - first) % (2 * span)
        return first + (j if j <= span else 2 * span - j)

    def clearance(name, x, y):
        solids = [o["footprint"] for o in shapes.get(name, []) if "footprint" in o]
        return min((np.hypot((x - cx) / rx, (y - cy) / ry) for cx, cy, rx, ry in solids), default=9.0)

    def guard(name, pts):
        low = float(min(clearance(name, x, y) for x, y in pts))
        print(f"Footprint clearance on {name}, with 1.0 at the object edge:", round(low, 2), flush=True)
        if low < 1.0:
            raise SystemExit(f"A person stands inside a solid object on {name}: {low:.2f}")

    def seg(spr, first, start, t):
        i = min(first + int(max(t, 0) * spr.fps), spr.n - 1)
        a, b = spr.path(i), spr.path(first)
        return i, start[0] + a[0] - b[0], start[1] + a[1] - b[1]

    def seg_end(spr, first, start):
        return seg(spr, first, start, 1e6)[1:]

    def seg_time(spr, first=0):
        return (spr.n - 1 - first) / spr.fps

    def back_from(spr, first, end):
        a, b = spr.path(spr.n - 1), spr.path(first)
        return end[0] - a[0] + b[0], end[1] - a[1] + b[1]

    def tail_from(spr, dist):
        end = spr.path(spr.n - 1)
        return next((i for i in range(spr.n - 1, -1, -1) if np.hypot(end[0] - spr.path(i)[0], end[1] - spr.path(i)[1]) >= dist), 0)

    def walk_points(spr, first, start):
        return [seg(spr, first, start, k / spr.fps)[1:] for k in range(spr.n - first)]

    def run_loop(spr, start, t, a=19, b=36):
        """The run loops between two matching frames. The root travel adds up on each lap."""
        frames = t * spr.fps
        laps, rest = divmod(frames, b - a)
        i = a + int(rest)
        pa, pb, pi = spr.path(a), spr.path(b), spr.path(i)
        return i, start[0] + laps * (pb[0] - pa[0]) + pi[0] - pa[0], start[1] + laps * (pb[1] - pa[1]) + pi[1] - pa[1]

    def shadow(f, x, y, rx, ry, pl):
        contact_shadow(f, x, y, rx, ry, 0.8, bayer, ~pl["paper"], 2, occ=pl["occ"])

    def person(f, spr, i, x, y, pl, grade=None, bob=0, sh=(6, 2), reveal=1.0):
        shadow(f, x, y + bob, sh[0], sh[1], pl)
        spr.draw(f, i, x, y + bob, occ=pl["occ"], grade=grade, bayer=bayer, reveal=reveal)

    def line(f, a, b, sag=0.0, colour=STRING, wiggle=0.0, T=0.0):
        n = max(int(np.hypot(b[0] - a[0], b[1] - a[1])), 2)
        for k in range(n + 1):
            u = k / n
            x = a[0] + (b[0] - a[0]) * u + np.sin(u * 14 + T * 5) * wiggle * np.sin(u * np.pi)
            y = a[1] + (b[1] - a[1]) * u + np.sin(u * np.pi) * sag
            if 0 <= int(y) < G and 0 <= int(x) < G:
                f[int(y), int(x)] = colour

    def kite(f, x, y, width, T):
        a = prop("kite", width)
        h = a.shape[0]
        lean = np.sin(T * 2.3) * 0.08
        out = a.copy()
        for row in range(h):
            out[row] = np.roll(a[row], int((row - h / 2) * lean), axis=0)
        stamp(f, out, x - a.shape[1] / 2, y - h * 0.32)
        return x, y + h * 0.34

    motes = []

    def run_motes(f):
        for m in motes:
            m[0] += m[2] / fps
            m[1] += m[3] / fps
            m[4] -= 1 / fps
            x, y = int(m[0]), int(m[1])
            if 0 <= x < G and 0 <= y < G and m[4] > 0:
                f[y, x] = MOTE
        motes[:] = [m for m in motes if m[4] > 0]

    built = {}

    def scene(name, builder):
        if name not in built:
            built[name] = builder()
        return built[name]

    def kitchen_base(k, night_paper=False):
        pl = P["dapur"]
        out = graded(pl, k)
        if night_paper:
            out[pl["paper"]] = NIGHT_PAPER
        return out

    def lamp_glow(f, power):
        lit = (np.hypot((X - 262) / 58.0, (Y - 212) / 34.0) + bayer * 0.35 < power) & ~P["dapur"]["paper"]
        f[lit] = np.clip(f[lit].astype(np.float32) * np.array([1.28, 1.14, 0.9]), 0, 255).astype(np.uint8)

    def city_lights(f, T):
        x0, y0, x1, y1 = WINDOW
        for k in range(26):
            x, y = x0 + (k * 37) % (x1 - x0), y0 + (k * 23) % (y1 - y0)
            if np.sin(T * 0.8 + k * 1.9) > -0.2:
                f[y, x] = LAMP

    # Kitchen: she works by day, then writes by the lamp, and sleep takes her.
    def build_kitchen():
        pl = P["dapur"]
        wash, walk, write, sleep = W["a_wash"], W["a_walk_r"], W["a_write"], W["a_sleep"]
        T_WALK, T_SLEEP = 8.4, 26.1
        first = tail_from(walk, TABLE[0] - SINK[0])
        FROM = back_from(walk, first, TABLE)
        T_AT = T_WALK + seg_time(walk, first)
        guard("dapur", [SINK, TABLE, FROM])

        def draw(T):
            u = np.clip((T - 2.0) / 18.0, 0, 1)
            k = DAY * (1 - u) + NIGHT * u
            f = kitchen_base(k)
            a = prop("kite", 15)
            stamp(f, a, PIN[0], PIN[1])
            if T >= 12:
                lamp_glow(f, min((T - 12) / 3, 1))
            if T >= 16:
                city_lights(f, T)
            # Each line of the verse leaves one more unfinished letter.
            count = sum(T >= t for t in (15.7, 20.9, 26.1, 28.4))
            for n in range(count):
                b = prop("letter", 12)
                stamp(f, b, PILE[0] + n * 2, PILE[1] - n * 2)
            grade = tuple(1 + (v - 1) * u for v in SPR_NIGHT)
            if T < T_WALK:
                person(f, wash, breathing(wash, T, 16), *SINK, pl, grade=grade, sh=(14, 5))
            elif T < T_AT:
                i, x, y = seg(walk, first, FROM, T - T_WALK)
                person(f, walk, i, x, y, pl, grade=grade, sh=(14, 5))
            elif T < T_SLEEP:
                person(f, write, breathing(write, T - T_AT, 16), *TABLE, pl, grade=grade, sh=(14, 5))
            else:
                person(f, sleep, sleep.index(T, "pingpong"), *TABLE, pl, grade=grade, sh=(16, 5))
            return f

        return draw

    # Street: she posts one letter, and the crowd keeps moving. She holds the next one and cannot post it.
    def build_street():
        pl = P["pos"]
        walk, post, hold, stand = W["b_walk_l"], W["b_post"], W["b_hold"], W["b_idle"]
        cr, cl = C["c_walk_r"], C["c_walk_l"]
        first = tail_from(walk, 50)
        FROM = back_from(walk, first, BOX_SPOT)
        T_AT = T_STREET + seg_time(walk, first)
        T_POSTED = max(T_AT + 1.2, 34.6)
        T_HOLD, T_DOWN = 36.6, 39.6
        tints = [(1.0, 1.0, 1.0), (0.82, 0.92, 1.1), (1.06, 0.98, 0.84), (0.9, 1.0, 0.92)]
        # The walkway is a wedge between the shopfronts and the kerb. Each lane starts and ends inside it.
        lanes = [(cr, 124, 251, 0.0, 145), (cl, 268, 251, 1.3, 145), (cr, 138, 258, 2.9, 96), (cl, 234, 256, 4.1, 96), (cr, 150, 252, 5.2, 118), (cl, 240, 260, 6.4, 90)]
        lanes = [(spr, x, y, ph, tail_from(spr, dist)) for spr, x, y, ph, dist in lanes]

        def on_walkway(x, y):
            return 116 <= x <= 276 and 250 <= y <= 281 - 0.26 * (x - 160)

        lane_points = [p for spr, x, y, _, first in lanes for p in walk_points(spr, first, (x, y))]
        off = [p for p in lane_points + walk_points(walk, first, FROM) if not on_walkway(*p)]
        if off:
            raise SystemExit(f"A person walks off the walkway on pos: {off[0]}")
        guard("pos", [BOX_SPOT, FROM])

        def draw(T):
            u = np.clip((T - T_STREET) / (T_PARK - T_STREET), 0, 1)
            k = np.array([1.02, 0.98, 0.94]) * (1 - u) + DUSK * u
            f = graded(pl, k)
            spr_grade = tuple(1 + (v - 1) * u for v in SPR_DUSK)
            people = []
            for n, (spr, x, y, ph, lane_first) in enumerate(lanes):
                t = (T + ph) % 7.6
                if t < seg_time(spr, lane_first):
                    i, px, py = seg(spr, lane_first, (x, y), t)
                    rv = min(1, t / 0.4, (seg_time(spr, lane_first) - t) / 0.4)
                    g = tuple(a * b for a, b in zip(spr_grade, tints[n % 4]))
                    people.append((py, spr, i, px, py, rv, g))
            if T < T_AT:
                i, x, y = seg(walk, first, FROM, T - T_STREET)
                her = (y, walk, i, x, y, 1.0, spr_grade)
            elif T < T_POSTED:
                her = (BOX_SPOT[1], post, breathing(post, T - T_AT, 16), *BOX_SPOT, 1.0, spr_grade)
            elif T < T_HOLD or T >= T_DOWN:
                her = (BOX_SPOT[1], stand, stand.index(T, "pingpong"), *BOX_SPOT, 1.0, spr_grade)
            else:
                her = (BOX_SPOT[1], hold, breathing(hold, T - T_HOLD, 16), *BOX_SPOT, 1.0, spr_grade)
            people.append(her)
            for _, s, i, x, y, rv, g in sorted(people, key=lambda p: p[0]):
                person(f, s, i, x, y, pl, grade=g, reveal=rv)
                if s is post and T < T_POSTED:
                    # The letter moves from her hand into the slot.
                    hand = s.point(i, "right", x, y)
                    v = np.clip((T - (T_POSTED - 0.5)) / 0.5, 0, 1)
                    a = prop("letter", 8)
                    stamp(f, a, hand[0] + (SLOT[0] - hand[0]) * v - 4, hand[1] + (SLOT[1] - hand[1]) * v - 3)
                if s is walk:
                    hand = s.point(i, "right", x, y)
                    a = prop("letter", 8)
                    stamp(f, a, hand[0] - 4, hand[1] - 3)
                if s is hold and T < T_DOWN:
                    hand = s.point(i, "right", x, y)
                    a = prop("letter", 8)
                    stamp(f, a, hand[0] - 4, hand[1] - 3)
            return f

        return draw

    # Sunday park: the women rise from their mats on the hit and dance.
    def build_park():
        pl = P["taman"]
        base = graded(pl, np.array([1.04, 1.02, 0.98]))
        groups = {
            "w": (V, "w_crouch", ["w_dance", "w_dance2"], "w_walk"),
            "f": (Fr, "fr_crouch", ["fr_dance", "fr_dance2"], "fr_walk"),
            "p": (Fr, "fp_crouch", ["fp_dance", "fp_dance2"], "fp_walk"),
        }
        rates = {}
        for g, _, names, _ in groups.values():
            for n in names:
                rates[n] = dance_rate(g[n])
        her_d, her_c, her_i = W["c_dance"], W["c_cry"], W["c_idle"]
        rates["c_dance"] = dance_rate(her_d)
        print("Dance speeds:", {k: round(v, 2) for k, v in rates.items()}, flush=True)
        T_CRY, T_STILL = 52.3, 57.5

        def walker(body, way):
            g, _, _, w = groups[body]
            return g[f"{w}_{way}"]

        def first_of(spr, y):
            end = spr.path(spr.n - 1)
            return next((i for i in range(spr.n) if y - end[1] + spr.path(i)[1] >= 208), spr.n - 1)

        guard("taman", [HER_PARK, FRIEND] + [(x, y) for _, x, y in PARK_CROWD] + [(x, y) for _, _, x, y in ARRIVALS]
              + [p for b, w, x, y in ARRIVALS for s in [walker(b, w)] for k in [first_of(s, y)] for p in walk_points(s, k, back_from(s, k, (x, y)))])

        def draw(T):
            f = base.copy()
            # The harbour glints behind the trees. The towers keep still.
            for k in range(40):
                x, y = 24 + (k * 83) % 312, 146 + (k * 7) % 16
                if not pl["paper"][y, x] and np.sin(T * 3 + k * 1.3) > 0.55:
                    f[y, x] = (230, 244, 250)
            flock(f, T, 5, 92, 24, 11, 7.0)
            people = []
            for n, (body, x, y) in enumerate(SITTERS):
                g, low, _, _ = groups[body]
                s = g[low]
                people.append((y, s, s.index(T + n * 0.5, "pingpong"), x, y, 0, 1.0))
            for n, (body, x, y) in enumerate(PARK_CROWD):
                g, low, names, _ = groups[body]
                at = beat_at(T_HIT, (n % 3) * 2)
                if T < at:
                    s = g[low]
                    people.append((y, s, s.index(T + n * 0.3, "pingpong"), x, y, 0, 1.0))
                else:
                    name = names[n % 2]
                    s = g[name]
                    people.append((y, s, s.index((T - at + n * BEAT) * rates[name], "pingpong"), x, y, hop(T), 1.0))
            for n, (body, way, x, y) in enumerate(ARRIVALS):
                g, _, names, _ = groups[body]
                s = walker(body, way)
                first = first_of(s, y)
                at = beat_at(47.0, n * 3)
                begin = at - seg_time(s, first)
                if T >= at:
                    name = names[n % 2]
                    d = g[name]
                    people.append((y, d, d.index((T - at + n * BEAT) * rates[name], "pingpong"), x, y, hop(T), 1.0))
                elif T >= begin:
                    i, px, py = seg(s, first, back_from(s, first, (x, y)), T - begin)
                    people.append((py, s, i, px, py, 0, min(1, (T - begin) / 0.3)))
            d = Fr["fr_dance"]
            people.append((FRIEND[1], d, d.index((T - T_HIT) * rates["fr_dance"], "pingpong"), *FRIEND, hop(T), 1.0))
            if T < T_CRY:
                people.append((HER_PARK[1], her_d, her_d.index((T - T_HIT) * rates["c_dance"], "pingpong"), *HER_PARK, hop(T), 1.0))
            elif T < T_STILL:
                people.append((HER_PARK[1], her_c, breathing(her_c, T - T_CRY, 20), *HER_PARK, 0, 1.0))
            else:
                people.append((HER_PARK[1], her_i, her_i.index(T, "pingpong"), *HER_PARK, 0, 1.0))
            for _, s, i, x, y, bob, rv in sorted(people, key=lambda p: p[0]):
                person(f, s, i, x, y, pl, bob=bob, sh=(5, 2), reveal=rv)
            return f

        return draw

    # Night kitchen: she dances alone, and the letters slide from the table.
    def build_alone():
        pl = P["dapur"]
        base = kitchen_base(NIGHT, True)
        dance, cry = W["a_dance"], W["a_cry"]
        rate = dance_rate(dance)
        T_CRY, T_FALL = 70.6, 73.1
        falling = [(rng.uniform(-6, 8), rng.uniform(0.5, 1.2), rng.uniform(0, 6), rng.uniform(150, 222), rng.uniform(250, 262)) for _ in range(8)]
        guard("dapur", [ALONE])

        def draw(T):
            f = base.copy()
            a = prop("kite", 15)
            stamp(f, a, PIN[0], PIN[1])
            lamp_glow(f, 1.0)
            city_lights(f, T)
            for n in range(8 if T < T_FALL else 3):
                b = prop("letter", 12)
                stamp(f, b, PILE[0] + n * 2, PILE[1] - n * 2)
            if T >= T_FALL:
                for k, (drift, speed, ph, rest_x, rest_y) in enumerate(falling):
                    t = (T - T_FALL) * speed
                    v = min(t, 1)
                    x = PILE[0] + (rest_x - PILE[0]) * v + np.sin(t * 6 + ph) * 4 * (1 - v) + drift
                    y = PILE[1] + (rest_y - PILE[1]) * v * v
                    b = prop("letter", 10)
                    stamp(f, b, x, y)
            if T < T_CRY:
                person(f, dance, dance.index((T - T_ALONE) * rate, "pingpong"), *ALONE, pl, grade=SPR_NIGHT, sh=(14, 5))
            else:
                person(f, cry, breathing(cry, T - T_CRY, 20), *ALONE, pl, grade=SPR_NIGHT, sh=(14, 5))
            return f

        return draw

    # Roof: she launches her own kite, and lets it go on the last word.
    def build_roof():
        pl = P["atap"]
        base = graded(pl, GOLDEN)
        run, hold, wave = W["r_run"], W["r_hold"], W["r_wave"]
        T_RUN_END = T_ROOF + 0.2 + next(k / fps for k in range(1, 900) if run_loop(run, ROOF_FROM, k / fps)[1] >= 196)
        STOP = run_loop(run, ROOF_FROM, T_RUN_END - T_ROOF - 0.2)[1:]
        pts = [run_loop(run, ROOF_FROM, k / fps)[1:] for k in range(int((T_RUN_END - T_ROOF) * fps))]
        guard("atap", [ROOF_FROM, STOP] + pts)
        print("Roof run stops at", [round(v, 1) for v in STOP], "at", round(T_RUN_END, 2), flush=True)

        def flight(T):
            u = min((T - T_RUN_END) / 5.0, 1)
            return STOP[0] - 40 * u + np.sin(T * 0.9) * 8, STOP[1] - 40 - 110 * (1 - (1 - u) ** 2) + np.sin(T * 1.7) * 4

        def draw(T):
            f = base.copy()
            # Laundry sways on the bamboo poles.
            for row, (a, b) in enumerate(LINES_ROOF):
                line(f, a, b, sag=1, colour=(120, 100, 76))
            for row, u, tone in SHIRTS:
                a, b = LINES_ROOF[row]
                x0, y0 = a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u
                sway = np.sin(T * 2.1 + u * 9 + row)
                for dy in range(9):
                    off = int(sway * dy * 0.3)
                    f[int(y0) + dy, int(x0) + off:int(x0) + off + 6] = tone
            flock(f, T, 4, 120, 20, 10, 3.0)
            if T < T_ROOF + 0.2:
                person(f, hold, hold.index(T, "pingpong"), *ROOF_FROM, pl, grade=SPR_GOLD)
                spr, i, x, y = hold, hold.index(T, "pingpong"), *ROOF_FROM
            elif T < T_RUN_END:
                i, x, y = run_loop(run, ROOF_FROM, T - T_ROOF - 0.2)
                spr = run
                person(f, run, i, x, y, pl, grade=SPR_GOLD)
            elif T < T_LET:
                spr, i, x, y = hold, breathing(hold, T - T_RUN_END, 16), *STOP
                person(f, hold, i, x, y, pl, grade=SPR_GOLD)
            else:
                spr, i, x, y = wave, wave.index(T, "pingpong"), *STOP
                person(f, wave, i, x, y, pl, grade=SPR_GOLD)
            hand = spr.point(i, "right", x, y)
            if T < T_RUN_END:
                kite(f, hand[0] + 15, hand[1] - 24, 19, T)
            elif T < T_LET:
                kx, ky = flight(T)
                tail = kite(f, kx, ky, 19, T)
                line(f, hand, tail, sag=6, T=T)
            else:
                t = T - T_LET
                kx, ky = flight(T_LET)
                kx, ky = kx - t * 24 - t * t * 1.2, ky - t * 7
                if kx > -30:
                    tail = kite(f, kx, ky, 19, T)
                    line(f, tail, (tail[0] + 14, tail[1] + 18), sag=3, wiggle=2, T=T)
                    if int(T * fps) % 2 == 0:
                        motes.append([kx, ky, rng.uniform(-3, 12), rng.uniform(2, 10), rng.uniform(0.6, 1.2)])
            run_motes(f)
            return f

        return draw

    # Wide sea: night falls on the paper. Her kite crosses his, and neither knows.
    def build_sea():
        pl = P["seberang"]
        day, night = graded(pl, GOLDEN), graded(pl, NIGHT * 0.86)
        him_w, her_s = H["l_wave"], W["l_stand"]
        T_END = 114.5
        stars = [(int(rng.uniform(8, 352)), int(rng.uniform(10, 300)), rng.uniform(0, 6)) for _ in range(90)]
        windows = [(int(rng.uniform(287, 320)), int(rng.uniform(112, 256)), rng.uniform(0, 1)) for _ in range(70)]
        windows = [w for w in windows if not pl["paper"][w[1], w[0]]]
        guard("seberang", [HEADLAND])

        def his(T):
            u = np.clip((T - T_SEA - 0.5) / (T_END - T_SEA - 0.5), 0, 1)
            return 112 + (340 - 112) * u, 196 - 72 * np.sin(np.pi * u) - 60 * u + np.sin(T * 2.2) * 2

        def hers(T):
            u = np.clip((T - T_SEA - 0.5) / (T_END - T_SEA - 0.5), 0, 1)
            return 296 + (20 - 296) * u, 104 + (u - 0.365) * 110 + np.sin(T * 1.9) * 2

        T_CROSS = T_SEA + 0.5 + 0.365 * (T_END - T_SEA - 0.5)
        CROSS = (112 + 228 * 0.365, 106)
        crossed = {"done": False}

        def fire_cross(T):
            if T >= T_CROSS and not crossed["done"]:
                crossed["done"] = True
                return True
            return False

        def draw(T):
            v = np.clip((T - T_SEA) / 14.0, 0, 1)
            f = (day * (1 - v) + night * v).astype(np.uint8)
            pp = (paper * (1 - v) + np.array(NIGHT_PAPER) * v).astype(np.uint8)
            f[pl["paper"]] = pp
            for x, y, ph in stars:
                if pl["paper"][y, x] and v > 0.45 and np.sin(T * 1.3 + ph) > 0.2 - (v - 0.45):
                    f[y, x] = (214, 218, 236)
            for x, y, at in windows:
                if v > at:
                    f[y, x] = LAMP
            for k in range(26):
                x, y = int(14 + (k * 37) % 66), int(286 + (k * 11) % 26)
                if not pl["paper"][y, x] and np.sin(T * 3 + k) > 0.6:
                    f[y, x] = (214, 240, 232)
            flock(f, T, 3, 214, 12, 7, 2.0)
            g = tuple(1 + (a - 1) * v for a in SPR_NIGHT)
            person(f, him_w, him_w.index(T, "pingpong"), *HEADLAND, pl, grade=g, sh=(3, 1))
            her_s.draw(f, her_s.index(T, "pingpong"), *TOWER_TOP, grade=g, bayer=bayer)
            for (kx, ky), drift in ((his(T), -8), (hers(T), 8)):
                if T < T_END + 3:
                    tail = kite(f, kx, ky, 12, T)
                    line(f, tail, (tail[0] + drift, tail[1] + 10), sag=2, wiggle=1.2, T=T)
                    if int(T * fps) % 3 == 0:
                        motes.append([kx, ky, rng.uniform(-5, 5), rng.uniform(2, 9), rng.uniform(0.6, 1.3)])
            # The moment the two kites pass, neither knows. Only the air shows it.
            if fire_cross(T):
                for _ in range(14):
                    motes.append([CROSS[0], CROSS[1], rng.uniform(-22, 22), rng.uniform(-18, 18), rng.uniform(0.7, 1.6)])
            run_motes(f)
            return f

        return draw

    font_big = ImageFont.truetype(font_path("msgothic.ttc"), 26)
    font_small = ImageFont.truetype(font_path("simsun.ttc"), 12)
    title = Image.new("RGB", (232, 54), INK)
    d = ImageDraw.Draw(title)
    d.fontmode = "1"
    d.text((116 - font_big.getlength(brief["title"]) / 2, 6), brief["title"], font=font_big, fill=tuple(int(v) for v in paper))
    d.text((116 - font_small.getlength(brief["title_zh"]) / 2, 37), brief["title_zh"], font=font_small, fill=(214, 208, 196))
    title = np.asarray(title)
    state = {"last": None, "scene": None, "at": 0.0}

    def draw(i, t, T):
        if T < T_STREET:
            name, f = "kitchen", scene("kitchen", build_kitchen)(T)
        elif T < T_PARK:
            name, f = "street", scene("street", build_street)(T)
        elif T < T_ALONE:
            name, f = "park", scene("park", build_park)(T)
        elif T < T_ROOF:
            name, f = "alone", scene("alone", build_alone)(T)
        elif T < T_SEA:
            name, f = "roof", scene("roof", build_roof)(T)
        else:
            name, f = "sea", scene("sea", build_sea)(T)
        if name != state["scene"]:
            state["scene"], state["at"] = name, T
            motes.clear()
        u = (T - state["at"]) / 0.17
        if u < 1 and state["last"] is not None:
            hide = bayer > u
            f[hide] = state["last"][hide]
        if 1.0 <= T < 7.0:
            h, w, _ = title.shape
            x0 = (G - w) // 2
            keep = bayer[16:16 + h, x0:x0 + w] < min(1, (T - 1.0) / 0.3, (7.0 - T) / 0.3)
            f[16:16 + h, x0:x0 + w][keep] = title[keep]
        caps.draw(f, T)
        if T < 0.6:
            f[bayer > T / 0.6] = paper
        left = ctx["end"] - T
        if left < 1.2:
            f[bayer > left / 1.2] = paper
        state["last"] = np.array(f, np.uint8)
        return f.astype(np.uint8)

    return draw
