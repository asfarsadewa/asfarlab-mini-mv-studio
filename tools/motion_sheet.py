# Bakes clips without cloth at a few frames, then builds a contact sheet to compare samples.
# Usage: python tools/motion_sheet.py <hero_dir> <out.png> clip[:azimuth] ... [--per 7] [--ppu 34]
import argparse, glob, json, os, shutil, subprocess, tempfile
from pathlib import Path
from PIL import Image, ImageDraw

from studio_paths import BLENDER
TOOL = Path(__file__).with_name("hero.py")
FRAMES = {"climb_1": 144, "climb_4": 144, "cradle": 192, "stance": 240, "strike": 120, "walking": 96, "crouch": 94, "cheer": 60, "wave": 40, "idle": 120}
ap = argparse.ArgumentParser()
ap.add_argument("hero")
ap.add_argument("out")
ap.add_argument("clips", nargs="+")
ap.add_argument("--per", type=int, default=7)
ap.add_argument("--ppu", type=int, default=34)
a = ap.parse_args()

rows = []
for spec in a.clips:
    clip, _, az = spec.partition(":")
    total = next((n for k, n in FRAMES.items() if clip.startswith(k)), 120)
    work = tempfile.mkdtemp()
    job = {"clip": clip, "out": work.replace("\\", "/"), "ppu": a.ppu, "azimuth": float(az or 45), "cloth": False, "outfit": False, "torch": False, "step": max(1, total // a.per), "travel": clip.startswith(("climb", "walking")), "canvas": 4.4}
    job_path = Path(work) / "job.json"
    job_path.write_text(json.dumps(job))
    r = subprocess.run([BLENDER, "--background", "--python", str(TOOL), "--", "bake", a.hero, str(job_path)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if "BAKED" not in r.stdout:
        print(clip, "FAILED", "\n".join(l for l in (r.stdout + r.stderr).splitlines() if "rror" in l or "File" in l)[-900:])
        continue
    rows.append((spec, [Image.open(f).convert("RGBA") for f in sorted(glob.glob(work + "/f_*.png"))][:a.per]))
    shutil.rmtree(work, ignore_errors=True)
if rows:
    size = rows[0][1][0].width * 2
    sheet = Image.new("RGB", (a.per * size + 110, len(rows) * size), (214, 210, 200))
    d = ImageDraw.Draw(sheet)
    for y, (name, frames) in enumerate(rows):
        d.text((4, y * size + 6), name, fill=(0, 0, 0))
        for x, f in enumerate(frames):
            big = f.resize((size, size), Image.NEAREST)
            sheet.paste(big, (110 + x * size, y * size), big)
    sheet.save(a.out)
    print(a.out, sheet.size)
