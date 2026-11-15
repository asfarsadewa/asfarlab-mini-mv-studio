# Radio mode: an optional audio pass that makes the song sound like it comes through an old AM or shortwave radio.
# A film turns it on in brief.json:
#   "radio": true   uses the studio default: AM, intensity 0.6, full mix, the tuning intro, seed 1.
#   "radio": {"mode": "sw", "tune": false}   changes any field. The others keep the default.
# render.py runs it on the take before the mastering, so the radio take is still mastered to -14 LUFS.
# Ported from the make-radio-sound tool: band-limit, tilt, saturation, slow station fade, hiss and crackles.
# Added for the studio: a fixed seed for repeatable renders, a wet/dry mix, and a tuning sweep at the start.
# Usage on its own: python tools/radio.py <in.mp3> <out.wav> [--mode am|sw] [--intensity 0.6] [--mix 1] [--tune] [--seed 1]
import argparse, subprocess, wave
import numpy as np
from scipy import signal as sps

RATE = 22050   # Real AM and shortwave arrive band-limited, mono. The render resamples to 48 kHz stereo after.
MODES = {
    "am": {"band": (200.0, 4500.0), "drive": 2.2, "fade": 0.18, "hiss": 0.025, "crackle": 1.5, "tilt_db": -3.0},
    "sw": {"band": (350.0, 2800.0), "drive": 3.0, "fade": 0.45, "hiss": 0.05, "crackle": 5.0, "tilt_db": -5.0},
}


def bandpass(low, high, order=6):
    nyq = 0.5 * RATE
    return sps.butter(order, [low / nyq, high / nyq], btype="band", output="sos")


def load_mono(path):
    raw = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(RATE),
                          "-f", "s16le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0


def save_wav(x, path):
    pcm = (np.clip(x, -0.98, 0.98) * 32767).astype(np.int16).tobytes()
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm)


def noise_band(n, band, rng):
    return sps.sosfiltfilt(bandpass(*band, order=4), rng.standard_normal(n)).astype(np.float32)


def radio(x, mode="am", intensity=0.6, mix=1.0, tune=False, seed=1):
    """x: mono samples at RATE. Returns mono samples at RATE."""
    cfg = MODES[mode]
    rng = np.random.default_rng(seed)
    n = len(x)
    band = cfg["band"]
    # Tilt: a little less top, as from a small speaker.
    low = sps.sosfiltfilt(sps.butter(2, 1500 / (0.5 * RATE), btype="low", output="sos"), x)
    y = low + 10 ** (cfg["tilt_db"] / 20) * (x - low)
    y = sps.sosfiltfilt(bandpass(*band), y).astype(np.float32)
    y = y / (np.max(np.abs(y)) or 1.0) * 0.9
    y = np.tanh(cfg["drive"] * y) / np.tanh(cfg["drive"])
    # The station drifts in and out slowly.
    t = np.arange(n) / RATE
    f1, f2 = 0.12 + rng.random() * 0.1, 0.6 + rng.random() * 0.3
    lfo = 0.7 * np.sin(2 * np.pi * f1 * t + rng.random() * 6.28) + 0.3 * np.sin(2 * np.pi * f2 * t + rng.random() * 6.28)
    y = y * (1.0 - cfg["fade"] * intensity * (0.5 - 0.5 * lfo))
    hiss = noise_band(n, band, rng)
    y = y + hiss / (np.max(np.abs(hiss)) or 1.0) * cfg["hiss"] * intensity
    crack = np.zeros(n, np.float32)
    for _ in range(int(rng.poisson(cfg["crackle"] * intensity * n / RATE))):
        s = int(rng.integers(0, n))
        length = max(8, int(RATE * rng.uniform(0.004, 0.022)))
        e = min(n, s + length)
        crack[s:e] += rng.uniform(0.4, 1.0) * np.exp(-np.linspace(0, 6, e - s)) * rng.standard_normal(e - s)
    crack = sps.sosfiltfilt(bandpass(*band, order=4), crack)
    y = y + crack / (np.max(np.abs(crack)) or 1.0) * 0.6 * (0.4 + 0.6 * intensity) * (intensity > 0)
    # Soft compression, as a radio's limiter.
    a = np.abs(y)
    y = np.where(a > 0.5, np.sign(y) * (0.5 + (a - 0.5) / 3.0), y) * 10 ** (2 / 20)
    if tune:
        # Tuning in: static and a sliding whistle for 1.2 s, then the station locks in over 0.8 s.
        k = int(1.2 * RATE)
        lock = int(0.8 * RATE)
        static = noise_band(k + lock, (300, 5000), rng)
        static = static / (np.max(np.abs(static)) or 1.0) * 0.45
        tt = np.arange(k + lock) / RATE
        whistle = 0.12 * np.sin(2 * np.pi * np.cumsum(2400 - 1900 * tt / tt[-1]) / RATE)
        ramp = np.clip((np.arange(k + lock) - k) / lock, 0, 1)
        m = min(n, k + lock)
        y[:m] = y[:m] * ramp[:m] + (static[:m] + whistle[:m]) * (1 - ramp[:m])
    y = y.astype(np.float32)
    if mix < 1:
        y = mix * y + (1 - mix) * x * (np.max(np.abs(y)) / (np.max(np.abs(x)) or 1.0))
    return y


DEFAULT = {"mode": "am", "intensity": 0.6, "mix": 1.0, "tune": True, "seed": 1}


def render_take(src, dst, cfg, seed=1):
    """Writes a radio version of the take to dst as a mono wav. render.py masters it after."""
    cfg = {**DEFAULT, **(cfg if isinstance(cfg, dict) else {})}
    x = load_mono(src)
    y = radio(x, cfg.get("mode", "am"), float(cfg.get("intensity", 0.6)), float(cfg.get("mix", 1.0)), bool(cfg.get("tune", True)),
              int(cfg.get("seed", seed)))
    save_wav(y, dst)
    return dst


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--mode", choices=sorted(MODES), default="am")
    ap.add_argument("--intensity", type=float, default=0.6)
    ap.add_argument("--mix", type=float, default=1.0)
    ap.add_argument("--tune", action="store_true")
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    render_take(a.input, a.output, {"mode": a.mode, "intensity": a.intensity, "mix": a.mix, "tune": a.tune, "seed": a.seed})
    print(f"Wrote {a.output}")
