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
    "male": {"voice": "ar-EG-ShakirNeural", "label": "رجل مصري", "locale": "ar-EG"},
    "female": {"voice": "ar-EG-SalmaNeural", "label": "امرأة مصرية", "locale": "ar-EG"},
}

GOLD_NAME = {"EGP": "مصر - الجنيه المصري", "SAR": "السعودية - الريال السعودي", "AED": "الإمارات - الدرهم الإماراتي", "KWD": "الكويت - الدينار الكويتي"}
GOLD_UNIT = {"EGP": "جنيه مصري", "SAR": "ريال سعودي", "AED": "درهم إماراتي", "KWD": "دينار كويتي"}
FX_UNIT = {"EGP": "جنيه مصري", "SAR": "ريال سعودي", "AED": "درهم إماراتي", "KWD": "دينار كويتي"}
BRAND_HASHTAGS = ["#ذهب_وأسعار", "#GoldAndRates", "#goldandrates"]
GOLD_KEYWORDS = ["سعر الذهب اليوم", "أسعار الذهب اليوم", "سعر الذهب في مصر", "سعر الذهب في السعودية", "سعر الذهب في الإمارات", "سعر الذهب في الكويت", "سعر جرام الذهب", "عيار 21", "عيار 24", "عيار 22", "عيار 18", "الجنيه الذهب", "الذهب اليوم"]
FX_KEYWORDS = ["سعر الدولار اليوم", "سعر الدولار مقابل الجنيه", "الدولار مقابل الريال السعودي", "الدولار مقابل الدرهم الإماراتي", "الدولار مقابل الدينار الكويتي", "1 دولار بكام", "سعر الدولار الآن", "أسعار العملات اليوم"]
DIRECT_GOLD_TERMS = ["الذهب", "ذهب", "gold", "gold price", "gold prices", "سعر الذهب", "اسعار الذهب", "أسعار الذهب", "عيار 18", "عيار 21", "عيار 22", "عيار 24", "جرام الذهب", "الجنيه الذهب", "سبائك الذهب", "سبيكة ذهب", "xau", "bullion"]
DIRECT_FX_TERMS = ["الدولار", "سعر الدولار", "الدولار اليوم", "دولار مقابل", "usd", "exchange rate", "currency", "currencies", "سعر الصرف", "أسعار العملات", "الجنيه المصري", "الريال السعودي", "الدرهم الإماراتي", "الدينار الكويتي"]
TREND_RULES = [(["سعر الذهب", "اسعار الذهب", "أسعار الذهب"], "#سعر_الذهب"), (["عيار 21"], "#عيار_21"), (["عيار 24"], "#عيار_24"), (["عيار 22"], "#عيار_22"), (["عيار 18"], "#عيار_18"), (["الجنيه الذهب"], "#الجنيه_الذهب"), (["سبائك الذهب", "سبيكة ذهب"], "#سبائك_الذهب"), (["الذهب", "ذهب", "gold"], "#الذهب")]
GOLD_EVERGREEN = ["#سعر_الذهب", "#أسعار_الذهب", "#الذهب", "#ذهب", "#سعر_الذهب_اليوم", "#أسعار_الذهب_اليوم", "#ذهب_وأسعار", "#Gold", "#GoldPrice"]
FX_EVERGREEN = ["#سعر_الدولار", "#الدولار", "#الدولار_اليوم", "#أسعار_العملات", "#سعر_الصرف", "#ذهب_وأسعار", "#GoldAndRates", "#goldandrates"]

def fetch_trending_queries(geo: str) -> list[str]:
    request = urllib.request.Request(TREND_URL.format(geo=geo), headers={"User-Agent": "GoldAndRates-Social-Automation/2.0", "Accept": "application/rss+xml, application/xml, text/xml"})
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        root = ET.fromstring(response.read())
    titles = []
    for element in root.iter():
        if element.tag.lower().endswith("item"):
            for child in element:
                if child.tag.lower().endswith("title") and child.text:
                    title = re.sub(r"\s+", " ", child.text).strip()
                    if title and title not in titles: titles.append(title)
                    break
    return titles[:30]

def normalize_for_match(value: str) -> str:
    return value.lower().replace("إ", "ا").replace("أ", "ا").replace("آ", "ا").replace("ة", "ه")

def is_relevant_trend(title: str, kind: str) -> bool:
    normalized = normalize_for_match(title)
    terms = DIRECT_GOLD_TERMS if kind == "gold" else DIRECT_FX_TERMS
    return any(normalize_for_match(term) in normalized for term in terms)

def trend_hashtags(trends: list[str], kind: str) -> list[str]:
    out = []
    for title in trends:
        normalized = normalize_for_match(title)
        if kind == "currency":
            rules = [(["سعر الدولار", "الدولار اليوم", "usd"], "#سعر_الدولار"), (["الدولار"], "#الدولار"), (["سعر الصرف", "أسعار العملات", "exchange rate"], "#أسعار_العملات"), (["الجنيه المصري"], "#الجنيه_المصري"), (["الريال السعودي"], "#الريال_السعودي"), (["الدرهم الإماراتي"], "#الدرهم_الإماراتي"), (["الدينار الكويتي"], "#الدينار_الكويتي")]
            for needles, tag in rules:
                if any(normalize_for_match(n) in normalized for n in needles):
                    if tag not in out: out.append(tag)
                    if len(out) >= 5: return out
        else:
            for needles, tag in TREND_RULES:
                if any(normalize_for_match(n) in normalized for n in needles):
                    if tag not in out: out.append(tag)
                    if len(out) >= 5: return out
    return out

def load_override() -> dict:
    raw = os.environ.get("OVERRIDE_JSON", "").strip()
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, dict): return data
        except json.JSONDecodeError as exc: raise SystemExit(f"Invalid OVERRIDE_JSON: {exc}")
    path = DATA_DIR / "manual_overrides.json"
    if not path.exists(): return {}
    try: data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError: return {}
    if not data.get("active"): return {}
    override_date = data.get("date")
    current_date = datetime.now(timezone.utc).date().isoformat()
    if override_date and override_date != current_date and not data.get("force"): return {}
    return data

def apply_overrides(market_data: dict, override: dict) -> dict:
    if not override: return market_data
    data = json.loads(json.dumps(market_data))
    for code, values in (override.get("gold") or {}).items():
        if code not in data.get("gold", {}): continue
        karats = data["gold"][code].setdefault("karats", {})
        for karat, value in (values or {}).items():
            try:
                number = float(value)
                if number > 0: karats[str(karat)] = number
            except (TypeError, ValueError): pass
    rates = (data.get("fx") or {}).setdefault("rates", {})
    for code, value in (override.get("fx") or {}).items():
        try:
            number = float(value)
            if number > 0: rates[code] = number
        except (TypeError, ValueError): pass
    return data

def choose_daily_voice() -> tuple[str, dict]:
    gender = os.environ.get("VOICE_GENDER", "male").strip().lower()
    if gender not in VOICE_PROFILES: gender = "male"
    return gender, VOICE_PROFILES[gender]

def money(value: float) -> str:
    number = float(value)
    return f"{int(round(number)):,}" if abs(number - round(number)) < 0.005 else f"{number:,.2f}"

def fx_money(value: float) -> str:
    number = float(value)
    return f"{number:,.4f}" if number < 1 else f"{number:,.2f}"

def build_hashtags(kind: str, trends: list[str]) -> list[str]:
    tags = trend_hashtags(trends, kind)
    pool = GOLD_EVERGREEN if kind == "gold" else FX_EVERGREEN
    for tag in tags + pool + BRAND_HASHTAGS:
        if tag not in tags: tags.append(tag)
        if len(tags) >= 15: break
    return tags

def build_gold_content(data: dict, voice_gender: str, voice_profile: dict, trends: list[str]) -> dict:
    gold = data["gold"]
    hashtags = build_hashtags("gold", trends)
    prices = [{"code": code, "name": GOLD_NAME[code], "unit": GOLD_UNIT[code], "karats": gold[code]["karats"]} for code in ["EGP", "SAR", "AED", "KWD"]]
    hook = "أسعار الذهب اليوم في مصر والسعودية والإمارات والكويت | سعر جرام الذهب عيار 24 و22 و21 و18."
    voice_lines = [
        "أسعار الذهب النهارده من موقع ذهب وأسعار.",
        "في مصر، جرام الذهب عيار 21 بـ " + money(gold["EGP"]["karats"]["21"]) + " جنيه.",
        "في السعودية، جرام الذهب عيار 21 بـ " + money(gold["SAR"]["karats"]["21"]) + " ريال.",
        "وفي الإمارات، جرام الذهب عيار 21 بـ " + money(gold["AED"]["karats"]["21"]) + " درهم.",
        "أما الكويت، فجرام الذهب عيار 21 بـ " + money(gold["KWD"]["karats"]["21"]) + " دينار.",
        "تابعوا موقع ذهب وأسعار على www.goldandrates.com."
    ]
    description_parts = [hook, "", "الأسعار:"]
    for item in prices:
        description_parts.append(item["name"])
        for karat in ["24", "22", "21", "18"]: description_parts.append(f"عيار {karat}: {money(item['karats'][karat])} {item['unit']}")
    description_parts.extend(["", "موقع ذهب وأسعار", "www.goldandrates.com", "", " ".join(hashtags)])
    return {"kind": "gold", "generatedAt": data["generatedAtUtc"], "language": "ar", "voiceGender": voice_gender, "voiceName": voice_profile["voice"], "voiceLabel": voice_profile["label"], "voiceLocale": voice_profile["locale"], "keywords": GOLD_KEYWORDS, "trendSignals": trends, "hashtags": hashtags, "hook": hook, "caption": "\n".join(description_parts), "description": "\n".join(description_parts), "prices": prices, "voiceScript": " ".join(voice_lines), "voiceSegments": voice_lines}

def build_currency_content(data: dict, voice_gender: str, voice_profile: dict, trends: list[str]) -> dict:
    rates = data["fx"]["rates"]
    hashtags = build_hashtags("currency", trends)
    pairs = [{"code": code, "unit": FX_UNIT[code], "rate": rates[code]} for code in ["EGP", "SAR", "AED", "KWD"]]
    hook = "أسعار العملات اليوم | سعر الدولار مقابل الجنيه والريال والدرهم والدينار."
    voice_segments = [
        "بصّوا معانا على سعر الدولار النهارده.",
        "الدولار النهارده بـ " + fx_money(rates["EGP"]) + " جنيه مصري.",
        "في السعودية، الدولار بـ " + fx_money(rates["SAR"]) + " ريال.",
        "وفي الإمارات، الدولار بـ " + fx_money(rates["AED"]) + " درهم.",
        "أما الكويت، فالدولار بـ " + fx_money(rates["KWD"]) + " دينار.",
        "ولكل الأسعار والتحديثات أول بأول، تابعوا موقع ذهب وأسعار على www.goldandrates.com."
    ]
    parts = [hook, "", "أسعار صرف الدولار:"] + [f"1 دولار = {fx_money(p['rate'])} {p['unit']}" for p in pairs] + ["", "موقع ذهب وأسعار", "www.goldandrates.com", "", " ".join(hashtags)]
    return {"kind": "currency", "generatedAt": data["generatedAtUtc"], "language": "ar", "voiceGender": voice_gender, "voiceName": voice_profile["voice"], "voiceLabel": voice_profile["label"], "voiceLocale": voice_profile["locale"], "keywords": FX_KEYWORDS, "trendSignals": trends, "hashtags": hashtags, "hook": hook, "caption": "\n".join(parts), "description": "\n".join(parts), "pairs": pairs, "voiceScript": " ".join(voice_segments), "voiceSegments": voice_segments}

def main() -> None:
    if not MARKET_DATA.exists(): raise SystemExit(f"Missing {MARKET_DATA}")
    market_data = json.loads(MARKET_DATA.read_text(encoding="utf-8"))
    market_data = apply_overrides(market_data, load_override())
    voice_gender, voice_profile = choose_daily_voice()
    results = {}
    for kind in ["gold", "currency"]:
        trends = []
        for geo in TREND_GEOS:
            try: trends.extend(fetch_trending_queries(geo))
            except Exception as exc: print(f"Trend fetch failed for {geo}: {exc}")
        relevant = []
        for trend in trends:
            if is_relevant_trend(trend, kind) and trend not in relevant: relevant.append(trend)
        results[kind] = build_gold_content(market_data, voice_gender, voice_profile, relevant) if kind == "gold" else build_currency_content(market_data, voice_gender, voice_profile, relevant)
    out = DATA_DIR / "social_content.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Generated social content: {out}")

if __name__ == "__main__": main()
