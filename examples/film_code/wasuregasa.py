# 忘れ傘: one red umbrella belongs to nobody. A wrong grab in the rain puts two strangers under it.
# The umbrella and the telephone cord are the only saturated red in the film. When she leaves, he returns it to the rack.
# In the outro the rain comes back, and a stranger makes the same mistake.
# The plate never moves. Footprints guard every path. No person holds one frame.
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pixkit import INK, Captions, Occlusion, Sprite, bayer_field, contact_shadow
from studio_paths import font_path

RED_CORD = (206, 34, 44)
RAIN_COLOUR = (196, 212, 232)
RAIN_GRADE = np.array([0.60, 0.68, 0.82])
RAIN_ADD = np.array([6, 10, 20])
SUN_GRADE = np.array([1.08, 1.02, 0.90])
NIGHT_GRADE = np.array([0.74, 0.72, 0.92])
DUSK_GRADE = np.array([1.02, 0.88, 0.80])
SPR_RAIN = (0.74, 0.80, 0.92)
SPR_NIGHT = (0.82, 0.80, 0.96)
SPR_DUSK = (1.02, 0.88, 0.82)
NIGHT_PAPER = (26, 30, 52)

CARDS = [
    (1.2, 6.6, "第1話 忘れ傘", "Payung yang Terlupa"),
    (27.9, 30.6, "第2話 青信号", "Lampu Hijau"),
    (47.5, 50.2, "第3話 屋上", "Di Atas Atap"),
    (61.2, 63.4, "第4話 十円玉", "Koin Sepuluh Yen"),
    (67.6, 70.0, "最終話 発車ベル", "Bel Keberangkatan"),
    (80.2, 83.0, "最終回のあと", "Sesudah Semuanya"),
]

RACK_SPOT = (148, 243)
RACK_SLOT = (146, 208)
HUB = (108, 188)
WHEEL_R = 44
DOOR_X = 105
PLATFORM_Y = 254
ROOM_FROM = (84, 220)
BOOTH = (277, 222)
COINS = (180, 262)
SCREEN = (197, 95, 236, 131)
LAMPS = [(95, 206), (255, 206), (131, 272), (240, 272)]
ANSWER_LAMP = (51, 203)

# Each dancer walks to a spot on the crossing. The fields are body, dance, walk way, x, y.
CROWD = [
    ("f", "f_dance", "se", 140, 232), ("x", "x_dance", "se", 116, 246), ("w", "w_dance", "se", 160, 222), ("f", "f_dance", "se", 132, 218),
    ("x", "x_dance", "se", 110, 258), ("w", "w_dance2", "se", 132, 256), ("f", "f_dance", "se", 152, 286), ("x", "x_dance", "se", 172, 281), ("w", "w_dance", "se", 196, 291),
    ("w", "w_dance2", "sw", 226, 256), ("f", "f_dance", "sw", 250, 250), ("x", "x_dance", "sw", 206, 272), ("w", "w_dance", "sw", 236, 275), ("f", "f_dance", "sw", 258, 258),
    ("f", "f_dance", "sw", 216, 212), ("w", "w_dance2", "sw", 240, 210), ("x", "x_dance", "sw", 198, 224), ("f", "f_dance", "sw", 182, 208),
]
ROOF_DANCERS = [("f_roof", "folk", 128, 250), ("w_roof", "her", 252, 252), ("x_clap", "hero", 140, 262), ("f_roof", "folk", 246, 276), ("x_clap", "hero", 150, 246), ("w_roof", "her", 100, 268)]


def cut_props(path):
    """Cuts the open and closed umbrella from the sheet. The sheet has a painted background, so colour keys it out."""
    arr = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
    top, low = arr.max(axis=2), arr.min(axis=2)
    solid = ((top - low) / np.maximum(top, 1) > 0.34) | (top < 112)
    h, w = solid.shape
    out = []
    for x0, x1 in ((0, w // 2 + 60), (w // 2 + 60, w)):
        part = solid[:, x0:x1]
        ys = np.nonzero(part.sum(axis=1) > 2)[0]
        xs = np.nonzero(part.sum(axis=0) > 2)[0]
        box = (x0 + xs.min(), ys.min(), x0 + xs.max() + 1, ys.max() + 1)
        rgb = arr[box[1]:box[3], box[0]:box[2]]
        mask = solid[box[1]:box[3], box[0]:box[2]]
        out.append(np.dstack([rgb, mask * 255.0]).astype(np.uint8))
    return out


def scaled(prop, width=None, height=None):
    """Scales a prop to whole pixels with hard alpha."""
    img = Image.fromarray(prop, "RGBA")
    k = width / img.width if width else height / img.height
    small = np.asarray(img.resize((max(2, int(img.width * k)), max(2, int(img.height * k))), Image.BOX)).copy()
    small[..., 3] = (small[..., 3] > 110) * 255
    return small


def stamp(f, a, x0, y0, mask=None):
    G = f.shape[0]
    h, w = a.shape[:2]
    x0, y0 = int(x0), int(y0)
    ax0, ay0, ax1, ay1 = max(x0, 0), max(y0, 0), min(x0 + w, G), min(y0 + h, G)
    if ax0 >= ax1 or ay0 >= ay1:
        return
    part = a[ay0 - y0:ay1 - y0, ax0 - x0:ax1 - x0]
    solid = part[..., 3] > 0
    if mask is not None:
        solid = solid & mask[ay0:ay1, ax0:ax1]
    f[ay0:ay1, ax0:ax1][solid] = part[..., :3][solid]


def make(ctx):
    G, fps, brief, A, root = ctx["grid"], ctx["fps"], ctx["brief"], ctx["a"], ctx["root"]
    paper = np.array(brief["paper"], np.uint8)
    beats = np.array(A["beats"])
    rng = np.random.default_rng(31)
    bayer = bayer_field(G)
    caps = Captions(brief["lines"], paper, top_font=(font_path("msgothic.ttc"), 16))
    shapes = json.loads((root / "occluders.json").read_text(encoding="utf-8"))

    def plate(name):
        d = np.asarray(Image.open(root / f"plates/{name}-360.png").convert("RGB")).copy()
        is_paper = (np.abs(d.astype(int) - paper.astype(int)).sum(axis=2) < 24) | (d.astype(int).sum(axis=2) > 720)
        d[is_paper] = paper
        return {"name": name, "day": d, "paper": is_paper, "occ": Occlusion(root, name)}

    P = {n: plate(n) for n in ("gate", "crossing", "rooftop", "rooms", "platform")}

    def graded(pl, k, add=0):
        out = np.clip(pl["day"] * k + add, 0, 255).astype(np.uint8)
        out[pl["paper"]] = paper
        return out

    GATE_RAIN, GATE_SUN = graded(P["gate"], RAIN_GRADE, RAIN_ADD), graded(P["gate"], SUN_GRADE)
    CROSS_RAIN = graded(P["crossing"], RAIN_GRADE, RAIN_ADD)
    ROOF_SUN = graded(P["rooftop"], np.array([1.05, 1.0, 0.92]))
    ROOM_NIGHT = graded(P["rooms"], NIGHT_GRADE)
    ROOM_NIGHT[P["rooms"]["paper"]] = NIGHT_PAPER
    PLAT_DUSK = graded(P["platform"], DUSK_GRADE)

    def loader(folder):
        return {n: Sprite(root, n, folder) for n in json.loads((root / folder / "jobs.json").read_text())}

    H, W, F = loader("hero"), loader("hero_her"), loader("hero_folk")

    def rehue(spr, colour):
        """Moves her mustard sweater to another colour, so no woman in the crowd looks like her."""
        frames = spr.frames.copy()
        rgb = frames[..., :3].astype(np.float32)
        top, low = rgb.max(axis=-1), rgb.min(axis=-1)
        mustard = (rgb[..., 0] >= rgb[..., 1]) & (rgb[..., 1] > rgb[..., 2]) & ((top - low) / np.maximum(top, 1) > 0.5) & (rgb[..., 1] / np.maximum(rgb[..., 0], 1) > 0.55)
        light = (rgb.mean(axis=-1) / 130.0)[..., None]
        rgb = np.where(mustard[..., None], np.clip(light * np.array(colour, np.float32), 0, 255), rgb)
        frames[..., :3] = rgb.astype(np.uint8)
        spr.frames = frames

    for name, spr in W.items():
        if name.startswith("s_"):
            rehue(spr, (170, 150, 196))
        elif name == "w_gate_b":
            rehue(spr, (132, 160, 122))
        elif name.startswith("w_"):
            rehue(spr, (98, 126, 178))

    # Props.
    OPEN, CLOSED = cut_props(root / "plates/umbrella-raw.png")
    grey_of = lambda a: np.dstack([np.clip(a[..., :3].mean(axis=2, keepdims=True) * np.array([1.5, 1.6, 1.8]) + 40, 0, 255), a[..., 3]]).astype(np.uint8)
    prop_cache = {}

    def prop(kind, size):
        key = (kind, size)
        if key not in prop_cache:
            if kind == "open":
                prop_cache[key] = scaled(OPEN, width=size)
            elif kind == "closed":
                prop_cache[key] = scaled(CLOSED, height=size)
            else:
                prop_cache[key] = grey_of(scaled(OPEN, width=size))
        return prop_cache[key]

    def open_umbrella(f, hand, width, T, kind="open", spin=8.0):
        """The handle bottom sits in the hand. The dome turns by mirroring the ribs."""
        a = prop(kind, width)
        if int(T * spin) % 2:
            a = a[:, ::-1]
        stamp(f, a, hand[0] - a.shape[1] / 2, hand[1] - a.shape[0] + 2)

    def closed_umbrella(f, hand, height, occ_mask=None):
        """The curved handle sits in the hand and the tip hangs down."""
        a = prop("closed", height)
        stamp(f, a, hand[0] - a.shape[1] / 2, hand[1] - 2, occ_mask)

    # Train: 4 carriages cut from the painted sheet.
    raw_train = Image.open(root / "plates/train-raw.png").convert("RGBA")
    raw_train = raw_train.crop(raw_train.getchannel("A").point(lambda v: 255 if v > 127 else 0).getbbox())
    CAR_H = 84
    CAR_W = int(raw_train.width * CAR_H / raw_train.height)
    car = np.asarray(raw_train.resize((CAR_W, CAR_H), Image.BOX)).copy()
    car[..., 3] = (car[..., 3] > 110) * 255
    DOOR_L, DOOR_R = int(CAR_W * 0.345), int(CAR_W * 0.452)
    DOOR_T, DOOR_B = int(CAR_H * 0.30), int(CAR_H * 0.74)
    TRAIN_Y = 240 - CAR_H
    door_patch = car[DOOR_T:DOOR_B, DOOR_L:DOOR_R].copy()
    door_glass = (door_patch[..., 0].astype(int) > 150) & (door_patch[..., 2].astype(int) < 150)

    def band(name, T):
        v = A[name]
        return v[min(int(T * fps), len(v) - 1)]

    def since_beat(T):
        past = beats[beats <= T]
        return T - past[-1] if len(past) else 9.0

    def beat_at(t, n=0):
        return float(beats[min(int(np.argmin(np.abs(beats - t))) + n, len(beats) - 1)])

    BEAT = float(np.median(np.diff(beats)))

    def hop(T):
        return -int(since_beat(T) < 0.08)

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

    def seg(spr, first, start, t):
        """A walk follows the root travel of the clip, so feet never slide."""
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
        return next(i for i in range(spr.n - 1, -1, -1) if np.hypot(end[0] - spr.path(i)[0], end[1] - spr.path(i)[1]) >= dist)

    def walk_points(spr, first, start):
        return [seg(spr, first, start, k / spr.fps)[1:] for k in range(spr.n - first)]

    # Gate timeline, rain.
    g_l, g_run, g_um = H["g_walk_l"], H["g_run"], H["g_walk_um"]
    T_REACH = 10.8
    first_l = tail_from(g_l, 66)
    HIM_FROM = back_from(g_l, first_l, RACK_SPOT)
    T_HIM = T_REACH - seg_time(g_l, first_l)
    T_TAKE = T_REACH + 0.7
    T_RUN = 14.2
    first_run = 0
    MEET = seg_end(g_run, first_run, RACK_SPOT)
    T_MEET = T_RUN + seg_time(g_run, first_run)
    HER_SPOT = (MEET[0] + 23, MEET[1] - 8)
    h_se = W["g_walk_se"]
    first_hse = tail_from(h_se, 67)
    HER_FROM = back_from(h_se, first_hse, HER_SPOT)
    T_HER_STOP = T_MEET + 0.1
    T_HER = T_HER_STOP - seg_time(h_se, first_hse)
    T_OPEN = 21.2
    T_LEAVE = 25.0
    first_um = max(g_um.n - 1 - int((27.9 - T_LEAVE) * g_um.fps), 0)
    w_sw = W["g_walk_sw"]
    first_wsw = max(w_sw.n - 1 - int((27.9 - T_LEAVE) * w_sw.fps), 0)

    # Commuters cross the forecourt in both weathers.
    COMMUTERS = [("f_gate_b", F, (205, 240), None), ("w_gate_b", W, (262, 250), None), ("f_gate_a", F, (240, 244), None), ("w_gate_a", W, (216, 240), None)]
    # While the two talk, commuters keep to a far lane.
    FAR_LANE = [("f_gate_a", F, (168, 246), None), ("w_gate_b", W, (136, 250), None)]

    # Crossing timeline.
    c_um, c_w = H["c_walk_um"], W["c_walk_sw"]
    T_CROSS, T_ROOF, T_ROOMS, T_PLAT, T_DRY = 27.9, 47.5, 61.2, 67.6, 80.2
    T_C_WALK, T_STOP, T_ON, T_STOP2 = 29.5, 37.3, 41.1, 44.0
    first_c = 40
    steps_c = int((T_STOP - T_C_WALK) * c_um.fps)
    c_mid = (172, 250)
    a, b = c_um.path(first_c + steps_c), c_um.path(first_c)
    C_FROM = (c_mid[0] - a[0] + b[0], c_mid[1] - a[1] + b[1])
    c_end = seg(c_um, 40, c_mid, T_STOP2 - T_ON)[1:]
    OTHER = (14, -4)

    def crowd_walker(body, way):
        return {"f": F[f"f_walk_{way}"] if way else None, "x": H[f"x_walk_{way}"] if way else None, "w": W[f"w_walk_{way}"] if way else None}[body]

    def walker_first(walker, y):
        """Walkers leave the pavement in front of the shops, so a path never starts on a wall."""
        end = walker.path(walker.n - 1)
        return next(i for i in range(walker.n) if y - end[1] + walker.path(i)[1] >= 205 or i == walker.n - 1)

    def dance_sprite(name):
        return F.get(name) or H.get(name) or W.get(name)

    # Rooftop timeline.
    r_h, r_w = H["r_walk"], W["r_walk"]
    ROOF_HIM = (196, 262)
    ROOF_HER = (226, 258)
    T_DANCE = T_ROOF + seg_time(r_h)
    T_TOSS = T_DANCE + 0.2
    SPIN_SPOT = (211, 274)

    # Rooms timeline.
    m_h, m_w, m_r = H["m_idle"], W["m_idle"], H["m_walk_r"]
    first_m = tail_from(m_r, 34)
    T_PACE = 63.8
    ROOM_TO = seg_end(m_r, first_m, ROOM_FROM)
    T_SNAP = 66.75

    # Platform timeline.
    p_run = H["p_run"]
    T_CLOSE, T_DEPART, T_CHASE = 70.9, 73.9, 74.6
    RUN_A, RUN_B, RUN_RATE = 19, 36, 1.5
    RUN_DIST = 213.0

    def run_at(t):
        """The run loops between two matching frames. The root travel adds up on each lap."""
        frames = t * p_run.fps * RUN_RATE
        span = RUN_B - RUN_A
        laps, rest = divmod(frames, span)
        i = RUN_A + int(rest)
        lap_x = p_run.path(RUN_B)[0] - p_run.path(RUN_A)[0]
        return i, DOOR_X + laps * lap_x + p_run.path(i)[0] - p_run.path(RUN_A)[0], PLATFORM_Y

    T_RUN_END = T_CHASE + next(k / fps for k in range(1, 900) if run_at(k / fps)[1] >= DOOR_X + RUN_DIST)
    RUN_STOP = (run_at(T_RUN_END - T_CHASE)[1], PLATFORM_Y)
    print("Platform run ends at", round(T_RUN_END, 2), "at x", round(RUN_STOP[0], 1), flush=True)

    def train_shift(T):
        t = max(T - T_DEPART, 0)
        return 0.5 * 54 * t * t

    # Dry timeline.
    d_nw, d_r, d_in = H["d_walk_nw"], H["d_walk_r"], H["d_walk_in"]
    DRY_FROM = back_from(d_nw, 0, RACK_SPOT)
    T_DRY_REACH = T_DRY + seg_time(d_nw)
    T_RETURN = T_DRY_REACH + 0.75
    T_D_WALK = T_DRY_REACH + 1.2
    first_dr = tail_from(d_r, 58)
    GATE_FRONT = seg_end(d_r, first_dr, RACK_SPOT)
    T_D_IN = T_D_WALK + seg_time(d_r, first_dr)
    T_GONE = T_D_IN + seg_time(d_in)

    # Coda: the rain returns, and a stranger takes the umbrella.
    T_RAIN_BACK = 95.5
    s_l, s_run, s_w = F["s_walk_l"], F["s_run"], W["s_walk"]
    T_S_REACH = 100.2
    first_sl = tail_from(s_l, 66)
    S_FROM = back_from(s_l, first_sl, RACK_SPOT)
    T_S = T_S_REACH - seg_time(s_l, first_sl)
    T_S_TAKE = T_S_REACH + 0.7
    T_S_RUN = T_S_REACH + 1.1
    first_srun = 0
    S_MEET = seg_end(s_run, first_srun, RACK_SPOT)
    T_S_MEET = T_S_RUN + seg_time(s_run, first_srun)
    S_HER = (S_MEET[0] + 23, S_MEET[1] - 8)
    first_sw = tail_from(s_w, 67)
    S_HER_FROM = back_from(s_w, first_sw, S_HER)
    T_SW = T_S_MEET + 0.1 - seg_time(s_w, first_sw)

    checks = {
        "gate": [RACK_SPOT, MEET, HER_SPOT, DRY_FROM, GATE_FRONT, S_MEET, S_HER] + walk_points(g_l, first_l, HIM_FROM) + walk_points(g_run, first_run, RACK_SPOT) + walk_points(h_se, first_hse, HER_FROM)
        + walk_points(g_um, first_um, MEET) + walk_points(d_nw, 0, DRY_FROM) + walk_points(d_r, first_dr, RACK_SPOT),
        "crossing": [c_mid, c_end, C_FROM]
        + [p for body, _, way, x, y in CROWD for w in [crowd_walker(body, way)] for k in [walker_first(w, y)] for p in walk_points(w, k, back_from(w, k, (x, y)))],
        "rooftop": [ROOF_HIM, ROOF_HER, SPIN_SPOT] + [(x, y) for _, _, x, y in ROOF_DANCERS] + walk_points(r_h, 0, back_from(r_h, 0, ROOF_HIM)) + walk_points(r_w, 40, back_from(r_w, 40, ROOF_HER)),
        "rooms": [ROOM_FROM, ROOM_TO],
        "platform": [RUN_STOP, (DOOR_X, PLATFORM_Y)],
    }
    lowest = {n: round(float(min(clearance(n, x, y) for x, y in pts)), 2) for n, pts in checks.items()}
    print("Footprint clearance, with 1.0 at the object edge:", lowest, flush=True)
    bad = {n: v for n, v in lowest.items() if v < 1.0}
    if bad:
        raise SystemExit(f"A person stands inside a solid object: {bad}")

    dancers = {k: v for d in (F, H, W) for k, v in d.items() if "dance" in k or "roof" in k or k == "x_clap"}
    rates = {k: dance_rate(v) for k, v in dancers.items()}
    print("Dance speeds:", {k: round(v, 2) for k, v in rates.items()}, flush=True)

    # Episode cards, as on a 1990s television drama.
    font_big = ImageFont.truetype(font_path("msgothic.ttc"), 20)
    font_small = ImageFont.truetype(font_path("msgothic.ttc"), 12)
    cards = []
    for a0, a1, big, small in CARDS:
        width = int(max(font_big.getlength(big), font_small.getlength(small))) + 20
        card = Image.new("RGB", (width, 44), INK)
        d = ImageDraw.Draw(card)
        d.fontmode = "1"
        d.text((width / 2 - font_big.getlength(big) / 2, 5), big, font=font_big, fill=tuple(int(v) for v in paper))
        d.text((width / 2 - font_small.getlength(small) / 2, 28), small, font=font_small, fill=(214, 208, 196))
        cards.append((a0, a1, np.asarray(card)))

    rain = [[rng.uniform(0, G + 80), rng.uniform(0, G), rng.uniform(300, 420)] for _ in range(240)]
    splashes = []
    state = {"last": None, "scene": None, "at": 0.0}

    def draw_rain(f, T, amount, ground):
        """Hard pixel rain. Drops break on the ground as small rings."""
        count = int(len(rain) * amount)
        for r in rain[:count]:
            r[1] += r[2] / fps
            r[0] -= r[2] * 0.12 / fps
            if r[1] > G or r[0] < 0:
                r[1], r[0] = 0.0, rng.uniform(0, G + 80)
            x, y = int(r[0]), int(r[1])
            for j in range(5):
                if 0 <= y + j < G and 0 <= x - j // 6 < G:
                    f[y + j, x - j // 6] = RAIN_COLOUR
        for _ in range(int(amount * 7)):
            x, y = int(rng.uniform(20, G - 20)), int(rng.uniform(190, 320))
            if ground[y, x]:
                splashes.append([x, y, 0.0])
        for s in splashes:
            s[2] += 1 / fps
            rad = int(s[2] * 22) + 1
            for dx in (-rad, rad):
                if 0 <= s[0] + dx < G:
                    f[s[1], s[0] + dx] = RAIN_COLOUR
        splashes[:] = [s for s in splashes if s[2] < 0.14]

    def shadow(f, x, y, rx, ry, pl):
        contact_shadow(f, x, y, rx, ry, 0.8, bayer, ~pl["paper"], 2, occ=pl["occ"])

    def person(f, spr, i, x, y, pl, grade=None, bob=0, sh=(8, 3), reveal=1.0):
        shadow(f, x, y + bob, sh[0], sh[1], pl)
        spr.draw(f, i, x, y + bob, occ=pl["occ"], grade=grade, bayer=bayer, reveal=reveal)

    def right_hand(spr, i, x, y):
        return spr.point(i, "right", x, y)

    def commuters(f, T, pl, grade, kind, width, ground_only=True):
        """Commuters cross the forecourt, one after another. Each uses a walk with a raised hand."""
        people = []
        quiet = 13.0 <= T < T_CROSS or T >= T_S - 1.0
        for n, (name, group, start, _) in enumerate(FAR_LANE if quiet else COMMUTERS):
            spr = group[name]
            period = seg_time(spr) + 1.6
            t = (T + n * 2.3) % period
            if t < seg_time(spr):
                i, x, y = seg(spr, 0, start, t)
                reveal = min(1, t / 0.4, (seg_time(spr) - t) / 0.4)
                people.append((y, spr, i, x, y, reveal))
        for y0, spr, i, x, y, reveal in sorted(people, key=lambda p: p[0]):
            person(f, spr, i, x, y, pl, grade=grade, sh=(7, 3), reveal=reveal)
            if kind and reveal >= 1:
                open_umbrella(f, right_hand(spr, i, x, y), width, T, kind, spin=3.0)

    def gate_rain_scene(T, bass):
        pl = P["gate"]
        f = GATE_RAIN.copy()
        commuters(f, T, pl, SPR_RAIN, "grey", 30)
        people = []
        # He walks out of the gates to the rack.
        if T >= T_HIM:
            if T < T_REACH:
                i, x, y = seg(g_l, first_l, HIM_FROM, T - T_HIM)
                people.append((y, "him", g_l, i, x, y, min(1, (T - T_HIM) / 0.3)))
            elif T < T_RUN:
                spr = H["g_reach"]
                people.append((RACK_SPOT[1], "him", spr, breathing(spr, T - T_REACH, 16), *RACK_SPOT, 1))
            elif T < T_MEET:
                i, x, y = seg(g_run, first_run, RACK_SPOT, T - T_RUN)
                people.append((y, "him", g_run, i, x, y, 1))
            elif T < T_OPEN:
                spr = H["g_offer"]
                people.append((MEET[1], "him", spr, breathing(spr, T - T_MEET, 16), *MEET, 1))
            elif T < T_LEAVE:
                spr = H["g_hold"]
                people.append((MEET[1], "him", spr, breathing(spr, T - T_OPEN, 16), *MEET, 1))
            else:
                i, x, y = seg(g_um, first_um, MEET, T - T_LEAVE)
                people.append((y, "him", g_um, i, x, y, 1))
        if T >= T_HER:
            if T < T_HER_STOP:
                i, x, y = seg(h_se, first_hse, HER_FROM, T - T_HER)
                people.append((y, "her", h_se, i, x, y, min(1, (T - T_HER) / 0.3)))
            elif T < 17.5:
                spr = W["g_idle"]
                people.append((HER_SPOT[1], "her", spr, spr.index(T, "pingpong"), *HER_SPOT, 1))
            elif T < T_LEAVE:
                spr = W["g_laugh"]
                people.append((HER_SPOT[1], "her", spr, breathing(spr, T - 17.5, 12), *HER_SPOT, 1))
            else:
                i, x, y = seg(w_sw, first_wsw, HER_SPOT, T - T_LEAVE)
                people.append((y, "her", w_sw, i, x, y, 1))
        if T < T_TAKE:
            closed_umbrella(f, RACK_SLOT, 26)
        for _, who, spr, i, x, y, reveal in sorted(people, key=lambda p: p[0]):
            person(f, spr, i, x, y, pl, grade=SPR_RAIN, reveal=reveal)
            if who == "him" and T >= T_TAKE:
                hand = right_hand(spr, i, x, y)
                if T < T_OPEN:
                    closed_umbrella(f, hand, 26)
                else:
                    open_umbrella(f, (hand[0] + 6, hand[1]), 38, T, spin=2.0)
        draw_rain(f, T, 1.0, ~pl["paper"])
        return f

    def signal(f, T, on):
        colour = (118, 232, 150) if on else (230, 196, 96)
        if since_beat(T) < 0.3 or not on:
            for x, y in LAMPS:
                f[y - 1:y + 2, x - 1:x + 2] = colour

    def big_screen(f, T, bass):
        """The big screen follows the couple. From the chorus it shows the red umbrella on the beat."""
        x0, y0, x1, y1 = SCREEN
        f[y0:y1, x0:x1] = (24, 28, 42)
        if T < 33.5:
            for k in range(x0 + 2, x1 - 2, 4):
                level = int((0.3 + 0.7 * band("mid", T) * (0.5 + 0.5 * np.sin(k * 1.7 + T * 5))) * (y1 - y0 - 6))
                f[y1 - 3 - level:y1 - 3, k:k + 3] = (86, 150, 132)
        else:
            a = prop("open", 30)
            if int(T * 4) % 2:
                a = a[:, ::-1]
            stamp(f, a, (x0 + x1) / 2 - a.shape[1] / 2, y0 + 7 - int(since_beat(T) < 0.1))

    def crossing_scene(T, bass):
        pl = P["crossing"]
        f = CROSS_RAIN.copy()
        big_screen(f, T, bass)
        signal(f, T, True)
        people = []
        for n, (body, dance, way, x, y) in enumerate(CROWD):
            walker = crowd_walker(body, way)
            at = beat_at(32.6, n % 3)
            first = walker_first(walker, y)
            begin = at - seg_time(walker, first)
            if T >= at:
                people.append((y, "D", dance, n, x, y, 1))
            elif T >= begin:
                i, px, py = seg(walker, first, back_from(walker, first, (x, y)), T - begin)
                people.append((py, "W", walker, i, px, py, min(1, (T - begin) / 0.3)))
        # The couple.
        def stand(at, laugh_from):
            spr = H["c_idle_um"]
            people.append((at[1], "H", spr, spr.index(T, "pingpong"), *at, 1))
            her = W["c_laugh"] if T >= laugh_from else W["c_idle"]
            j = breathing(her, T - laugh_from, 12) if T >= laugh_from else her.index(T, "pingpong")
            people.append((at[1] + OTHER[1], "S", her, j, at[0] + OTHER[0], at[1] + OTHER[1], 1))

        def stroll(first, start, t):
            i, x, y = seg(c_um, first, start, t)
            people.append((y, "H", c_um, i, x, y, 1))
            j = min(first + int(t * c_w.fps), c_w.n - 1)
            people.append((y + OTHER[1], "S", c_w, j, x + OTHER[0], y + OTHER[1], 1))

        if T < T_C_WALK:
            stand(C_FROM, 99.0)
        elif T < T_STOP:
            stroll(first_c, C_FROM, T - T_C_WALK)
        elif T < T_ON:
            stand(c_mid, 38.2)
        elif T < T_STOP2:
            stroll(40, c_mid, T - T_ON)
        else:
            stand(c_end, 44.0)
        hero_at = None
        for _, kind, a1, a2, x, y, reveal in sorted(people, key=lambda p: p[0]):
            if kind == "D":
                spr = dance_sprite(a1)
                i = spr.index((T + a2 * BEAT) * rates[a1], "pingpong")
                person(f, spr, i, x, y, pl, grade=SPR_RAIN, bob=hop(T), sh=(6, 2))
            elif kind == "W":
                person(f, a1, a2, x, y, pl, grade=SPR_RAIN, sh=(6, 2), reveal=reveal)
            else:
                person(f, a1, a2, x, y, pl, grade=SPR_RAIN, sh=(6, 2))
                if kind == "H":
                    hero_at = right_hand(a1, a2, x, y)
                elif T_STOP <= T < 40.6:
                    # 'Only your right shoulder is wet': drops break on her shoulder, outside the dome.
                    for _ in range(3):
                        px, py = int(x + rng.uniform(3, 7)), int(y - rng.uniform(14, 18))
                        f[py, px] = (240, 246, 255)
        if hero_at:
            open_umbrella(f, (hero_at[0] + 5, hero_at[1]), 27, T, spin=3.0)
        draw_rain(f, T, 0.8, ~pl["paper"])
        return f

    def wheel(f, T):
        """The ferris wheel turns slowly. Each car hangs level."""
        a0 = T * 0.55
        cx, cy = HUB
        for k in range(180):
            a = k / 180 * 2 * np.pi
            x, y = int(cx + np.cos(a) * WHEEL_R), int(cy + np.sin(a) * WHEEL_R)
            f[y, x] = (92, 126, 138)
        tones = [(86, 150, 132), (232, 196, 96), (120, 168, 214), (240, 232, 214)]
        for k in range(8):
            a = a0 + k * np.pi / 4
            ex, ey = cx + np.cos(a) * WHEEL_R, cy + np.sin(a) * WHEEL_R
            for u in np.linspace(0, 1, 44):
                f[int(cy + (ey - cy) * u), int(cx + (ex - cx) * u)] = (112, 146, 156)
            sway = np.sin(T * 1.4 + k) * 0.8
            x0, y0 = int(ex - 4 + sway), int(ey + 1)
            f[y0:y0 + 6, x0:x0 + 9] = tones[k % 4]
            f[y0 + 1:y0 + 3, x0 + 1:x0 + 8] = (54, 66, 84)
        for dx in range(-4, 5):
            for dy in range(-4, 5):
                if dx * dx + dy * dy <= 16:
                    f[cy + dy, cx + dx] = (166, 150, 132)

    def rooftop_scene(T, bass):
        pl = P["rooftop"]
        f = ROOF_SUN.copy()
        wheel(f, T)
        people = []
        if T < T_DANCE:
            i, x, y = seg(r_h, 0, back_from(r_h, 0, ROOF_HIM), T - T_ROOF)
            people.append((y, r_h, i, x, y, None, 0))
            t_her = T - (T_DANCE - seg_time(r_w, 40))
            if t_her >= 0:
                j, x2, y2 = seg(r_w, 40, back_from(r_w, 40, ROOF_HER), t_her)
                people.append((y2, r_w, j, x2, y2, None, 0))
        else:
            spr = H["r_dance"]
            people.append((ROOF_HIM[1], spr, spr.index((T - T_DANCE) * dance_rate(spr), "pingpong"), *ROOF_HIM, None, hop(T)))
            spr = W["r_dance"]
            people.append((ROOF_HER[1], spr, spr.index((T - T_DANCE) * dance_rate(spr), "pingpong"), *ROOF_HER, None, hop(T)))
        for n, (name, owner, x, y) in enumerate(ROOF_DANCERS):
            spr = {"folk": F, "her": W, "hero": H}[owner][name]
            people.append((y, spr, spr.index((T + n * BEAT) * rates[name], "pingpong"), x, y, None, hop(T)))
        hand = None
        if T >= T_TOSS:
            # The umbrella goes up on the beat, opens, then spins on its tip between them.
            u = min((T - T_TOSS) / (BEAT * 2), 1)
            x = ROOF_HIM[0] + (SPIN_SPOT[0] - ROOF_HIM[0]) * u
            y = SPIN_SPOT[1] - np.sin(np.pi * u) * 80 - (1 - u) * 18
            people.append((SPIN_SPOT[1], None, 0, x, y, None, 0))
        for yy, spr, i, x, y, _, bob in sorted(people, key=lambda p: p[0]):
            if spr is None:
                shadow(f, SPIN_SPOT[0], SPIN_SPOT[1], 10, 3, pl)
                open_umbrella(f, (x, y), 30, T, spin=12.0)
                continue
            person(f, spr, i, x, y, pl, bob=bob, sh=(7, 3))
            if spr is r_h and T < T_TOSS:
                closed_umbrella(f, right_hand(spr, i, x, y), 20)
        return f

    def cord(f, a, b, T, snapped):
        """The red telephone cord crosses the paper. It breaks when the call ends."""
        for k in range(161):
            u = k / 160
            if snapped > 0 and 0.46 < u < 0.54:
                continue
            x = a[0] + (b[0] - a[0]) * u
            sag = np.sin(np.pi * u) * (34 + band("bass", T) * 10)
            fall = 0.0
            if snapped > 0:
                side = abs(u - 0.5) * 2
                fall = snapped * snapped * 340 * (1 - side)
            y = a[1] + (b[1] - a[1]) * u + sag + fall + np.sin(u * 90 + T * 6) * 1.2
            xi, yi = int(x), int(y)
            if 0 <= yi < G and 0 <= xi < G:
                f[yi, xi] = RED_CORD

    def rooms_scene(T, bass):
        pl = P["rooms"]
        f = ROOM_NIGHT.copy()
        # The answering machine lamp blinks red.
        if int(T * 4) % 2 == 0:
            f[ANSWER_LAMP[1] - 1:ANSWER_LAMP[1] + 1, ANSWER_LAMP[0]:ANSWER_LAMP[0] + 2] = RED_CORD
        if T < T_PACE:
            spr, i, x, y = m_h, breathing(m_h, T - T_ROOMS, 16), *ROOM_FROM
        else:
            tt = T - T_PACE
            if tt < seg_time(m_r, first_m):
                i, x, y = seg(m_r, first_m, ROOM_FROM, tt)
                spr = m_r
            else:
                spr, i, x, y = m_h, breathing(m_h, tt, 16), *ROOM_TO
        person(f, spr, i, x, y, pl, grade=SPR_NIGHT, sh=(6, 2))
        a = spr.point(i, "right", x, y)
        j = breathing(m_w, T - T_ROOMS, 16)
        person(f, m_w, j, *BOOTH, pl, grade=SPR_NIGHT, sh=(6, 2))
        b = m_w.point(j, "right", *BOOTH)
        # One ten yen coin lands on the stack on each beat.
        count = 0
        for n in range(14):
            at = beat_at(T_ROOMS, n)
            if T >= at:
                u = min((T - at) / 0.16, 1)
                cy = COINS[1] - count * 3 - (1 - u) * 40
                row = int(cy)
                f[row:row + 3, COINS[0] - 4:COINS[0] + 5] = (166, 108, 62)
                f[row, COINS[0] - 3:COINS[0] + 4] = (222, 164, 104)
                f[row + 2, COINS[0] - 4:COINS[0] + 5] = (108, 66, 40)
                count += 1
        cord(f, a, b, T, max(T - T_SNAP, 0) / 0.8)
        return f

    def draw_train(f, T):
        shift = train_shift(T)
        x0 = DOOR_X - (DOOR_L + DOOR_R) / 2 - CAR_W + shift
        pl = P["platform"]
        blocked = pl["occ"].blocks(240)
        visible = ~blocked
        visible[240:, :] = False
        for n in range(4):
            stamp(f, car, x0 + n * CAR_W, TRAIN_Y, visible)
        # The door of the second carriage.
        dx0 = int(x0 + CAR_W + DOOR_L)
        dw, dh = DOOR_R - DOOR_L, DOOR_B - DOOR_T
        dy0 = TRAIN_Y + DOOR_T
        region = np.zeros((G, G), bool)
        ax0, ax1 = max(dx0, 0), min(dx0 + dw, G)
        if ax0 < ax1:
            region[dy0:dy0 + dh, ax0:ax1] = True
        region &= visible
        close = np.clip((T - T_CLOSE) / 0.4, 0, 1)
        if region.any():
            # She stands in the lit doorway. Only the door opening shows her.
            inside = f.copy()
            inside[region] = (232, 196, 120)
            her_spr = W["p_wave"] if 68.8 <= T < T_CLOSE else W["p_idle"]
            her_spr.draw(inside, her_spr.index(T, "pingpong"), dx0 + dw / 2, dy0 + dh + 4, occ=None, grade=SPR_DUSK)
            f[region] = inside[region]
            half = dw // 2
            open_by = int((1 - close) * half)
            leaves = door_patch.copy()
            if close >= 1:
                leaves[..., 3] = (~door_glass) * 255
            left = leaves[:, :half]
            right = leaves[:, half:]
            mask = region
            stamp(f, left, dx0 - open_by, dy0, mask)
            stamp(f, right, dx0 + half + open_by, dy0, mask)
        return x0

    def platform_scene(T, bass):
        pl = P["platform"]
        f = PLAT_DUSK.copy()
        draw_train(f, T)
        if T < T_CHASE:
            spr = H["p_idle"]
            i, x, y = spr.index(T, "pingpong"), DOOR_X, PLATFORM_Y
        elif T < T_RUN_END:
            i, x, y = run_at(T - T_CHASE)
            spr = p_run
        else:
            spr = H["p_end"]
            i, x, y = spr.index(T, "pingpong"), *RUN_STOP
        person(f, spr, i, x, y, pl, grade=SPR_DUSK, sh=(8, 3))
        closed_umbrella(f, right_hand(spr, i, x, y), 24)
        return f

    def gate_dry_scene(T, bass):
        pl = P["gate"]
        wet = np.clip((T - T_RAIN_BACK) / 3.0, 0, 1)
        f = (GATE_SUN * (1 - wet) + GATE_RAIN * wet).astype(np.uint8)
        grade = tuple(1 + (v - 1) * wet for v in SPR_RAIN)
        commuters(f, T, pl, grade, "grey" if wet > 0.4 else None, 30)
        people = []
        if T < T_DRY_REACH:
            i, x, y = seg(d_nw, 0, DRY_FROM, T - T_DRY)
            people.append((y, "him", d_nw, i, x, y, 1))
        elif T < T_D_WALK:
            spr = H["d_reach"]
            people.append((RACK_SPOT[1], "him", spr, breathing(spr, T - T_DRY_REACH, 16), *RACK_SPOT, 1))
        elif T < T_D_IN:
            i, x, y = seg(d_r, first_dr, RACK_SPOT, T - T_D_WALK)
            people.append((y, "him", d_r, i, x, y, 1))
        elif T < T_GONE:
            i, x, y = seg(d_in, 0, GATE_FRONT, T - T_D_IN)
            people.append((y, "him", d_in, i, x, y, min(1, (T_GONE - T) / 0.5)))
        # The stranger.
        if T >= T_S:
            if T < T_S_REACH:
                i, x, y = seg(s_l, first_sl, S_FROM, T - T_S)
                people.append((y, "st", s_l, i, x, y, min(1, (T - T_S) / 0.3)))
            elif T < T_S_RUN:
                spr = F["s_reach"]
                people.append((RACK_SPOT[1], "st", spr, breathing(spr, T - T_S_REACH, 16), *RACK_SPOT, 1))
            elif T < T_S_MEET:
                i, x, y = seg(s_run, first_srun, RACK_SPOT, T - T_S_RUN)
                people.append((y, "st", s_run, i, x, y, 1))
            else:
                spr = F["s_offer"]
                people.append((S_MEET[1], "st", spr, breathing(spr, T - T_S_MEET, 16), *S_MEET, 1))
        if T >= T_SW:
            if T < T_S_MEET + 0.1:
                i, x, y = seg(s_w, first_sw, S_HER_FROM, T - T_SW)
                people.append((y, "sw", s_w, i, x, y, min(1, (T - T_SW) / 0.3)))
            elif T < T_S_MEET + 1.0:
                spr = W["s_idle"]
                people.append((S_HER[1], "sw", spr, spr.index(T, "pingpong"), *S_HER, 1))
            else:
                spr = W["s_laugh"]
                people.append((S_HER[1], "sw", spr, breathing(spr, T - T_S_MEET - 1.0, 12), *S_HER, 1))
        in_rack = T_RETURN <= T < T_S_TAKE
        if in_rack:
            closed_umbrella(f, RACK_SLOT, 26)
        for _, who, spr, i, x, y, reveal in sorted(people, key=lambda p: p[0]):
            person(f, spr, i, x, y, pl, grade=grade if wet > 0 else None, reveal=reveal)
            if (who == "him" and T < T_RETURN) or (who == "st" and T >= T_S_TAKE):
                closed_umbrella(f, right_hand(spr, i, x, y), 26)
        if wet > 0:
            draw_rain(f, T, wet, ~pl["paper"])
        return f

    def draw(i, t, T):
        bass = band("bass", T)
        if T < T_CROSS:
            name, f = "gate", gate_rain_scene(T, bass)
        elif T < T_ROOF:
            name, f = "crossing", crossing_scene(T, bass)
        elif T < T_ROOMS:
            name, f = "rooftop", rooftop_scene(T, bass)
        elif T < T_PLAT:
            name, f = "rooms", rooms_scene(T, bass)
        elif T < T_DRY:
            name, f = "platform", platform_scene(T, bass)
        else:
            name, f = "dry", gate_dry_scene(T, bass)
        if name != state["scene"]:
            state["scene"], state["at"] = name, T
            splashes.clear()
        u = (T - state["at"]) / 0.17
        if u < 1 and state["last"] is not None:
            hide = bayer > u
            f[hide] = state["last"][hide]
        for a0, a1, card in cards:
            if a0 <= T < a1:
                h, w, _ = card.shape
                x0 = (G - w) // 2
                keep = bayer[16:16 + h, x0:x0 + w] < min(1, (T - a0) / 0.25, (a1 - T) / 0.25)
                f[16:16 + h, x0:x0 + w][keep] = card[keep]
        caps.draw(f, T)
        if T < 0.6:
            f[bayer > T / 0.6] = paper
        left = ctx["end"] - T
        if left < 1.2:
            f[bayer > left / 1.2] = paper
        state["last"] = np.array(f, np.uint8)
        return f.astype(np.uint8)

    return draw
