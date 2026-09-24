import concurrent.futures
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "data" / "market_data.json"

GOLD_CODES = ["EGP", "SAR", "AED", "KWD"]
GOLD_API_URL = os.environ.get("GOLDANDRATES_PRICE_API_URL", "").strip()
FX_URL = "https://open.er-api.com/v6/latest/USD"

TIMEOUT = 60
MAX_ATTEMPTS = 3
RETRY_DELAYS = (3, 7)


def fetch_json(url: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "GoldAndRates-Social-Automation/3.0",
            "Accept": "application/json,text/plain,*/*",
            "Cache-Control": "no-cache",
        },
    )

    last_error: Exception | None = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            if attempt < MAX_ATTEMPTS:
                delay = RETRY_DELAYS[attempt - 1]
                print(
                    f"Request attempt {attempt}/{MAX_ATTEMPTS} failed: {exc}. "
                    f"Retrying in {delay}s...",
                    file=sys.stderr,
                )
                time.sleep(delay)

    raise last_error or RuntimeError("Request failed")


def gold_url(code: str) -> str:
    if not GOLD_API_URL:
        raise RuntimeError("GOLDANDRATES_PRICE_API_URL is not configured")

    parsed = urllib.parse.urlsplit(GOLD_API_URL)
    params = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
    params["code"] = code
    query = urllib.parse.urlencode(params)

    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, query, parsed.fragment)
    )


def fetch_gold(code: str) -> tuple[str, dict]:
    payload = fetch_json(gold_url(code))

    if not isinstance(payload, dict):
        raise ValueError(f"{code}: API response is not a JSON object")

    karats = payload.get("karats") or {}
    required = ("24", "22", "21", "18")

    if not all(k in karats and float(karats[k] or 0) > 0 for k in required):
        raise ValueError(f"{code}: missing usable 24K/22K/21K/18K prices")

    return code, {
        "country": payload.get("country", code),
        "code": code,
        "status": payload.get("status", "unknown"),
        "mode": payload.get("mode", ""),
        "source": payload.get("source", "GoldAndRates"),
        "updatedAt": payload.get("generatedAt") or payload.get("updatedAt"),
        "karats": {k: float(karats[k]) for k in required},
        "buy": {
            k: float((payload.get("buy") or {}).get(k, 0) or 0)
            for k in required
        },
    }


def fetch_fx() -> dict:
    payload = fetch_json(FX_URL)
    rates = payload.get("rates") or {}
    needed = ["EGP", "SAR", "AED", "KWD"]

    if not all(float(rates.get(k, 0) or 0) > 0 for k in needed):
        raise ValueError("FX API is missing EGP/SAR/AED/KWD rates")

    return {
        "base": payload.get("base_code") or payload.get("base") or "USD",
        "provider": "open.er-api.com",
        "updatedAt": payload.get("time_last_update_utc"),
        "rates": {k: float(rates[k]) for k in needed},
    }


def main() -> int:
    market_data: dict = {
        "generatedAtUtc": None,
        "gold": {},
        "fx": None,
        "errors": [],
        "status": "ok",
    }

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {code: executor.submit(fetch_gold, code) for code in GOLD_CODES}
        for code, future in futures.items():
            try:
                key, value = future.result()
                market_data["gold"][key] = value
            except Exception as exc:
                market_data["errors"].append(f"{code}: {exc}")

    try:
        market_data["fx"] = fetch_fx()
    except Exception as exc:
        market_data["errors"].append(f"FX: {exc}")

    if set(market_data["gold"].keys()) != set(GOLD_CODES):
        market_data["status"] = "error"
    if market_data["fx"] is None:
        market_data["status"] = "error"

    if market_data["status"] != "ok":
        print(
            "Market data fetch failed: " + " | ".join(market_data["errors"]),
            file=sys.stderr,
        )
        return 1

    market_data["generatedAtUtc"] = time.strftime(
        "%Y-%m-%dT%H:%M:%SZ",
        time.gmtime(),
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(market_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
