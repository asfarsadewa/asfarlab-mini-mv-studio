# Checks a render for phone delivery.
# It re-encodes the file the way a social app might (720 square, about 1.5 Mbps), then saves master and re-encoded crops side by side.
# It also reports codec, size, loudness, and the mean difference between the two.
# Usage: python tools/qa.py <video.mp4> --times 3,5.5,7.5 --crop 330,330,420,420
import argparse, json, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8")
ap = argparse.ArgumentParser()
ap.add_argument("video")
ap.add_argument("--times", default="3,5.5,7.5")
ap.add_argument("--crop", default="330,330,420,420")
a = ap.parse_args()
video = Path(a.video)
sheet = video.with_suffix(".qa.png")
tmp = Path(tempfile.mkdtemp())
repost = tmp / "repost.mp4"
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video), "-vf", "scale=720:720:flags=bicubic",
                "-c:v", "libx264", "-preset", "veryfast", "-b:v", "1500k", "-maxrate", "1800k", "-bufsize", "3000k", "-c:a", "aac", "-b:a", "128k", str(repost)], check=True)

probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_name,width,height,pix_fmt,r_frame_rate,duration,color_space:format=size,duration", "-of", "json", str(video)], capture_output=True, text=True, encoding="utf-8").stdout)
print(json.dumps(probe))
meter = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(video), "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8").stderr
print(" ".join(l.strip() for l in meter.splitlines()[-12:] if l.strip().startswith(("I:", "Peak:"))))


def grab(src, t, name):
    path = tmp / name
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", str(t), "-i", str(src), "-frames:v", "1", str(path)], check=True)
    return Image.open(path).convert("RGB")


x, y, w, h = [int(v) for v in a.crop.split(",")]
times = [float(v) for v in a.times.split(",")]
out = Image.new("RGB", (len(times) * (w + 8), 2 * h + 8), (60, 60, 60))
for k, t in enumerate(times):
    master = grab(video, t, f"m{k}.png")
    social = grab(repost, t, f"r{k}.png").resize(master.size, Image.BICUBIC)
    print(f"t={t}: mean abs difference {np.abs(np.asarray(master, float) - np.asarray(social, float)).mean():.2f} of 255")
    box = (x, y, x + w, y + h)
    out.paste(master.crop(box), (k * (w + 8), 0))
    out.paste(social.crop(box), (k * (w + 8), h + 8))
out.save(sheet)
print(f"{sheet}: top row is the master. Bottom row is the simulated re-upload.")
