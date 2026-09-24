import hashlib
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

CORE_KEYWORDS = [
    "سعر الذهب اليوم",
    "أسعار الذهب اليوم",
    "سعر الذهب في مصر",
    "سعر جرام الذهب",
    "سعر الذهب الآن",
    "عيار 21",
    "عيار 24",
    "عيار 22",
    "عيار 18",
    "الجنيه الذهب",
    "الذهب اليوم",
    "تحليل أسعار الذهب",
]

DIRECT_GOLD_TERMS = [
    "الذهب",
    "ذهب",
    "gold",
    "gold price",
    "gold prices",
    "سعر الذهب",
    "اسعار الذهب",
    "أسعار الذهب",
    "عيار 18",
    "عيار 21",
    "عيار 22",
    "عيار 24",
    "جرام الذهب",
    "الجنيه الذهب",
    "سبائك الذهب",
    "سبيكة ذهب",
    "xau",
    "bullion",
]

TREND_HASHTAG_RULES = [
    (["سعر الذهب", "اسعار الذهب", "أسعار الذهب"], "#سعر_الذهب"),
    (["عيار 21"], "#عيار_21"),
    (["عيار 24"], "#عيار_24"),
    (["عيار 22"], "#عيار_22"),
    (["عيار 18"], "#عيار_18"),
    (["الجنيه الذهب"], "#الجنيه_الذهب"),
    (["سبائك الذهب", "سبيكة ذهب"], "#سبائك_الذهب"),
    (["الذهب", "ذهب", "gold"], "#الذهب"),
]

EVERGREEN_HASHTAGS = [
    "#الذهب",
    "#سعر_الذهب",
    "#أسعار_الذهب",
    "#ذهب",
    "#سعر_الذهب_اليوم",
    "#الذهب_في_مصر",
    "#عيار_21",
    "#عيار_24",
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
    return any(
        normalize_for_match(term) in normalized
        for term in DIRECT_GOLD_TERMS
    )


def extract_trend_keywords(title: str) -> list[str]:
    normalized = normalize_for_match(title)
    keywords: list[str] = []

    patterns = [
        ("سعر الذهب", "سعر الذهب"),
        ("اسعار الذهب", "أسعار الذهب"),
        ("الذهب اليوم", "الذهب اليوم"),
        ("عيار 21", "عيار 21"),
        ("عيار 24", "عيار 24"),
        ("عيار 22", "عيار 22"),
        ("عيار 18", "عيار 18"),
        ("جرام الذهب", "سعر جرام الذهب"),
        ("الجنيه الذهب", "الجنيه الذهب"),
        ("سبائك الذهب", "سبائك الذهب"),
        ("سبيكة ذهب", "سبائك الذهب"),
        ("xau", "XAU الذهب"),
    ]

    for needle, keyword in patterns:
        if normalize_for_match(needle) in normalized and keyword not in keywords:
            keywords.append(keyword)

    return keywords


def build_keywords(related_trends: list[str]) -> list[str]:
    keywords = CORE_KEYWORDS.copy()

    for trend in related_trends:
        for keyword in extract_trend_keywords(trend):
            if keyword not in keywords:
                keywords.append(keyword)
            if len(keywords) >= 16:
                break
        if len(keywords) >= 16:
            break

    return keywords


def build_trend_hashtags(related_trends: list[str]) -> list[str]:
    tags: list[str] = []

    for trend in related_trends:
        normalized = normalize_for_match(trend)
        for needles, tag in TREND_HASHTAG_RULES:
            if any(normalize_for_match(needle) in normalized for needle in needles):
                if tag not in tags:
                    tags.append(tag)
                if len(tags) >= 5:
                    return tags

    return tags


def build_hashtags(related_trends: list[str]) -> list[str]:
    trend_tags = build_trend_hashtags(related_trends)
    hashtags = trend_tags.copy()

    for tag in EVERGREEN_HASHTAGS:
        if tag not in hashtags:
            hashtags.append(tag)
        if len(hashtags) >= 12:
            break

    return hashtags


def choose_daily_voice() -> tuple[str, dict]:
    # Stable per calendar day: rerunning the workflow the same day does not
    # unexpectedly switch the speaker. The hash makes the choice appear random
    # across days rather than simply alternating male/female.
    day_key = datetime.now(timezone.utc).date().isoformat()
    digest = hashlib.sha256(day_key.encode("utf-8")).hexdigest()
    gender = "male" if int(digest[0], 16) % 2 == 0 else "female"
    return gender, VOICE_PROFILES[gender]


def generate_copy(
    data: dict,
    keywords: list[str],
    hashtags: list[str],
    related_trends: list[str],
) -> dict:
    p = data["karats"]
    currency = data["currency"]

    price_line = (
        f"سعر الذهب اليوم في مصر: عيار 21 = {p['21']} {currency}"
    )

    hook = (
        f"{price_line} | "
        "عيار 24 و22 و18 وتحديثات الذهب أولًا بأول مع ذهب وأسعار."
    )

    voice_script = (
        f"{hook}\n"
        f"عيار 24: {p['24']} {currency}.\n"
        f"عيار 22: {p['22']} {currency}.\n"
        f"عيار 21: {p['21']} {currency}.\n"
        f"عيار 18: {p['18']} {currency}."
    )

    trend_section = ""
    if related_trends:
        trend_section = (
            "\n\nإشارة ترند مرتبطة بالذهب اليوم: "
            + related_trends[0]
        )

    description = (
        f"{hook}\n\n"
        "أسعار الذهب اليوم، سعر جرام الذهب، عيار 21، عيار 24، "
        "عيار 22، عيار 18، والجنيه الذهب في مصر. "
        "تابع ذهب وأسعار لمعرفة تحديثات الأسعار بشكل مستمر."
        + trend_section
        + "\n\nالكلمات المفتاحية: "
        + "، ".join(keywords)
        + "\n\n"
        + " ".join(hashtags)
        + "\n\nللمزيد من أسعار الذهب والتحديثات: https://goldandrates.com/"
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

        for title in titles:
            if is_relevant_trend(title) and title not in trend_signals:
                trend_signals.append(title)

    related_trends = trend_signals[:5]
    keywords = build_keywords(related_trends)
    hashtags = build_hashtags(related_trends)
    voice_gender, voice_profile = choose_daily_voice()

    copy = generate_copy(data, keywords, hashtags, related_trends)

    payload = {
        "generatedAt": data["generatedAt"],
        "language": "ar",
        "source": "ذهب وأسعار",
        "voiceGender": voice_gender,
        "voiceName": voice_profile["voice"],
        "voiceLabel": voice_profile["label"],
        "voiceLocale": voice_profile["locale"],
        "trendSource": "Google Trends Trending Now RSS",
        "trendGeos": TREND_GEOS,
        "trendSignals": related_trends,
        "trendHashtags": build_trend_hashtags(related_trends),
        "trendFetchErrors": trend_errors,
        "keywords": keywords,
        "hashtags": hashtags,
        "hook": copy["hook"],
        "caption": copy["caption"],
        "description": copy["description"],
        "voiceScript": copy["voiceScript"],
        "videoData": {
            "title": "أسعار الذهب اليوم - ذهب وأسعار",
            "hook": copy["hook"],
            "karats": data["karats"],
            "currency": data["currency"],
            "voiceGender": voice_gender,
            "voiceName": voice_profile["voice"],
            "voiceLabel": voice_profile["label"],
            "voiceLocale": voice_profile["locale"],
            "keywords": keywords,
            "hashtags": hashtags,
            "trendSignals": related_trends,
            "trendHashtags": build_trend_hashtags(related_trends),
        },
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
    }

    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
