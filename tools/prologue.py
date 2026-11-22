# The typewriter prologue: an optional card before the song that types out the background of the story.
# A film turns it on in brief.json:
#   "prologue": {"text": ["First paragraph.", "Second paragraph."]}
# Optional fields: "cps" (characters per second, default 22), "hold" (seconds after the last character, default 2.0),
# "size" (font size in grid pixels, default 13) and "clicks" (false for silence, default true).
# render.py plays it before the song on a full render, and on a test render with --prologue on.
# The text is user copy, so it follows the ASD-STE100 register.
# The song starts after the card. The analog pass and the end card treat the prologue as part of the film.
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pixkit import INK, glyph_font
from studio_paths import font_path

RATE = 48000
LEAD = 0.6       # Blank paper before the first key.
PAUSE_STOP = 0.2
PAUSE_PARA = 0.7


def _font(text, size):
    # Courier New Bold reads as a typewriter at grid scale. Text outside Latin falls back to the studio glyph fonts.
    font = ImageFont.truetype(font_path("courbd.ttf"), size)
    if all(ord(c) < 0x250 for c in text):
        return font
    return glyph_font(text, size)


class Prologue:
    def __init__(self, cfg, grid, paper, fps, seed=7):
        self.grid, self.fps = grid, fps
        self.paper = np.array(paper, np.uint8)
        self.paper_rgb = [int(v) for v in paper]
        paras = [p.strip() for p in cfg["text"] if p.strip()]
        self.cps = float(cfg.get("cps", 22))
        self.hold = float(cfg.get("hold", 2.0))
        self.clicks = cfg.get("clicks", True)
        self.font = _font("".join(paras), int(cfg.get("size", 13)))
        rng = np.random.default_rng(seed)
        margin, width = 28, grid - 56
        step = round(self.font.size * 1.45)

        # Wrap each paragraph to the page width. Each character gets its place, its time and a little ribbon wear.
        self.chars, self.keys, self.bells = [], [], []
        lines = []
        for para in paras:
            line = ""
            for word in para.split():
                trial = f"{line} {word}".strip()
                if self.font.getlength(trial) > width and line:
                    lines.append((line, False))
                    line = word
                else:
                    line = trial
            lines.append((line, True))
        top = max(28, (grid - 64 - step * (len(lines) + sum(end for _, end in lines))) // 2)
        t, y = LEAD, top
        for text, para_end in lines:
            x = margin
            for c in text:
                if c != " ":
                    self.chars.append((t, c, x, y + int(rng.integers(-1, 2)), float(rng.uniform(0.72, 1.0))))
                    self.keys.append(t)
                x += self.font.getlength(c)
                t += 1 / self.cps + (PAUSE_STOP if c in ".,;:" else 0)
            self.bells.append(t)
            t += PAUSE_PARA if para_end else 0.18
            y += step * (2 if para_end else 1)
        self.end_typing = t
        self.seconds = t + self.hold
        self.cursor = [(c[0], c[2] + self.font.getlength(c[1]), c[3]) for c in self.chars]

    def frame(self, t):
        im = Image.new("RGB", (self.grid, self.grid), tuple(int(v) for v in self.paper))
        d = ImageDraw.Draw(im)
        d.fontmode = "1"
        shown = [c for c in self.chars if c[0] <= t]
        for _, c, x, y, ink in shown:
            colour = tuple(int(p + (i - p) * ink) for p, i in zip(self.paper_rgb, INK))
            d.text((x, y), c, font=self.font, fill=colour)
        # A block cursor waits after the last character and blinks twice a second.
        if shown and int(t * 2) % 2 == 0:
            _, cx, cy = self.cursor[len(shown) - 1]
            h = self.font.size
            d.rectangle((cx + 1, cy + h - 3, cx + 6, cy + h - 1), fill=tuple(int(v) for v in INK))
        return np.asarray(im, np.uint8)

    def audio(self, seconds):
        """Stereo 48 kHz samples: a key strike for each character and a small bell at each line end."""
        n = int(round(seconds * RATE))
        out = np.zeros(n, np.float32)
        if not self.clicks:
            return np.stack([out, out], axis=1)
        rng = np.random.default_rng(11)
        k = int(0.035 * RATE)
        env = np.exp(-np.arange(k) / (0.006 * RATE)).astype(np.float32)
        for t in self.keys:
            i = int(t * RATE)
            if i + k >= n:
                continue
            noise = rng.standard_normal(k).astype(np.float32)
            # A short body thump under the bright strike.
            body = np.sin(2 * math.pi * rng.uniform(140, 190) * np.arange(k) / RATE).astype(np.float32)
            out[i:i + k] += (0.18 * noise + 0.22 * body) * env * rng.uniform(0.6, 1.0)
        b = int(0.9 * RATE)
        bell = (np.sin(2 * math.pi * 2093 * np.arange(b) / RATE) * np.exp(-np.arange(b) / (0.25 * RATE))).astype(np.float32)
        for t in self.bells:
            i = int(t * RATE)
            if i + b < n:
                out[i:i + b] += 0.08 * bell
        out = np.clip(out, -0.9, 0.9)
        return np.stack([out, out], axis=1)
