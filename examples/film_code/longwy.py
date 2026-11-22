# Le dernier bal: Longwy, Lorraine, 1979. The steel company closes the blast furnaces of the valley one by one.
# Marcel walks out of the works gate after his last shift. At home Josette puts on the dress from the 1949 dance.
# In the canteen the workers hold one last dance while their own radio sings in the street. Marcel and Josette dance
# close while the furnace glows red through the window, until the glow dies. At dawn they walk home past the cold furnace.
# The plates never move. A mid shot is a locked camera on part of a plate, scaled with nearest pixels.
# The typewriter prologue before the song comes from the brief. render.py draws it.
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pixkit import INK, Captions, Occlusion, Sprite, bayer_field, contact_shadow, title_mask
from studio_paths import font_path

# Stage spots in plate pixels.
GATE, HOUSES = (150, 263), (296, 277)
COLD_FROM, COLD_TO = ((150, 263), (290, 276)), ((141, 266), (281, 279))
MIRROR = (205, 268)
MARCEL, JOSETTE = (164, 266), (174, 266)
COUPLE_A = [("man_a", (124, 252)), ("woman_a", (134, 252))]
COUPLE_B = [("man_b", (213, 253)), ("woman_b", (223, 253))]
RADIO_MAN, CHEER_MAN = (84, 262), (98, 268)
WINDOW = (140, 188, 232, 236)

MID_STREET = (178, 222, 294, 298, 3)
MID_COUPLE = (111, 202, 227, 278, 3)

NIGHT = (0.42, 0.44, 0.68)
DAWN = (0.80, 0.84, 0.98)


class Lyrics(Captions):
    """Three caption rows: the sung French, then Simplified Chinese, then Bahasa Indonesia."""

    def __init__(self, lines, paper):
        self.bars = []
        for line in lines:
            words = [line[key] for key in ("ja", "zh", "id")]
            # A long French line steps the sung row down in size, so the bar fits the frame.
            for sung in (15, 14, 13, 12):
                fonts = [ImageFont.truetype(font_path(name), size) for name, size in
                         [("msgothic.ttc", sung), ("msyh.ttc", 14), ("msgothic.ttc", 12)]]
                width = round(max(font.getlength(s) for font, s in zip(fonts, words))) + 14
                if width <= 356:
                    break
            if width > 356:
                raise ValueError(f"Caption too wide: {words}")
            bar = Image.new("RGB", (width, 54), INK)
            draw = ImageDraw.Draw(bar)
            draw.fontmode = "1"
            for s, font, y, colour in zip(words, fonts, [2, 19, 38], [paper, (239, 219, 174), (220, 215, 208)]):
                draw.text(((width - font.getlength(s)) // 2, y), s, font=font, fill=tuple(int(v) for v in colour))
            self.bars.append((line["from"], line["to"], np.asarray(bar)))


def make(ctx):
    G, fps, brief, A, root = ctx["grid"], ctx["fps"], ctx["brief"], ctx["a"], ctx["root"]
    paper = np.array(brief["paper"], np.uint8)
    beats = np.array(A["beats"])
    bayer = bayer_field(G)
    Y, X = np.mgrid[:G, :G]
    caps = Lyrics(brief["lines"], paper)
    shapes = json.loads((root / "occluders.json").read_text(encoding="utf-8"))

    def beat(t):
        return float(beats[np.argmin(np.abs(beats - t))])

    T_HANDS, T_HOME, T_TWIRL, T_COME = beat(15.2), beat(28.3), beat(33.3), beat(41.1)
    T_HIT, T_MID, T_RADIO, T_CHEER = brief["hit"], beat(50.7), beat(65.0), beat(78.2)
    T_BRIDGE, T_FINAL, T_DIM, T_DAWN = beat(83.0), beat(92.1), beat(101.0), beat(108.5)

    def plate(name):
        d = np.asarray(Image.open(root / f"plates/{name}-360.png").convert("RGB")).copy()
        is_paper = (np.abs(d.astype(int) - paper.astype(int)).sum(axis=2) < 24) | (d.astype(int).sum(axis=2) > 720)
        d[is_paper] = paper
        occ = Occlusion(root, name) if shapes.get(name) else None
        return {"name": name, "day": d, "paper": is_paper, "occ": occ}

    P = {n: plate(n) for n in ["furnace", "furnace_cold", "home", "canteen"]}

    def graded(pl, k):
        # The street goes to night. Warm lamps, lit windows and the furnace glow keep their colour.
        d = pl["day"].astype(np.float32)
        out = d * np.array(k, np.float32)
        warm = (d[..., 0] > 170) & (d[..., 0] - d[..., 2] > 70)
        out[warm] = d[warm]
        out[pl["paper"]] = paper
        return np.clip(out, 0, 255).astype(np.uint8)

    STREET = graded(P["furnace"], NIGHT)
    COLD = graded(P["furnace_cold"], DAWN)
    # The furnace glow in the canteen window: its warm pixels, which pulse and then die.
    wx0, wy0, wx1, wy1 = WINDOW
    hall = P["canteen"]["day"].astype(np.float32)
    in_window = np.zeros((G, G), bool)
    in_window[wy0:wy1, wx0:wx1] = True
    glow = in_window & (hall[..., 0] > 150) & (hall[..., 0] - hall[..., 2] > 50)
    cold_glass = np.array((70, 74, 98), np.float32)

    def canteen_plate(T):
        f = hall.copy()
        pulse = 1.0 + 0.12 * np.sin(T * 2.1) + 0.05 * np.sin(T * 5.3)
        if T >= T_DIM:
            # The furnace goes out: the window glow cools to dark glass over the last chorus.
            u = min((T - T_DIM) / (T_DAWN - T_DIM - 0.5), 1.0)
            f[glow] = f[glow] * (1 - u) * pulse + cold_glass * u
        else:
            f[glow] = f[glow] * pulse
        return np.clip(f, 0, 255).astype(np.uint8)

    sprites = {}

    def S(folder, name):
        if (folder, name) not in sprites:
            sprites[(folder, name)] = Sprite(root, name, folder)
        return sprites[(folder, name)]

    def draw_all(f, people, pl):
        """people: (y, sprite, frame, x, reveal). Back to front."""
        for y, s, i, x, rev in sorted(people, key=lambda p: p[0]):
            if rev <= 0:
                continue
            ppu = s.meta["ppu"]
            contact_shadow(f, x, y, max(2, ppu // 3), max(1, ppu // 8), 0.8, bayer, ~pl["paper"], 2, occ=pl["occ"])
            s.draw(f, i, x, y, occ=pl["occ"], bayer=bayer, reveal=rev)

    def loop(spr, T, t0, lag=0.0):
        return int(max(T - t0 + lag, 0) * spr.fps) % spr.n

    def stand(folder, clip, spot, T, t0, lag=0.0, rev=1.0):
        s = S(folder, clip)
        return (spot[1], s, loop(s, T, t0, lag), spot[0], rev)

    def walk(folder, clip, a, b, t0, t1, T, fade_in=0.0, fade_out=0.0):
        u = float(np.clip((T - t0) / (t1 - t0), 0, 1))
        spr = S(folder, clip)
        p0, p1 = spr.path(0), spr.path(spr.n - 1)
        stride = max(np.hypot(p1[0] - p0[0], p1[1] - p0[1]), 1.0)
        d = u * np.hypot(b[0] - a[0], b[1] - a[1])
        rev = 1.0
        if fade_in:
            rev = min(rev, (T - t0) / fade_in)
        if fade_out:
            rev = min(rev, (t1 - T) / fade_out)
        x, y = a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u
        return (y, spr, int(d / stride * (spr.n - 1)) % spr.n, x, float(np.clip(rev, 0, 1)))

    def reframe(f, box):
        x0, y0, x1, y1, k = box
        crop = f[y0:y1, x0:x1].repeat(k, axis=0).repeat(k, axis=1)
        h, w = crop.shape[:2]
        out = np.empty_like(f)
        out[:] = paper
        ox, oy = (G - w) // 2, max(40, (290 - h) // 2)
        out[oy - 2:oy + h + 2, ox - 2:ox + w + 2] = (58, 48, 44)
        out[oy:oy + h, ox:ox + w] = crop
        return out

    # --- Scene 1: the works at night. Marcel walks out of the gate after his last shift. ---
    def street(T):
        pl = P["furnace"]
        f = STREET.copy()
        draw_all(f, [walk("marcel", "f_walk", GATE, HOUSES, 1.0, T_HOME - 0.3, T, fade_in=0.5, fade_out=0.5)], pl)
        return reframe(f, MID_STREET) if T_HANDS <= T < beat(19.2) else f

    # --- Scene 2: the kitchen. Josette puts on the dress from the 1949 dance and turns in front of the mirror. ---
    def home(T):
        pl = P["home"]
        f = pl["day"].copy()
        if T < T_TWIRL:
            p = stand("josette", "h_idle", MIRROR, T, T_HOME)
        elif T < T_COME:
            p = stand("josette", "h_twirl", MIRROR, T, T_TWIRL)
        else:
            p = stand("josette", "h_idle", MIRROR, T, T_COME)
        draw_all(f, [p], pl)
        return f

    # --- Scenes 3 to 5: the canteen dance. The radio verse, the bridge and the dying glow. ---
    def canteen(T):
        pl = P["canteen"]
        f = canteen_plate(T)
        people = [stand("marcel", "c_hug", MARCEL, T, T_HIT), stand("josette", "c_hug", JOSETTE, T, T_HIT, 0.15)]
        radio_verse = T_RADIO <= T < T_BRIDGE
        for k, (who, spot) in enumerate(COUPLE_A + COUPLE_B):
            if radio_verse and (who == "man_a" or (who == "man_b" and T >= T_CHEER)):
                continue
            people.append(stand(who, "c_dance", spot, T, T_HIT, 0.35 * k))
        if radio_verse:
            # One man leaves the floor to listen at the radio. On Cœur d'acier another joins him and raises his fists.
            people.append(stand("man_a", "c_idle", RADIO_MAN, T, T_RADIO))
            if T >= T_CHEER:
                people.append(stand("man_b", "c_cheer", CHEER_MAN, T, T_CHEER))
        draw_all(f, people, pl)
        mid = (T_MID <= T < beat(55.2)) or (T_BRIDGE <= T < T_FINAL)
        return reframe(f, MID_COUPLE) if mid else f

    # --- Scene 6: dawn. The furnace is cold, and they walk home together. ---
    def dawn(T):
        pl = P["furnace_cold"]
        f = COLD.copy()
        people = [walk("marcel", "f_walk", *COLD_FROM, T_DAWN, ctx["end"] - 0.3, T, fade_in=0.4),
                  walk("josette", "f_walk", *COLD_TO, T_DAWN, ctx["end"] - 0.3, T, fade_in=0.4)]
        draw_all(f, people, pl)
        return f

    # The furnace tower fills the top left, so the title card sits at the top right.
    title = title_mask(brief, G, x=226)
    state = {"last": None, "scene": None, "at": 0.0}
    SCENES = [(T_HOME, "street", street), (T_HIT, "home", home), (T_DAWN, "canteen", canteen)]

    def scene_at(T):
        for end, name, fn in SCENES:
            if T < end:
                return name, fn
        return "dawn", dawn

    def draw(i, t, T):
        name, builder = scene_at(T)
        f = builder(T)
        mid = (T_HANDS <= T < beat(19.2)) or (T_MID <= T < beat(55.2)) or (T_BRIDGE <= T < T_FINAL)
        key = (name, mid)
        if key != state["scene"]:
            state["scene"], state["at"] = key, T
        u = (T - state["at"]) / 0.2
        if u < 1 and state["last"] is not None:
            hide = bayer > u
            f[hide] = state["last"][hide]
        if 1.0 <= T < 7.2:
            keep = title & (bayer < min(1, (T - 1.0) / 0.3, (7.2 - T) / 0.3))
            f[keep] = INK
        caps.draw(f, T)
        if T < 0.6:
            f[bayer > T / 0.6] = paper
        left = ctx["end"] - T
        if left < 1.2:
            f[bayer > left / 1.2] = paper
        state["last"] = np.array(f, np.uint8)
        return f.astype(np.uint8)

    return draw
