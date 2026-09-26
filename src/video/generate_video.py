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
GOLD_LAYERS = {}


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
    for i in range(-HEIGHT, WIDTH, 90):
        d.line((i, HEIGHT, i + HEIGHT, 0), fill=(255, 224, 116, 28) if KIND == "gold" else (110, 190, 255, 30), width=2)
    for y in range(180, HEIGHT, 140):
        d.line((0, y, WIDTH, y), fill=(255, 255, 255, 16), width=1)
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
    centered(d, today_ar(), 1690, 30, True, (225, 229, 238))
    centered(d, "موقع ذهب وأسعار", 1760, 28, True, (245, 245, 248))
    centered(d, "www.goldandrates.com", 1810, 34, True, (255, 224, 116))


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
    img = background()
    layers = []
    def text_layer(name, draw_fn, delay):
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw_fn(ImageDraw.Draw(layer))
        p = FRAMES / name
        layer.save(p)
        layers.append((p, 0, 0, delay))
    hook = "أسعار الذهب اليوم" if KIND == "gold" else "أسعار العملات اليوم"
    text_layer("intro_hook.png", lambda d: centered(d, hook, 760, 78, True, (255, 255, 255)), 0.25)
    text_layer("intro_date.png", lambda d: centered(d, today_ar(), 870, 42, True, (225, 229, 238)), 0.25)
    p = FRAMES / "01_intro.png"
    img.convert("RGB").save(p, quality=96)
    GOLD_LAYERS[str(p)] = layers
    return p


def make_gold_market_slide(item, index):
    img = background()
    layers = []
    def full_text(name, draw_fn, delay):
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw_fn(ImageDraw.Draw(layer))
        p = FRAMES / name
        layer.save(p)
        layers.append((p, 0, 0, delay))
    full_text(f"gold_{index:02d}_title.png", lambda d: centered(d, item["name"], 270, 58, True, (255, 224, 116)), 0.25)
    full_text(f"gold_{index:02d}_subtitle.png", lambda d: centered(d, "أسعار الجرام اليوم", 360, 38, True, (224, 227, 235)), 0.25)
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
            ld.text(((870 - (box[2]-box[0]))/2, y), str(text), font=font, fill=fill, stroke_width=1, stroke_fill=(0, 0, 0, 120))
        local_center(f"عيار {karat}", 25, 42, (244, 245, 248))
        local_center(f"{money(item['karats'][karat])} {item['unit']}", 92, 58, accent)
        row_path = FRAMES / f"gold_{index:02d}_row_{n}.png"
        layer.save(row_path)
        layers.append((row_path, (WIDTH - 870) // 2, 500 + n * 235, 0.25))
    footer(img)
    p = FRAMES / f"gold_{index:02d}_base.png"
    img.convert("RGB").save(p, quality=96)
    GOLD_LAYERS[str(p)] = layers
    return p


def make_currency_slide(item, index):
    # Currency page: static background/footer; all page content fades in together.
    img = background()
    layers = []
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    accent = (105, 205, 255)
    centered(d, item["name"], 500, 58, True, accent)
    centered(d, "مقابل دولار أمريكي واحد", 625, 40, True, (224, 227, 235))
    d.rounded_rectangle((105, 755, 975, 1220), radius=36, fill=(4, 8, 16, 224), outline=accent + (225,), width=3)
    centered(d, fx_money(item["value"]), 855, 112, True, accent)
    centered(d, item["unit"], 1010, 48, True, (244, 245, 248))
    content_path = FRAMES / f"fx_{index:02d}_content.png"
    layer.save(content_path)
    layers.append((content_path, 0, 0, 0.25))
    footer(img)
    p = FRAMES / f"fx_{index:02d}_base.png"
    img.convert("RGB").save(p, quality=96)
    GOLD_LAYERS[str(p)] = layers
    return p


def make_cta():
    img = background()
    layers = []
    accent = (255, 224, 116) if KIND == "gold" else (105, 205, 255)
    specs = [("cta_1.png", "كل الأسعار بتتحدث أول بأول", 520, 56, (245, 246, 249), 0.25), ("cta_2.png", "تابع النشرة اليومية", 640, 76, accent, 1.05), ("cta_3.png", "وزور موقع ذهب وأسعار", 785, 54, (245, 246, 249), 1.85), ("cta_4.png", "www.goldandrates.com", 900, 60, accent, 2.65)]
    for name, text_value, y, size, fill, delay in specs:
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        centered(ImageDraw.Draw(layer), text_value, y, size, True, fill)
        p = FRAMES / name
        layer.save(p)
        layers.append((p, 0, 0, delay))
    footer(img)
    p = FRAMES / "99_cta.png"
    img.convert("RGB").save(p, quality=96)
    GOLD_LAYERS[str(p)] = layers
    return p


def make_segment(image_path, duration, index):
    segment = ARTIFACTS / f"{KIND}_segment_{index:02d}.mp4"
    layers = GOLD_LAYERS.get(str(image_path))
    if not layers:
        vf = "format=yuv420p"
        run(["ffmpeg", "-y", "-loop", "1", "-i", image_path, "-t", f"{duration:.3f}", "-vf", vf, "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", segment])
    else:
        cmd = ["ffmpeg", "-y", "-loop", "1", "-i", image_path]
        for layer_path, _, _, _ in layers:
            cmd += ["-loop", "1", "-i", layer_path]
        filters = []
        previous = "[0:v]"
        for i, (layer_path, x, y, delay) in enumerate(layers):
            label = f"l{i}"
            out = f"v{i}"
            filters.append(f"[{i+1}:v]format=rgba,fade=t=in:st={delay:.2f}:d=0.55:alpha=1[{label}]")
            filters.append(f"{previous}[{label}]overlay=x={x}:y={y}:eof_action=repeat[{out}]")
            previous = f"[{out}]"
        filters.append(f"{previous}format=yuv420p[vout]")
        cmd += ["-t", f"{duration:.3f}", "-filter_complex", ";".join(filters), "-map", "[vout]", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", segment]
        run(cmd)
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
    run(["ffmpeg", "-y", "-i", video_path, "-stream_loop", "-1", "-i", MUSIC, "-t", f"{duration:.3f}", "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-af", "volume=0.90,loudnorm=I=-13:TP=-1.2:LRA=7,afade=t=in:st=0:d=0.35,afade=t=out:st=" + f"{max(0,duration-1.1):.3f}:d=1.1", "-shortest", OUTPUT])
    if not OUTPUT.exists() or OUTPUT.stat().st_size == 0:
        raise RuntimeError(f"Final MP4 was not created: {OUTPUT}")
    streams = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=codec_name", "-of", "csv=p=0", str(OUTPUT)], text=True).strip()
    if not streams:
        raise RuntimeError("Final MP4 has no audio stream")
    print(f"Verified audio stream: {streams}", flush=True)
