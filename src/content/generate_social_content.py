import hashlib
import json
import os
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MARKET_DATA = ROOT / "data" / "market_data.json"
DATA_DIR = ROOT / "data"

TREND_GEOS = ["EG", "SA"]
TREND_URL = "https://trends.google.com/trending/rss?geo={geo}"
REQUEST_TIMEOUT = 15

VOICE_PROFILES = {
    "male": {
        "voice": "ar-EG-ShakirNeural",
        "label": "رجل مصري",
        "locale": "ar-EG",
    },
    "female": {
        "voice": "ar-EG-SalmaNeural",
        "label": "امرأة مصرية",
        "locale": "ar-EG",
    },
}

GOLD_NAME = {
    "EGP": "مصر - الجنيه المصري",
    "SAR": "السعودية - الريال السعودي",
    "AED": "الإمارات - الدرهم الإماراتي",
    "KWD": "الكويت - الدينار الكويتي",
}

GOLD_UNIT = {
    "EGP": "جنيه مصري",
    "SAR": "ريال سعودي",
    "AED": "درهم إماراتي",
    "KWD": "دينار كويتي",
}

FX_UNIT = {
    "EGP": "جنيه مصري",
    "SAR": "ريال سعودي",
    "AED": "درهم إماراتي",
    "KWD": "دينار كويتي",
}

BRAND_HASHTAGS = [
    "#ذهب_وأسعار",
    "#GoldAndRates",
    "#goldandrates",
]

GOLD_KEYWORDS = [
    "سعر الذهب اليوم",
    "أسعار الذهب اليوم",
    "سعر الذهب في مصر",
    "سعر الذهب في السعودية",
    "سعر الذهب في الإمارات",
    "سعر الذهب في الكويت",
    "سعر جرام الذهب",
    "عيار 21",
    "عيار 24",
    "عيار 22",
    "عيار 18",
    "الجنيه الذهب",
    "الذهب اليوم",
]

FX_KEYWORDS = [
    "سعر الدولار اليوم",
    "سعر الدولار مقابل الجنيه",
    "الدولار مقابل الريال السعودي",
    "الدولار مقابل الدرهم الإماراتي",
    "الدولار مقابل الدينار الكويتي",
    "1 دولار بكام",
    "سعر الدولار الآن",
    "أسعار العملات اليوم",
]

DIRECT_GOLD_TERMS = [
    "الذهب", "ذهب", "gold", "gold price", "gold prices",
    "سعر الذهب", "اسعار الذهب", "أسعار الذهب",
    "عيار 18", "عيار 21", "عيار 22", "عيار 24",
    "جرام الذهب", "الجنيه الذهب", "سبائك الذهب", "سبيكة ذهب",
    "xau", "bullion",
]

DIRECT_FX_TERMS = [
    "الدولار", "سعر الدولار", "الدولار اليوم", "دولار مقابل",
    "usd", "exchange rate", "currency", "currencies",
    "سعر الصرف", "أسعار العملات", "الجنيه المصري", "الريال السعودي",
    "الدرهم الإماراتي", "الدينار الكويتي",
]

TREND_RULES = [
    (["سعر الذهب", "اسعار الذهب", "أسعار الذهب"], "#سعر_الذهب"),
    (["عيار 21"], "#عيار_21"),
    (["عيار 24"], "#عيار_24"),
    (["عيار 22"], "#عيار_22"),
    (["عيار 18"], "#عيار_18"),
    (["الجنيه الذهب"], "#الجنيه_الذهب"),
    (["سبائك الذهب", "سبيكة ذهب"], "#سبائك_الذهب"),
    (["الذهب", "ذهب", "gold"], "#الذهب"),
]

GOLD_EVERGREEN = [
    "#سعر_الذهب", "#أسعار_الذهب", "#الذهب", "#ذهب",
    "#سعر_الذهب_اليوم", "#أسعار_الذهب_اليوم",
    "#ذهب_وأسعار", "#Gold", "#GoldPrice",
]

FX_EVERGREEN = [
    "#سعر_الدولار", "#الدولار", "#الدولار_اليوم",
    "#أسعار_العملات", "#سعر_الصرف",
    "#ذهب_وأسعار", "#GoldAndRates", "#goldandrates",
]


def fetch_trending_queries(geo: str) -> list[str]:
    request = urllib.request.Request(
        TREND_URL.format(geo=geo),
        headers={
            "User-Agent": "GoldAndRates-Social-Automation/2.0",
            "Accept": "application/rss+xml, application/xml, text/xml",
        },
    )

    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        root = ET.fromstring(response.read())

    titles: list[str] = []
    for element in root.iter():
        if element.tag.lower().endswith("item"):
            for child in element:
                if child.tag.lower().endswith("title") and child.text:
                    title = re.sub(r"\s+", " ", child.text).strip()
                    if title and title not in titles:
                        titles.append(title)
                    break
    return titles[:30]


def normalize_for_match(value: str) -> str:
    return (
        value.lower()
        .replace("إ", "ا")
        .replace("أ", "ا")
        .replace("آ", "ا")
        .replace("ة", "ه")
    )


def is_relevant_trend(title: str, kind: str) -> bool:
    normalized = normalize_for_match(title)
    terms = DIRECT_GOLD_TERMS if kind == "gold" else DIRECT_FX_TERMS
    return any(
        normalize_for_match(term) in normalized
        for term in terms
    )


def trend_hashtags(trends: list[str], kind: str) -> list[str]:
    out: list[str] = []
    for title in trends:
        normalized = normalize_for_match(title)
        if kind == "currency":
            currency_rules = [
                (["سعر الدولار", "الدولار اليوم", "usd"], "#سعر_الدولار"),
                (["الدولار"], "#الدولار"),
                (["سعر الصرف", "أسعار العملات", "exchange rate"], "#أسعار_العملات"),
                (["الجنيه المصري"], "#الجنيه_المصري"),
                (["الريال السعودي"], "#الريال_السعودي"),
                (["الدرهم الإماراتي"], "#الدرهم_الإماراتي"),
                (["الدينار الكويتي"], "#الدينار_الكويتي"),
            ]
            for needles, tag in currency_rules:
                if any(normalize_for_match(n) in normalized for n in needles):
                    if tag not in out:
                        out.append(tag)
                    if len(out) >= 5:
                        return out
        else:
            for needles, tag in TREND_RULES:
                if any(normalize_for_match(n) in normalized for n in needles):
                    if tag not in out:
                        out.append(tag)
                    if len(out) >= 5:
                        return out
    return out


def load_override() -> dict:
    raw = os.environ.get("OVERRIDE_JSON", "").strip()
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid OVERRIDE_JSON: {exc}")

    path = DATA_DIR / "manual_overrides.json"
    if not path.exists():
        return {}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}

    if not data.get("active"):
        return {}

    override_date = data.get("date")
    current_date = datetime.now(timezone.utc).date().isoformat()
    if override_date and override_date != current_date and not data.get("force"):
        return {}

    return data


def apply_overrides(market_data: dict, override: dict) -> dict:
    if not override:
        return market_data

    data = json.loads(json.dumps(market_data))

    gold_overrides = override.get("gold") or {}
    for code, values in gold_overrides.items():
        if code not in data.get("gold", {}):
            continue
        karats = data["gold"][code].setdefault("karats", {})
        for karat, value in (values or {}).items():
            try:
                number = float(value)
                if number > 0:
                    karats[str(karat)] = number
            except (TypeError, ValueError):
                continue

    fx_overrides = override.get("fx") or {}
    rates = (data.get("fx") or {}).setdefault("rates", {})
    for code, value in fx_overrides.items():
        try:
            number = float(value)
            if number > 0:
                rates[code] = number
        except (TypeError, ValueError):
            continue

    return data


def choose_daily_voice() -> tuple[str, dict]:
    voice_date = os.environ.get(
        "VOICE_DATE",
        datetime.now(timezone.utc).date().isoformat(),
    )
    digest = hashlib.sha256(voice_date.encode("utf-8")).hexdigest()
    gender = "male" if int(digest[0], 16) % 2 == 0 else "female"
    return gender, VOICE_PROFILES[gender]


def money(value: float) -> str:
    number = float(value)
    if abs(number - round(number)) < 0.005:
        return f"{int(round(number)):,}"
    return f"{number:,.2f}"


def fx_money(value: float) -> str:
    number = float(value)
    if number < 1:
        return f"{number:,.4f}"
    return f"{number:,.2f}"


def build_hashtags(kind: str, trends: list[str]) -> list[str]:
    tags = trend_hashtags(trends, kind)
    pool = GOLD_EVERGREEN if kind == "gold" else FX_EVERGREEN

    for tag in tags + pool + BRAND_HASHTAGS:
        if tag not in tags:
            tags.append(tag)
        if len(tags) >= 15:
            break

    return tags


def build_gold_content(data: dict, voice_gender: str, voice_profile: dict, trends: list[str]) -> dict:
    gold = data["gold"]
    hashtags = build_hashtags("gold", trends)
    prices = []

    for code in ["EGP", "SAR", "AED", "KWD"]:
        prices.append({
            "code": code,
            "name": GOLD_NAME[code],
            "unit": GOLD_UNIT[code],
            "karats": gold[code]["karats"],
        })

    hook = (
        "أسعار الذهب اليوم في مصر والسعودية والإمارات والكويت | "
        "سعر جرام الذهب عيار 24 و22 و21 و18."
    )

    voice_lines = [
        "أسعار الذهب اليوم في مصر والسعودية والإمارات والكويت.",
        "مصر: عيار 24 بـ " + money(gold["EGP"]["karats"]["24"]) + "، "
        + "22 بـ " + money(gold["EGP"]["karats"]["22"]) + "، "
        + "21 بـ " + money(gold["EGP"]["karats"]["21"]) + "، "
        + "18 بـ " + money(gold["EGP"]["karats"]["18"]) + " جنيه.",
        "السعودية: عيار 24 بـ " + money(gold["SAR"]["karats"]["24"]) + "، "
        + "22 بـ " + money(gold["SAR"]["karats"]["22"]) + "، "
        + "21 بـ " + money(gold["SAR"]["karats"]["21"]) + "، "
        + "18 بـ " + money(gold["SAR"]["karats"]["18"]) + " ريال.",
        "الإمارات: عيار 24 بـ " + money(gold["AED"]["karats"]["24"]) + "، "
        + "22 بـ " + money(gold["AED"]["karats"]["22"]) + "، "
        + "21 بـ " + money(gold["AED"]["karats"]["21"]) + "، "
        + "18 بـ " + money(gold["AED"]["karats"]["18"]) + " درهم.",
        "الكويت: عيار 24 بـ " + money(gold["KWD"]["karats"]["24"]) + "، "
        + "22 بـ " + money(gold["KWD"]["karats"]["22"]) + "، "
        + "21 بـ " + money(gold["KWD"]["karats"]["21"]) + "، "
        + "18 بـ " + money(gold["KWD"]["karats"]["18"]) + " دينار.",
        "للتفاصيل والتحديثات اليومية: ذهب وأسعار، goldandrates.com."
    ]

    description_parts = [
        hook,
        "",
        "الأسعار:",
    ]

    for item in prices:
        description_parts.append(item["name"])
        for karat in ["24", "22", "21", "18"]:
            description_parts.append(
                f"عيار {karat}: {money(item['karats'][karat])} {item['unit']}"
            )

    description_parts.extend([
        "",
        "ذهب وأسعار",
        "goldandrates.com",
        "",
        " ".join(hashtags),
    ])

    return {
        "kind": "gold",
        "generatedAt": data["generatedAtUtc"],
        "language": "ar",
        "voiceGender": voice_gender,
        "voiceName": voice_profile["voice"],
        "voiceLabel": voice_profile["label"],
        "voiceLocale": voice_profile["locale"],
        "keywords": GOLD_KEYWORDS,
        "trendSignals": trends,
        "hashtags": hashtags,
        "hook": hook,
        "caption": "\n".join(description_parts),
        "description": "\n".join(description_parts),
        "voiceScript": " ".join(voice_lines),
        "videoData": {
            "title": "أسعار الذهب اليوم - ذهب وأسعار",
            "websiteName": "ذهب وأسعار",
            "websiteUrl": "https://goldandrates.com/",
            "markets": prices,
            "hook": hook,
            "hashtags": hashtags,
        },
    }


def build_currency_content(data: dict, voice_gender: str, voice_profile: dict, trends: list[str]) -> dict:
    rates = data["fx"]["rates"]
    hashtags = build_hashtags("currency", trends)

    values = [
        {"code": "EGP", "name": "الجنيه المصري", "value": rates["EGP"], "unit": "جنيه مصري"},
        {"code": "SAR", "name": "الريال السعودي", "value": rates["SAR"], "unit": "ريال سعودي"},
        {"code": "AED", "name": "الدرهم الإماراتي", "value": rates["AED"], "unit": "درهم إماراتي"},
        {"code": "KWD", "name": "الدينار الكويتي", "value": rates["KWD"], "unit": "دينار كويتي"},
    ]

    hook = (
        "سعر الدولار اليوم | 1 دولار بكام بالجنيه المصري والريال السعودي "
        "والدرهم الإماراتي والدينار الكويتي؟"
    )

    voice_script = (
        "سعر الدولار اليوم. "
        + "واحد دولار يساوي "
        + fx_money(rates["EGP"]) + " جنيه مصري. "
        + fx_money(rates["SAR"]) + " ريال سعودي. "
        + fx_money(rates["AED"]) + " درهم إماراتي. "
        + fx_money(rates["KWD"]) + " دينار كويتي. "
        + "للتفاصيل والتحديثات اليومية، تابع ذهب وأسعار على goldandrates.com."
    )

    description_parts = [
        hook,
        "",
        "الأسعار:",
        f"1 دولار = {fx_money(rates['EGP'])} جنيه مصري",
        f"1 دولار = {fx_money(rates['SAR'])} ريال سعودي",
        f"1 دولار = {fx_money(rates['AED'])} درهم إماراتي",
        f"1 دولار = {fx_money(rates['KWD'])} دينار كويتي",
        "",
        "ذهب وأسعار",
        "goldandrates.com",
        "",
        " ".join(hashtags),
    ]

    return {
        "kind": "currency",
        "generatedAt": data["generatedAtUtc"],
        "language": "ar",
        "voiceGender": voice_gender,
        "voiceName": voice_profile["voice"],
        "voiceLabel": voice_profile["label"],
        "voiceLocale": voice_profile["locale"],
        "keywords": FX_KEYWORDS,
        "trendSignals": trends,
        "hashtags": hashtags,
        "hook": hook,
        "caption": "\n".join(description_parts),
        "description": "\n".join(description_parts),
        "voiceScript": voice_script,
        "videoData": {
            "title": "سعر الدولار اليوم - ذهب وأسعار",
            "websiteName": "ذهب وأسعار",
            "websiteUrl": "https://goldandrates.com/",
            "rates": values,
            "hook": hook,
            "hashtags": hashtags,
        },
    }


def fetch_relevant_trends(kind: str) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    signals: list[str] = []

    for geo in TREND_GEOS:
        try:
            titles = fetch_trending_queries(geo)
        except Exception as exc:
            errors.append(f"{geo}: {type(exc).__name__}: {exc}")
            continue

        for title in titles:
            if is_relevant_trend(title, kind) and title not in signals:
                signals.append(title)

    return signals[:5], errors


def main() -> int:
    kind = os.environ.get("VIDEO_TYPE", "gold").strip().lower()
    if kind not in {"gold", "currency"}:
        raise SystemExit("VIDEO_TYPE must be gold or currency")

    if not MARKET_DATA.exists():
        raise SystemExit("data/market_data.json not found")

    data = json.loads(MARKET_DATA.read_text(encoding="utf-8"))
    override = load_override()
    data = apply_overrides(data, override)

    trends, trend_errors = fetch_relevant_trends(kind)
    voice_gender, voice_profile = choose_daily_voice()

    if kind == "gold":
        payload = build_gold_content(data, voice_gender, voice_profile, trends)
        output = DATA_DIR / "gold_content.json"
    else:
        payload = build_currency_content(data, voice_gender, voice_profile, trends)
        output = DATA_DIR / "currency_content.json"

    payload["trendFetchErrors"] = trend_errors
    payload["overrideApplied"] = bool(override)
    payload["overrideSource"] = (
        "workflow_dispatch"
        if os.environ.get("OVERRIDE_JSON")
        else ("data/manual_overrides.json" if override else None)
    )

    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    if kind == "gold":
        egp = data["gold"]["EGP"]["karats"]
        legacy = {
            "generatedAt": data["generatedAtUtc"],
            "source": "ذهب وأسعار",
            "currency": "EGP",
            "karats": {
                "24": egp["24"],
                "22": egp["22"],
                "21": egp["21"],
                "18": egp["18"],
            },
            "status": "ok",
        }
        (DATA_DIR / "prices.json").write_text(
            json.dumps(legacy, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
