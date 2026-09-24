import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "data" / "prices.json"
TIMEOUT = 15

def fetch_json(url: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "GoldAndRates-Social-Automation/1.0"},
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))

def normalize(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("Price API response must be a JSON object")

    karats = payload.get("karats") or payload.get("gold") or {}
    result = {
        "generatedAt": payload.get("generatedAt") or payload.get("updatedAt"),
        "source": payload.get("source", "GoldAndRates"),
        "currency": payload.get("currency", "EGP"),
        "karats": {},
        "status": "ok",
    }

    for karat in (24, 22, 21, 18):
        value = karats.get(str(karat), karats.get(karat))
        if value is None:
            raise ValueError(f"Missing price for {karat}K")
        result["karats"][str(karat)] = value

    return result

def main() -> int:
    url = os.environ.get("GOLDANDRATES_PRICE_API_URL")
    if not url:
        print("GOLDANDRATES_PRICE_API_URL is not configured.", file=sys.stderr)
        return 2

    try:
        normalized = normalize(fetch_json(url))
    except Exception as exc:
        print(f"Price fetch failed: {exc}", file=sys.stderr)
        return 1

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
