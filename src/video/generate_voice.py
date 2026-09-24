import asyncio
import json
import os
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

    async def synthesize() -> None:
        communicate = edge_tts.Communicate(
            text=script,
            voice=voice,
            rate="+0%",
            volume="+0%",
        )
        await communicate.save(str(OUTPUT_AUDIO))

    try:
        asyncio.run(synthesize())
    except Exception as exc:
        print(f"Voice generation failed: {exc}", file=sys.stderr)
        raise SystemExit(1)

    metadata = {
        "generatedAt": content.get("generatedAt"),
        "videoType": KIND,
        "voiceGender": content.get("voiceGender"),
        "voiceName": voice,
        "voiceLabel": content.get("voiceLabel"),
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
