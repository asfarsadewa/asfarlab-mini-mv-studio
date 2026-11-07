# Transcribes a take with ElevenLabs Scribe v2 and saves the word timings beside it.
# It proves that the vocals exist and shows where each line falls. Existing transcripts are reused.
# Usage: python tools/transcribe.py <take.mp3> [--lang jpn]
import argparse, json, os, sys
from pathlib import Path
import requests

sys.stdout.reconfigure(encoding="utf-8")
ap = argparse.ArgumentParser()
ap.add_argument("take")
ap.add_argument("--lang", default="jpn")
a = ap.parse_args()

path = Path(a.take).with_suffix(".words.json")
if path.exists():
    data = json.loads(path.read_text(encoding="utf-8"))
else:
    with open(a.take, "rb") as f:
        r = requests.post(
            "https://api.elevenlabs.io/v1/speech-to-text",
            headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"]},
            data={"model_id": "scribe_v2", "language_code": a.lang, "timestamps_granularity": "word", "tag_audio_events": "false"},
            files={"file": f},
            timeout=300,
        )
    if not r.ok:
        sys.exit(f"Scribe HTTP {r.status_code}: {r.text[:300]}")
    data = r.json()
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

# These languages do not put spaces between words.
NO_SPACES = {"jpn", "zho", "cmn", "yue", "tha"}

# Print phrases: a gap of 0.6 s or more starts a new phrase.
words = [w for w in data.get("words", []) if w.get("type") == "word"]
phrase, start, end = "", None, 0
for w in words:
    if start is not None and w["start"] - end >= 0.6:
        print(f"{start:6.2f}-{end:6.2f} {phrase}")
        phrase, start = "", None
    start = w["start"] if start is None else start
    phrase += w["text"] if data.get("language_code") in NO_SPACES or not phrase else " " + w["text"]
    end = w["end"]
if phrase:
    print(f"{start:6.2f}-{end:6.2f} {phrase}")
print(f"{Path(a.take).name}: {len(words)} words, language {data.get('language_code')}")
