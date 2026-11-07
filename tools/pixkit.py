# Shared drawing for pixel films: Bayer helpers, depth occlusion, baked sprites, fire and captions.
# Everything draws on a whole-pixel grid. Soft changes use Bayer thresholds, so pixels stay crisp.
import json
from pathlib import Path
import numpy as np
from studio_paths import font_path, studio_handle
from PIL import Image, ImageDraw, ImageFont

BAYER4 = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16.0
FIRE = np.array([(58, 20, 24), (110, 28, 24), (170, 44, 24), (214, 78, 28), (240, 120, 36), (250, 170, 60), (254, 214, 110), (255, 240, 190)], np.uint8)
INK = (24, 22, 28)


def bayer_field(size):
    return np.tile(BAYER4, (size // 4 + 1, size // 4 + 1))[:size, :size]


class Occlusion:
    """A label map and a base row per label. blocks(y) marks every pixel of an object nearer than row y."""

    def __init__(self, root, plate):
        self.labels = np.asarray(Image.open(Path(root) / "occlusion" / f"{plate}.png"))
        bases = json.loads((Path(root) / "occlusion" / f"{plate}.json").read_text())
        self.base = np.zeros(max(int(k) for k in bases) + 2 if bases else 2, np.int32)
        for k, v in bases.items():
            self.base[int(k)] = v

    def blocks(self, feet_y, lift=0):
        mask = self.base[self.labels] > feet_y
        return np.roll(mask, lift, axis=0) if lift else mask


class Sprite:
    # Longest run of one frame, per sprite and spot. render.py reports a long run, because it looks like a frozen person.
    runs = {}

    def __init__(self, root, name, hero="hero"):
        path = Path(root) / hero / "sprites"
        self.name = f"{hero}/{name}"
        self.last = {}
        self.meta = json.loads((path / f"{name}.json").read_text())
        strip = np.asarray(Image.open(path / f"{name}.png").convert("RGBA"))
        self.n, self.size = self.meta["count"], self.meta["size"]
        self.frames = strip.reshape(self.n, self.size, self.size, 4)
        self.anchor = self.meta["anchor"]
        self.fps = self.meta["fps"]

    def index(self, seconds, mode="loop", first=0):
        i = first + int(max(seconds, 0) * self.fps)
        if mode == "loop":
            return i % self.n
        if mode == "pingpong":
            cycle = max(2 * (self.n - 1), 1)
            i %= cycle
            return i if i < self.n else cycle - i
        return min(i, self.n - 1)

    def point(self, i, name, x, y):
        px, py = self.meta["frames"][i][name]
        return x + px - self.anchor[0], y + py - self.anchor[1]

    def path(self, i):
        return self.meta["frames"][i]["path"]

    def draw(self, f, i, x, y, occ=None, lift=0, grade=None, rim=None, reveal=1.0, bayer=None, light=None):
        """Draw frame i with its anchor at x, y. Feet at row y decide which occluders hide this sprite."""
        spot = (round(x / 4), round(y / 4))
        last_i, run = self.last.get(spot, (None, 0))
        run = run + 1 if last_i == i else 1
        self.last[spot] = (i, run)
        key = (self.name, spot)
        Sprite.runs[key] = max(Sprite.runs.get(key, 0), run)
        G = f.shape[0]
        fr = self.frames[i]
        x0, y0 = int(round(x - self.anchor[0])), int(round(y - self.anchor[1]))
        ax0, ay0 = max(x0, 0), max(y0, 0)
        ax1, ay1 = min(x0 + self.size, G), min(y0 + self.size, G)
        if ax0 >= ax1 or ay0 >= ay1:
            return
        part = fr[ay0 - y0:ay1 - y0, ax0 - x0:ax1 - x0]
        solid = part[..., 3] > 0
        rgb = part[..., :3].astype(np.float32)
        if grade is not None:
            rgb = rgb * np.array(grade, np.float32)
        if light is not None:
            cx, cy, radius, warm = light
            yy, xx = np.mgrid[ay0:ay1, ax0:ax1]
            near = np.hypot(xx - cx, yy - cy) + (bayer[ay0:ay1, ax0:ax1] * 8 if bayer is not None else 0) < radius
            rgb[near] = part[..., :3][near] * np.array(warm, np.float32)
        if rim is not None:
            # The hard rim marks the edge that faces the light.
            away = rim["dx"]
            edge = solid & ~np.roll(solid, away, axis=1)
            rgb[edge] = rim["colour"]
        mask = solid
        if reveal < 1 and bayer is not None:
            mask = mask & (bayer[ay0:ay1, ax0:ax1] < reveal)
        if occ is not None:
            mask = mask & ~occ.blocks(y, lift)[ay0:ay1, ax0:ax1]
        f[ay0:ay1, ax0:ax1][mask] = np.clip(rgb[mask], 0, 255).astype(np.uint8)


def contact_shadow(f, x, y, rx, ry, opacity, bayer, ground, offset=2, occ=None, lift=0):
    """Ground the feet: a dark Bayer ellipse, pushed to screen right as in ANU. It falls on drawn ground only."""
    G = f.shape[0]
    cx = x + offset
    x0, x1, y0, y1 = max(int(cx - rx), 0), min(int(cx + rx) + 1, G), max(int(y - ry), 0), min(int(y + ry) + 1, G)
    if x0 >= x1 or y0 >= y1:
        return
    yy, xx = np.mgrid[y0:y1, x0:x1]
    fall = 1 - np.hypot((xx - cx) / rx, (yy - y) / ry)
    mask = (fall > 0) & (bayer[y0:y1, x0:x1] < opacity * np.clip(fall * 2, 0, 1)) & ground[y0:y1, x0:x1]
    if occ is not None:
        # A nearer object hides the shadow as well as the person.
        mask &= ~occ.blocks(y, lift)[y0:y1, x0:x1]
    f[y0:y1, x0:x1][mask] = (f[y0:y1, x0:x1][mask] * 0.5).astype(np.uint8)


def disc(f, cx, cy, r, opacity, colour, bayer):
    G = f.shape[0]
    x0, x1, y0, y1 = max(int(cx - r), 0), min(int(cx + r) + 1, G), max(int(cy - r), 0), min(int(cy + r) + 1, G)
    if x0 >= x1 or y0 >= y1:
        return
    yy, xx = np.mgrid[y0:y1, x0:x1]
    mask = ((xx - cx) ** 2 + (yy - cy) ** 2 <= r * r) & (bayer[y0:y1, x0:x1] < opacity)
    f[y0:y1, x0:x1][mask] = colour


def small_flame(f, x, y, T, size):
    G = f.shape[0]
    for k in range(int(size)):
        wob = int(np.sin(T * 17 + k * 1.7 + x) * (k / 3))
        half = max(int((size - k) / 2.5), 0)
        colour = FIRE[int(np.clip(7 - k * 6 / max(size, 1), 0, 7))]
        row = y - k
        if 0 <= row < G:
            f[row, max(x + wob - half, 0):min(x + wob + half + 1, G)] = colour


class Fire:
    """A cellular flame. The wind pushes it to the right as it climbs."""

    def __init__(self, rng, height=70, width=44):
        self.v = np.zeros((height, width), np.int16)
        self.rng = rng

    def step(self, heat, decay):
        h, w = self.v.shape
        seed = np.zeros(w, np.int16)
        if heat > 0:
            taper = np.clip(1.25 - np.abs(np.arange(w) - w / 2) / 11, 0, 1)
            seed = (heat * taper + self.rng.integers(-3, 4, w)).clip(0, 36).astype(np.int16)
        self.v[-1] = seed
        for y in range(h - 2, -1, -1):
            shift = self.rng.integers(-1, 2, w) - (self.rng.random(w) < 0.35).astype(int)
            self.v[y] = np.maximum(self.v[y + 1][np.clip(np.arange(w) + shift, 0, w - 1)] - self.rng.integers(0, decay + 1, w), 0)

    def draw(self, f, ox, oy, blocked=None):
        h, w = self.v.shape
        ys, xs = np.nonzero(self.v > 2)
        idx = np.minimum(self.v[ys, xs] * len(FIRE) // 30, len(FIRE) - 1)
        py, px = ys + oy - h, xs + ox - w // 2
        ok = (py >= 0) & (py < f.shape[0]) & (px >= 0) & (px < f.shape[1])
        py, px, idx = py[ok], px[ok], idx[ok]
        if blocked is not None:
            keep = ~blocked[py, px]
            py, px, idx = py[keep], px[keep], idx[keep]
        f[py, px] = FIRE[idx]


END_CARD_SECONDS = 3.5
STUDIO_LINE = "Generated in Mini MV Studio"
STUDIO_HANDLE = studio_handle()


def end_card(size, paper, year):
    """The studio credit that closes every film. render.py adds it after the song. A film must not draw its own."""
    im = Image.new("RGB", (size, size), tuple(int(v) for v in paper))
    d = ImageDraw.Draw(im)
    d.fontmode = "1"
    font = ImageFont.truetype(font_path("msgothic.ttc"), 16)
    middle = size // 2
    for text, y in ((STUDIO_LINE, middle - 30), (STUDIO_HANDLE, middle - 8), (str(year), middle + 14)):
        if not text:
            continue
        d.text(((size - font.getlength(text)) // 2, y), text, font=font, fill=INK)
    return np.asarray(im)


class Captions:
    """Two-line lyric bars: the sung language on top, the translation below. Text renders with no anti-aliasing."""

    def __init__(self, lines, paper, top_font=(font_path("msgothic.ttc"), 16), low_font=(font_path("msgothic.ttc"), 12)):
        ja, low = ImageFont.truetype(*top_font), ImageFont.truetype(*low_font)
        ink, text = tuple(INK), tuple(int(v) for v in paper)

        def shape(font, ch):
            mask = font.getmask(ch, mode="1")
            return mask.size, bytes(mask)

        # A font that lacks a glyph draws an empty box. Stop before that reaches a film.
        for font, key in ((ja, "ja"), (low, "id")):
            missing = shape(font, "\U000F0000")
            bad = sorted({c for line in lines for c in line[key] if c != " " and shape(font, c) == missing})
            if bad:
                raise SystemExit(f"The caption font has no glyph for: {''.join(bad)}. Pass a font with these characters.")
        self.bars = []
        for line in lines:
            w = max(int(ja.getlength(line["ja"])), int(low.getlength(line["id"]))) + 14
            if w > 360:
                raise SystemExit(f"This caption is too wide for the frame: {line['id']}")
            # A song in Bahasa Indonesia needs no second line. An empty "id" gives a one-line bar.
            im = Image.new("RGB", (w, 36 if line["id"] else 21), ink)
            d = ImageDraw.Draw(im)
            d.fontmode = "1"
            d.text(((w - ja.getlength(line["ja"])) // 2, 3), line["ja"], font=ja, fill=text)
            if line["id"]:
                d.text(((w - low.getlength(line["id"])) // 2, 21), line["id"], font=low, fill=(214, 208, 196))
            self.bars.append((line["from"], line["to"], np.asarray(im)))

    def draw(self, f, T, bottom=6):
        G = f.shape[0]
        for start, end, bar in self.bars:
            if start <= T < end:
                h, w, _ = bar.shape
                x = (G - w) // 2
                f[G - bottom - h:G - bottom, x:x + w] = bar
