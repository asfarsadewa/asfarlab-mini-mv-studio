# Urip Maneh: two souls keep missing each other across lifetimes in Java.
# A wayang gunungan sweeps across the frame to end each life. In the chorus the lovers are shadows on the screen.
# A stone carver cuts her face into a wall. Six hundred years later she stands in front of it.
# The plate never moves. Footprints guard every path. No person holds one frame.
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pixkit import INK, Captions, Occlusion, Sprite, bayer_field, contact_shadow
from studio_paths import font_path

SCREEN = (93, 89, 268, 170)
PANEL = (143, 165, 209, 225)
HIS_SIDE, HER_SIDE = 140, 222
LAMP = (255, 222, 150)
PETAL = (252, 226, 214)
CHIP = (232, 214, 184)
NIGHT = np.array([0.70, 0.70, 0.86])
DAWN_LIGHT = np.array([1.06, 0.96, 0.84])
SHADOW = (0.1, 0.075, 0.06)
SPR_NIGHT = (0.8, 0.8, 0.94)
SPR_DAWN = (1.08, 0.97, 0.86)
DANCER_GRADE = (0.84, 0.76, 0.7)

# Scene edges. A wipe has the gunungan cross the frame around its time.
T_L1, T_L1W, T_L2, T_L3, T_CH, T_NOW, T_CLOSE, T_LAST = 14.0, 20.4, 27.9, 45.0, 56.1, 88.8, 96.4, 109.5
WIPES = (T_L1, T_L2, T_L3, T_CH, T_NOW)
WIPE_HALF = 0.55

CARVE = (178, 268)
QUAY = 250
SHIP_Y = 296
WIDE_HE, WIDE_SHE = (172, 258), (192, 258)
DANCERS = [(84, 244), (118, 234), (150, 228), (232, 228), (264, 234), (296, 244), (112, 262), (150, 274), (226, 274), (264, 262)]
VILLAGERS = [("r", 92, 268, 0.0), ("l", 306, 262, 2.1), ("r", 130, 280, 4.4), ("l", 270, 238, 1.2)]
BAND = [(30, 248), (46, 251), (62, 248), (78, 251)]
TOWN = [("k_walk_r", 200, 246, 0.0), ("k_walk_l", 340, 254, 2.5), ("k_walk_r", 110, 256, 5.0)]
CITY = [(0, 122, 214), (1, 246, 248), (0, 138, 226), (1, 254, 256), (0, 112, 222), (1, 238, 252), (0, 150, 236), (1, 228, 240)]
LANTERNS = [(24, 240), (124, 240), (226, 240), (336, 240)]


def key_sheet(path):
    """Cuts one object from a sheet with a flat magenta background."""
    arr = np.asarray(Image.open(path).convert("RGB")).astype(np.int32)
    keep = ~((arr[..., 0] > 170) & (arr[..., 2] > 170) & (arr[..., 1] < 110))
    ys, xs = np.nonzero(keep.sum(axis=1) > 2)[0], np.nonzero(keep.sum(axis=0) > 2)[0]
    box = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
    return np.dstack([arr[box[1]:box[3], box[0]:box[2]], keep[box[1]:box[3], box[0]:box[2]] * 255]).astype(np.uint8)


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
    rng = np.random.default_rng(61)
    bayer = bayer_field(G)
    Y, X = np.mgrid[:G, :G]
    caps = Captions(brief["lines"], paper, top_font=(font_path("msgothic.ttc"), 16), low_font=(font_path("simsun.ttc"), 12))
    shapes = json.loads((root / "occluders.json").read_text(encoding="utf-8"))

    def plate(name):
        d = np.asarray(Image.open(root / f"plates/{name}-360.png").convert("RGB")).copy()
        is_paper = (np.abs(d.astype(int) - paper.astype(int)).sum(axis=2) < 24) | (d.astype(int).sum(axis=2) > 720)
        d[is_paper] = paper
        return {"name": name, "day": d, "paper": is_paper, "occ": Occlusion(root, name)}

    P = {n: plate(n) for n in ("kelir", "candi", "candi_old", "relief", "relief_old", "kali", "jogja")}

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

    H1, H2, H3, H4 = (loader(f"hero_h{k}") for k in (1, 2, 3, 4))
    W1, W2, W3, W4 = (loader(f"hero_w{k}") for k in (1, 2, 3, 4))
    FM, FK, FJ, FD = loader("folk_m"), loader("folk_k"), loader("folk_j"), loader("folk_d")

    sheets = {n: key_sheet(root / f"plates/{n}-raw.png") for n in ("gunungan", "kapal", "wajah")}
    prop_cache = {}

    def prop(name, width):
        if (name, width) not in prop_cache:
            a = scaled(sheets[name], width)
            if name == "kapal":
                # Thin rigging blends with the magenta key when it shrinks. Drop those pixels.
                rgb = a[..., :3].astype(int)
                a[..., 3] = a[..., 3] * ~((rgb[..., 0] - rgb[..., 1] > 34) & (rgb[..., 2] - rgb[..., 1] > 34))
            prop_cache[(name, width)] = a
        return prop_cache[(name, width)]

    birds = load_birds(root / "plates/bird-raw.png")
    bird_cache = {}

    def flock(f, T, n, height, speed, width, offset=0.0):
        for k in range(n):
            x = ((T + offset) * speed - k * width * 1.4) % (G + 160) - 80
            frame = int((T / 0.8 + k * 0.37) * 8) % 8
            if (width, frame) not in bird_cache:
                bird_cache[(width, frame)] = scaled(np.asarray(birds[frame]), width)
            a = bird_cache[(width, frame)]
            stamp(f, a, x - a.shape[1] / 2, height + (k % 3) * width * 0.5 + np.sin(T * 1.1 + k) * 2)

    def since_beat(T):
        past = beats[beats <= T]
        return T - past[-1] if len(past) else 9.0

    def band(name, T):
        v = A[name]
        return v[min(int(T * fps), len(v) - 1)]

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

    def inside(name, pts, test):
        off = [p for p in pts if not test(*p)]
        if off:
            raise SystemExit(f"A person leaves the walkable area on {name}: {off[0]}")

    def seg(spr, first, start, t, rate=1.0):
        i = min(first + int(max(t, 0) * spr.fps * rate), spr.n - 1)
        a, b = spr.path(i), spr.path(first)
        return i, start[0] + a[0] - b[0], start[1] + a[1] - b[1]

    def seg_end(spr, first, start):
        return seg(spr, first, start, 1e6)[1:]

    def seg_time(spr, first=0, rate=1.0):
        return (spr.n - 1 - first) / spr.fps / rate

    def back_from(spr, first, end):
        a, b = spr.path(spr.n - 1), spr.path(first)
        return end[0] - a[0] + b[0], end[1] - a[1] + b[1]

    def tail_from(spr, dist):
        end = spr.path(spr.n - 1)
        return next((i for i in range(spr.n - 1, -1, -1) if np.hypot(end[0] - spr.path(i)[0], end[1] - spr.path(i)[1]) >= dist), 0)

    def walk_points(spr, first, start):
        return [seg(spr, first, start, k / spr.fps)[1:] for k in range(spr.n - first)]

    def run_loop(spr, start, t, rate=1.0, a=19, b=36):
        frames = t * spr.fps * rate
        laps, rest = divmod(frames, b - a)
        i = a + int(rest)
        pa, pb, pi = spr.path(a), spr.path(b), spr.path(i)
        return i, start[0] + laps * (pb[0] - pa[0]) + pi[0] - pa[0], start[1] + laps * (pb[1] - pa[1]) + pi[1] - pa[1]

    def shadow(f, x, y, rx, ry, pl):
        contact_shadow(f, x, y, rx, ry, 0.8, bayer, ~pl["paper"], 2, occ=pl["occ"])

    def person(f, spr, i, x, y, pl, grade=None, sh=(6, 2), reveal=1.0, light=None):
        shadow(f, x, y, sh[0], sh[1], pl)
        spr.draw(f, i, x, y, occ=pl["occ"], grade=grade, bayer=bayer, reveal=reveal, light=light)

    motes = []

    def run_motes(f, colour=LAMP):
        for m in motes:
            m[0] += m[2] / fps
            m[1] += m[3] / fps
            m[4] -= 1 / fps
            x, y = int(m[0]), int(m[1])
            if 0 <= x < G and 0 <= y < G and m[4] > 0:
                f[y, x] = m[5] if len(m) > 5 else colour
        motes[:] = [m for m in motes if m[4] > 0]

    petals = [[rng.uniform(0, G), rng.uniform(40, 300), rng.uniform(0, 6), rng.uniform(8, 20)] for _ in range(70)]

    def fall_petals(f, T, n, x0=0, x1=None, floor=300):
        x1 = G if x1 is None else x1
        for k, (x, y, ph, speed) in enumerate(petals[:n]):
            py = 60 + (y + T * speed) % (floor - 60)
            px = x0 + (x + np.sin(T * 0.9 + ph) * 14 + T * 3) % (x1 - x0)
            f[int(py), int(px)] = PETAL

    built = {}

    def scene(name, builder):
        if name not in built:
            built[name] = builder()
        return built[name]

    # The shadow stage: the lamp breathes on the screen. Shadows fall only on the screen.
    kelir = P["kelir"]
    kelir_base = graded(kelir, np.array([0.86, 0.82, 0.8]))
    x0, y0, x1, y1 = SCREEN
    screen_mask = np.zeros((G, G), bool)
    screen_mask[y0:y1, x0:x1] = True
    radial = np.clip(1.16 - np.hypot((X - 180) / 118.0, (Y - 128) / 66.0) * 0.32, 0.78, 1.2)[..., None]

    def stage(T, power=1.0):
        f = kelir_base.copy()
        flicker = 1.0 + np.sin(T * 7.3) * 0.015 + np.sin(T * 11.9) * 0.012 + band("bass", T) * 0.03
        lit = np.clip(kelir_base[screen_mask].astype(np.float32) * (radial[screen_mask] * flicker * power), 0, 255).astype(np.uint8)
        f[screen_mask] = lit
        return f

    def cast(f, spr, i, x, y, reveal=1.0):
        """A person becomes a shadow on the screen. The shadow stops at the edge of the screen."""
        temp = f.copy()
        spr.draw(temp, i, x, y, occ=None, grade=SHADOW, bayer=bayer, reveal=reveal)
        f[screen_mask] = temp[screen_mask]

    def players(f, T):
        # The gamelan players and the dalang sit in front of the screen.
        for n, (spr, x, y) in enumerate(((FM["g_sit"], 104, 196), (FM["g_sit2"], 256, 196), (FM["g_sit"], 120, 214), (FM["g_sit2"], 240, 214))):
            person(f, spr, spr.index(T + n * 0.7, "pingpong"), x, y, kelir, sh=(5, 2))
        d = FK["dalang"]
        person(f, d, d.index(T, "pingpong"), 178, 218, kelir, sh=(5, 2))

    def planted(f, T, drop=0.0, sway=0.0):
        a = prop("gunungan", 76)
        stamp(f, a, 180 - a.shape[1] / 2 + np.sin(T * 1.4) * sway, 170 - a.shape[0] + 2 + drop)

    def build_open():
        def draw(T):
            f = stage(T, min(1, 0.72 + T * 0.1))
            planted(f, T, 0, 1.6)
            players(f, T)
            return f
        return draw

    # Life one. He cuts her face out of the stone, one strike at a time.
    def face_on_wall(f, progress, grade=None):
        x0, y0, x1, y1 = PANEL
        a = prop("wajah", x1 - x0).copy()
        if grade is not None:
            a[..., :3] = np.clip(a[..., :3] * np.array(grade), 0, 255).astype(np.uint8)
        h, w = a.shape[:2]
        if progress < 1:
            # The cut spreads down from the crown.
            rows = (np.arange(h)[:, None] / h + bayer[:h, :w] * 0.22) < progress * 1.22
            a[..., 3] = a[..., 3] * rows
        stamp(f, a, x0, y0)

    def build_carve():
        pl = P["relief"]
        base = graded(pl, np.array([1.02, 1.0, 0.96]))
        carve = H1["k_carve"]
        guard("relief", [CARVE])
        strikes = [t for t in beats if T_L1 <= t < T_L1W][::2]

        def draw(T):
            f = base.copy()
            face_on_wall(f, np.clip((T - T_L1) / (T_L1W - T_L1 - 0.8), 0, 1))
            # The arm rises between beats and lands on the beat.
            phase = np.clip(since_beat(T) / 0.4, 0, 1)
            i = int(round((1 - abs(1 - 2 * phase)) * (carve.n - 1)))
            person(f, carve, i, *CARVE, pl, sh=(16, 5))
            near = min((abs(T - t) for t in strikes), default=9)
            if near < 0.5 / fps:
                for _ in range(10):
                    motes.append([176 + rng.uniform(-14, 14), 214 + rng.uniform(-12, 8), rng.uniform(-30, 30), rng.uniform(4, 44), rng.uniform(0.3, 0.8), CHIP])
            run_motes(f)
            return f
        return draw

    def build_court():
        pl = P["candi"]
        base = graded(pl, np.array([1.03, 1.0, 0.95]))
        s_r, s_up = W1["c_walk"], W1["c_up"]
        h_i, h_r = H1["c_idle"], H1["c_reach"]
        v_r, v_l = FM["v_walk_r"], FM["v_walk_l"]
        HIM = (94, 246)
        first = tail_from(s_r, 86)
        S_TO = (206, 252)
        S_FROM = back_from(s_r, first, S_TO)
        T_UP = T_L1W + seg_time(s_r, first)
        guard("candi", [HIM, S_FROM, S_TO] + [(x, y) for _, x, y, _ in VILLAGERS])

        def draw(T):
            f = base.copy()
            flock(f, T, 4, 96, 22, 11, 3.0)
            fall_petals(f, T, 28, 70, 330, 270)
            people = []
            if T < T_UP:
                i, x, y = seg(s_r, first, S_FROM, T - T_L1W)
                her = (s_r, i, x, y, 1.0)
            else:
                i, x, y = seg(s_up, 0, S_TO, T - T_UP)
                her = (s_up, i, x, y, min(1, (T_L2 + 0.5 - T) / 0.5))
            people.append((her[3], "her", *her))
            if T < T_UP:
                # Two attendants walk behind her.
                for n, gap in enumerate((18, 36)):
                    j, ax, ay = seg(v_r, 0, (S_FROM[0] - gap, S_FROM[1] + (n * 2 - 1) * 3), T - T_L1W + 0.2 * n)
                    people.append((ay, "folk", v_r, j, ax, ay, min(1, (T - T_L1W) / 0.4)))
            for way, x, y, ph in VILLAGERS:
                spr = v_r if way == "r" else v_l
                t = (T + ph) % 7.0
                if t < seg_time(spr):
                    j, vx, vy = seg(spr, 0, (x, y), t)
                    people.append((vy, "folk", spr, j, vx, vy, min(1, t / 0.4, (seg_time(spr) - t) / 0.4)))
            spr = h_r if T >= 21.4 else h_i
            people.append((HIM[1], "him", spr, breathing(spr, T - 21.4, 16) if T >= 21.4 else spr.index(T, "pingpong"), *HIM, 1.0))
            for _, who, spr, i, x, y, rv in sorted(people, key=lambda p: p[0]):
                person(f, spr, i, x, y, pl, reveal=rv)
            return f
        return draw

    # Life two. The ship leaves, and the river runs out of quay.
    def build_river():
        pl = P["kali"]
        base = graded(pl, NIGHT)
        sway, walk_t = FK["k_sway"], FK["k_walk_r"]
        run, reach, idle = H2["q_run"], H2["q_reach"], H2["q_idle"]
        wave = W2["d_wave"]
        T_SAIL, T_RUN = 31.0, 31.6
        RUN_FROM = (118, QUAY)
        RATE = 1.5
        T_STOP = T_RUN + next(k / fps for k in range(1, 900) if run_loop(run, RUN_FROM, k / fps, RATE)[1] >= 272)
        STOP = (run_loop(run, RUN_FROM, T_STOP - T_RUN, RATE)[1], QUAY)
        print("River run stops at", round(STOP[0], 1), "at", round(T_STOP, 2), flush=True)
        guard("kali", [RUN_FROM, STOP])
        ship_w = 150
        ship = prop("kapal", ship_w)

        def ship_at(T):
            t = max(T - T_SAIL, 0)
            return 52 + 0.5 * 16 * t * t

        def draw(T):
            f = base.copy()
            # The lamps breathe, and their light shakes on the water.
            for x, y in LANTERNS:
                glow = (np.hypot((X - x) / 26.0, (Y - y) / 12.0) + bayer * 0.35) < 0.9 + np.sin(T * 3 + x) * 0.06
                glow &= ~pl["paper"]
                f[glow] = np.clip(f[glow].astype(np.float32) * np.array([1.2, 1.08, 0.86]), 0, 255).astype(np.uint8)
                for k in range(22):
                    px, py = x + int(np.sin(T * 2 + k * 2.1) * (3 + k % 7)), 268 + (k * 3) % 30
                    if 0 <= px < G and not pl["paper"][py, px] and np.sin(T * 4 + k) > 0:
                        f[py, px] = LAMP
            people = []
            for n, (x, y) in enumerate(BAND):
                people.append((y, sway, sway.index(T + n * 0.6, "pingpong"), x, y, 1.0))
            for name, x, y, ph in TOWN:
                spr = FK[name]
                t = (T + ph) % 8.0
                if t < seg_time(spr):
                    j, px, py = seg(spr, 0, (x, y), t)
                    people.append((py, spr, j, px, py, min(1, t / 0.4, (seg_time(spr) - t) / 0.4)))
            if T < T_RUN:
                people.append((QUAY, idle, idle.index(T, "pingpong"), *RUN_FROM, 1.0))
            elif T < T_STOP:
                i, x, y = run_loop(run, RUN_FROM, T - T_RUN, RATE)
                people.append((y, run, i, x, y, 1.0))
            elif T < 41.0:
                people.append((QUAY, reach, breathing(reach, T - T_STOP, 16), *STOP, 1.0))
            else:
                people.append((QUAY, idle, idle.index(T, "pingpong"), *STOP, 1.0))
            for _, spr, i, x, y, rv in sorted(people, key=lambda p: p[0]):
                is_him = spr in (run, reach, idle)
                light = (x, y - 11, 15, (1.9, 1.75, 1.45)) if is_him else None
                person(f, spr, i, x, y, pl, grade=SPR_NIGHT, sh=(4, 1), reveal=rv, light=light)
            sx = ship_at(T)
            if sx < G + 20:
                # She stands on the deck, and the ship carries her.
                stamp(f, ship, sx, SHIP_Y - ship.shape[0])
                # She stands on the open foredeck, in the deck lamp.
                px, py = sx + ship_w * 0.8, SHIP_Y - ship.shape[0] * 0.42
                lit = (np.hypot((X - px) / 16.0, (Y - py + 9) / 15.0) + bayer * 0.3 < 1.0) & (Y < py + 1)
                f[lit] = np.clip(f[lit].astype(np.float32) * np.array([1.5, 1.34, 1.05]) + 14, 0, 255).astype(np.uint8)
                wave.draw(f, wave.index(T, "pingpong"), px, py, grade=(1.3, 1.2, 1.1), bayer=bayer)
                for k in range(8):
                    wx = int(sx + k * 16 - t_wake(T) % 16)
                    if 0 <= wx < G:
                        f[SHIP_Y - 1, wx] = (214, 226, 236)
            return f

        def t_wake(T):
            return T * 22

        return draw

    # Life three. They pass on a crowded street. Each one stops and looks back, then walks on.
    def build_street():
        pl = P["jogja"]
        base = pl["day"].copy()
        base[pl["paper"]] = paper
        h_w, h_l, s_w, s_l = H3["j_walk"], H3["j_look"], W3["j_walk"], W3["j_look"]
        c_r, c_l = FJ["j_r"], FJ["j_l"]
        MEET = (196, 230)
        first_h = tail_from(h_w, 62)
        first_s = tail_from(s_w, 62)
        T_PASS = 50.0
        H_FROM = back_from(h_w, first_h, (MEET[0] + 6, MEET[1] + 1))
        S_FROM = back_from(s_w, first_s, (MEET[0] - 6, MEET[1] + 5))
        T_H = T_PASS - seg_time(h_w, first_h)
        T_S = T_PASS - seg_time(s_w, first_s)
        H_AT, S_AT = (MEET[0] + 6, MEET[1] + 1), (MEET[0] - 6, MEET[1] + 5)
        T_ON = T_PASS + 2.0

        def street(x, y):
            top = 207 + 0.26 * (x - 110)
            return 108 <= x <= 262 and top <= y <= top + 42

        pts = walk_points(h_w, first_h, H_FROM) + walk_points(s_w, first_s, S_FROM)
        lanes = [(c_r if w == 0 else c_l, x, y, 2.3 * n) for n, (w, x, y) in enumerate(CITY)]
        lanes = [(s, x, y, ph, tail_from(s, 74)) for s, x, y, ph in lanes]
        for s, x, y, _, fr in lanes:
            pts = pts + walk_points(s, fr, (x, y))
        inside("jogja", pts, street)
        guard("jogja", pts)

        def draw(T):
            f = base.copy()
            # Neon breathes in the wet road. The plate itself stays still.
            for k, (x, y, tone) in enumerate(((130, 226, (240, 120, 170)), (190, 232, (110, 220, 210)), (156, 216, (240, 120, 170)), (226, 244, (250, 190, 110)))):
                for n in range(16):
                    px, py = x + int(np.sin(T * 1.4 + n * 1.9 + k) * 9), y + (n * 2) % 20
                    if np.sin(T * 3 + n * 1.2 + k) > 0.3:
                        f[py, px] = tone
            people = []
            for s, x, y, ph, fr in lanes:
                t = (T + ph) % (seg_time(s, fr) + 1.2)
                if t < seg_time(s, fr):
                    j, px, py = seg(s, fr, (x, y), t)
                    people.append((py, s, j, px, py, min(1, t / 0.4, (seg_time(s, fr) - t) / 0.4)))
            if T < T_PASS:
                if T >= T_H:
                    j, x, y = seg(h_w, first_h, H_FROM, T - T_H)
                    people.append((y, h_w, j, x, y, 1.0))
            elif T < T_ON:
                people.append((H_AT[1], h_l, h_l.index(T, "pingpong"), *H_AT, 1.0))
            else:
                j, x, y = seg(h_w, 40, H_AT, T - T_ON, 0.55)
                people.append((y, h_w, j, x, y, 1.0))
            if T < T_PASS:
                if T >= T_S:
                    j, x, y = seg(s_w, first_s, S_FROM, T - T_S)
                    people.append((y, s_w, j, x, y, 1.0))
            elif T < T_ON:
                people.append((S_AT[1], s_l, s_l.index(T, "pingpong"), *S_AT, 1.0))
            else:
                j, x, y = seg(s_w, 40, S_AT, T - T_ON, 0.55)
                people.append((y, s_w, j, x, y, 1.0))
            for _, spr, i, x, y, rv in sorted(people, key=lambda p: p[0]):
                person(f, spr, i, x, y, pl, sh=(5, 2), reveal=rv)
            return f
        return draw

    # The chorus: the two souls as shadows on the screen. Then every life passes. Then the kayon is planted.
    def build_shadow():
        h_w, s_w = H1["sh_walk"], W1["sh_walk"]
        h_i, s_i = H1["sh_idle"], W1["sh_idle"]
        h_r, s_r = H1["sh_reach"], W1["sh_reach"]
        h_d, s_d = H1["sh_court"], W1["sh_court"]
        RATE = 0.5
        first_h = tail_from(h_w, 46)
        first_s = tail_from(s_w, 46)
        HF = back_from(h_w, first_h, (HIS_SIDE, 170))
        SF = back_from(s_w, first_s, (HER_SIDE, 170))
        T_START = T_CH - WIPE_HALF
        T_MET = T_START + seg_time(h_w, first_h, RATE)
        T_REACH, T_DANCE, T_APART = T_MET + 0.1, 63.9, 69.2
        T_LIVES, T_LOST, T_KAYON, T_RISE = 76.7, 79.9, 83.2, 86.0
        lives = [(H1["sh_idle"], 122, 76.7), (H2["sh_idle"], 180, 77.8), (H3["sh_idle"], 238, 78.9)]
        souls = [(W1["sh_idle"], 150, 79.9), (W2["sh_idle"], 208, 80.8), (W3["sh_idle"], 262, 81.7)]
        stars = [(int(rng.uniform(100, 262)), int(rng.uniform(95, 150)), rng.uniform(0, 6)) for _ in range(60)]

        def draw(T):
            f = stage(T, 1.0 + 0.06 * (T >= T_RISE))
            if T < T_LIVES:
                if T < T_MET:
                    i, x, y = seg(h_w, first_h, HF, T - T_START, RATE)
                    cast(f, h_w, i, x, y)
                    i, x, y = seg(s_w, first_s, SF, T - T_START, RATE)
                    cast(f, s_w, i, x, y)
                elif T < T_DANCE:
                    cast(f, h_r, breathing(h_r, T - T_REACH, 16), HIS_SIDE, 170)
                    cast(f, s_r, breathing(s_r, T - T_REACH, 16), HER_SIDE, 170)
                elif T < T_APART:
                    # 'The stars change their places': they dance, and points of light drift on the screen.
                    cast(f, h_d, h_d.index(T - T_DANCE, "pingpong"), HIS_SIDE, 170)
                    cast(f, s_d, s_d.index(T - T_DANCE, "pingpong"), HER_SIDE, 170)
                    for x, y, ph in stars:
                        px = x + (T - T_DANCE) * 3 * np.sin(ph)
                        py = y + np.sin(T * 0.6 + ph) * 3
                        if screen_mask[int(py), int(px)] and np.sin(T * 2.2 + ph) > -0.3:
                            f[int(py), int(px)] = (255, 250, 220)
                else:
                    # She walks away along the screen. He keeps one hand out.
                    cast(f, h_r, breathing(h_r, T - T_APART, 16), HIS_SIDE, 170)
                    i, x, y = seg(s_w_out, 0, (HER_SIDE, 170), T - T_APART, 0.42)
                    cast(f, s_w_out, i, x, y, reveal=min(1, max(T_LIVES - T, 0) / 2.0))
            elif T < T_KAYON:
                for spr, x, at in lives:
                    if T >= at:
                        cast(f, spr, spr.index(T, "pingpong"), x, 170, reveal=min(1, (T - at) / 0.3) * min(1, max(T_KAYON - T, 0) / 0.5))
                for spr, x, at in souls:
                    if T >= at:
                        # Each of her lives fades, a little after it appears.
                        fade = 1 - np.clip((T - at - 0.9) / 0.9, 0, 1)
                        if fade > 0:
                            cast(f, spr, spr.index(T, "pingpong"), x, 170, reveal=min(1, (T - at) / 0.3) * fade)
            if T >= T_KAYON:
                v = min((T - T_KAYON) / 1.1, 1)
                drop = -(1 - v * v) * 140
                planted(f, T, drop, 0.8)
                if v >= 1 and since_beat(T) < 0.03:
                    for _ in range(8):
                        motes.append([180 + rng.uniform(-34, 34), 168, rng.uniform(-20, 20), rng.uniform(-40, -8), rng.uniform(0.4, 1.0)])
            players(f, T)
            run_motes(f)
            return f

        s_w_out = W1["sh_out"]
        return draw

    # The present. Dawn at the same temple. The dancers practise in the courtyard.
    def dancers(people, T):
        for n, (x, y) in enumerate(DANCERS):
            spr = FD["d_court"] if n % 2 else FD["d_court2"]
            people.append((y, spr, spr.index(T + n * 1.1, "pingpong"), x, y, 1.0))

    def rays(f, T, power):
        for k in range(5):
            cx = 30 + k * 66 + np.sin(T * 0.3 + k) * 6
            band_ = np.abs((X - cx) - (Y - 60) * 0.42) < 9 + k % 3 * 3
            pick = band_ & (bayer < 0.2 * power) & (Y > 60) & (Y < 300) & ~P["candi_old"]["paper"]
            f[pick] = np.clip(f[pick].astype(np.float32) * 1.12 + 10, 0, 255).astype(np.uint8)

    def build_dawn():
        pl = P["candi_old"]
        base = graded(pl, DAWN_LIGHT)
        h_w, s_w = H4["n_walk"], W4["n_walk"]
        first = tail_from(h_w, 50)
        H_TO, S_TO = (132, 254), (222, 248)
        H_FROM, S_FROM = back_from(h_w, first, H_TO), back_from(s_w, first, S_TO)
        guard("candi_old", [H_FROM, S_FROM, H_TO, S_TO] + DANCERS)
        h_i, s_i = H4["n_idle"], W4["n_idle"]

        def draw(T):
            f = base.copy()
            rays(f, T, 1.0)
            flock(f, T, 5, 56, 18, 11, 1.0)
            fall_petals(f, T, 52, 20, 340, 280)
            people = []
            dancers(people, T)
            if T < T_NOW - WIPE_HALF + seg_time(h_w, first):
                j, x, y = seg(h_w, first, H_FROM, T - T_NOW + WIPE_HALF)
                people.append((y, h_w, j, x, y, 1.0))
                j, x, y = seg(s_w, first, S_FROM, T - T_NOW + WIPE_HALF)
                people.append((y, s_w, j, x, y, 1.0))
            else:
                people.append((H_TO[1], h_i, h_i.index(T, "pingpong"), *H_TO, 1.0))
                people.append((S_TO[1], s_i, s_i.index(T, "pingpong"), *S_TO, 1.0))
            for _, spr, i, x, y, rv in sorted(people, key=lambda p: p[0]):
                g = SPR_DAWN if spr in (h_w, s_w, h_i, s_i) else DANCER_GRADE
                person(f, spr, i, x, y, pl, grade=g, sh=(5, 2), reveal=rv)
            return f
        return draw

    def build_touch():
        pl = P["relief_old"]
        base = graded(pl, np.array([1.04, 0.98, 0.9]))
        touch, face, walk, h_look, h_face = W4["b_touch"], W4["b_face"], H4["a_walk"], H4["a_look"], H4["a_face"]
        SHE, HE = (148, 268), (226, 268)
        first = tail_from(walk, 58)
        HF = back_from(walk, first, HE)
        T_IN = T_CLOSE + 1.0
        T_AT = T_IN + seg_time(walk, first)
        T_TURN = 103.2
        guard("relief_old", [SHE, HE, HF])

        def draw(T):
            f = base.copy()
            face_on_wall(f, 1.0, (0.86, 0.76, 0.62))
            fall_petals(f, T, 18, 50, 300, 276)
            people = []
            if T < T_TURN:
                people.append((SHE[1], touch, breathing(touch, T - T_CLOSE, 20), *SHE))
            else:
                people.append((SHE[1], face, face.index(T, "pingpong"), *SHE))
            if T < T_IN:
                pass
            elif T < T_AT:
                j, x, y = seg(walk, first, HF, T - T_IN)
                people.append((y, walk, j, x, y))
            elif T < T_TURN + 1.6:
                people.append((HE[1], h_look, h_look.index(T, "pingpong"), *HE))
            else:
                people.append((HE[1], h_face, h_face.index(T, "pingpong"), *HE))
            for _, spr, i, x, y in sorted(people, key=lambda p: p[0]):
                person(f, spr, i, x, y, pl, sh=(16, 5))
            return f
        return draw

    def build_last():
        pl = P["candi_old"]
        base = graded(pl, np.array([1.12, 1.04, 0.92]))
        he_t, she_t, he_w, she_w = H4["n_touch"], W4["n_touch"], H4["n_walk"], W4["n_walk"]
        T_TOUCH = 113.7
        T_REACH = T_TOUCH - 29 / he_t.fps
        steps = int((T_REACH - T_LAST) * he_w.fps)
        first = he_w.n - 1 - steps
        HE_FROM, SHE_FROM = back_from(he_w, first, WIDE_HE), back_from(she_w, first, WIDE_SHE)
        guard("candi_old", [HE_FROM, SHE_FROM, WIDE_HE, WIDE_SHE])
        fired = {"done": False}
        cx, cy = (WIDE_HE[0] + WIDE_SHE[0]) / 2, WIDE_HE[1]
        pool = (np.hypot((X - cx) / 58.0, (Y - cy) / 24.0) + bayer * 0.28 < 1.0) & ~pl["paper"]
        base[pool] = np.clip(base[pool].astype(np.float32) * np.array([1.2, 1.14, 1.02]) + 8, 0, 255).astype(np.uint8)

        def draw(T):
            f = base.copy()
            rays(f, T, 1.6)
            flock(f, T, 6, 62, 22, 11, 8.0)
            fall_petals(f, T, 70, 10, 350, 290)
            people = []
            dancers(people, T)
            if T < T_REACH:
                j, x, y = seg(he_w, first, HE_FROM, T - T_LAST)
                people.append((y, he_w, j, x, y, 1.0))
                j, x, y = seg(she_w, first, SHE_FROM, T - T_LAST)
                people.append((y, she_w, j, x, y, 1.0))
            else:
                people.append((WIDE_HE[1], he_t, breathing(he_t, T - T_REACH, 30), *WIDE_HE, 1.0))
                people.append((WIDE_SHE[1], she_t, breathing(she_t, T - T_REACH, 30), *WIDE_SHE, 1.0))
            for _, spr, i, x, y, rv in sorted(people, key=lambda p: p[0]):
                g = (1.1, 1.04, 0.96) if spr in (he_t, she_t, he_w, she_w) else DANCER_GRADE
                person(f, spr, i, x, y, pl, grade=g, sh=(5, 2), reveal=rv)
            if T >= T_TOUCH and not fired["done"]:
                fired["done"] = True
                for _ in range(60):
                    motes.append([cx, cy - 24, rng.uniform(-52, 52), rng.uniform(-62, 22), rng.uniform(0.8, 3.0), PETAL if rng.random() < 0.5 else LAMP])
            run_motes(f)
            return f
        return draw

    def scene_at(T):
        if T < T_L1:
            return "open", build_open
        if T < T_L1W:
            return "carve", build_carve
        if T < T_L2:
            return "court", build_court
        if T < T_L3:
            return "river", build_river
        if T < T_CH:
            return "street", build_street
        if T < T_NOW:
            return "shadow", build_shadow
        if T < T_CLOSE:
            return "dawn", build_dawn
        if T < T_LAST:
            return "touch", build_touch
        return "last", build_last

    gun_w = 300
    font_big = ImageFont.truetype(font_path("msgothic.ttc"), 26)
    font_small = ImageFont.truetype(font_path("simsun.ttc"), 12)
    title = Image.new("RGB", (190, 54), INK)
    d = ImageDraw.Draw(title)
    d.fontmode = "1"
    d.text((95 - font_big.getlength(brief["title"]) / 2, 6), brief["title"], font=font_big, fill=tuple(int(v) for v in paper))
    d.text((95 - font_small.getlength(brief["title_zh"]) / 2, 37), brief["title_zh"], font=font_small, fill=(214, 208, 196))
    title = np.asarray(title)
    state = {"last": None, "scene": None, "at": 0.0}

    def draw(i, t, T):
        name, builder = scene_at(T)
        wipe = next((w for w in WIPES if abs(T - w) < WIPE_HALF), None)
        if wipe is not None:
            old_name, old_builder = scene_at(wipe - 0.001)
            new_name, new_builder = scene_at(wipe + 0.001)
            old = scene(old_name, old_builder)(T)
            new = scene(new_name, new_builder)(T)
            u = (T - wipe + WIPE_HALF) / (2 * WIPE_HALF)
            edge = -gun_w / 2 + (G + gun_w) * u
            f = np.where((X < edge)[..., None], new, old).astype(np.uint8)
            g = prop("gunungan", gun_w)
            stamp(f, g, edge - gun_w / 2, (G - g.shape[0]) / 2 + 10)
            state["scene"], state["at"] = new_name, wipe - 9
        else:
            f = scene(name, builder)(T)
            if name != state["scene"]:
                state["scene"], state["at"] = name, T
                motes.clear()
            u = (T - state["at"]) / 0.2
            if u < 1 and state["last"] is not None:
                hide = bayer > u
                f[hide] = state["last"][hide]
        if 1.2 <= T < 9.0:
            h, w, _ = title.shape
            x0 = (G - w) // 2
            keep = bayer[0 + 2:2 + h, x0:x0 + w] < min(1, (T - 1.2) / 0.3, (9.0 - T) / 0.3)
            f[2:2 + h, x0:x0 + w][keep] = title[keep]
        caps.draw(f, T)
        if T < 0.6:
            f[bayer > T / 0.6] = paper
        left = ctx["end"] - T
        if left < 1.2:
            f[bayer > left / 1.2] = paper
        state["last"] = np.array(f, np.uint8)
        return f.astype(np.uint8)

    return draw
