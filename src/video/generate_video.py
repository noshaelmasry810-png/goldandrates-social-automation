import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import arabic_reshaper
from bidi.algorithm import get_display

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
ARTIFACTS = ROOT / "artifacts"
FRAMES = ARTIFACTS / "frames"
FPS = 30
WIDTH = 1080
HEIGHT = 1920

KIND = os.environ.get("VIDEO_TYPE", "gold").strip().lower()
CONTENT = DATA_DIR / ("gold_content.json" if KIND == "gold" else "currency_content.json")
AUDIO = ARTIFACTS / f"goldandrates_{KIND}_voice.mp3"
OUTPUT = ARTIFACTS / f"goldandrates_{KIND}_daily.mp4"

FONT_REGULAR = None
FONT_BOLD = None


def run(command: list[str]) -> None:
    print(">", " ".join(command))
    subprocess.run(command, check=True)


def find_font(bold: bool = False) -> str:
    candidates = [
        "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf"
        if bold else "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf"
        if bold else "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return path
    result = subprocess.check_output(
        ["fc-match", "Noto Sans Arabic:style=Bold" if bold else "Noto Sans Arabic"],
        text=True,
    )
    path = result.split(":", 1)[0].strip()
    if Path(path).exists():
        return path
    raise FileNotFoundError("No Arabic-capable font was found")


def rtl(value: str) -> str:
    return get_display(arabic_reshaper.reshape(str(value)))


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REGULAR, size)


def wrap_rtl(text: str, fnt: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = str(text).split()
    if not words:
        return []

    dummy = Image.new("RGB", (10, 10))
    draw = ImageDraw.Draw(dummy)
    lines = []
    current = words[0]

    for word in words[1:]:
        candidate = f"{current} {word}"
        if draw.textbbox((0, 0), rtl(candidate), font=fnt)[2] <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word

    lines.append(current)
    return lines


def draw_text(
    img: Image.Image,
    text: str,
    y: int,
    size: int,
    bold: bool = False,
    max_width: int = 900,
    fill=(255, 255, 255),
) -> int:
    draw = ImageDraw.Draw(img)
    fnt = font(size, bold)
    lines = wrap_rtl(text, fnt, max_width)
    gap = max(10, size // 5)
    cursor = y

    for line in lines:
        display = rtl(line)
        bbox = draw.textbbox((0, 0), display, font=fnt)
        x = (WIDTH - (bbox[2] - bbox[0])) // 2
        draw.text((x, cursor), display, font=fnt, fill=fill)
        cursor += size + gap

    return cursor - y


def draw_plain_center(img: Image.Image, text: str, y: int, size: int, bold: bool = False, fill=(255, 224, 116)) -> None:
    draw = ImageDraw.Draw(img)
    fnt = font(size, bold)
    bbox = draw.textbbox((0, 0), str(text), font=fnt)
    x = (WIDTH - (bbox[2] - bbox[0])) // 2
    draw.text((x, y), str(text), font=fnt, fill=fill)


def background(seed: int) -> Image.Image:
    import math

    img = Image.new("RGB", (WIDTH, HEIGHT))
    px = img.load()

    for y in range(HEIGHT):
        t = y / max(1, HEIGHT - 1)
        base = int(10 + 18 * (1 - t))
        gold = int(28 + 24 * t)
        for x in range(WIDTH):
            glow = int(18 * max(0, 1 - abs(x - WIDTH * 0.5) / (WIDTH * 0.5)))
            px[x, y] = (base + glow // 3, base + glow // 4, gold)

    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)

    for i in range(9):
        y = 320 + i * 175
        pts = []
        for x in range(0, WIDTH + 1, 80):
            yy = y + int(34 * math.sin((x / 110.0) + seed * 0.8 + i))
            pts.append((x, yy))
        d.line(pts, fill=(238, 194, 73, 42), width=4)

    for i in range(16):
        x = (seed * 97 + i * 173) % WIDTH
        y = (seed * 53 + i * 211) % HEIGHT
        r = 3 + (i % 4) * 2
        d.ellipse((x - r, y - r, x + r, y + r), fill=(250, 214, 110, 68))

    overlay = overlay.filter(ImageFilter.GaussianBlur(0.8))
    return Image.alpha_composite(img.convert("RGBA"), overlay)


def panel(img: Image.Image, box: tuple[int, int, int, int]) -> None:
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle(
        box,
        radius=32,
        fill=(6, 9, 16, 218),
        outline=(231, 190, 76, 180),
        width=3,
    )
    img.alpha_composite(layer)


def footer(img: Image.Image) -> None:
    draw_text(img, "ذهب وأسعار", 1775, 32, True, 850, (245, 245, 247))
    draw_plain_center(img, "goldandrates.com", 1840, 34, True, (255, 224, 116))


def make_intro(content: dict) -> Path:
    img = background(1)
    panel(img, (65, 360, 1015, 1410))

    title = "أسعار الذهب اليوم" if KIND == "gold" else "سعر الدولار اليوم"
    draw_text(img, title, 150, 64, True, 920, (248, 219, 132))
    draw_text(img, content["hook"], 475, 46, True, 860, (246, 246, 248))

    if KIND == "gold":
        first = content["videoData"]["markets"][0]
        val = first["karats"]["21"]
        draw_text(img, "عيار 21 في مصر", 850, 48, True, 850, (235, 236, 241))
        draw_text(img, f"{money(val)} جنيه", 940, 104, True, 850, (255, 224, 116))
    else:
        rates = {item["code"]: item["value"] for item in content["videoData"]["rates"]}
        draw_text(img, "1 دولار =", 845, 52, True, 850, (235, 236, 241))
        draw_text(img, f"{fx_money(rates['EGP'])} جنيه مصري", 935, 90, True, 850, (255, 224, 116))

    footer(img)
    path = FRAMES / "01_intro.png"
    img.convert("RGB").save(path, quality=95)
    return path


def make_gold_market_slide(item: dict, index: int) -> Path:
    img = background(10 + index)
    panel(img, (70, 260, 1010, 1540))
    draw_text(img, item["name"], 340, 54, True, 900, (248, 219, 132))
    draw_text(img, "سعر الجرام", 445, 36, False, 850, (220, 223, 230))

    cards = [
        ("24", item["karats"]["24"]),
        ("22", item["karats"]["22"]),
        ("21", item["karats"]["21"]),
        ("18", item["karats"]["18"]),
    ]

    y = 585
    for karat, value in cards:
        panel(img, (130, y, 950, y + 190))
        draw_text(img, f"عيار {karat}", y + 28, 42, True, 760, (244, 244, 247))
        draw_text(img, f"{money(value)} {item['unit']}", y + 82, 58, True, 760, (255, 224, 116))
        y += 225

    footer(img)
    path = FRAMES / f"gold_{index:02d}.png"
    img.convert("RGB").save(path, quality=95)
    return path


def make_currency_slide(item: dict, index: int) -> Path:
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


def make_cta() -> Path:
    img = background(50)
    panel(img, (70, 470, 1010, 1430))
    draw_text(img, "ذهب وأسعار", 610, 72, True, 900, (255, 224, 116))
    draw_text(img, "أسعار الذهب والعملات تتحدث يوميًا", 760, 50, True, 900, (246, 246, 249))
    draw_plain_center(img, "goldandrates.com", 960, 56, True, (255, 224, 116))
    draw_text(img, "تابع التحديث القادم", 1085, 44, False, 850, (220, 223, 230))
    return_path = FRAMES / "99_cta.png"
    img.convert("RGB").save(return_path, quality=95)
    return return_path


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


def audio_duration(path: Path) -> float:
    output = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        text=True,
    ).strip()
    return max(1.0, float(output))


def make_segment(image_path: Path, duration: float, index: int) -> Path:
    segment = ARTIFACTS / f"{KIND}_segment_{index:02d}.mp4"
    vf = (
        "zoompan="
        "z='min(zoom+0.0007,1.08)':"
        "x='iw/2-(iw/zoom/2)':"
        "y='ih/2-(ih/zoom/2)':"
        "d=1:s=1080x1920:fps=30,"
        "format=yuv420p"
    )
    run([
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", str(image_path),
        "-t", f"{duration:.3f}",
        "-vf", vf,
        "-an",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "20",
        str(segment),
    ])
    return segment


def concat_segments(segments: list[Path]) -> Path:
    list_file = ARTIFACTS / f"{KIND}_segments.txt"
    list_file.write_text(
        "".join(f"file '{p.as_posix().replace(chr(39), chr(39) + chr(92) + chr(39) + chr(39))}'\n" for p in segments),
        encoding="utf-8",
    )
    silent = ARTIFACTS / f"{KIND}_silent.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(silent)])
    return silent


def mux_audio(video_path: Path, audio_path: Path, duration: float) -> None:
    run([
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-t", f"{duration:.3f}",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "160k",
        "-shortest",
        str(OUTPUT),
    ])


def main() -> None:
    global FONT_REGULAR, FONT_BOLD
    if KIND not in {"gold", "currency"}:
        raise SystemExit("VIDEO_TYPE must be gold or currency")
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise SystemExit("ffmpeg/ffprobe is required")
    if not CONTENT.exists():
        raise SystemExit(f"{CONTENT} not found")
    if not AUDIO.exists():
        raise SystemExit(f"{AUDIO} not found")

    FONT_REGULAR = find_font(False)
    FONT_BOLD = find_font(True)

    content = json.loads(CONTENT.read_text(encoding="utf-8"))
    FRAMES.mkdir(parents=True, exist_ok=True)

    slides = [make_intro(content)]

    if KIND == "gold":
        for idx, item in enumerate(content["videoData"]["markets"], start=1):
            slides.append(make_gold_market_slide(item, idx))
    else:
        for idx, item in enumerate(content["videoData"]["rates"], start=1):
            slides.append(make_currency_slide(item, idx))

    slides.append(make_cta())

    total = audio_duration(AUDIO)
    if KIND == "gold":
        middle = 0.78 / 4
        weights = [0.18] + [middle] * 4 + [0.04]
    else:
        middle = 0.78 / 4
        weights = [0.18] + [middle] * 4 + [0.04]

    durations = [total * w for w in weights]
    durations[-1] += total - sum(durations)

    segments = [
        make_segment(slides[i], durations[i], i + 1)
        for i in range(len(slides))
    ]

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
        "websiteName": "ذهب وأسعار",
        "websiteUrl": "https://goldandrates.com/",
        "hook": content.get("hook"),
        "hashtags": content.get("hashtags", []),
        "overrideApplied": content.get("overrideApplied", False),
    }

    (ARTIFACTS / f"{KIND}_video.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Generated: {OUTPUT}")
    print(f"Duration: {total:.2f}s")


if __name__ == "__main__":
    main()
