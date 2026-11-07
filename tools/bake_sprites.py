# Bakes each job in jobs.json with Blender, then packs the frames into one light sprite strip.
# Packing hardens the alpha, shares one small palette across the clip, and darkens the outer edge pixels.
# Usage: python tools/bake_sprites.py <hero_dir> [job ...]
import glob, json, shutil, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
from PIL import Image

from studio_paths import BLENDER
# One batch uses one version of the rig tool, if another agent edits it during the batch.
TOOL = Path(shutil.copy(Path(__file__).with_name("hero.py"), tempfile.mkdtemp()))
hero = Path(sys.argv[1])
jobs = json.loads((hero / "jobs.json").read_text())
names = sys.argv[2:] or list(jobs)
out_dir = hero / "sprites"
out_dir.mkdir(exist_ok=True)
for name in names:
    job = dict(jobs[name])
    work = Path(tempfile.mkdtemp())
    job["out"] = str(work).replace("\\", "/")
    (work / "job.json").write_text(json.dumps(job))
    r = subprocess.run([BLENDER, "--background", "--python", str(TOOL), "--", "bake", str(hero), str(work / "job.json")], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if "BAKED" not in r.stdout:
        sys.exit(f"{name} FAILED:\n" + "\n".join(l for l in (r.stdout + r.stderr).splitlines() if "rror" in l or "File " in l)[-1200:])
    files = sorted(glob.glob(str(work / "f_*.png")))
    frames = np.stack([np.asarray(Image.open(f).convert("RGBA")) for f in files])
    n, h, w, _ = frames.shape
    alpha = frames[..., 3] > 127
    # One palette for the whole clip stops colours from flickering between frames.
    strip = Image.fromarray(frames[..., :3].reshape(n * h, w, 3), "RGB")
    solid = frames[..., :3][alpha].reshape(1, -1, 3)
    pal = Image.fromarray(solid, "RGB").quantize(colors=job.get("colours", 40 if job["ppu"] >= 16 else 28), method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    rgb = np.asarray(strip.quantize(palette=pal, dither=Image.Dither.NONE).convert("RGB")).reshape(n, h, w, 3).copy()
    # Dark depth-buffer outline: a body pixel that touches an empty pixel gets darker.
    inner = alpha.copy()
    for ax, s in ((1, 1), (1, -1), (2, 1), (2, -1)):
        inner &= np.roll(alpha, s, axis=ax)
    edge = alpha & ~inner
    rgb[edge] = (rgb[edge] * 0.55).astype(np.uint8)
    pack = np.dstack([rgb.reshape(n * h, w, 3), (alpha.reshape(n * h, w) * 255).astype(np.uint8)])
    Image.fromarray(pack, "RGBA").save(out_dir / f"{name}.png", optimize=True)
    meta = json.loads((work / "meta.json").read_text())
    # The lowest solid row of the first frames is where the feet meet the ground.
    meta["count"] = n
    (out_dir / f"{name}.json").write_text(json.dumps(meta))
    size = (out_dir / f"{name}.png").stat().st_size / 1024
    print(f"{name}: {n} frames, {w}x{h}, {size:.0f} KB", flush=True)
    shutil.rmtree(work, ignore_errors=True)
shutil.rmtree(TOOL.parent, ignore_errors=True)
