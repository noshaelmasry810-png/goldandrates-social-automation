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

    if not voice:
        raise SystemExit("content file is missing voiceName")
    if not script:
        raise SystemExit("content file is missing voiceScript")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    TARGET_SECONDS = 30.0
    MIN_SECONDS = 20.0
    MAX_SECONDS = 40.0

    def probe_duration() -> float:
        value = subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(OUTPUT_AUDIO),
            ],
            text=True,
        ).strip()
        return float(value)

    async def synthesize(rate: str) -> None:
        communicate = edge_tts.Communicate(
            text=script,
            voice=voice,
            rate=rate,
            volume="+0%",
        )
        await communicate.save(str(OUTPUT_AUDIO))

    try:
        asyncio.run(synthesize("+0%"))
        baseline = probe_duration()

        # Aim near 30s without exceeding the service's practical ±100% range.
        requested = round((baseline / TARGET_SECONDS - 1.0) * 100)
        requested = max(-50, min(100, requested))

        if abs(baseline - TARGET_SECONDS) > 1.0:
            rate = f"{requested:+d}%"
            print(f"Baseline duration: {baseline:.2f}s; retiming voice with rate {rate}")
            asyncio.run(synthesize(rate))
        else:
            rate = "+0%"

        duration = probe_duration()

        if duration > MAX_SECONDS and rate != "+100%":
            print("Voice is still above 40s; retrying at +100% rate.")
            asyncio.run(synthesize("+100%"))
            duration = probe_duration()
            rate = "+100%"

        if duration > MAX_SECONDS:
            raise SystemExit(
                f"Generated narration is {duration:.2f}s, above the {MAX_SECONDS:.0f}s limit. "
                "Shorten the voiceScript."
            )

        if duration < MIN_SECONDS:
            print(f"Voice is {duration:.2f}s; keeping it because the script is already compact.")
        
    except Exception as exc:
        print(f"Voice generation failed: {exc}", file=sys.stderr)
        raise SystemExit(1)

    metadata = {
        "generatedAt": content.get("generatedAt"),
        "videoType": KIND,
        "voiceGender": content.get("voiceGender"),
        "voiceName": voice,
        "voiceLabel": content.get("voiceLabel"),
        "speechRate": rate,
        "durationSeconds": round(duration, 3),
        "voiceLocale": content.get("voiceLocale"),
        "audioFile": str(OUTPUT_AUDIO.relative_to(ROOT)),
    }

    OUTPUT_META.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Generated voice: {voice}")
    print(f"Audio: {OUTPUT_AUDIO}")


if __name__ == "__main__":
    main()
