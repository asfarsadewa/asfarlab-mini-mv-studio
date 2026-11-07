# Kirim Salam: Jakarta, 1985. Three shy friends send a radio dedication every Saturday night to the sweet girl
# in their alley. The DJ with the soft voice reads it out, and we only ever see her from behind.
# In the final chorus she turns around: she was the girl all along. The night ends in a disco at the station.
# The plate never moves. Footprints guard every path. Every walker faces the way that it moves.
import json
import numpy as np
from scipy import ndimage
from PIL import Image, ImageDraw, ImageFont
from pixkit import INK, Captions, Occlusion, Sprite, bayer_field, contact_shadow
from studio_paths import font_path

BULBS = [(255, 92, 92), (255, 214, 90), (110, 230, 140), (120, 180, 255)]
SPARK = (255, 250, 236)
ON_AIR = (255, 70, 60)

TRIO = ["hero", "boy_b", "boy_c"]
WATCH = [(170, 272), (206, 278), (242, 272)]
QUEUE = [(130, 276), (164, 280), (198, 282)]
ALLEY_TRIO = [(164, 264), (200, 270), (236, 264)]
ALLEY_CROWD = [("folk_j", "n_da", 150, 236), ("folk_c", "n_band", 186, 230), ("folk_a", "n_cheer", 222, 232), ("folk_b", "n_db", 250, 240),
               ("folk_c", "n_disco", 140, 248), ("folk_j", "n_band", 262, 252)]
ROOM_TRIO = [(116, 276), (180, 282), (244, 278)]
DJ = (185, 274)
FLOOR = [("hero", "p_band", 162, 236), ("girl", "p_disco", 186, 232), ("boy_b", "p_band", 210, 236), ("boy_c", "p_disco", 236, 242),
         ("folk_j", "n_da", 146, 214), ("folk_c", "n_disco", 176, 210), ("folk_a", "n_band", 214, 212), ("folk_b", "n_db", 240, 220),
         ("folk_j", "n_cheer", 132, 250), ("folk_c", "n_db", 200, 254), ("folk_a", "n_da", 226, 258)]


def make(ctx):
    G, fps, brief, A, root = ctx["grid"], ctx["fps"], ctx["brief"], ctx["a"], ctx["root"]
    paper = np.array(brief["paper"], np.uint8)
    beats = np.array(A["beats"])
    rng = np.random.default_rng(1985)
    bayer = bayer_field(G)
    Y, X = np.mgrid[:G, :G]
    caps = Captions(brief["lines"], paper, top_font=(font_path("msgothic.ttc"), 16), low_font=(font_path("simsun.ttc"), 12))
    shapes = json.loads((root / "occluders.json").read_text(encoding="utf-8"))

    def beat(t):
        return float(beats[np.argmin(np.abs(beats - t))])

    def beat_index(T):
        return int(np.searchsorted(beats, T))

    T_ROOM, T_PHONE, T_STUDIO, T_HIT, T_ROOM2, T_STUDIO2, T_ROOM3, T_GO, T_LOBBY, T_FINAL, T_TURN, T_PARTY = (
        beat(8.3), beat(15.8), beat(24.3), brief["hit"], beat(47.7), beat(56.0), beat(63.7), beat(67.2), beat(74.9), beat(78.5), beat(83.3), beat(87.0))

    def plate(name):
        d = np.asarray(Image.open(root / f"plates/{name}-360.png").convert("RGB")).copy()
        is_paper = (np.abs(d.astype(int) - paper.astype(int)).sum(axis=2) < 24) | (d.astype(int).sum(axis=2) > 720)
        d[is_paper] = paper
        return {"name": name, "day": d, "paper": is_paper, "occ": Occlusion(root, name)}

    P = {n: plate(n) for n in ("kamar", "gang", "studio", "pesta")}
    sprites = {}

    def S(folder, name):
        if (folder, name) not in sprites:
            sprites[(folder, name)] = Sprite(root, name, folder)
        return sprites[(folder, name)]

    def clearance(name, x, y):
        solids = [o["footprint"] for o in shapes.get(name, []) if "footprint" in o]
        return min((np.hypot((x - cx) / rx, (y - cy) / ry) for cx, cy, rx, ry in solids), default=9.0)

    def guard(name, pts):
        low = float(min(clearance(name, x, y) for x, y in pts))
        print(f"Footprint clearance on {name}, with 1.0 at the object edge:", round(low, 2), flush=True)
        if low < 1.0:
            raise SystemExit(f"A person stands inside a solid object on {name}: {low:.2f}")

    guard("gang", WATCH + QUEUE + ALLEY_TRIO + [(x, y) for _, _, x, y in ALLEY_CROWD])
    guard("kamar", ROOM_TRIO)
    guard("studio", [DJ])
    guard("pesta", [(x, y) for _, _, x, y in FLOOR])
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
        heading(spr, b[0] - a[0], b[1] - a[1])
        u = float(np.clip((T - t0) / (t1 - t0), 0, 1))
        p0, p1 = spr.path(0), spr.path(spr.n - 1)
        stride = max(np.hypot(p1[0] - p0[0], p1[1] - p0[1]), 1.0)
        walked = u * np.hypot(b[0] - a[0], b[1] - a[1])
        return int(walked / stride * (spr.n - 1)) % spr.n, a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u

    def person(f, spr, i, x, y, pl, grade=None, sh=(5, 2), reveal=1.0, light=None):
        contact_shadow(f, x, y, sh[0], sh[1], 0.8, bayer, ~pl["paper"], 2, occ=pl["occ"])
        spr.draw(f, i, x, y, occ=pl["occ"], grade=grade, bayer=bayer, reveal=reveal, light=light)

    def dance(spr, T, offset):
        """Dancers keep the clip at its own speed. Each one starts on a different beat."""
        return spr.index(T + offset * 0.5, "loop")

    # The alley bulbs change colour on each beat.
    g = P["gang"]["day"].astype(int)
    bright = (g.max(axis=2) > 200) & (g.max(axis=2) - g.min(axis=2) > 90) & (Y < 200) & ~P["gang"]["paper"]
    # Only small isolated lights are bulbs. A lit window is a large patch, so it keeps its own colour.
    bright &= ndimage.uniform_filter(bright.astype(float), size=7) < 0.22
    # The strings hang over the middle of the alley. Roof tiles outside that band keep still.
    bright &= (X > 120) & (X < 300) & (Y > 128) & (Y < 205)
    bulb_group = (X // 6 + Y // 5) % 4

    def bulbs(f, T):
        """Each bulb keeps its colour. Two groups take turns to glow on the beat."""
        k = beat_index(T)
        dim = bright & ((bulb_group % 2) == (k % 2))
        glow = bright & ~dim
        f[dim] = (f[dim] * 0.55).astype(np.uint8)
        f[glow] = np.clip(f[glow] * 1.15 + 20, 0, 255).astype(np.uint8)

    def alley(T, people, dim=1.0):
        pl = P["gang"]
        f = pl["day"].copy()
        bulbs(f, T)
        for y, s, i, x, rev in sorted(people, key=lambda p: p[0]):
            person(f, s, i, x, y, pl, reveal=rev)
        return f

    def intro(T):
        # She walks past, and the three of them stand and watch her go.
        people = []
        s = S("girl", "w_walk_r")
        t0, t1 = 0.8, T_ROOM - 0.3
        if t0 <= T < t1:
            i, x, y = walk_between(s, (128, 236), (272, 228), t0, t1, T)
            people.append((y, s, i, x, min(1.0, (T - t0) / 0.6, (t1 - T) / 0.6)))
        for k, (who, (x, y)) in enumerate(zip(TRIO, WATCH)):
            b = S(who, "g_back")
            people.append((y, b, b.index(T + k * 0.7, "pingpong"), x, 1.0))
        return alley(T, people)

    def room(T, clip="r_band"):
        pl = P["kamar"]
        f = pl["day"].copy()
        # The boombox pulses with the bass, and the bulb sways a little.
        v = A["bass"][min(int(T * fps), len(A["bass"]) - 1)]
        box = (X > 230) & (X < 280) & (Y > 196) & (Y < 222) & ~pl["paper"]
        f[box] = np.clip(f[box] * (1 + v * 0.35), 0, 255).astype(np.uint8)
        for k, (who, (x, y)) in enumerate(zip(TRIO, ROOM_TRIO)):
            s = S(who, clip if k != 1 else ("r_disco" if clip == "r_band" else "r_band"))
            person(f, s, dance(s, T, k), x, y, pl, sh=(12, 4))
        return f

    def phone(T):
        people = []
        for k, (who, (x, y)) in enumerate(zip(TRIO, QUEUE)):
            s = S(who, "g_phone" if k == 0 else "g_idle")
            people.append((y, s, s.index(T + k * 0.6, "pingpong"), x, 1.0))
        return alley(T, people)

    def studio(T, turn=False):
        pl = P["studio"]
        f = pl["day"].copy()
        lamp = (np.hypot(X - 186, (Y - 158) * 1.6) < 14) & ~pl["paper"]
        on = 0.75 + 0.25 * (beat_index(T) % 2)
        f[lamp] = np.clip(np.array(ON_AIR) * on, 0, 255).astype(np.uint8)
        if not turn or T < T_TURN:
            s = S("girl", "s_back")
            person(f, s, s.index(T, "pingpong"), *DJ, pl, sh=(12, 4))
        else:
            s = S("girl", "s_front" if T < T_TURN + 1.2 else "s_wave")
            person(f, s, s.index(T - T_TURN, "pingpong"), *DJ, pl, sh=(12, 4))
        return f

    def chorus(T):
        people = []
        for k, (who, (x, y)) in enumerate(zip(TRIO, ALLEY_TRIO)):
            s = S(who, "g_band")
            people.append((y, s, dance(s, T, 0), x, 1.0))
        for k, (who, name, x, y) in enumerate(ALLEY_CROWD):
            s = S(who, name)
            people.append((y, s, dance(s, T, k + 1), x, min(1.0, (T - T_HIT) / 0.5 + 0.3)))
        return alley(T, people)

    def leaving(T):
        # They set off up the alley, side by side, to find the voice.
        people = []
        for k, who in enumerate(TRIO):
            s = S(who, "g_walk_up")
            a = (176 + k * 22, 286)
            b = (186 + k * 14, 196)
            i, x, y = walk_between(s, a, b, T_GO, T_LOBBY - 0.2, T)
            people.append((y, s, i, x, min(1.0, (T_LOBBY - 0.2 - T) / 0.8)))
        return alley(T, people)

    def lobby(T, party=False):
        pl = P["pesta"]
        f = pl["day"].copy()
        if not party:
            # The lights are low as they walk in.
            f[:] = np.where(pl["paper"][..., None], f, (f * 0.55).astype(np.uint8))
            for k, who in enumerate(TRIO):
                s = S(who, "p_walk_up")
                i, x, y = walk_between(s, (168 + k * 22, 290), (172 + k * 20, 248), T_LOBBY, T_FINAL - 0.2, T)
                person(f, s, i, x, y, pl, grade=(0.7, 0.7, 0.8))
            return f
        # The mirror ball throws sparkles that move with the beat.
        k = beat_index(T)
        sr = np.random.default_rng(k)
        for _ in range(70):
            x, y = int(sr.uniform(40, 330)), int(sr.uniform(120, 290))
            if not pl["paper"][y, x]:
                f[y, x] = SPARK
        for n, (who, name, x, y) in enumerate(sorted(FLOOR, key=lambda p: p[3])):
            s = S(who, name)
            person(f, s, dance(s, T, n), x, y, pl)
        return f

    title = Image.new("RGB", (200, 50), INK)
    d = ImageDraw.Draw(title)
    d.fontmode = "1"
    big, small = ImageFont.truetype(font_path("msgothic.ttc"), 22), ImageFont.truetype(font_path("simsun.ttc"), 14)
    d.text((100 - big.getlength(brief["title"]) / 2, 5), brief["title"], font=big, fill=tuple(int(v) for v in paper))
    d.text((100 - small.getlength(brief["title_zh"]) / 2, 31), brief["title_zh"], font=small, fill=(214, 208, 196))
    title = np.asarray(title)
    state = {"last": None, "scene": None, "at": 0.0}

    def scene_at(T):
        for end, name, fn in ((T_ROOM, "intro", intro), (T_PHONE, "room", room), (T_STUDIO, "phone", phone), (T_HIT, "studio", studio),
                              (T_ROOM2, "chorus", chorus), (T_STUDIO2, "room2", lambda t: room(t, "r_disco")), (T_ROOM3, "studio2", studio),
                              (T_GO, "room3", room), (T_LOBBY, "leave", leaving), (T_FINAL, "lobby", lobby), (T_PARTY, "turn", lambda t: studio(t, True))):
            if T < end:
                return name, fn
        return "party", lambda t: lobby(t, True)

    def draw(i, t, T):
        name, builder = scene_at(T)
        f = builder(T)
        if name != state["scene"]:
            state["scene"], state["at"] = name, T
        u = (T - state["at"]) / 0.2
        if u < 1 and state["last"] is not None:
            hide = bayer > u
            f[hide] = state["last"][hide]
        if 1.0 <= T < 7.5:
            h, w, _ = title.shape
            x0 = (G - w) // 2
            keep = bayer[6:6 + h, x0:x0 + w] < min(1, (T - 1.0) / 0.3, (7.5 - T) / 0.3)
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
