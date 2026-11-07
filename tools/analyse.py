# Measures a take: duration, tempo, beats, loudness per second, and the strongest sustained rise in energy.
# It also writes per-frame band levels (0 to 1) that the renderer reads.
# Usage: python tools/analyse.py <take.mp3> [--fps 30]
import argparse, json
from pathlib import Path
import librosa
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("take")
ap.add_argument("--fps", type=int, default=30)
a = ap.parse_args()

y, sr = librosa.load(a.take, sr=44100, mono=True)
dur = len(y) / sr
hop = int(round(sr / a.fps))
S = np.abs(librosa.stft(y, n_fft=2048, hop_length=hop))
f = librosa.fft_frequencies(sr=sr, n_fft=2048)


def band(lo, hi):
    v = S[(f >= lo) & (f < hi)].mean(axis=0)
    return np.clip(v / max(np.percentile(v, 98), 1e-9), 0, 1)


rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=hop)[0]
level = np.clip(rms / max(np.percentile(rms, 98), 1e-9), 0, 1)
onset = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
tempo, beats = librosa.beat.beat_track(onset_envelope=onset, sr=sr, hop_length=hop)
beat_times = librosa.frames_to_time(beats, sr=sr, hop_length=hop).tolist()

# The chorus test: the second with the largest gain of the next 4 s over the previous 4 s.
per_s = np.array([rms[int(i * a.fps):int((i + 1) * a.fps)].mean() for i in range(int(dur))])
gain = np.zeros_like(per_s)
for i in range(4, len(per_s) - 4):
    gain[i] = per_s[i:i + 4].mean() / max(per_s[i - 4:i].mean(), 1e-9)
rise = int(np.argmax(gain))
snapped = min(beat_times, key=lambda t: abs(t - rise)) if beat_times else float(rise)

out = {
    "duration": round(dur, 3), "fps": a.fps, "tempo": round(float(np.atleast_1d(tempo)[0]), 1),
    "beats": [round(t, 3) for t in beat_times], "rise_at": round(snapped, 3), "rise_gain": round(float(gain[rise]), 2),
    "loudness_per_second": [round(float(v / per_s.max()), 2) for v in per_s],
    "level": np.round(level, 3).tolist(), "bass": np.round(band(20, 180), 3).tolist(),
    "mid": np.round(band(180, 2500), 3).tolist(), "high": np.round(band(2500, 12000), 3).tolist(),
}
path = Path(a.take).with_suffix(".analysis.json")
path.write_text(json.dumps(out))
print(path.name, {k: out[k] for k in ("duration", "tempo", "rise_at", "rise_gain")}, "beats", len(beat_times))
print("  loudness/s", " ".join(f"{v:.1f}" for v in out["loudness_per_second"]))
