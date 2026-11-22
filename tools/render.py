# Renders one film: steps the picture frame by frame, masters the audio, and writes a square mp4.
# The film module lives at mvs/<id>/film.py. It exposes make(ctx), which returns draw(i, t, T) -> HxWx3 uint8.
# Usage: python tools/render.py mvs/<id> [--scale 3] [--stills 0.5,5.1,9] [--out output/name.mp4] [--strict]
# Analog mode: if brief.json has an "analog" block, tools/analog.py treats every frame at the delivery size.
# Radio mode: if brief.json has a "radio" block, tools/radio.py turns the take into an old radio sound before mastering.
# Prologue: if brief.json has a "prologue" block, tools/prologue.py types the story background before the song.
# A full render plays it. A test render plays it with --prologue on. --stills then counts from the start of the prologue.
import argparse, datetime, importlib.util, json, re, subprocess, sys
from pathlib import Path
from PIL import Image
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from pixkit import END_CARD_SECONDS, Sprite, bayer_field, end_card
from analog import Analog
import radio
from prologue import Prologue, RATE

sys.stdout.reconfigure(encoding="utf-8")
ap = argparse.ArgumentParser()
ap.add_argument("root")
ap.add_argument("--scale", type=int, default=3)
ap.add_argument("--stills", default="")
ap.add_argument("--out", default="")
ap.add_argument("--full", action="store_true", help="Render the full window of the brief. The default is the test window.")
ap.add_argument("--window", default="", help="Override the window, as start,end in song seconds.")
ap.add_argument("--analog", default="", help="Override the analog block of the brief as JSON, such as '{\"crt\": true}'. Use 'off' to turn it off.")
ap.add_argument("--radio", default="", help="Override the radio block of the brief as JSON, such as '{\"mode\": \"sw\"}'. Use 'off' to turn it off.")
ap.add_argument("--prologue", default="", help="on or off. The default plays the prologue of the brief on a full render only.")
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
work = root / "build"
work.mkdir(exist_ok=True)
use_prologue = brief.get("prologue") and (a.prologue == "on" or (a.full and a.prologue != "off"))
prologue = Prologue(brief["prologue"], grid, brief["paper"], fps) if use_prologue else None
pro_frames = round(prologue.seconds * fps) if prologue else 0
total = pro_frames + song_frames + end_frames
# The review canvas reads the length of the prologue of the delivery, so that its timeline matches the video.
if a.full:
    marker = root / "prologue.json"
    if prologue:
        marker.write_text(json.dumps({"seconds": pro_frames / fps}) + "\n", encoding="utf-8")
    elif marker.exists():
        marker.unlink()
radio_cfg = brief.get("radio")
if a.radio:
    radio_cfg = None if a.radio == "off" else {**(radio_cfg if isinstance(radio_cfg, dict) else {}), **json.loads(a.radio)}
# The take keeps its timing: the radio pass is zero-phase, so beats and word times still fit.
source = radio.render_take(take, work / "radio_take.wav", radio_cfg) if radio_cfg else take
# Each film delivers into its own folder.
# The delivery takes the full romanized title as its file name, such as "Mou Ichimai.mp4". Older films keep <id>_mv.mp4.
delivery = f"{brief['romanized']}.mp4" if brief.get("romanized") else f"{brief['id']}_mv.mp4"
out = Path(a.out or f"output/{brief['id']}/{delivery if a.full else brief['id'] + '_test.mp4'}")
out.parent.mkdir(parents=True, exist_ok=True)

# Master the whole take to -14 LUFS with a fixed gain, then cut the window, so a cut keeps the level of the song.
measured = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(source), "-af", "loudnorm=I=-14:TP=-1.5:LRA=14:print_format=json", "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8").stderr
m = json.loads(re.search(r"\{[^{}]*\}", measured, re.S).group(0))
norm = f"loudnorm=I=-14:TP=-1.5:LRA=14:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true"
length = end - start
whole = (song_frames + end_frames) / fps
wav = work / ("song.wav" if prologue else "audio.wav")
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source), "-af",
                f"{norm},aresample=48000,atrim={start}:{end},asetpts=PTS-STARTPTS,afade=t=in:d=0.08,afade=t=out:st={length - 0.6}:d=0.6,apad=whole_dur={whole}",
                "-ac", "2", "-c:a", "pcm_s16le", str(wav)], check=True)
if prologue:
    # The typewriter keys play before the song. The song wav keeps its own master.
    import wave
    keys = (prologue.audio(pro_frames / fps) * 32767).astype("<i2")
    with wave.open(str(work / "prologue.wav"), "wb") as w:
        w.setnchannels(2), w.setsampwidth(2), w.setframerate(RATE)
        w.writeframes(keys.tobytes())
    wav = work / "audio.wav"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(work / "prologue.wav"), "-i", str(work / "song.wav"),
                    "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1", "-ac", "2", "-c:a", "pcm_s16le", str(wav)], check=True)

spec = importlib.util.spec_from_file_location("film", root / "film.py")
film = importlib.util.module_from_spec(spec)
spec.loader.exec_module(film)
draw = film.make({"root": root, "brief": brief, "a": analysis, "start": start, "end": end, "fps": fps, "grid": grid})

credit = end_card(grid, brief["paper"], brief.get("year", datetime.date.today().year))
bayer = bayer_field(grid)
last_song_frame = credit
side = grid * a.scale
analog_cfg = brief.get("analog")
if a.analog:
    analog_cfg = None if a.analog == "off" else {**(analog_cfg or {}), **json.loads(a.analog)}
analog = Analog(analog_cfg, side, fps) if analog_cfg else None
# With analog mode the pipe carries finished frames at the delivery size. Tape noise needs a little more compression.
in_side = side if analog else grid
ff = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                       "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{in_side}x{in_side}", "-r", str(fps), "-i", "-", "-i", str(wav),
                       "-vf", f"scale={side}:{side}:flags=neighbor:out_color_matrix=bt709:out_range=tv,format=yuv420p",
                       "-c:v", "libx264", "-preset", "slow", "-crf", "18" if analog else "14", "-profile:v", "high",
                       "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
                       "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
stills = {round(float(s) * fps) for s in a.stills.split(",") if s}
for i in range(total):
    t = i / fps
    s = i - pro_frames
    if s < 0:
        frame = prologue.frame(t)
        last_pro_frame = frame
    elif s < song_frames:
        frame = draw(s, s / fps, start + s / fps)
        last_song_frame = frame
        if prologue and s < 0.4 * fps:
            # The typed page gives way to the film through a Bayer dissolve.
            frame = np.where((bayer < (s + 1) / (0.4 * fps))[..., None], frame, last_pro_frame).astype(np.uint8)
    else:
        # The card appears through a Bayer dissolve from the last frame of the film.
        reveal = (s - song_frames + 1) / (0.4 * fps)
        frame = np.where((bayer < reveal)[..., None], credit, last_song_frame).astype(np.uint8)
    assert frame.shape == (grid, grid, 3) and frame.dtype == np.uint8
    if analog:
        frame = analog(np.ascontiguousarray(frame.repeat(a.scale, axis=0).repeat(a.scale, axis=1)), i)
    ff.stdin.write(frame.tobytes())
    if i in stills:
        big = frame if analog else np.asarray(Image.fromarray(frame).resize((side, side), Image.NEAREST))
        Image.fromarray(big).save(work / f"still_{t:05.2f}.png")
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
