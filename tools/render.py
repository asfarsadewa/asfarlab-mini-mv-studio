# Renders one film: steps the picture frame by frame, masters the audio, and writes a square mp4.
# The film module lives at mvs/<id>/film.py. It exposes make(ctx), which returns draw(i, t, T) -> HxWx3 uint8.
# Usage: python tools/render.py mvs/<id> [--scale 3] [--stills 0.5,5.1,9] [--out output/name.mp4] [--strict]
import argparse, datetime, importlib.util, json, re, subprocess, sys
from pathlib import Path
from PIL import Image
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from pixkit import END_CARD_SECONDS, Sprite, bayer_field, end_card

sys.stdout.reconfigure(encoding="utf-8")
ap = argparse.ArgumentParser()
ap.add_argument("root")
ap.add_argument("--scale", type=int, default=3)
ap.add_argument("--stills", default="")
ap.add_argument("--out", default="")
ap.add_argument("--full", action="store_true", help="Render the full window of the brief. The default is the test window.")
ap.add_argument("--window", default="", help="Override the window, as start,end in song seconds.")
ap.add_argument("--strict", action="store_true", help="Exit with an error if a sprite holds one frame too long. The mp4 is still written.")
a = ap.parse_args()

root = Path(a.root)
brief = json.loads((root / "brief.json").read_text(encoding="utf-8"))
take = root / "music" / f"{brief['take']}.mp3"
analysis = json.loads(take.with_suffix(".analysis.json").read_text())
window = brief["full"] if a.full else brief["test"]
start, end = window["start"], window["end"]
if a.window:
    start, end = [float(v) for v in a.window.split(",")]
fps, grid = brief["fps"], brief["grid"]
song_frames = round((end - start) * fps)
# Every full film closes with the studio credit, after the song. The year is the year of production.
end_frames = round(END_CARD_SECONDS * fps) if a.full else 0
total = song_frames + end_frames
work = root / "build"
work.mkdir(exist_ok=True)
# Each film delivers into its own folder.
out = Path(a.out or f"output/{brief['id']}/{brief['id']}_{'mv' if a.full else 'test'}.mp4")
out.parent.mkdir(parents=True, exist_ok=True)

# Master the whole take to -14 LUFS with a fixed gain, then cut the window, so a cut keeps the level of the song.
measured = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(take), "-af", "loudnorm=I=-14:TP=-1.5:LRA=14:print_format=json", "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8").stderr
m = json.loads(re.search(r"\{[^{}]*\}", measured, re.S).group(0))
norm = f"loudnorm=I=-14:TP=-1.5:LRA=14:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true"
length = end - start
whole = total / fps
wav = work / "audio.wav"
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(take), "-af",
                f"{norm},aresample=48000,atrim={start}:{end},asetpts=PTS-STARTPTS,afade=t=in:d=0.08,afade=t=out:st={length - 0.6}:d=0.6,apad=whole_dur={whole}",
                "-ac", "2", "-c:a", "pcm_s16le", str(wav)], check=True)

spec = importlib.util.spec_from_file_location("film", root / "film.py")
film = importlib.util.module_from_spec(spec)
spec.loader.exec_module(film)
draw = film.make({"root": root, "brief": brief, "a": analysis, "start": start, "end": end, "fps": fps, "grid": grid})

credit = end_card(grid, brief["paper"], brief.get("year", datetime.date.today().year))
bayer = bayer_field(grid)
last_song_frame = credit
side = grid * a.scale
ff = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                       "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{grid}x{grid}", "-r", str(fps), "-i", "-", "-i", str(wav),
                       "-vf", f"scale={side}:{side}:flags=neighbor:out_color_matrix=bt709:out_range=tv,format=yuv420p",
                       "-c:v", "libx264", "-preset", "slow", "-crf", "14", "-profile:v", "high",
                       "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
                       "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
stills = {round(float(s) * fps) for s in a.stills.split(",") if s}
for i in range(total):
    t = i / fps
    if i < song_frames:
        frame = draw(i, t, start + t)
        last_song_frame = frame
    else:
        # The card appears through a Bayer dissolve from the last frame of the film.
        reveal = (i - song_frames + 1) / (0.4 * fps)
        frame = np.where((bayer < reveal)[..., None], credit, last_song_frame).astype(np.uint8)
    assert frame.shape == (grid, grid, 3) and frame.dtype == np.uint8
    ff.stdin.write(frame.tobytes())
    if i in stills:
        Image.fromarray(frame).resize((side, side), Image.NEAREST).save(work / f"still_{t:05.2f}.png")
ff.stdin.close()
if ff.wait():
    sys.exit("ffmpeg failed.")
print(f"{out}: {total} frames, {side}x{side}, {out.stat().st_size / 1e6:.1f} MB")
frozen = sorted(((run / fps, name) for (name, _), run in Sprite.runs.items() if run > 0.4 * fps), reverse=True)
if frozen:
    print("Frozen people: these sprites held one frame too long. Fix each one:", [f"{name} {seconds:.1f} s" for seconds, name in frozen])
    if a.strict:
        sys.exit("Strict mode: the film has frozen people.")
else:
    print("Frozen people: none.")
