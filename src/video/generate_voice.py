import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import edge_tts

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "artifacts"

KIND = os.environ.get("VIDEO_TYPE", "gold").strip().lower()
CONTENT = DATA_DIR / ("gold_content.json" if KIND == "gold" else "currency_content.json")
OUTPUT_AUDIO = OUTPUT_DIR / f"goldandrates_{KIND}_voice.mp3"
OUTPUT_META = OUTPUT_DIR / f"{KIND}_voice.json"


def main() -> None:
    if KIND not in {"gold", "currency"}:
        raise SystemExit("VIDEO_TYPE must be gold or currency")

    if not CONTENT.exists():
        raise SystemExit(f"{CONTENT} not found")

    content = json.loads(CONTENT.read_text(encoding="utf-8"))

    voice = str(content.get("voiceName") or "").strip()
    script = str(content.get("voiceScript") or "").strip()
    segments = content.get("voiceSegments")
    if not isinstance(segments, list) or not segments:
        segments = [script]

    if not voice:
        raise SystemExit("content file is missing voiceName")
    if not script:
        raise SystemExit("content file is missing voiceScript")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    MIN_SECONDS = 20.0
    MAX_SECONDS = 40.0
    RATE = "-5%"
    PITCH = "+0Hz"

    def probe_duration(path: Path) -> float:
        value = subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            text=True,
        ).strip()
        return max(0.01, float(value))

    async def synthesize(text: str, output: Path) -> None:
        communicate = edge_tts.Communicate(
            text=text,
            voice=voice,
            rate=RATE,
            pitch=PITCH,
            volume="+0%",
        )
        await communicate.save(str(output))

    segment_files: list[Path] = []
    durations: list[float] = []

    try:
        for index, segment_text in enumerate(segments, start=1):
            text_value = str(segment_text).strip()
            if not text_value:
                continue
            output = OUTPUT_DIR / f"{KIND}_voice_segment_{index:02d}.mp3"
            output.unlink(missing_ok=True)
            asyncio.run(synthesize(text_value, output))
            duration = probe_duration(output)
            if not output.exists() or output.stat().st_size == 0:
                raise RuntimeError(f"Voice segment was not created: {output}")
            segment_files.append(output)
            durations.append(duration)
            print(f"Voice segment {index}: {duration:.2f}s | {text_value}")

        if not segment_files:
            raise SystemExit("No voice segments were generated")

        list_file = OUTPUT_DIR / f"{KIND}_voice_segments.txt"
        list_file.write_text(
            "".join(f"file '{p.as_posix()}'\n" for p in segment_files),
            encoding="utf-8",
        )

        concat_raw = OUTPUT_DIR / f"{KIND}_voice_concat.mp3"
        run_cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(list_file),
            "-c:a", "libmp3lame",
            "-b:a", "160k",
            str(concat_raw),
        ]
        print(">", " ".join(run_cmd), flush=True)
        subprocess.run(run_cmd, check=True)

        total = probe_duration(concat_raw)
        if total > MAX_SECONDS:
            raise SystemExit(
                f"Generated narration is {total:.2f}s, above the {MAX_SECONDS:.0f}s limit. "
                "Shorten the voiceSegments."
            )

        # Keep the reel at least 20s without changing speech timing:
        # any required padding is assigned to the final CTA scene.
        pad_seconds = max(0.0, MIN_SECONDS - total)
        if pad_seconds > 0:
            padded = OUTPUT_DIR / f"{KIND}_voice_padded.mp3"
            cmd = [
                "ffmpeg", "-y",
                "-i", str(concat_raw),
                "-af", "apad",
                "-t", f"{MIN_SECONDS:.3f}",
                "-c:a", "libmp3lame",
                "-b:a", "160k",
                str(padded),
            ]
            print(">", " ".join(cmd), flush=True)
            subprocess.run(cmd, check=True)
            padded.replace(OUTPUT_AUDIO)
            durations[-1] += pad_seconds
            total = MIN_SECONDS
        else:
            concat_raw.replace(OUTPUT_AUDIO)

    except Exception as exc:
        print(f"Voice generation failed: {exc}", file=sys.stderr)
        raise SystemExit(1)

    timing = {
        "generatedAt": content.get("generatedAt"),
        "videoType": KIND,
        "voiceGender": content.get("voiceGender"),
        "voiceName": voice,
        "voiceLabel": content.get("voiceLabel"),
        "voiceLocale": content.get("voiceLocale"),
        "speechRate": RATE,
        "speechPitch": PITCH,
        "durationSeconds": round(total, 3),
        "segments": [
            {
                "index": index,
                "text": str(text).strip(),
                "durationSeconds": round(duration, 3),
            }
            for index, (text, duration) in enumerate(zip(segments, durations), start=1)
        ],
        "audioFile": str(OUTPUT_AUDIO.relative_to(ROOT)),
    }

    OUTPUT_META.write_text(
        json.dumps(timing, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Generated voice: {voice}")
    print(f"Audio: {OUTPUT_AUDIO}")
    print(f"Duration: {total:.2f}s")




if __name__ == "__main__":
    main()
