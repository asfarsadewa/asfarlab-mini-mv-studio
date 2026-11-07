# Draws a labelled coordinate grid over a snapped plate, for tracing anchors and occlusion shapes.
# An optional crop zooms into one region.
# Usage: python tools/plate_grid.py <plate.png> <out.png> [--crop x0,y0,x1,y1] [--zoom 3] [--every 20]
import argparse
from PIL import Image, ImageDraw

ap = argparse.ArgumentParser()
ap.add_argument("plate")
ap.add_argument("out")
ap.add_argument("--crop", default="")
ap.add_argument("--zoom", type=int, default=3)
ap.add_argument("--every", type=int, default=20)
a = ap.parse_args()
im = Image.open(a.plate).convert("RGB")
x0, y0, x1, y1 = [int(v) for v in a.crop.split(",")] if a.crop else (0, 0, im.width, im.height)
big = im.crop((x0, y0, x1, y1)).resize(((x1 - x0) * a.zoom, (y1 - y0) * a.zoom), Image.NEAREST)
d = ImageDraw.Draw(big)
for x in range(x0 - x0 % a.every, x1 + 1, a.every):
    if x >= x0:
        d.line([((x - x0) * a.zoom, 0), ((x - x0) * a.zoom, big.height)], fill=(255, 0, 180))
        d.text(((x - x0) * a.zoom + 2, 1), str(x), fill=(0, 0, 255))
for y in range(y0 - y0 % a.every, y1 + 1, a.every):
    if y >= y0:
        d.line([(0, (y - y0) * a.zoom), (big.width, (y - y0) * a.zoom)], fill=(255, 0, 180))
        d.text((2, (y - y0) * a.zoom + 1), str(y), fill=(0, 0, 255))
big.save(a.out)
