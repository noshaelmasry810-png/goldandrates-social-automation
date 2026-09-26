import base64
import io
import json
import math
import os
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageOps
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
MUSIC = ROOT / "assets" / "music" / "news_bulletin.mp3"
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


def centered(draw, text, y, size, bold=True, fill=(255, 255, 255)):
    font = fnt(size, bold)
    box = draw.textbbox((0, 0), str(text), font=font)
    w = box[2] - box[0]
    draw.text(((WIDTH - w) / 2, y), str(text), font=font, fill=fill, stroke_width=1, stroke_fill=(0, 0, 0, 120))


def logo_image():
    raw = base64.b64decode(LOGO_PNG_B64)
    logo = Image.open(io.BytesIO(raw)).convert("RGBA")
    # Keep the supplied logo modest in size because the embedded source is small;
    # a small crisp logo looks better than enlarging a low-resolution raster.
    target_w = 155
    target_h = max(1, int(logo.height * target_w / logo.width))
    logo = logo.resize((target_w, target_h), Image.Resampling.LANCZOS)
    return ImageEnhance.Sharpness(logo).enhance(1.8)


def add_brand(img):
    logo = logo_image()
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    x = WIDTH - logo.width - 48
    y = 42
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((x - 18, y - 14, x + logo.width + 18, y + logo.height + 14), radius=22,
                        fill=(3, 7, 13, 175), outline=(255, 224, 116, 170), width=2)
    layer.alpha_composite(logo, (x, y))
    img.alpha_composite(layer)


def procedural_background():
    # Premium fallback that preserves the intended gold/financial identity even if
    # the external PNG assets are not present in the repository.
    base = Image.new("RGB", (WIDTH, HEIGHT))
    px = base.load()
    for y in range(HEIGHT):
        for x in range(WIDTH):
            nx, ny = x / WIDTH, y / HEIGHT
            if KIND == "gold":
                glow = max(0.0, 1.0 - math.hypot(nx - 0.55, ny - 0.38) * 1.35)
                px[x, y] = (int(18 + 48 * glow), int(12 + 32 * glow), int(8 + 9 * glow))
            else:
                glow = max(0.0, 1.0 - math.hypot(nx - 0.55, ny - 0.35) * 1.45)
                px[x, y] = (int(5 + 7 * glow), int(15 + 28 * glow), int(32 + 70 * glow))
    d = ImageDraw.Draw(base, "RGBA")
    # financial grid / diagonal market lines
    for i in range(-HEIGHT, WIDTH, 90):
        d.line((i, HEIGHT, i + HEIGHT, 0), fill=(255, 224, 116, 28) if KIND == "gold" else (110, 190, 255, 30), width=2)
    for y in range(180, HEIGHT, 140):
        d.line((0, y, WIDTH, y), fill=(255, 255, 255, 16), width=1)
    # glowing market line
    pts = []
    for x in range(0, WIDTH + 1, 30):
        yy = int(1040 - 190 * math.sin(x / 115.0) - 75 * math.sin(x / 41.0))
        pts.append((x, yy))
    d.line(pts, fill=(255, 224, 116, 75) if KIND == "gold" else (90, 205, 255, 85), width=6)
    return base.filter(ImageFilter.GaussianBlur(5.0)).convert("RGBA")


def background():
    asset = BACKGROUND_DIR / ("gold_video_background.png" if KIND == "gold" else "currency_video_background.png")
    if asset.exists():
        source = Image.open(asset).convert("RGB")
        ratio = max(WIDTH / source.width, HEIGHT / source.height)
        source = source.resize((int(source.width * ratio), int(source.height * ratio)), Image.Resampling.LANCZOS)
        left, top = (source.width - WIDTH) // 2, (source.height - HEIGHT) // 2
        source = source.crop((left, top, left + WIDTH, top + HEIGHT))
        source = source.filter(ImageFilter.GaussianBlur(5.5))
        img = source.convert("RGBA")
    else:
        img = procedural_background()
    # Dark veil keeps the news graphics readable while leaving the artwork visible.
    img.alpha_composite(Image.new("RGBA", img.size, (0, 0, 0, 92)))
    add_brand(img)
    return img


def card(img, box, accent=(255, 224, 116), alpha=224):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle(box, radius=36, fill=(4, 8, 16, alpha), outline=accent + (225,), width=3)
    img.alpha_composite(layer)


def footer(img):
    d = ImageDraw.Draw(img)
    centered(d, "موقع ذهب وأسعار", 1765, 28, True, (245, 245, 248))
    centered(d, "www.goldandrates.com", 1815, 34, True, (255, 224, 116))


def money(v):
    n = float(v)
    return f"{int(round(n)):,}" if abs(n - round(n)) < .005 else f"{n:,.2f}"


def fx_money(v):
    n = float(v)
    return f"{n:,.4f}" if n < 1 else f"{n:,.2f}"


def today_ar():
    dt = datetime.now(timezone.utc) + timedelta(hours=3)
    days = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
    months = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]
    return f"{days[dt.weekday()]} {dt.day} {months[dt.month-1]} {dt.year}"


def make_intro(content):
    # Opening is hook + date only. Product/karat pricing appears on the next slide.
    img = background(); d = ImageDraw.Draw(img)
    centered(d, today_ar(), 245, 38, True, (225, 229, 238))
    if KIND == "gold":
        centered(d, "النشرة اليومية لأسعار الذهب", 430, 58, True, (255, 224, 116))
        centered(d, "عيار 21 عامل كام النهارده؟", 535, 76, True, (255, 255, 255))
    else:
        rates = {x["code"]: x["value"] for x in content["videoData"]["rates"]}
        centered(d, "النشرة اليومية لأسعار العملات", 430, 56, True, (105, 205, 255))
        centered(d, "الدولار وصل لكام النهارده؟", 535, 76, True, (255, 255, 255))
    footer(img)
    p = FRAMES / "01_intro.png"; img.convert("RGB").save(p, quality=96); return p


def make_gold_market_slide(item, index):
    # Build a clean base plus four transparent, independently animated price cards.
    img = background(); d = ImageDraw.Draw(img)
    centered(d, item["name"], 270, 58, True, (255, 224, 116))
    centered(d, "أسعار الجرام اليوم", 360, 38, True, (224, 227, 235))
    y0 = 500
    for n, karat in enumerate(("24", "22", "21", "18")):
        layer = Image.new("RGBA", (870, 210), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        accent = (255, 224, 116)
        if karat == "21":
            ld.rounded_rectangle((0, 0, 870, 210), radius=36, fill=(8, 12, 20, 238), outline=accent + (255,), width=4)
            ld.rounded_rectangle((8, 8, 862, 202), radius=30, outline=(255, 244, 180, 115), width=2)
        else:
            ld.rounded_rectangle((0, 0, 870, 210), radius=36, fill=(4, 8, 16, 224), outline=accent + (225,), width=3)
        def local_center(text, y, size, fill):
            font = fnt(size, True)
            box = ld.textbbox((0, 0), str(text), font=font)
            ld.text(((870 - (box[2]-box[0]))/2, y), str(text), font=font, fill=fill,
                    stroke_width=1, stroke_fill=(0, 0, 0, 120))
        local_center(f"عيار {karat}", 25, 42, (244, 245, 248))
        local_center(f"{money(item['karats'][karat])} {item['unit']}", 92, 58, accent)
        row_path = FRAMES / f"gold_{index:02d}_row_{n}.png"
        layer.save(row_path)
    footer(img)
    p = FRAMES / f"gold_{index:02d}_base.png"; img.convert("RGB").save(p, quality=96); return p

def make_currency_slide(item, index):
    img = background(); d = ImageDraw.Draw(img)
    centered(d, item["name"], 500, 58, True, (105, 205, 255))
    centered(d, "مقابل دولار أمريكي واحد", 625, 40, True, (224, 227, 235))
    card(img, (105, 755, 975, 1220), accent=(105, 205, 255))
    centered(d, fx_money(item["value"]), 855, 112, True, (105, 205, 255))
    centered(d, item["unit"], 1010, 48, True, (244, 245, 248))
    footer(img)
    p = FRAMES / f"fx_{index:02d}.png"; img.convert("RGB").save(p, quality=96); return p


def make_cta():
    img = background(); d = ImageDraw.Draw(img)
    centered(d, "كل الأسعار بتتحدث أول بأول", 520, 56, True, (245, 246, 249))
    centered(d, "تابع النشرة اليومية", 640, 76, True, (255, 224, 116) if KIND == "gold" else (105, 205, 255))
    centered(d, "وزور موقع ذهب وأسعار", 785, 54, True, (245, 246, 249))
    centered(d, "www.goldandrates.com", 900, 60, True, (255, 224, 116) if KIND == "gold" else (105, 205, 255))
    footer(img)
    p = FRAMES / "99_cta.png"; img.convert("RGB").save(p, quality=96); return p


def make_segment(image_path, duration, index):
    segment = ARTIFACTS / f"{KIND}_segment_{index:02d}.mp4"
    if KIND == "gold" and Path(image_path).name.endswith("_base.png"):
        # Animate each karat card independently: slide in from the right with staggered timing.
        stem = Path(image_path).stem
        inputs = ["-loop", "1", "-i", image_path]
        for n in range(4):
            inputs += ["-loop", "1", "-i", FRAMES / f"{stem.replace('_base','')}_row_{n}.png"]
        filters = []
        current = "[0:v]"
        for n in range(4):
            delay = 0.35 + n * 0.42
            speed = 900.0
            target_x = 105.0
            y = 500 + n * 235
            xexpr = f"if(lt(t,{delay:.2f}),1080,max({target_x:.0f},1080-(t-{delay:.2f})*{speed:.0f}))"
            out = f"[v{n}]"
            filters.append(f"{current}[{n+1}:v]overlay=x='{xexpr}':y={y}:eof_action=repeat:shortest=1{out}")
            current = out
        vf = ";".join(filters) + f";{current}zoompan=z='min(zoom+0.00030,1.045)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps=30,fade=t=in:st=0:d=0.45,fade=t=out:st={max(0,duration-0.65):.3f}:d=0.65,format=yuv420p"
        run(["ffmpeg", "-y", *inputs, "-t", f"{duration:.3f}", "-filter_complex", vf,
             "-map", current.strip("[]"), "-an", "-c:v", "libx264", "-preset", "veryfast",
             "-crf", "19", "-pix_fmt", "yuv420p", segment])
    else:
        vf = (
            f"zoompan=z='min(zoom+0.00038,1.055)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d=1:s=1080x1920:fps=30,fade=t=in:st=0:d=0.55,fade=t=out:st={max(0,duration-0.65):.3f}:d=0.65,format=yuv420p"
        )
        run(["ffmpeg", "-y", "-loop", "1", "-i", image_path, "-t", f"{duration:.3f}", "-vf", vf, "-an",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", segment])
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
    run([
        "ffmpeg", "-y", "-i", video_path, "-stream_loop", "-1", "-i", MUSIC,
        "-t", f"{duration:.3f}", "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-af", "volume=0.90,loudnorm=I=-13:TP=-1.2:LRA=7,afade=t=in:st=0:d=0.35,afade=t=out:st=" + f"{max(0,duration-1.1):.3f}:d=1.1",
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
    durations = [6.67] * len(slides)
    total = sum(durations)
    if not 39.5 <= total <= 40.5:
        raise SystemExit(f"Video duration {total:.2f}s is outside the 40s target")
    segments = [make_segment(slides[i], durations[i], i + 1) for i in range(len(slides))]
    silent = concat_segments(segments)
    mux_music(silent, total)
    print(f"Final {KIND} bulletin duration: {total:.2f}s", flush=True)
    print(f"Final MP4: {OUTPUT}", flush=True)

if __name__ == "__main__":
    main()
