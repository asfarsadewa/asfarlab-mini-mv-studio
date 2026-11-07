# Builds a textured 3D model from one image with Tripo P2 on fal. An existing output is kept.
# Usage: python tools/tripo.py <image.png> <out.glb> [--faces 30000]
import argparse, base64, json, mimetypes, os, sys, time, urllib.request
from pathlib import Path
import requests

ENDPOINT = "tripo3d/p2/image-to-3d"
ap = argparse.ArgumentParser()
ap.add_argument("image")
ap.add_argument("out")
ap.add_argument("--faces", type=int, default=30000)
a = ap.parse_args()
out = Path(a.out)
if out.exists():
    print(f"Skip: {out} exists.")
    sys.exit(0)

KEY = os.environ.get("FAL_KEY") or os.environ["FAL_AI_KEY"]
HEADERS = {"Authorization": f"Key {KEY}", "Content-Type": "application/json"}


def call(url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    with urllib.request.urlopen(urllib.request.Request(url, data, HEADERS), timeout=120) as r:
        return json.load(r)


mime = mimetypes.guess_type(a.image)[0] or "image/png"
uri = f"data:{mime};base64,{base64.b64encode(Path(a.image).read_bytes()).decode()}"
job = call(f"https://queue.fal.run/{ENDPOINT}", {
    "image_url": uri, "face_limit": a.faces, "texture": True, "pbr": True, "export_uv": True, "texture_quality": "standard",
})
print("Submitted", job["request_id"], flush=True)
for _ in range(120):
    time.sleep(10)
    status = call(job["status_url"])
    if status["status"] == "COMPLETED":
        break
    print(status["status"], flush=True)
else:
    sys.exit("Tripo did not finish in 20 minutes.")
result = call(job["response_url"])
mesh = result.get("model_mesh") or {}
url = mesh.get("url") or (result.get("model_urls") or {}).get("pbr_model")
if not url:
    sys.exit(f"No mesh in the result. Keys: {list(result)}")
out.parent.mkdir(parents=True, exist_ok=True)
# requests carries its own certificate bundle. The fal CDN fails with the bundle of urllib on this machine.
download = requests.get(url, timeout=300)
download.raise_for_status()
out.write_bytes(download.content)
out.with_suffix(".json").write_text(json.dumps({"endpoint": ENDPOINT, "request": job["request_id"], "faces": a.faces, "source": a.image}, indent=2))
print(f"Wrote {out}: {out.stat().st_size / 1e6:.1f} MB")
