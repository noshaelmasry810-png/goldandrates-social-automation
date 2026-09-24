import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRICES = ROOT / "data" / "prices.json"
OUTPUT = ROOT / "data" / "content.json"

TREND_GEOS = ["EG", "SA"]
TREND_URL = "https://trends.google.com/trending/rss?geo={geo}"
REQUEST_TIMEOUT = 15

# Strong, evergreen search terms tightly related to the GoldAndRates niche.
CORE_KEYWORDS = [
    "سعر الذهب اليوم",
    "أسعار الذهب",
    "سعر الذهب في مصر",
    "عيار 21",
    "عيار 24",
    "سعر جرام الذهب",
    "سعر الذهب الآن",
    "الجنيه الذهب",
    "الذهب اليوم",
    "تحليل الذهب",
]

# Trend signals are only promoted into the copy when they are clearly
# relevant to gold/finance. Unrelated trending topics are ignored.
RELEVANCE_TERMS = {
    "ذهب", "الذهب", "gold", "فضة", "silver", "سعر", "اسعار", "أسعار",
    "جنيه", "اقتصاد", "اقتصادية", "اقتصاديات", "دولار", "الدولار",
    "عملة", "عملات", "تضخم", "inflation", "اقتصاد", "بورصة", "أسواق",
    "market", "markets", "finance", "financial", "xau", "bullion",
}

EVERGREEN_HASHTAGS = [
    "#الذهب",
    "#سعر_الذهب",
    "#أسعار_الذهب",
    "#ذهب",
    "#عيار_21",
    "#عيار_24",
    "#سعر_الذهب_اليوم",
    "#الذهب_في_مصر",
    "#Gold",
    "#GoldPrice",
]


def fetch_trending_queries(geo: str) -> list[str]:
    url = TREND_URL.format(geo=geo)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "GoldAndRates-Social-Automation/1.0",
            "Accept": "application/rss+xml, application/xml, text/xml",
        },
    )

    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        raw = response.read()

    root = ET.fromstring(raw)
    titles: list[str] = []

    # Google Trends RSS uses RSS item/title elements. Keep this generic enough
    # to tolerate harmless namespace changes.
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


def is_relevant_trend(title: str) -> bool:
    normalized = normalize_for_match(title)
    return any(normalize_for_match(term) in normalized for term in RELEVANCE_TERMS)


def trend_hashtag(title: str) -> str | None:
    cleaned = re.sub(r"[^\w\u0600-\u06FF]+", "", title, flags=re.UNICODE)
    if not cleaned:
        return None
    # Keep hashtags short enough to remain readable and avoid generating
    # machine-looking spam tags from long news headlines.
    if len(cleaned) > 35:
        return None
    return "#" + cleaned


def build_keywords(related_trends: list[str]) -> list[str]:
    keywords = CORE_KEYWORDS.copy()

    for trend in related_trends:
        if len(keywords) >= 15:
            break
        trend_clean = trend.strip()
        if trend_clean and trend_clean not in keywords:
            keywords.append(trend_clean)

    return keywords


def build_hashtags(related_trends: list[str]) -> list[str]:
    hashtags = EVERGREEN_HASHTAGS.copy()

    for trend in related_trends:
        tag = trend_hashtag(trend)
        if tag and tag not in hashtags:
            hashtags.insert(-2, tag)
        if len(hashtags) >= 14:
            break

    return hashtags


def generate_copy(data: dict, keywords: list[str], hashtags: list[str]) -> dict:
    p = data["karats"]
    currency = data["currency"]

    price_line = (
        f"سعر الذهب اليوم في مصر: عيار 21 = {p['21']} {currency}"
    )

    hook = (
        f"{price_line} | "
        "تابع أسعار الذهب وعيار 24 و22 و18 وتحديثات السوق أولًا بأول."
    )

    voice_script = (
        f"{hook}\n"
        f"عيار 24: {p['24']} {currency}.\n"
        f"عيار 22: {p['22']} {currency}.\n"
        f"عيار 21: {p['21']} {currency}.\n"
        f"عيار 18: {p['18']} {currency}."
    )

    description = (
        f"{hook}\n\n"
        "أسعار الذهب اليوم، سعر جرام الذهب، عيار 21، عيار 24، "
        "عيار 22، عيار 18، والذهب في مصر. "
        "تابع GoldAndRates لمعرفة تحديثات الأسعار بشكل مستمر.\n\n"
        + "الكلمات المفتاحية: "
        + "، ".join(keywords)
        + "\n\n"
        + " ".join(hashtags)
    )

    return {
        "hook": hook,
        "caption": description,
        "description": description,
        "voiceScript": voice_script,
    }


def main() -> None:
    data = json.loads(PRICES.read_text(encoding="utf-8"))
    if data.get("status") != "ok":
        raise SystemExit("prices.json does not contain fresh price data")

    trend_errors: list[str] = []
    trend_signals: list[str] = []

    for geo in TREND_GEOS:
        try:
            titles = fetch_trending_queries(geo)
        except Exception as exc:
            trend_errors.append(f"{geo}: {type(exc).__name__}: {exc}")
            continue

        # Preserve only relevant trend signals for potential copy use.
        for title in titles:
            if is_relevant_trend(title) and title not in trend_signals:
                trend_signals.append(title)

    related_trends = trend_signals[:5]
    keywords = build_keywords(related_trends)
    hashtags = build_hashtags(related_trends)

    copy = generate_copy(data, keywords, hashtags)

    payload = {
        "generatedAt": data["generatedAt"],
        "language": "ar",
        "source": "GoldAndRates",
        "trendSource": "Google Trends Trending Now RSS",
        "trendGeos": TREND_GEOS,
        "trendSignals": related_trends,
        "trendFetchErrors": trend_errors,
        "keywords": keywords,
        "hashtags": hashtags,
        "hook": copy["hook"],
        "caption": copy["caption"],
        "description": copy["description"],
        "voiceScript": copy["voiceScript"],
        "videoData": {
            "title": "أسعار الذهب اليوم",
            "hook": copy["hook"],
            "karats": data["karats"],
            "currency": data["currency"],
            "keywords": keywords,
            "hashtags": hashtags,
        },
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
    }

    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
