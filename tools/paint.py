# Paints one image with an OpenAI image model. An existing output is kept.
# Pass reference images with --image. Later images are style or identity references.
# Usage: python tools/paint.py out.png --prompt-file x.prompt.txt [--image ref.png ...] [--quality medium] [--size 1024x1024] [--background transparent]
import argparse, base64, os, sys
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("out")
ap.add_argument("--prompt-file", required=True)
ap.add_argument("--image", action="append", default=[])
ap.add_argument("--model", default="gpt-image-2.6-sunburst")
ap.add_argument("--quality", default="medium")
ap.add_argument("--size", default="1024x1024")
ap.add_argument("--background", default=None)
a = ap.parse_args()

out = Path(a.out)
if out.exists():
    print(f"Skip: {out} exists.")
    sys.exit(0)
if not os.environ.get("OPENAI_API_KEY"):
    sys.exit("Set OPENAI_API_KEY.")
from openai import OpenAI

prompt = Path(a.prompt_file).read_text(encoding="utf-8")
args = {"model": a.model, "prompt": prompt, "quality": a.quality, "size": a.size}
if a.background:
    args["background"] = a.background
client = OpenAI(timeout=280)
if a.image:
    handles = [open(p, "rb") for p in a.image]
    try:
        result = client.images.edit(image=handles, **args)
    finally:
        for h in handles:
            h.close()
else:
    result = client.images.generate(**args)
out.parent.mkdir(parents=True, exist_ok=True)
temp = out.with_name(out.stem + ".tmp" + out.suffix)
temp.write_bytes(base64.b64decode(result.data[0].b64_json))
os.replace(temp, out)
print(f"Wrote {out}: {out.stat().st_size / 1024:.0f} KB")
