# Checks that this machine can run the studio. It prints the name of each key and never its value.
# Usage: python tools/doctor.py
import importlib.util, json, os, re, shutil, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from studio_paths import ROOT, find_blender, font_path, studio_handle

failed = 0


def report(ok, name, detail="", needed=True):
    global failed
    mark = "OK  " if ok else ("FAIL" if needed else "WARN")
    failed += 0 if ok or not needed else 1
    print(f"{mark}  {name}{': ' + detail if detail else ''}")


report(sys.version_info >= (3, 11), "Python 3.11 or newer", sys.version.split()[0])
for module, package in (("numpy", "numpy"), ("PIL", "pillow"), ("cv2", "opencv-python-headless"), ("librosa", "librosa"), ("requests", "requests"), ("openai", "openai")):
    report(importlib.util.find_spec(module) is not None, f"Python package {package}", "" if importlib.util.find_spec(module) else "run pip install -r requirements.txt")
for tool in ("ffmpeg", "ffprobe"):
    report(shutil.which(tool) is not None, f"{tool} on PATH")
blender = find_blender()
try:
    out = subprocess.run([blender, "--version"], capture_output=True, text=True, timeout=60).stdout
    version = re.search(r"Blender (\d+\.\d+)", out)
    report(bool(version) and int(version.group(1).split(".")[0]) >= 5, "Blender 5 or newer", version.group(0) if version else blender)
except (OSError, subprocess.SubprocessError):
    report(False, "Blender 5 or newer", "set BLENDER to the path of the program")
for name in ("msgothic.ttc", "simsun.ttc"):
    try:
        report(True, f"Caption font for {name}", font_path(name))
    except SystemExit as e:
        report(False, f"Caption font for {name}", str(e))
for key, job in (("GEMINI_API_KEY", "songs"), ("OPENAI_API_KEY", "plates and concepts"), ("ELEVENLABS_API_KEY", "word timings")):
    report(bool(os.environ.get(key)), f"{key} for {job}", needed=False)
report(bool(os.environ.get("FAL_KEY") or os.environ.get("FAL_AI_KEY")), "FAL_KEY for 3D models", needed=False)
report(bool(studio_handle()), "Handle in studio.json for the end card", "" if studio_handle() else "the end card leaves this line out", needed=False)
print("INFO  Motion clips come from the PINOC connector or any Mixamo rig GLB. See docs/PRODUCTION.md, step 7.")
sys.exit(1 if failed else 0)
