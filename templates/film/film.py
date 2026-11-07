# The smallest film: one plate and captions. Add scenes and people as docs/PRODUCTION.md describes.
# mvs/noroshi/film.py is the worked example.
import numpy as np
from PIL import Image
from pixkit import Captions, bayer_field


def make(ctx):
    G, brief, root = ctx["grid"], ctx["brief"], ctx["root"]
    paper = np.array(brief["paper"], np.uint8)
    bayer = bayer_field(G)
    caps = Captions(brief["lines"], paper)
    plate_path = root / "plates/scene-360.png"
    plate = np.asarray(Image.open(plate_path).convert("RGB")).copy() if plate_path.exists() else np.full((G, G, 3), paper, np.uint8)

    def draw(i, t, T):
        f = plate.copy()
        caps.draw(f, T)
        if T < 0.6:
            f[bayer > T / 0.6] = paper
        left = ctx["end"] - T
        if left < 1.2:
            f[bayer > left / 1.2] = paper
        return f

    return draw
