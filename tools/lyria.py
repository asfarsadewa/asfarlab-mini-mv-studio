# Generates the Lyria takes named in a brief. A complete take is skipped. Each take gets one retry.
# A complete take has audio and a receipt. An approved film keeps its audio, even if the receipt is missing.
# Usage: python tools/lyria.py mvs/<id>
import base64, json, os, subprocess, sys, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
MODEL = "lyria-3.5"


def request(prompt):
    body = json.dumps({"model": MODEL, "input": prompt, "response_format": {"type": "audio"}}).encode()
    headers = {"Content-Type": "application/json", "x-goog-api-key": os.environ["GEMINI_API_KEY"]}
    with urllib.request.urlopen(urllib.request.Request(URL, body, headers), timeout=300) as r:
        return json.load(r)


def probe_seconds(path):
    """Returns the audio length, or 0 if ffprobe cannot read the file."""
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    try:
        return float(r.stdout)
    except ValueError:
        return 0.0


def take(root, name, style, lyrics, approved=False):
    out = root / "music" / f"{name}.mp3"
    receipt = root / "music" / f"{name}.json"
    if out.exists() and (receipt.exists() or approved):
        return f"Skip {name}: the take exists."
    if out.exists():
        print(f"{name}: the audio has no receipt, so an earlier run did not finish. A new take replaces it.", flush=True)
    prompt = f"{style}\n\nLyrics, sung exactly as written:\n{lyrics}"
    for attempt in (1, 2):
        try:
            started = time.time()
            data = request(prompt)
            blocks = [b for s in data.get("steps", []) for b in s.get("content", [])]
            audio = next((b for b in blocks if b.get("type") == "audio" and b.get("data")), None)
            if audio is None:
                raise RuntimeError(f"No audio block. Status {data.get('status')}. Text: {[b.get('text') for b in blocks]}")
            # Write to temporary names, validate, then rename. The receipt arrives last, so it marks a complete take.
            temp_audio, temp_receipt = out.with_name(f"{name}.tmp.mp3"), receipt.with_name(f"{name}.tmp.json")
            try:
                temp_audio.write_bytes(base64.b64decode(audio["data"], validate=True))
                if probe_seconds(temp_audio) <= 0:
                    raise RuntimeError("The audio cannot be read.")
                temp_receipt.write_text(json.dumps({
                    "model": MODEL, "prompt": prompt, "interactionId": data.get("id"), "mime": audio.get("mime_type"),
                    "seconds": round(time.time() - started, 1), "text": [b.get("text") for b in blocks if b.get("type") == "text"],
                }, ensure_ascii=False, indent=2), encoding="utf-8")
                os.replace(temp_audio, out)
                os.replace(temp_receipt, receipt)
            finally:
                temp_audio.unlink(missing_ok=True)
                temp_receipt.unlink(missing_ok=True)
            return f"Generated {name}."
        except urllib.error.HTTPError as e:
            error = f"HTTP {e.code}: {e.read().decode(errors='replace')[:400]}"
        except Exception as e:
            error = str(e)[:400]
        print(f"{name} attempt {attempt} failed: {error}", flush=True)
    return f"FAILED {name}."


root = Path(sys.argv[1])
brief = json.loads((root / "brief.json").read_text(encoding="utf-8"))
(root / "music").mkdir(exist_ok=True)
with ThreadPoolExecutor() as pool:
    jobs = [pool.submit(take, root, n, s, brief["lyrics"], "approved" in brief) for n, s in brief["takes"].items()]
    results = [j.result() for j in jobs]
print("\n".join(results))
# A studio song runs about 1:30. Older films set their own limits in their briefs.
low, high = brief.get("min_seconds", 75), brief.get("max_seconds", 110)
short = False
for name in brief["takes"]:
    path = root / "music" / f"{name}.mp3"
    if path.exists():
        seconds = probe_seconds(path)
        print(f"{name}: {seconds:.1f} s" + (f"  OUTSIDE: the song must run {low} to {high} s. Change the prompt and the lyrics." if not low <= seconds <= high else ""))
        short = short or not low <= seconds <= high
sys.exit(1 if short or any(r.startswith("FAILED") for r in results) else 0)
