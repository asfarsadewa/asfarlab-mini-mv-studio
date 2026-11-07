# Pulls runs of consecutive frames from a video as cropped strips, to judge motion and occlusion.
# Each spec is name:start:step:count:x:y:w:h with times in seconds and the crop in grid pixels.
# Usage: python tools/strip.py <video.mp4> <out.png> --scale 3 --zoom 2 spec [spec ...]
import argparse, subprocess, tempfile
from pathlib import Path
from PIL import Image, ImageDraw

ap = argparse.ArgumentParser()
ap.add_argument("video")
ap.add_argument("out")
ap.add_argument("specs", nargs="+")
ap.add_argument("--scale", type=int, default=3)
ap.add_argument("--zoom", type=int, default=2)
a = ap.parse_args()
rows = []
tmp = Path(tempfile.mkdtemp())
for spec in a.specs:
    name, start, step, count, x, y, w, h = spec.split(":")
    start, step, count, x, y, w, h = float(start), float(step), int(count), int(x), int(y), int(w), int(h)
    cells = []
    for k in range(count):
        p = tmp / f"{name}_{k}.png"
        s = a.scale
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{start + k * step:.3f}", "-i", a.video, "-frames:v", "1",
                        "-vf", f"crop={w * s}:{h * s}:{x * s}:{y * s},scale={w * a.zoom * s // 3}:{h * a.zoom * s // 3}:flags=neighbor", str(p)], check=True)
        cells.append(Image.open(p).convert("RGB"))
    rows.append((name, start, step, cells))
width = max(sum(c.width + 4 for c in r[3]) for r in rows)
height = sum(r[3][0].height + 16 for r in rows)
sheet = Image.new("RGB", (width, height), (50, 50, 50))
d = ImageDraw.Draw(sheet)
y = 0
for name, start, step, cells in rows:
    d.text((3, y + 2), f"{name} from {start}s, every {step}s", fill=(255, 255, 255))
    x = 0
    for c in cells:
        sheet.paste(c, (x, y + 15))
        x += c.width + 4
    y += cells[0].height + 16
sheet.save(a.out)
print(a.out, sheet.size)
