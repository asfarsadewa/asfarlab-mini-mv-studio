# The sprite proof gate. Bakes one idle frame per character at its final scale and places it on its real plate.
# Read the sheet before any batch bake. It costs minutes and catches a sprite that does not read.
# Each spec is hero:plate:ppu:x:y, with an optional colour grade for the plate as :r,g,b.
# Usage: python tools/proof.py mvs/<id> hero_boy:yard:14:148:272 hero:room:32:150:250:0.62,0.62,0.72 [--azimuth 15] [--job '{"spots":[280,17]}']
import argparse, json, shutil, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

from studio_paths import BLENDER
TOOL = Path(__file__).with_name("hero.py")
sys.stdout.reconfigure(encoding="utf-8")
ap = argparse.ArgumentParser()
ap.add_argument("root")
ap.add_argument("specs", nargs="+")
ap.add_argument("--azimuth", type=float, default=15)
ap.add_argument("--job", default="{}", help="Extra job fields, such as spots or colours, as JSON.")
a = ap.parse_args()

root = Path(a.root).resolve()
brief = json.loads((root / "brief.json").read_text(encoding="utf-8"))
paper = np.array(brief["paper"], np.uint8)
CROP, ZOOM = 90, 4
rows = []
for spec in a.specs:
    parts = spec.split(":")
    hero, plate_name, ppu, x, y = parts[0], parts[1], float(parts[2]), int(parts[3]), int(parts[4])
    plate = np.asarray(Image.open(root / "plates" / f"{plate_name}-360.png").convert("RGB")).copy()
    if len(parts) > 5:
        ground = ~(plate == paper).all(axis=2)
        plate[ground] = np.clip(plate[ground] * np.array([float(v) for v in parts[5].split(",")]), 0, 255).astype(np.uint8)
    work = Path(tempfile.mkdtemp())
    job = {"clip": "idle", "azimuth": a.azimuth, "ppu": ppu, "canvas": 4.4, "cloth": False, "outfit": False, "frames": [0, 1], "out": work.as_posix()}
    job.update(json.loads(a.job))
    (work / "job.json").write_text(json.dumps(job))
    r = subprocess.run([BLENDER, "--background", "--python", str(TOOL), "--", "bake", str(root / hero), str(work / "job.json")], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if "BAKED" not in r.stdout:
        sys.exit(f"{spec} FAILED:\n" + "\n".join(l for l in (r.stdout + r.stderr).splitlines() if "rror" in l)[-800:])
    meta = json.loads((work / "meta.json").read_text())
    px = np.asarray(Image.open(work / "f_0000.png").convert("RGBA"))
    solid = px[..., 3] > 127
    # Match the bake: one small palette and a dark outer edge.
    colours = job.get("colours", 40 if ppu >= 16 else 28)
    pal = Image.fromarray(px[..., :3][solid].reshape(1, -1, 3), "RGB").quantize(colors=colours, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    rgb = np.asarray(Image.fromarray(px[..., :3], "RGB").quantize(palette=pal, dither=Image.Dither.NONE).convert("RGB")).copy()
    inner = solid.copy()
    for ax, s in ((0, 1), (0, -1), (1, 1), (1, -1)):
        inner &= np.roll(solid, s, axis=ax)
    edge = solid & ~inner
    rgb[edge] = (rgb[edge] * 0.55).astype(np.uint8)
    ax0, ay0 = round(x - meta["anchor"][0]), round(y - meta["anchor"][1])
    ys, xs = np.nonzero(solid)
    frame = plate.copy()
    keep = (ys + ay0 >= 0) & (ys + ay0 < 360) & (xs + ax0 >= 0) & (xs + ax0 < 360)
    frame[ys[keep] + ay0, xs[keep] + ax0] = rgb[ys[keep], xs[keep]]
    height = int(ys.max() - ys.min() + 1)
    print(f"{spec}: the person stands {height} grid pixels tall.")
    rows.append((spec, frame, x, y))
    shutil.rmtree(work, ignore_errors=True)

# Each row shows the whole frame at phone size, then a close crop.
FULL = 360
side = FULL + CROP * ZOOM
sheet = Image.new("RGB", (side, len(rows) * FULL), (40, 40, 44))
d = ImageDraw.Draw(sheet)
for k, (spec, frame, x, y) in enumerate(rows):
    im = Image.fromarray(frame)
    sheet.paste(im, (0, k * FULL))
    x0, y0 = min(max(x - CROP // 2, 0), 360 - CROP), min(max(y - CROP // 2 - 10, 0), 360 - CROP)
    sheet.paste(im.crop((x0, y0, x0 + CROP, y0 + CROP)).resize((CROP * ZOOM, CROP * ZOOM), Image.NEAREST), (FULL, k * FULL))
    d.text((4, k * FULL + 3), spec, fill=(200, 0, 90))
out = root / "build" / "proof.png"
out.parent.mkdir(exist_ok=True)
sheet.save(out)
print(out)
