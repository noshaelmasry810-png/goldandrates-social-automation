import base64
import json
import math
import os
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from logo_asset import LOGO_PNG_B64

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
ARTIFACTS = ROOT / "artifacts"
FRAMES = ARTIFACTS / "frames"
BACKGROUND_DIR = ROOT / "assets" / "backgrounds"
FPS = 30
WIDTH, HEIGHT = 1080, 1920
KIND = os.environ.get("VIDEO_TYPE", "gold").strip().lower()
CONTENT = DATA_DIR / ("gold_content.json" if KIND == "gold" else "currency_content.json")
MUSIC = ARTIFACTS / "news_bulletin_music.mp3"
OUTPUT = ARTIFACTS / f"goldandrates_{KIND}_daily.mp4"
FONT_REGULAR = FONT_BOLD = None


def run(cmd):
    print(">", " ".join(map(str, cmd)), flush=True)
    subprocess.run([str(x) for x in cmd], check=True)


def font_path(bold=False):
    candidates = [
        "/usr/local/share/fonts/Tajawal-Bold.ttf" if bold else "/usr/local/share/fonts/Tajawal-Regular.ttf",
        "/usr/share/fonts/truetype/tajawal/Tajawal-Bold.ttf" if bold else "/usr/share/fonts/truetype/tajawal/Tajawal-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf" if bold else "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
    ]
    for p in candidates:
        if Path(p).exists():
            return p
    return subprocess.check_output(["fc-match", "Tajawal:style=Bold" if bold else "Tajawal:style=Regular"], text=True).strip().split(":", 1)[0]


def fnt(size, bold=False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REGULAR, size)


def rtl(text):
    return str(text)


def text_width(draw, text, font):
    b = draw.textbbox((0, 0), rtl(text), font=font)
    return b[2] - b[0]


def centered(draw, text, y, size, bold=True, fill=(255, 255, 255)):
    font = fnt(size, bold)
    w = text_width(draw, text, font)
    draw.text(((WIDTH - w) / 2, y), rtl(text), font=font, fill=fill, stroke_width=1, stroke_fill=(0, 0, 0, 80))


def logo_image():
    raw = base64.b64decode(LOGO_PNG_B64)
    logo = Image.open(__import__('io').BytesIO(raw)).convert("RGBA")
    target_w = 250
    target_h = max(1, int(logo.height * target_w / logo.width))
    return logo.resize((target_w, target_h), Image.Resampling.LANCZOS)


def add_brand(img):
    logo = logo_image()
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x, y = 55, 48
    d.rounded_rectangle((x - 18, y - 15, x + logo.width + 18, y + logo.height + 15), radius=22, fill=(5, 8, 14, 155), outline=(255, 224, 116, 120), width=2)
    layer.alpha_composite(logo, (x, y))
    img.alpha_composite(layer)


def background(seed=1):
    asset = BACKGROUND_DIR / ("gold_video_background.png" if KIND == "gold" else "currency_video_background.png")
    if asset.exists():
        source = Image.open(asset).convert("RGB")
        ratio = max(WIDTH / source.width, HEIGHT / source.height)
        source = source.resize((int(source.width * ratio), int(source.height * ratio)), Image.Resampling.LANCZOS)
        left, top = (source.width - WIDTH) // 2, (source.height - HEIGHT) // 2
        source = source.crop((left, top, left + WIDTH, top + HEIGHT)).filter(ImageFilter.GaussianBlur(5.0))
        img = source.convert("RGBA")
        img.alpha_composite(Image.new("RGBA", img.size, (0, 0, 0, 88)))
    else:
        img = Image.new("RGBA", (WIDTH, HEIGHT), (12, 12, 20, 255))
    add_brand(img)
    return img


def card(img, box, accent=(255, 224, 116), alpha=218):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle(box, radius=34, fill=(5, 8, 15, alpha), outline=accent + (210,), width=3)
    img.alpha_composite(layer)


def footer(img):
    d = ImageDraw.Draw(img)
    centered(d, "موقع ذهب وأسعار", 1770, 30, True, (245, 245, 248))
    centered(d, "www.goldandrates.com", 1825, 34, True, (255, 224, 116))


def money(v):
    n = float(v)
    return f"{int(round(n)):,}" if abs(n - round(n)) < .005 else f"{n:,.2f}"


def fx_money(v):
    n = float(v)
    return f"{n:,.4f}" if n < 1 else f"{n:,.2f}"


def today_ar():
    # The workflow runs in UTC; the +03:00 offset keeps the bulletin date aligned with Egypt/Saudi local time.
    dt = datetime.now(timezone.utc) + timedelta(hours=3)
    days = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
    months = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]
    return f"{days[dt.weekday()]} {dt.day} {months[dt.month-1]} {dt.year}"


def make_intro(content):
    img = background(1)
    d = ImageDraw.Draw(img)
    # Strong bulletin hook: date + curiosity + first key price.
    centered(d, today_ar(), 300, 38, True, (220, 224, 232))
    if KIND == "gold":
        market = content["videoData"]["markets"][0]
        centered(d, "قبل ما تشوف سعر الذهب...", 515, 62, True, (255, 224, 116))
        centered(d, "شوف عيار 21 النهارده!", 610, 66, True, (255, 255, 255))
        card(img, (105, 790, 975, 1250))
        centered(d, "عيار 21 في مصر", 850, 48, True, (230, 233, 240))
        centered(d, f"{money(market['karats']['21'])} جنيه", 955, 104, True, (255, 224, 116))
    else:
        rates = {x["code"]: x["value"] for x in content["videoData"]["rates"]}
        centered(d, "قبل ما تشوف أسعار العملات...", 515, 58, True, (255, 224, 116))
        centered(d, "شوف الدولار وصل لكام!", 610, 66, True, (255, 255, 255))
        card(img, (105, 790, 975, 1250))
        centered(d, "الدولار مقابل الجنيه", 850, 48, True, (230, 233, 240))
        centered(d, f"{fx_money(rates['EGP'])} جنيه", 955, 100, True, (255, 224, 116))
    footer(img)
    p = FRAMES / "01_intro.png"; img.convert("RGB").save(p, quality=96); return p


def make_gold_market_slide(item, index):
    img = background(10 + index); d = ImageDraw.Draw(img)
    centered(d, item["name"], 300, 58, True, (255, 224, 116))
    centered(d, "أسعار الجرام اليوم", 395, 38, True, (224, 227, 235))
    y = 565
    for karat in ("24", "22", "21", "18"):
        card(img, (105, y, 975, y + 210))
        centered(d, f"عيار {karat}", y + 25, 42, True, (244, 245, 248))
        centered(d, f"{money(item['karats'][karat])} {item['unit']}", y + 92, 58, True, (255, 224, 116))
        y += 235
    footer(img)
    p = FRAMES / f"gold_{index:02d}.png"; img.convert("RGB").save(p, quality=96); return p


def make_currency_slide(item, index):
    img = background(20 + index); d = ImageDraw.Draw(img)
    centered(d, item["name"], 480, 58, True, (255, 224, 116))
    centered(d, "مقابل دولار أمريكي واحد", 610, 40, True, (224, 227, 235))
    card(img, (105, 735, 975, 1190))
    centered(d, fx_money(item["value"]), 820, 112, True, (255, 224, 116))
    centered(d, item["unit"], 970, 48, True, (244, 245, 248))
    footer(img)
    p = FRAMES / f"fx_{index:02d}.png"; img.convert("RGB").save(p, quality=96); return p


def make_cta():
    img = background(50); d = ImageDraw.Draw(img)
    centered(d, "كل الأسعار بتتحدث أول بأول", 560, 56, True, (245, 246, 249))
    centered(d, "تابع النشرة اليومية", 665, 72, True, (255, 224, 116))
    centered(d, "وزور موقع ذهب وأسعار", 805, 52, True, (245, 246, 249))
    centered(d, "www.goldandrates.com", 930, 58, True, (255, 224, 116))
    footer(img)
    p = FRAMES / "99_cta.png"; img.convert("RGB").save(p, quality=96); return p


def audio_duration(path):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)], text=True).strip())


def make_segment(image_path, duration, index):
    segment = ARTIFACTS / f"{KIND}_segment_{index:02d}.mp4"
    # Gentle zoom + cinematic fade. The text stays sharp because blur is only on the background.
    vf = (
        "zoompan=z='min(zoom+0.00055,1.055)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        "d=1:s=1080x1920:fps=30,fade=t=in:st=0:d=0.35,fade=t=out:st="
        f"{max(0,duration-0.45):.3f}:d=0.45,format=yuv420p"
    )
    run(["ffmpeg", "-y", "-loop", "1", "-i", image_path, "-t", f"{duration:.3f}", "-vf", vf, "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", segment])
    if not segment.exists() or segment.stat().st_size == 0:
        raise RuntimeError(f"Video segment was not created: {segment}")
    return segment


def concat_segments(segments):
    list_file = ARTIFACTS / f"{KIND}_segments.txt"
    list_file.write_text("".join(f"file '{Path(p).as_posix()}'\n" for p in segments), encoding="utf-8")
    silent = ARTIFACTS / f"{KIND}_silent.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file, "-c", "copy", silent])
    return silent


def mux_music(video_path, duration):
    # Re-encode the final audio with a deliberate gain and verify that an audio stream exists.
    run([
        "ffmpeg", "-y", "-i", video_path, "-stream_loop", "-1", "-i", MUSIC,
        "-t", f"{duration:.3f}", "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-af", "volume=0.55,loudnorm=I=-16:TP=-1.5:LRA=7,afade=t=in:st=0:d=0.5,afade=t=out:st=" + f"{max(0,duration-1.0):.3f}:d=1.0",
        "-shortest", OUTPUT,
    ])
    if not OUTPUT.exists() or OUTPUT.stat().st_size == 0:
        raise RuntimeError(f"Final MP4 was not created: {OUTPUT}")
    streams = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=codec_name", "-of", "csv=p=0", str(OUTPUT)], text=True).strip()
    if not streams:
        raise RuntimeError("Final MP4 has no audio stream")
    print(f"Verified audio stream: {streams}", flush=True)


def main():
    global FONT_REGULAR, FONT_BOLD
    if KIND not in {"gold", "currency"}:
        raise SystemExit("VIDEO_TYPE must be gold or currency")
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            raise SystemExit(f"{tool} is required")
    if not CONTENT.exists(): raise SystemExit(f"{CONTENT} not found")
    if not MUSIC.exists(): raise SystemExit(f"{MUSIC} not found")
    FONT_REGULAR, FONT_BOLD = font_path(False), font_path(True)
    content = json.loads(CONTENT.read_text(encoding="utf-8"))
    FRAMES.mkdir(parents=True, exist_ok=True)
    for p in ARTIFACTS.glob(f"{KIND}_segment_*.mp4"): p.unlink(missing_ok=True)
    OUTPUT.unlink(missing_ok=True)

    slides = [make_intro(content)]
    if KIND == "gold":
        slides.extend(make_gold_market_slide(item, i) for i, item in enumerate(content["videoData"]["markets"], 1))
    else:
        slides.extend(make_currency_slide(item, i) for i, item in enumerate(content["videoData"]["rates"], 1))
    slides.append(make_cta())

    durations = [3.2] + [3.4] * (len(slides) - 2) + [3.4]
    total = sum(durations)
    if not 15 <= total <= 35:
        raise SystemExit(f"Video duration {total:.2f}s is outside 15-35s")
    segments = [make_segment(slides[i], durations[i], i + 1) for i in range(len(slides))]
    silent = concat_segments(segments)
    mux_music(silent, total)
    print(f"Final {KIND} bulletin duration: {total:.2f}s", flush=True)
    print(f"Final MP4: {OUTPUT}", flush=True)


if __name__ == "__main__":
    main()
