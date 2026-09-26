import math
import struct
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "artifacts"
WAV = ARTIFACTS / "news_bulletin_music.wav"
SR = 44100
DURATION = 42.0
TAU = 2.0 * math.pi

# Original energetic financial-news bulletin bed.
# No vocals, no samples, no copyrighted melody: punchy kick, snare, ticking hats,
# low synth pulse, bright brass-like stabs and a repeating headline motif.
def env(t, attack=0.008, release=0.20):
    return min(1.0, t / attack) * min(1.0, max(0.0, (release - t) / release))

def kick(t):
    if t >= 0.14:
        return 0.0
    f = 145.0 - 105.0 * (t / 0.14)
    return 0.34 * math.sin(TAU * f * t) * math.exp(-28.0 * t)

def snare(t):
    if t >= 0.11:
        return 0.0
    noise = math.sin(TAU * 1800 * t) + 0.55 * math.sin(TAU * 3200 * t) + 0.25 * math.sin(TAU * 5100 * t)
    return 0.12 * noise * math.exp(-34.0 * t)

def hat(t):
    if t >= 0.025:
        return 0.0
    return 0.035 * math.sin(TAU * 7600 * t) * math.exp(-110.0 * t)

def stab(t, freq):
    return 0.075 * env(t, 0.008, 0.30) * (
        math.sin(TAU * freq * t) +
        0.32 * math.sin(TAU * freq * 2.01 * t) +
        0.18 * math.sin(TAU * freq * 3.02 * t)
    )

def main():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    roots = [220.0, 246.94, 261.63, 293.66, 329.63, 369.99, 392.0, 440.0]
    with wave.open(str(WAV), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        frames = bytearray()
        total = int(SR * DURATION)
        step = 60.0 / 132.0
        for n in range(total):
            t = n / SR
            beat_no = int(t / step)
            p = t % step
            section = int(t // 5.25)
            root = roots[min(section, len(roots) - 1)]
            val = kick(p)
            half = t % (step * 2)
            if abs(half - step) < 0.002:
                val += snare((half - step) + 0.001)
            if p < 0.025 or abs(p - step / 2) < 0.001:
                val += hat(p if p < 0.025 else p - step / 2)
            # Driving eighth-note synth pulse.
            pulse_p = t % (step / 2)
            pulse = 0.045 * math.sin(TAU * root * 2 * pulse_p) * math.exp(-5.0 * pulse_p)
            val += pulse
            # Headline stabs on selected beats; brighter as the bulletin progresses.
            if beat_no % 8 in (0, 3, 6):
                val += stab(p, root * (2.0 if beat_no % 16 == 0 else 1.5))
            # Rising ticker motif every 8 beats.
            motif = [root, root * 1.25, root * 1.5, root * 2.0]
            m = beat_no % 8
            if m in (1, 3, 5, 7):
                mt = t % step
                val += 0.055 * env(mt, 0.006, 0.20) * math.sin(TAU * motif[(m // 2) % 4] * mt)
            # Continuous low bed.
            val += 0.018 * math.sin(TAU * root * t)
            fade = min(1.0, t / 0.7, max(0.0, (DURATION - t) / 1.2))
            sample = max(-0.82, min(0.82, val * fade * 1.35))
            frames.extend(struct.pack("<h", int(sample * 32767)))
        wf.writeframes(frames)
    print(f"Generated energetic original news music WAV: {WAV}")

if __name__ == "__main__":
    main()
