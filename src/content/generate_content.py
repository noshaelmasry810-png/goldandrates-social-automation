import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRICES = ROOT / "data" / "prices.json"
OUTPUT = ROOT / "data" / "content.json"

def main() -> None:
    data = json.loads(PRICES.read_text(encoding="utf-8"))
    if data.get("status") != "ok":
        raise SystemExit("prices.json does not contain fresh price data")

    p = data["karats"]
    text = (
        "أسعار الذهب اليوم\n"
        f"عيار 24: {p['24']} {data['currency']}\n"
        f"عيار 22: {p['22']} {data['currency']}\n"
        f"عيار 21: {p['21']} {data['currency']}\n"
        f"عيار 18: {p['18']} {data['currency']}"
    )

    payload = {
        "generatedAt": data["generatedAt"],
        "language": "ar",
        "caption": text,
        "voiceScript": text,
        "videoData": {"title": "أسعار الذهب اليوم", "karats": p, "currency": data["currency"]},
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

if __name__ == "__main__":
    main()
