# Snaps a generated plate to a true pixel grid and a fixed palette.
# Each grid cell takes the median colour of its source pixels, so soft edges do not create new colours.
# Near-paper colours become the exact paper colour, so the background is flat.
# Usage: python tools/snap_plate.py <raw.png> <out.png> --grid 360 --colours 48 --paper 251,249,245
import argparse
import numpy as np
from PIL import Image

ap = argparse.ArgumentParser()
ap.add_argument("raw")
ap.add_argument("out")
ap.add_argument("--grid", type=int, default=360)
ap.add_argument("--colours", type=int, default=48)
ap.add_argument("--paper", default="251,249,245")
ap.add_argument("--paper-tolerance", type=int, default=14)
a = ap.parse_args()

src = np.asarray(Image.open(a.raw).convert("RGB"))
h, w, _ = src.shape
ys = np.linspace(0, h, a.grid + 1).astype(int)
xs = np.linspace(0, w, a.grid + 1).astype(int)
cells = np.zeros((a.grid, a.grid, 3), np.uint8)
for y in range(a.grid):
    for x in range(a.grid):
        cells[y, x] = np.median(src[ys[y]:ys[y + 1], xs[x]:xs[x + 1]].reshape(-1, 3), axis=0)

paper = np.array([int(v) for v in a.paper.split(",")], np.uint8)
is_paper = np.abs(cells.astype(int) - paper).max(axis=2) <= a.paper_tolerance
# Quantise only the drawing, so the paper does not use up palette entries.
drawing = cells[~is_paper].reshape(1, -1, 3)
quant = Image.fromarray(drawing, "RGB").quantize(colors=a.colours - 1, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
out = np.tile(paper, (a.grid, a.grid, 1)).astype(np.uint8)
out[~is_paper] = np.asarray(quant.convert("RGB")).reshape(-1, 3)

Image.fromarray(out, "RGB").save(a.out)
Image.fromarray(out, "RGB").resize((a.grid * 3, a.grid * 3), Image.NEAREST).save(a.out.replace(".png", "-x3.png"))
print(f"{a.out}: {a.grid}x{a.grid}, {len(np.unique(out.reshape(-1, 3), axis=0))} colours, {is_paper.mean():.0%} paper")
