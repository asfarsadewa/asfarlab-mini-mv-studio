# Analog mode: an optional tape and tube pass over the finished frame. A film turns it on in brief.json:
#   "analog": {"tape": true, "scanlines": false, "crt": false, "bw": false, "amount": 1.0}
# The pass runs at the delivery size, after the nearest-neighbour upscale, so it can soften the pixel grid like a real
# signal. Every effect is deterministic for a frame number, so a render is repeatable.
# Tape: shadow (lifted and crushed blacks, no vignette), wash (tired colour, soft highlights), luma smear and ghost,
#   chroma bleed to the right, light noise, random tracking tears, dropouts, creases and head-switch shear.
# Black and white: the picture becomes monochrome, with a little extra contrast, like a 1950s print or television.
# Scanlines: dark gaps between lines, brighter in highlights. Optional.
# CRT: barrel curvature, rounded corners in a dark bezel, an aperture-grille phosphor mask, bloom and a glass glare.
import math
import cv2
import numpy as np


def _h(x):
    """Deterministic hash in [0, 1)."""
    return (math.sin(x * 12.9898 + 78.233) * 43758.5453) % 1.0


class Analog:
    def __init__(self, cfg, side, fps):
        self.cfg = {"tape": True, "scanlines": False, "crt": False, "bw": False, "amount": 1.0, **cfg}
        self.side, self.fps = side, fps
        S = side
        yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
        u, v = (xx - S / 2) / (S / 2), (yy - S / 2) / (S / 2)
        r2 = u * u + v * v
        self.noise = [np.random.default_rng(k).normal(0, 3.0, (S // 2, S // 2)).astype(np.float32) for k in range(8)]
        # Scanlines: one line pair for each source pixel row would be too coarse. Use 2 screen rows per line.
        line = (np.arange(S) % 3 == 2).astype(np.float32)
        self.scan = (1 - 0.32 * line)[:, None, None].astype(np.float32)
        if self.cfg["crt"]:
            # Barrel curvature: sample the flat picture from a bulged screen.
            k = 0.075
            # Divide by 1 + k, so the middle of each side lands on the tube edge. Only the corners round off.
            su = u * (1 + k * r2) / (1 + k)
            sv = v * (1 + k * r2) / (1 + k)
            self.map_x = (su * S / 2 + S / 2).astype(np.float32)
            self.map_y = (sv * S / 2 + S / 2).astype(np.float32)
            # The visible tube: a rounded rectangle on the curved screen, with a soft edge.
            ax, ay = np.abs(su), np.abs(sv)
            corner = 0.10
            dx, dy = np.maximum(ax - (1 - corner), 0), np.maximum(ay - (1 - corner), 0)
            dist = np.where((ax > 1 - corner) & (ay > 1 - corner), np.sqrt(dx * dx + dy * dy) - corner, np.maximum(ax, ay) - 1)
            # A wide, feathered edge: the picture fades into the bezel. A smoothstep keeps the blend soft.
            e = np.clip(-dist / 0.06, 0, 1)
            self.tube = (e * e * (3 - 2 * e))[..., None].astype(np.float32)
            # Only a slight fall-off toward the rim, as on a real tube.
            self.rim = np.clip(1 - 0.10 * (su * su + sv * sv) ** 2, 0.8, 1)[..., None].astype(np.float32)

            # Aperture grille: vertical red, green and blue stripes, subtle.
            stripe = np.arange(S) % 3
            mask = np.full((S, 3), 0.80, np.float32)
            for c in range(3):
                mask[stripe == c, c] = 1.06
            self.grille = mask[None, :, :]
            # Glass glare: a faint soft highlight at the top left.
            self.glare = (np.clip(1 - ((u + 0.55) ** 2 / 0.35 + (v + 0.65) ** 2 / 0.12), 0, 1) ** 2 * 14)[..., None].astype(np.float32)
            self.bezel = np.array([16, 15, 14], np.float32)

    def tape(self, src, i):
        S, t = self.side, i / self.fps
        # Tracking tear: now and then a band of lines slides sideways.
        if _h(math.floor(t * 3.0)) > 0.66:
            y0 = int(_h(math.floor(t * 0.7) + 0.31) * (S - 120)) + int(t * 40) % 60
            hgt = 12 + int(_h(math.floor(t * 9)) * 36)
            src = src.copy()
            for r in range(y0, min(S, y0 + hgt), 2):
                s = int((_h(r * 0.37 + math.floor(t * 25)) - 0.35) * 64)
                src[r:r + 2] = np.roll(src[r:r + 2], s, axis=1)
        ycc = cv2.cvtColor(src, cv2.COLOR_RGB2YCrCb).astype(np.float32)
        Y, Cr, Cb = ycc[..., 0], ycc[..., 1], ycc[..., 2]
        # Luma smear and a faint ghost to the right.
        Y2 = 0.65 * Y + 0.35 * cv2.blur(Y, (5, 1))
        Y2 = Y2 * 0.9 + np.roll(cv2.blur(Y, (9, 1)), 24, axis=1) * 0.14
        # Wash and shadow: lifted blacks, crushed lower mids, soft highlights.
        Y2 = 16 + Y2 * 0.82
        Y2 = Y2 - 0.10 * np.maximum(0, 90 - Y2)
        Y2 = Y2 - 0.25 * np.maximum(0, Y2 - 205)

        def bleed(C):
            c = cv2.resize(C, (S // 6, S), interpolation=cv2.INTER_AREA)
            c = cv2.GaussianBlur(c, (5, 1), 0)
            c = cv2.resize(c, (S, S), interpolation=cv2.INTER_LINEAR)
            return 128 + (np.roll(c, 8, axis=1) - 128) * 0.76

        Y2 += cv2.resize(self.noise[i % 8], (S, S), interpolation=cv2.INTER_NEAREST)
        out = cv2.cvtColor(np.clip(np.dstack([Y2, bleed(Cr), bleed(Cb)]), 0, 255).astype(np.uint8), cv2.COLOR_YCrCb2RGB).astype(np.float32)
        out *= np.array([1.04, 0.99, 0.92], np.float32)   # A warm, tired tint.
        rng = np.random.default_rng(i * 7 + 1)
        for _ in range(rng.poisson(1.2)):
            y, x = rng.integers(0, S), rng.integers(0, S - 40)
            out[y:y + rng.integers(1, 3), x:x + rng.integers(24, 200)] *= 0.3
        for _ in range(rng.poisson(0.8)):
            y, x, ln = rng.integers(0, S), rng.integers(0, S - 40), rng.integers(24, 220)
            out[y:y + 1, x:x + ln] = out[y:y + 1, x:x + ln] * 0.3 + 190
        if _h(math.floor(t * 2.2) + 0.77) > 0.86:
            y = int(_h(math.floor(t * 2.2) + 0.13) * S)
            out[y:y + 2] = out[y:y + 2] * 0.5 + 110
            out[y + 2:y + 5] *= 0.78
        # Head-switching noise: the bottom lines shear right.
        hs = max(6, S // 110)
        out[S - hs:] = np.roll(out[S - hs:], 20 + int(_h(i) * 16), axis=1) * 0.85 + 16
        return out

    def __call__(self, frame, i):
        """frame: the finished frame at the delivery size, RGB uint8. Returns the analog frame, RGB uint8."""
        cfg = self.cfg
        out = self.tape(frame, i) if cfg["tape"] else frame.astype(np.float32)
        if cfg["bw"]:
            # Luma only, with a gentle S-curve for the contrast of old film. The tube and scanlines come after.
            lum = out[..., 0] * 0.299 + out[..., 1] * 0.587 + out[..., 2] * 0.114
            lum = 255 * (0.5 + 0.5 * np.tanh((lum / 255 - 0.5) * 2.2) / np.tanh(1.1))
            out = np.repeat(lum[..., None], 3, axis=2).astype(np.float32)
        if cfg["scanlines"]:
            # Bright lines spread into the gap, as on a real tube.
            lum = out.mean(axis=2, keepdims=True) / 255.0
            out = out * (self.scan + (1 - self.scan) * lum * 0.6)
        if cfg["crt"]:
            glow = cv2.GaussianBlur(np.maximum(out - 150, 0), (0, 0), self.side / 160)
            out = out * self.grille + glow * 0.35
            out = cv2.remap(out, self.map_x, self.map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
            out = out * self.rim + self.glare
            out = out * self.tube + self.bezel * (1 - self.tube)
        res = np.clip(out, 0, 255).astype(np.uint8)
        if cfg["amount"] < 1:
            res = cv2.addWeighted(frame, 1 - cfg["amount"], res, cfg["amount"], 0)
        return res
