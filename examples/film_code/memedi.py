# Memedi Sawah: a scarecrow loves one small sparrow, and his job is to scare her away.
# The farmer pulls the rope, the tin cans rattle, and his arms dance. Each dance sends her off.
# At harvest the farmer takes him down. He lies still, so she lands on his open hand, and the flock follows.
# One rice field in four seasons, plus two close views of the mound. The plates never move.
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pixkit import INK, Captions, Occlusion, Sprite, bayer_field, contact_shadow
from studio_paths import font_path

ROPE = (78, 56, 40)
CAN = [(176, 184, 194), (236, 240, 244), (100, 104, 116)]
POLE = [(150, 118, 70), (196, 162, 102), (104, 78, 48)]
STRAW = (232, 196, 96)
DAWN = np.array([1.02, 0.99, 0.98])
GOLD = np.array([1.03, 1.0, 0.94])
HAZE = np.array([1.02, 0.98, 0.92])

# Scene edges, on the lyric lines.
T_CLOSE, T_PULL, T_GOLD, T_PANEN, T_REST, T_OUTRO = 6.2, 29.0, 35.27, 52.9, 67.3, 87.6

# Wide plates: the mound, the farmer's place and the field paths, in grid pixels.
MOUND = (183, 237)
LIFT_WIDE = 11
FARMER = (129, 216)
WIFE_REAP = (122, 262)
NEAR_POLE = (168, 233)
LIE_WIDE = (186, 241)
# Close plates: the mound top.
MOUND_CLOSE = (180, 193)
LIFT_CLOSE = 34
LIE_CLOSE = (186, 206)


def key_birds(path):
    """Cuts 8 sparrow frames from the sheet. The sheet background is half transparent, so only solid pixels count."""
    arr = np.asarray(Image.open(path).convert("RGBA"))
    solid = arr[..., 3] >= 224
    h, w = solid.shape
    cw, ch = w // 4, h // 2
    frames = []
    for row in range(2):
        for col in range(4):
            cell = solid[row * ch:(row + 1) * ch, col * cw:(col + 1) * cw]
            ys, xs = np.nonzero(cell)
            # Keep the main body. A stray speck far from the centre of mass is dropped.
            cy, cx = np.median(ys), np.median(xs)
            keep = (np.abs(ys - cy) < ch * 0.4) & (np.abs(xs - cx) < cw * 0.45)
            ys, xs = ys[keep], xs[keep]
            y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
            part = arr[row * ch + y0:row * ch + y1, col * cw + x0:col * cw + x1].copy()
            part[..., 3] = cell[y0:y1, x0:x1] * 255
            frames.append(part)
    return frames


def scaled(a, width):
    img = Image.fromarray(a, "RGBA")
    k = width / img.width
    small = np.asarray(img.resize((max(2, round(img.width * k)), max(2, round(img.height * k))), Image.BOX)).copy()
    small[..., 3] = (small[..., 3] > 120) * 255
    return small


def stamp(f, a, x0, y0):
    G = f.shape[0]
    h, w = a.shape[:2]
    x0, y0 = int(round(x0)), int(round(y0))
    ax0, ay0, ax1, ay1 = max(x0, 0), max(y0, 0), min(x0 + w, G), min(y0 + h, G)
    if ax0 >= ax1 or ay0 >= ay1:
        return
    part = a[ay0 - y0:ay1 - y0, ax0 - x0:ax1 - x0]
    solid = part[..., 3] > 0
    f[ay0:ay1, ax0:ax1][solid] = part[..., :3][solid]


def ease(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


def make(ctx):
    G, fps, brief, A, root = ctx["grid"], ctx["fps"], ctx["brief"], ctx["a"], ctx["root"]
    paper = np.array(brief["paper"], np.uint8)
    beats = np.array(A["beats"])
    rng = np.random.default_rng(31)
    bayer = bayer_field(G)
    caps = Captions(brief["lines"], paper, top_font=(font_path("msgothic.ttc"), 16), low_font=(font_path("simsun.ttc"), 12))
    shapes = json.loads((root / "occluders.json").read_text(encoding="utf-8"))
    BEAT = float(np.median(np.diff(beats)))

    def plate(name, k):
        d = np.asarray(Image.open(root / f"plates/{name}-360.png").convert("RGB")).copy()
        # Paper counts only where it connects to the frame edge, so pale water stays inside the island.
        near = (np.abs(d.astype(int) - paper.astype(int)).sum(axis=2) < 30) | (d.astype(int).sum(axis=2) > 715)
        from scipy.ndimage import label
        lab, _ = label(near)
        edge = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
        is_paper = np.isin(lab, list(edge))
        out = np.clip(d * k, 0, 255).astype(np.uint8)
        out[is_paper] = paper
        return {"name": name, "img": out, "paper": is_paper, "occ": Occlusion(root, name)}

    P = {"sawah": plate("sawah", DAWN), "sawah_kuning": plate("sawah_kuning", GOLD), "panen": plate("panen", HAZE),
         "tandur": plate("tandur", DAWN), "cedhak": plate("cedhak", DAWN), "cedhak_tandur": plate("cedhak_tandur", DAWN)}

    def loader(folder):
        out = {}
        jobs = root / folder / "jobs.json"
        if jobs.exists():
            for n in json.loads(jobs.read_text()):
                if (root / folder / "sprites" / f"{n}.png").exists():
                    out[n] = Sprite(root, n, folder)
        return out

    H, F, M = loader("hero"), loader("hero_tani"), loader("hero_mbok")

    # The top of the hat in each frame, for the sparrow to sit on.
    def tops(spr):
        out = []
        ax = spr.anchor[0]
        for fr in spr.frames:
            a = fr[..., 3] > 0
            band = a[:, max(int(ax) - 3, 0):int(ax) + 4]
            rows = np.nonzero(band.any(axis=1))[0]
            out.append(int(rows.min()) if len(rows) else 0)
        return out

    # Perch points along the top edge of a lying body, for the flock to land on.
    def perches(spr, i, x, y, n):
        a = spr.frames[i][..., 3] > 0
        cols = np.nonzero(a.any(axis=0))[0]
        pts = []
        for c in np.linspace(cols.min() + 2, cols.max() - 2, n):
            c = int(c)
            r = int(np.nonzero(a[:, c])[0].min())
            pts.append((x + c - spr.anchor[0], y + r - spr.anchor[1]))
        return pts

    TOPS = {n: tops(s) for n, s in H.items()}

    birds = key_birds(root / "plates/emprit-raw.png")
    bird_cache = {}

    def bird(f, x, y, width, frame, flip=False):
        key = (width, frame, flip)
        if key not in bird_cache:
            a = scaled(birds[frame], width)
            bird_cache[key] = a[:, ::-1].copy() if flip else a
        a = bird_cache[key]
        # Feet sit at x, y.
        stamp(f, a, x - a.shape[1] / 2, y - a.shape[0] + 1)

    def flying(f, x, y, width, T, phase, flip):
        bird(f, x, y + width * 0.3, width, int((T * 9 + phase) % 4), flip)

    def perched(f, x, y, width, T, phase, flip=False):
        # Each sitting bird stands, looks back, pecks and hops, so none of them freezes.
        cycle = (T * 1.3 + phase) % 4
        frame = 4 + int(cycle)
        hop = -1 if frame == 7 and (cycle % 1) < 0.5 else 0
        bird(f, x, y + hop, width, frame, flip)

    def since_beat(T):
        past = beats[beats <= T]
        return T - past[-1] if len(past) else 9.0

    def beat_at(t):
        return float(beats[int(np.argmin(np.abs(beats - t)))])

    def breathing(spr, t, first=0):
        i = int(max(t, 0) * spr.fps)
        span = max(spr.n - 1 - first, 1)
        if i < first:
            return i
        j = (i - first) % (2 * span)
        return first + (j if j <= span else 2 * span - j)

    def dance_rate(spr):
        y = np.array([fr["right"][1] for fr in spr.meta["frames"]], float)
        y = y - y.mean()
        spectrum = np.abs(np.fft.rfft(y * np.hanning(len(y))))
        spectrum[:2] = 0
        period = len(y) / max(int(np.argmax(spectrum)), 1) / spr.fps
        best = min((1, 2, 4, 8), key=lambda m: abs(period / (BEAT * m) - 1))
        return float(np.clip(period / (BEAT * best), 0.75, 1.35))

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

    def walk_between(spr, a, b, t, first=0):
        """Walks from a to b. The frame comes from the distance walked, so the feet do not slide."""
        p0 = np.array(spr.path(first))
        dist_total = np.hypot(b[0] - a[0], b[1] - a[1])
        steps = [np.hypot(*(np.array(spr.path(i)) - p0)) for i in range(first, spr.n)]
        speed = steps[-1] / max((spr.n - 1 - first) / spr.fps, 1e-3)
        d = min(t * speed, dist_total)
        u = d / max(dist_total, 1e-3)
        # Loop the clip for a path longer than the clip.
        lap = steps[-1]
        rest = d % max(lap, 1e-3)
        i = first + int(np.searchsorted(steps, rest))
        return min(i, spr.n - 1), a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u, d >= dist_total

    def walk_time(spr, a, b, first=0):
        p0 = np.array(spr.path(first))
        lap = np.hypot(*(np.array(spr.path(spr.n - 1)) - p0))
        speed = lap / max((spr.n - 1 - first) / spr.fps, 1e-3)
        return np.hypot(b[0] - a[0], b[1] - a[1]) / speed

    def shadow(f, x, y, rx, ry, pl):
        contact_shadow(f, x, y, rx, ry, 0.8, bayer, ~pl["paper"], 2, occ=pl["occ"])

    def person(f, spr, i, x, y, pl, lift=0, sh=(5, 2)):
        if sh:
            shadow(f, x, y, sh[0], sh[1], pl)
        spr.draw(f, i, x, y - lift, occ=pl["occ"], bayer=bayer)

    def line(f, a, b, sag=0.0, colour=ROPE, wiggle=0.0, T=0.0):
        n = max(int(np.hypot(b[0] - a[0], b[1] - a[1])), 2)
        pts = []
        for k in range(n + 1):
            u = k / n
            x = a[0] + (b[0] - a[0]) * u + np.sin(u * 14 + T * 5) * wiggle * np.sin(u * np.pi)
            y = a[1] + (b[1] - a[1]) * u + np.sin(u * np.pi) * sag
            pts.append((x, y))
            if 0 <= int(y) < G and 0 <= int(x) < G:
                f[int(y), int(x)] = colour
        return pts

    def pole(f, base, height, width):
        x0, y1 = int(base[0]), int(base[1])
        for k in range(height):
            y = y1 - k
            for d in range(width):
                tone = POLE[1] if d == 0 else (POLE[2] if d == width - 1 else POLE[0])
                if 0 <= y < G:
                    f[y, x0 - width // 2 + d] = tone
            # Bamboo nodes.
            if k % 9 == 4 and 0 <= y < G:
                f[y, x0 - width // 2:x0 - width // 2 + width] = POLE[2]

    def rope_with_cans(f, a, b, tug, T, size=1):
        """The rope sags at rest. A pull pulls it tight, and the cans jump."""
        pts = line(f, a, b, sag=6 * (1 - tug) + 1, T=T, wiggle=tug * 0.6)
        for u in (0.3, 0.5, 0.7):
            x, y = pts[int(u * (len(pts) - 1))]
            jump = -int(round(tug * 2 * abs(np.sin(T * 26 + u * 9))))
            for dy in range(3 * size):
                for dx in range(2 * size):
                    yy, xx = int(y) + 1 + dy + jump, int(x) + dx - size
                    if 0 <= yy < G and 0 <= xx < G:
                        f[yy, xx] = CAN[0] if dx == 0 else CAN[1] if dy == 0 else CAN[2] if dx == 2 * size - 1 else CAN[0]

    def tug_of(T, start):
        """The pull lands on every second beat from start. It is strongest just after the beat."""
        if T < start:
            return 0.0
        s = since_beat(T)
        past = beats[beats <= T]
        k = len(past)
        if k % 2:
            return 0.0
        return max(0.0, 1 - s / (BEAT * 0.9))

    # The flock: each bird follows a slow loop with its own phase. A surge spreads the loop.
    FLOCK = [(rng.uniform(0, 2 * np.pi), rng.uniform(0.6, 1.0), rng.uniform(-1, 1)) for _ in range(28)]

    def flock(f, T, cx, cy, rx, ry, n, width, spread=1.0, speed=0.9):
        for k in range(n):
            ph, r, wob = FLOCK[k]
            a = T * speed + ph
            x = cx + np.cos(a) * rx * r * spread + np.sin(T * 2.1 + k) * 4
            y = cy + np.sin(2 * a) * ry * r * spread * 0.6 + wob * 6
            flying(f, x, y, width, T, k * 0.7, np.cos(a + np.pi / 2) < 0)

    built = {}

    def scene(name, builder):
        if name not in built:
            built[name] = builder()
        return built[name]

    def has(group, *names):
        return all(n in group for n in names)

    # Intro: dawn on the green field. The scarecrow stands on his pole. The farmer waits at his hut.
    def build_intro():
        pl = P["sawah"]
        stand, idle = H.get("w_stand"), F.get("t_idle")
        guard("sawah", [FARMER])

        def draw(T):
            f = pl["img"].copy()
            pole(f, (MOUND[0], MOUND[1] + 2), 30, 2)
            if idle:
                person(f, idle, idle.index(T, "pingpong"), *FARMER, pl)
            if stand:
                person(f, stand, breathing(stand, T), MOUND[0], MOUND[1], pl, lift=LIFT_WIDE, sh=(5, 2))
            hand = (FARMER[0] + 4, FARMER[1] - 12)
            rope_with_cans(f, hand, (MOUND[0], MOUND[1] - 20), 0, T)
            # Three far birds cross the dawn.
            for k in range(3):
                x = (T * 22 + k * 30) % (G + 60) - 30
                flying(f, x, 120 + k * 7 + np.sin(T + k) * 3, 4, T, k, False)
            return f

        return draw

    # Close: she lands on his hat, visits his straw hand, steals one straw and comes back.
    def build_close():
        pl = P["cedhak"]
        stand = H.get("c_stand")
        WIDTH = 18
        T_LAND, T_HOP, T_PECK, T_OFF, T_BACK = 7.6, 12.6, 18.4, 21.0, 24.4

        def spots(T):
            i = breathing(stand, T - T_CLOSE)
            x, y = MOUND_CLOSE[0], MOUND_CLOSE[1] - LIFT_CLOSE
            top = TOPS["c_stand"][i]
            hat = (x - stand.anchor[0] + stand.anchor[0] + 1, y - stand.anchor[1] + top + 1)
            hand = stand.point(i, "right", x, y)
            return i, hat, (hand[0] - 1, hand[1] - 2)

        def draw(T):
            f = pl["img"].copy()
            pole(f, (MOUND_CLOSE[0], MOUND_CLOSE[1] + 3), LIFT_CLOSE + 44, 5)
            i, hat, hand = spots(T)
            person(f, stand, i, MOUND_CLOSE[0], MOUND_CLOSE[1], pl, lift=LIFT_CLOSE, sh=(9, 3))
            # Her path: in from the right, onto the hat, onto the hand, away with a straw, and back.
            if T < T_LAND:
                u = ease((T - T_CLOSE) / (T_LAND - T_CLOSE))
                x = 380 + (hat[0] - 380) * u
                y = 90 + (hat[1] - 90) * u - np.sin(np.pi * u) * 30
                flying(f, x, y, WIDTH, T, 0, True)
            elif T < T_HOP:
                perched(f, *hat, WIDTH, T, 0, flip=True)
            elif T < T_HOP + 0.6:
                u = ease((T - T_HOP) / 0.6)
                x = hat[0] + (hand[0] - hat[0]) * u
                y = hat[1] + (hand[1] - hat[1]) * u - np.sin(np.pi * u) * 10
                bird(f, x, y, WIDTH, 7, True)
            elif T < T_OFF:
                # On the hand. From the peck line she tugs at the straw.
                if T >= T_PECK:
                    pull = min((T - T_PECK) / 1.5, 1)
                    line(f, (hand[0] - 5, hand[1] + 1), (hand[0] - 5 - 2 * pull, hand[1] + 1 + 5 * pull), colour=STRAW)
                    bird(f, *hand, WIDTH, 6 if int(T * 3) % 2 else 4, True)
                else:
                    perched(f, *hand, WIDTH, T, 1.3, flip=True)
            elif T < T_BACK:
                # A wide loop over the field, with the straw in her beak.
                u = (T - T_OFF) / (T_BACK - T_OFF)
                a = u * 2 * np.pi
                x = 180 + np.sin(a) * 120 + (hat[0] - 180) * ease(u * 1.4 - 0.4)
                y = 110 - np.sin(a * 0.5) * 40 + (hat[1] - 110) * ease(u * 1.6 - 0.6)
                flip = np.cos(a) > 0
                flying(f, x, y, WIDTH, T, 0, not flip)
                line(f, (x + (6 if not flip else -6), y + 1), (x + (11 if not flip else -11), y + 3), colour=STRAW)
            else:
                perched(f, *hat, WIDTH, T, 2.1, flip=True)
                line(f, (hat[0] - 7, hat[1] - 2), (hat[0] - 12, hat[1] - 1), colour=STRAW)
            return f

        return draw

    # Pre-chorus: the farmer pulls the rope. The cans rattle, his arms jerk, and she flies.
    def build_pull():
        pl = P["sawah"]
        stand, jerk, pull, idle = H.get("w_stand"), H.get("w_dance"), F.get("t_pull"), F.get("t_idle")
        T_TUG, T_FLY = beat_at(29.36), 32.3
        rate = dance_rate(jerk) if jerk else 1.0

        def draw(T):
            f = pl["img"].copy()
            pole(f, (MOUND[0], MOUND[1] + 2), 30, 2)
            tug = tug_of(T, T_TUG)
            if T < T_TUG:
                spr, i = idle, idle.index(T, "pingpong")
            else:
                spr, i = pull, pull.index((T - T_TUG) * 1.0, "loop")
            person(f, spr, i, *FARMER, pl)
            hand = spr.point(i, "right", *FARMER)
            if T < T_TUG:
                s, j = stand, breathing(stand, T)
            else:
                s, j = jerk, jerk.index((T - T_TUG) * rate, "pingpong")
            person(f, s, j, MOUND[0], MOUND[1], pl, lift=LIFT_WIDE)
            rope_with_cans(f, hand, (MOUND[0], MOUND[1] - 20), tug, T)
            top = TOPS[s.name.split("/")[1]][j]
            hat = (MOUND[0] + 1, MOUND[1] - LIFT_WIDE - s.anchor[1] + top + 1)
            if T < T_FLY:
                perched(f, *hat, 4, T, 0, flip=True)
            else:
                u = (T - T_FLY) / 2.5
                flying(f, hat[0] + u * 150, hat[1] - u * 70 - np.sin(u * 3) * 6, 4, T, 0, False)
            return f

        return draw

    # Chorus on gold rice: he dances on his pole. The flock wheels, and every wave of his arms sends it off.
    def build_gold():
        pl = P["sawah_kuning"]
        jerk, pull = H["w_dance"], F["t_pull"]
        wife = M.get("m_dance")
        rate = dance_rate(jerk)
        T_COME, T_GO = 47.7, 50.2

        def draw(T):
            f = pl["img"].copy()
            pole(f, (MOUND[0], MOUND[1] + 2), 30, 2)
            tug = tug_of(T, T_GOLD)
            i = pull.index((T - T_GOLD), "loop")
            person(f, pull, i, *FARMER, pl)
            hand = pull.point(i, "right", *FARMER)
            if wife:
                wx, wy = FARMER[0] - 22, FARMER[1] + 9
                person(f, wife, wife.index((T - T_GOLD) * dance_rate(wife), "pingpong"), wx, wy, pl)
            j = jerk.index((T - T_GOLD) * rate, "pingpong")
            person(f, jerk, j, MOUND[0], MOUND[1], pl, lift=LIFT_WIDE)
            rope_with_cans(f, hand, (MOUND[0], MOUND[1] - 20), tug, T)
            # The flock spreads on each pull and gathers between pulls.
            spread = 1.0 + tug * 0.5
            flock(f, T, 200, 120, 120, 40, 22, 4, spread)
            # One bird comes close on "kowe teka", then the dance sends her away.
            if T_COME - 1.5 < T < T_GO + 2.0:
                if T < T_GO:
                    u = ease((T - (T_COME - 1.5)) / 1.5)
                    x = 300 + (MOUND[0] + 12 - 300) * u
                    y = 110 + (MOUND[1] - 44 - 110) * u
                else:
                    u = (T - T_GO) / 2.0
                    x = MOUND[0] + 12 + u * 160
                    y = MOUND[1] - 44 - u * 90
                flying(f, x, y, 5, T, 0.5, T < T_GO)
            return f

        return draw

    # Bridge: harvest. The farmer walks to the pole and takes him down. He falls into the stubble.
    def build_panen():
        pl = P["panen"]
        walk, walk_back, reach, idle = F["t_walk_se"], F["t_walk_nw"], F["t_reach"], F["t_idle"]
        reap = M["m_reap"]
        stand, fall, lie = H["w_stand"], H["w_fall"], H["w_lie"]
        T_WALK = 54.4
        T_AT = T_WALK + walk_time(walk, FARMER, NEAR_POLE)
        T_REACH = 60.4
        T_FALL = beat_at(61.7)
        T_BACK = T_REACH + reach.n / reach.fps + 0.2
        T_HOME = T_BACK + walk_time(walk_back, NEAR_POLE, FARMER)
        guard("panen", [FARMER, NEAR_POLE, WIFE_REAP])

        def draw(T):
            f = pl["img"].copy()
            pole(f, (MOUND[0], MOUND[1] + 2), 30, 2)
            people = []
            people.append((WIFE_REAP[1], reap, reap.index((T - T_PANEN) * 0.9, "pingpong"), *WIFE_REAP, 0))
            if T < T_WALK:
                people.append((FARMER[1], idle, idle.index(T, "pingpong"), *FARMER, 0))
            elif T < T_REACH:
                i, x, y, done = walk_between(walk, FARMER, NEAR_POLE, T - T_WALK)
                if done:
                    people.append((NEAR_POLE[1], idle, idle.index(T, "pingpong"), *NEAR_POLE, 0))
                else:
                    people.append((y, walk, i, x, y, 0))
            elif T < T_BACK:
                people.append((NEAR_POLE[1], reach, reach.index(T - T_REACH, "hold"), *NEAR_POLE, 0))
            elif T < T_HOME:
                i, x, y, _ = walk_between(walk_back, NEAR_POLE, FARMER, T - T_BACK)
                people.append((y, walk_back, i, x, y, 0))
            else:
                people.append((FARMER[1], idle, idle.index(T, "pingpong"), *FARMER, 0))
            # The scarecrow: on the pole, then the fall, then rest on the earth.
            if T < T_FALL:
                people.append((MOUND[1], stand, breathing(stand, T), MOUND[0], MOUND[1], LIFT_WIDE))
            elif T < T_FALL + fall.n / fall.fps:
                k = fall.index(T - T_FALL, "hold")
                # He tips back off the pole. The height drops over the whole fall, so he never stands on the ground first.
                u = ease((T - T_FALL) / (fall.n / fall.fps))
                x = MOUND[0] + (LIE_WIDE[0] - MOUND[0]) * u
                y = MOUND[1] + (LIE_WIDE[1] - MOUND[1]) * u
                people.append((y, fall, k, x, y, LIFT_WIDE * (1 - u)))
            else:
                people.append((LIE_WIDE[1], lie, breathing(lie, T - T_FALL, 0), *LIE_WIDE, 0))
            for _, spr, i, x, y, lift in sorted(people, key=lambda p: p[0]):
                person(f, spr, i, x, y, pl, lift=lift)
            return f

        return draw

    # Final chorus, close: the pole is gone with the old rice. He lies still. She lands on his open hand. Then a thousand birds come.
    def build_rest():
        pl = P["cedhak_tandur"]
        lie = H["c_lie"]
        WIDTH = 17
        T_SHE, T_FLOCK = 73.26, 78.4
        # The hand rises over frames 70 to 100, so it is open before she lands.
        OPEN = 100

        def pose(T):
            return breathing(lie, T - T_REST, OPEN)

        def draw(T):
            f = pl["img"].copy()
            i = pose(T)
            person(f, lie, i, *LIE_CLOSE, pl, sh=None)
            hand = lie.point(i, "right", *LIE_CLOSE)
            hand = (hand[0], hand[1] - 2)
            if T < T_SHE:
                u = ease((T - (T_SHE - 2.4)) / 2.4)
                if T > T_SHE - 2.4:
                    x = -20 + (hand[0] + 20) * u
                    y = 70 + (hand[1] - 70) * u - np.sin(np.pi * u) * 20
                    flying(f, x, y, WIDTH, T, 0, False)
            else:
                perched(f, *hand, WIDTH, T, 0.4)
            # The flock arrives one bird at a time and settles on him and on the mound.
            ground = ((-34, 4), (32, 6), (-18, 14), (22, 15), (0, 18), (-40, 10), (40, 12), (-62, 31), (60, 30), (-80, 40), (78, 39), (-50, -25), (52, -26), (-96, 48), (96, 48), (-70, -35), (70, -35))
            spots = perches(lie, i, *LIE_CLOSE, 9) + [(MOUND_CLOSE[0] + dx, MOUND_CLOSE[1] + dy) for dx, dy in ground]
            for k, (sx, sy) in enumerate(spots):
                arrive = T_FLOCK + k * 0.24
                if T < arrive - 1.6:
                    continue
                flip = k % 2 == 0
                if T < arrive:
                    u = ease((T - (arrive - 1.6)) / 1.6)
                    x0 = 380 if flip else -20
                    flying(f, x0 + (sx - x0) * u, 40 + (sy - 40) * u - np.sin(np.pi * u) * 15, WIDTH - 2, T, k, flip)
                else:
                    perched(f, sx, sy, WIDTH - 2, T, k * 0.9, flip)
            return f

        return draw

    # Outro: new rice. The farmer and his wife plant. He lies on the mound under his birds.
    def build_outro():
        pl = P["tandur"]
        lie, plant, plant2 = H["w_lie"], F["t_plant"], M["m_plant"]
        guard("tandur", [FARMER, WIFE_REAP])
        perch = None

        def draw(T):
            nonlocal perch
            f = pl["img"].copy()
            people = [(WIFE_REAP[1], plant2, plant2.index(T - T_OUTRO, "pingpong"), *WIFE_REAP),
                      (FARMER[1] + 14, plant, plant.index(T - T_OUTRO + 0.7, "pingpong"), FARMER[0] + 10, FARMER[1] + 14),
                      (LIE_WIDE[1], lie, breathing(lie, T - T_OUTRO), *LIE_WIDE)]
            for _, spr, i, x, y in sorted(people, key=lambda p: p[0]):
                person(f, spr, i, x, y, pl)
            i = breathing(lie, T - T_OUTRO)
            for k, (sx, sy) in enumerate(perches(lie, i, *LIE_WIDE, 6)):
                perched(f, sx, sy, 4, T, k)
            # The flock lifts once and settles again.
            if 92.0 < T < 96.0:
                flock(f, T, 190, 170, 60, 20, 8, 4, 1.0, 1.4)
            return f

        return draw

    font_big = ImageFont.truetype(font_path("msgothic.ttc"), 26)
    font_small = ImageFont.truetype(font_path("simsun.ttc"), 12)
    title = Image.new("RGB", (232, 54), INK)
    d = ImageDraw.Draw(title)
    d.fontmode = "1"
    d.text((116 - font_big.getlength(brief["title"]) / 2, 6), brief["title"], font=font_big, fill=tuple(int(v) for v in paper))
    sub = brief["title_zh"]
    d.text((116 - font_small.getlength(sub) / 2, 37), sub, font=font_small, fill=(214, 208, 196))
    title = np.asarray(title)
    state = {"last": None, "scene": None, "at": 0.0}
    SCENES = [(T_CLOSE, "intro", build_intro), (T_PULL, "close", build_close), (T_GOLD, "pull", build_pull),
              (T_PANEN, "gold", build_gold), (T_REST, "panen", build_panen), (T_OUTRO, "rest", build_rest), (1e9, "outro", build_outro)]

    def draw(i, t, T):
        name, builder = next((n, b) for end, n, b in SCENES if T < end)
        f = scene(name, builder)(T)
        if name != state["scene"]:
            state["scene"], state["at"] = name, T
        u = (T - state["at"]) / 0.17
        if u < 1 and state["last"] is not None:
            hide = bayer > u
            f[hide] = state["last"][hide]
        if 0.8 <= T < 5.8:
            h, w, _ = title.shape
            x0 = (G - w) // 2
            keep = bayer[18:18 + h, x0:x0 + w] < min(1, (T - 0.8) / 0.3, (5.8 - T) / 0.3)
            f[18:18 + h, x0:x0 + w][keep] = title[keep]
        caps.draw(f, T)
        if T < 0.6:
            f[bayer > T / 0.6] = paper
        left = ctx["end"] - T
        if left < 1.2:
            f[bayer > left / 1.2] = paper
        state["last"] = np.array(f, np.uint8)
        return f.astype(np.uint8)

    return draw
