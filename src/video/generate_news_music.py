import math
import struct
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "artifacts"
WAV = ARTIFACTS / "news_bulletin_music.wav"
MP3 = ARTIFACTS / "news_bulletin_music.mp3"
SR = 44100
DURATION = 24.0
TAU = 2.0 * math.pi

# Original, royalty-free procedural news-bed: short brass/synth pulses,
# low kick, restrained hi-hat and a rising headline motif. No vocals.
def tone(t, freq, attack=0.01, release=0.18, amp=0.12):
    env = min(1.0, t / attack) * min(1.0, max(0.0, (release - t) / release))
    return amp * env * (math.sin(TAU * freq * t) + 0.28 * math.sin(TAU * freq * 2 * t))

def beat(t, bpm=126):
    step = 60.0 / bpm
    p = t % step
    out = 0.0
    # Kick on quarter notes.
    if p < 0.12:
        f = 110.0 - 65.0 * (p / 0.12)
        out += 0.24 * math.sin(TAU * f * p) * math.exp(-22.0 * p)
    # Snare on beats 2 and 4.
    half = step * 2
    q = (t % half)
    if abs(q - step) < 0.045 or abs(q - (half - 0.02)) < 0.045:
        out += 0.07 * math.sin(TAU * 1800 * p) * math.exp(-35.0 * p)
    # Light hi-hat on eighth notes.
    eighth = step / 2
    hp = t % eighth
    if hp < 0.018:
        out += 0.025 * math.sin(TAU * 7000 * hp) * math.exp(-90.0 * hp)
    return out

def main():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    notes = [220.0, 277.18, 329.63, 440.0, 554.37, 659.25]
    with wave.open(str(WAV), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        frames = bytearray()
        total = int(SR * DURATION)
        for n in range(total):
            t = n / SR
            section = int(t // 4.0)
            local = t % 4.0
            idx = min(section, len(notes) - 1)
            root = notes[idx]
            val = beat(t)
            # Pulsing headline motif; quieter under the final CTA.
            motif = [root, root * 1.25, root * 1.5, root * 2.0]
            pos = int(local * 2.0) % 4
            mt = local % 0.5
            val += tone(mt, motif[pos], attack=0.015, release=0.34, amp=0.105)
            # Soft sustained pad.
            val += 0.025 * math.sin(TAU * root * t)
            # Fade in/out.
            fade = min(1.0, t / 0.8, max(0.0, (DURATION - t) / 1.0))
            sample = max(-0.75, min(0.75, val * fade))
            frames.extend(struct.pack("<h", int(sample * 32767)))
        wf.writeframes(frames)
    print(f"Generated original news music WAV: {WAV}")

if __name__ == "__main__":
    main()
