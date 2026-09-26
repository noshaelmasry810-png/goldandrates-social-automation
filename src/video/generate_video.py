import json
import math
import os
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

try:
    from PIL import features
    HAS_RAQM = bool(features.check("raqm"))
except Exception:
    HAS_RAQM = False

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
except Exception:
    arabic_reshaper = None
    get_display = None

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
ARTIFACTS = ROOT / "artifacts"
FRAMES = ARTIFACTS / "frames"
BACKGROUND_DIR = ROOT / "assets" / "backgrounds"

FPS = 30
WIDTH = 1080
HEIGHT = 1920
KIND = os.environ.get("VIDEO_TYPE", "gold").strip().lower()
CONTENT = DATA_DIR / ("gold_content.json" if KIND == "gold" else "currency_content.json")
AUDIO = ARTIFACTS / f"goldandrates_{KIND}_voice.mp3"
VOICE_TIMING = ARTIFACTS / f"{KIND}_voice.json"
OUTPUT = ARTIFACTS / f"goldandrates_{KIND}_daily.mp4"
FONT_REGULAR = None
FONT_BOLD = None


def run(command: list[str]) -> None:
    print(">", " ".join(command), flush=True)
    subprocess.run(command, check=True)


def find_font(bold=False) -> str:
    candidates = [
        "/usr/local/share/fonts/Tajawal-Bold.ttf" if bold else "/usr/local/share/fonts/Tajawal-Regular.ttf",
        "/usr/share/fonts/truetype/tajawal/Tajawal-Bold.ttf" if bold else "/usr/share/fonts/truetype/tajawal/Tajawal-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf" if bold else "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf" if bold else "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return path
    style = "Bold" if bold else "Regular"
    path = subprocess.check_output(["fc-match", f"Tajawal:style={style}"], text=True).strip().split(":", 1)[0]
    if Path(path).exists():
        return path
    raise FileNotFoundError("No Arabic-capable font was found")


def rtl(value: str) -> str:
    text = str(value)
    if HAS_RAQM:
        return text
    if arabic_reshaper and get_display:
        return get_display(arabic_reshaper.reshape(text))
    raise RuntimeError("Arabic RTL rendering requires Pillow RAQM or arabic-reshaper/python-bidi.")


def fnt(size: int, bold=False):
    path = FONT_BOLD if bold else FONT_REGULAR
    if not path:
        raise RuntimeError("Fonts are not initialized")
    return ImageFont.truetype(path, size)


def draw_text(img, text, y, size, bold=False, max_width=900, fill=(255, 255, 255)):
    draw = ImageDraw.Draw(img)
    font_obj = fnt(size, bold)
    words = str(text).split()
    lines = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), rtl(candidate), font=font_obj, direction="rtl", language="ar") if HAS_RAQM else draw.textbbox((0, 0), rtl(candidate), font=font_obj)
        if current and bbox[2] - bbox[0] > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    gap = max(10, size // 5)
    cursor = y
    for line in lines:
        rendered = rtl(line)
        bbox = draw.textbbox((0, 0), rendered, font=font_obj, direction="rtl", language="ar") if HAS_RAQM else draw.textbbox((0, 0), rendered, font=font_obj)
        x = (WIDTH - (bbox[2] - bbox[0])) // 2
        if HAS_RAQM:
            draw.text((x, cursor), rendered, font=font_obj, fill=fill, direction="rtl", language="ar")
        else:
            draw.text((x, cursor), rendered, font=font_obj, fill=fill)
        cursor += size + gap
    return cursor - y


def center_plain(img, text, y, size, bold=False, fill=(255, 224, 116)):
    draw = ImageDraw.Draw(img)
    font_obj = fnt(size, bold)
    bbox = draw.textbbox((0, 0), str(text), font=font_obj)
    draw.text(((WIDTH - (bbox[2] - bbox[0])) // 2, y), str(text), font=font_obj, fill=fill)


def background(seed=1):
    asset = BACKGROUND_DIR / ("gold_video_background.png" if KIND == "gold" else "currency_video_background.png")
    if asset.exists():
        source = Image.open(asset).convert("RGB")
        ratio = max(WIDTH / source.width, HEIGHT / source.height)
        size = (int(source.width * ratio), int(source.height * ratio))
        source = source.resize(size, Image.Resampling.LANCZOS)
        left = (source.width - WIDTH) // 2
        top = (source.height - HEIGHT) // 2
        source = source.crop((left, top, left + WIDTH, top + HEIGHT))
        # The background stays intentionally soft/dim so prices and Arabic text stay dominant.
        source = source.filter(ImageFilter.GaussianBlur(4.5))
        img = source.convert("RGBA")
        img.alpha_composite(Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 95)))
        return img

    # Safe fallback if the two new assets have not been uploaded yet.
    img = Image.new("RGBA", (WIDTH, HEIGHT), (12, 12, 20, 255))
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    for i in range(9):
        y = 300 + i * 180
        pts = [(x, y + int(30 * math.sin(x / 120 + seed + i))) for x in range(0, WIDTH + 1, 80)]
        d.line(pts, fill=(238, 194, 73, 55), width=4)
    return Image.alpha_composite(img, overlay.filter(ImageFilter.GaussianBlur(1)))


def panel(img, box):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle(box, radius=32, fill=(6, 9, 16, 218), outline=(231, 190, 76, 180), width=3)
    img.alpha_composite(layer)


def footer(img):
    draw_text(img, "موقع ذهب وأسعار", 1775, 32, True, 850, (245, 245, 247))
    center_plain(img, "goldandrates.com", 1840, 34, True, (255, 224, 116))


def money(value):
    number = float(value)
    return f"{int(round(number)):,}" if abs(number - round(number)) < 0.005 else f"{number:,.2f}"


def fx_money(value):
    number = float(value)
    return f"{number:,.4f}" if number < 1 else f"{number:,.2f}"


def make_intro(content):
    img = background(1)
    panel(img, (65, 360, 1015, 1410))
    title = "أسعار الذهب اليوم" if KIND == "gold" else "سعر الدولار اليوم"
    draw_text(img, title, 150, 64, True, 920, (248, 219, 132))
    draw_text(img, content["hook"], 475, 46, True, 860, (246, 246, 248))
    if KIND == "gold":
        first = content["videoData"]["markets"][0]
        draw_text(img, "عيار 21 في مصر", 850, 48, True, 850, (235, 236, 241))
        draw_text(img, f"{money(first['karats']['21'])} جنيه", 940, 104, True, 850, (255, 224, 116))
    else:
        rates = {x["code"]: x["value"] for x in content["videoData"]["rates"]}
        draw_text(img, "1 دولار =", 845, 52, True, 850, (235, 236, 241))
        draw_text(img, f"{fx_money(rates['EGP'])} جنيه مصري", 935, 90, True, 850, (255, 224, 116))
    footer(img)
    path = FRAMES / "01_intro.png"
    img.convert("RGB").save(path, quality=95)
    return path


def make_gold_market_slide(item, index):
    img = background(10 + index)
    panel(img, (70, 260, 1010, 1540))
    draw_text(img, item["name"], 340, 54, True, 900, (248, 219, 132))
    draw_text(img, "سعر الجرام", 445, 36, False, 850, (220, 223, 230))
    y = 585
    for karat in ("24", "22", "21", "18"):
        panel(img, (130, y, 950, y + 190))
        draw_text(img, f"عيار {karat}", y + 28, 42, True, 760, (244, 244, 247))
        draw_text(img, f"{money(item['karats'][karat])} {item['unit']}", y + 82, 58, True, 760, (255, 224, 116))
        y += 225
    footer(img)
    path = FRAMES / f"gold_{index:02d}.png"
    img.convert("RGB").save(path, quality=95)
    return path


def make_currency_slide(item, index):
    img = background(20 + index)
    panel(img, (70, 430, 1010, 1390))
    draw_text(img, item["name"], 555, 58, True, 900, (248, 219, 132))
    draw_text(img, "مقابل دولار أمريكي واحد", 690, 40, False, 900, (220, 223, 230))
    draw_text(img, fx_money(item["value"]), 805, 108, True, 900, (255, 224, 116))
    draw_text(img, item["unit"], 950, 48, True, 900, (244, 244, 247))
    footer(img)
    path = FRAMES / f"fx_{index:02d}.png"
    img.convert("RGB").save(path, quality=95)
    return path


def make_cta():
    img = background(50)
    panel(img, (70, 470, 1010, 1430))
    draw_text(img, "موقع ذهب وأسعار", 610, 72, True, 900, (255, 224, 116))
    draw_text(img, "أسعار الذهب والعملات تتحدث يوميًا", 760, 50, True, 900, (246, 246, 249))
    center_plain(img, "goldandrates.com", 960, 56, True, (255, 224, 116))
    draw_text(img, "تابع التحديث القادم", 1085, 44, False, 850, (220, 223, 230))
    path = FRAMES / "99_cta.png"
    img.convert("RGB").save(path, quality=95)
    return path


def audio_duration(path):
    value = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)], text=True).strip()
    return max(1.0, float(value))


def make_segment(image_path, duration, index):
    segment = ARTIFACTS / f"{KIND}_segment_{index:02d}.mp4"
    vf = "zoompan=z='min(zoom+0.0007,1.08)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps=30,format=yuv420p"
    run(["ffmpeg", "-y", "-loop", "1", "-i", str(image_path), "-t", f"{duration:.3f}", "-vf", vf, "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", str(segment)])
    if not segment.exists() or segment.stat().st_size == 0:
        raise RuntimeError(f"Video segment was not created: {segment}")
    return segment


def concat_segments(segments):
    list_file = ARTIFACTS / f"{KIND}_segments.txt"
    list_file.write_text("".join(f"file '{p.as_posix()}'\n" for p in segments), encoding="utf-8")
    silent = ARTIFACTS / f"{KIND}_silent.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(silent)])
    if not silent.exists() or silent.stat().st_size == 0:
        raise RuntimeError(f"Silent video was not created: {silent}")
    return silent


def mux_audio(video_path, audio_path, duration):
    run(["ffmpeg", "-y", "-i", str(video_path), "-i", str(audio_path), "-t", f"{duration:.3f}", "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-af", "apad", "-shortest", str(OUTPUT)])
    if not OUTPUT.exists() or OUTPUT.stat().st_size == 0:
        raise RuntimeError(f"Final MP4 was not created: {OUTPUT}")


def main():
    global FONT_REGULAR, FONT_BOLD
    if KIND not in {"gold", "currency"}:
        raise SystemExit("VIDEO_TYPE must be gold or currency")
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            raise SystemExit(f"{tool} is required")
    if not CONTENT.exists():
        raise SystemExit(f"{CONTENT} not found")
    if not AUDIO.exists():
        raise SystemExit(f"{AUDIO} not found")

    FONT_REGULAR = find_font(False)
    FONT_BOLD = find_font(True)
    print(f"Arabic RAQM support: {HAS_RAQM}", flush=True)
    print(f"Regular font: {FONT_REGULAR}", flush=True)
    print(f"Bold font: {FONT_BOLD}", flush=True)

    content = json.loads(CONTENT.read_text(encoding="utf-8"))
    if not VOICE_TIMING.exists():
        raise SystemExit(f"{VOICE_TIMING} not found")
    timing = json.loads(VOICE_TIMING.read_text(encoding="utf-8"))
    scene_durations = [float(x["durationSeconds"]) for x in timing.get("segments", []) if float(x.get("durationSeconds", 0)) > 0]
    FRAMES.mkdir(parents=True, exist_ok=True)
    for old in ARTIFACTS.glob(f"{KIND}_segment_*.mp4"):
        old.unlink(missing_ok=True)
    OUTPUT.unlink(missing_ok=True)

    slides = [make_intro(content)]
    if KIND == "gold":
        slides.extend(make_gold_market_slide(item, i) for i, item in enumerate(content["videoData"]["markets"], 1))
    else:
        slides.extend(make_currency_slide(item, i) for i, item in enumerate(content["videoData"]["rates"], 1))
    slides.append(make_cta())

    total = audio_duration(AUDIO)
    if not 20.0 <= total <= 40.0:
        raise SystemExit(f"Generated narration duration is {total:.2f}s; expected 20-40s.")
    if len(scene_durations) != len(slides):
        raise SystemExit(f"Voice/video scene mismatch: {len(scene_durations)} voice segments for {len(slides)} video slides.")

    segments = [make_segment(slides[i], scene_durations[i], i + 1) for i in range(len(slides))]
    silent = concat_segments(segments)
    mux_audio(silent, AUDIO, total)

    metadata = {
        "generatedAt": content.get("generatedAt"),
        "videoType": KIND,
        "video": str(OUTPUT.relative_to(ROOT)),
        "width": WIDTH,
        "height": HEIGHT,
        "fps": FPS,
        "durationSeconds": round(total, 3),
        "voiceGender": content.get("voiceGender"),
        "voiceName": content.get("voiceName"),
        "websiteName": "موقع ذهب وأسعار",
        "websiteUrl": "https://goldandrates.com/",
        "font": "Tajawal",
        "arabicRtl": True,
        "background": "premium_gold" if KIND == "gold" else "premium_currency",
        "backgroundBlur": True,
        "hook": content.get("hook"),
        "hashtags": content.get("hashtags", []),
        "overrideApplied": content.get("overrideApplied", False),
    }
    (ARTIFACTS / f"{KIND}_video.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Generated: {OUTPUT}", flush=True)
    print(f"Duration: {total:.2f}s", flush=True)
    print(f"Scene durations: {[round(x, 2) for x in scene_durations]}", flush=True)


if __name__ == "__main__":
    main()
