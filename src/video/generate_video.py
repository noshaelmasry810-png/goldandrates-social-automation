import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import arabic_reshaper
from bidi.algorithm import get_display

ROOT = Path(__file__).resolve().parents[2]
CONTENT = ROOT / "data" / "content.json"
ARTIFACTS = ROOT / "artifacts"
FRAMES = ARTIFACTS / "frames"
AUDIO = ARTIFACTS / "goldandrates_voice.mp3"
OUTPUT = ARTIFACTS / "goldandrates_daily.mp4"

WIDTH = 1080
HEIGHT = 1920
FPS = 30


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
    try:
        result = subprocess.check_output(
            ["fc-match", "Noto Sans Arabic" if not bold else "Noto Sans Arabic:style=Bold"],
            text=True,
        )
        path = result.split(":", 1)[0].strip()
        if Path(path).exists():
            return path
    except Exception:
        pass
    raise FileNotFoundError("No Arabic-capable font was found on the runner")


FONT_REGULAR = find_font(False)
FONT_BOLD = find_font(True)


def rtl(text: str) -> str:
    shaped = arabic_reshaper.reshape(str(text))
    return get_display(shaped)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REGULAR, size)


def text_width(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.FreeTypeFont) -> float:
    bbox = draw.textbbox((0, 0), text, font=fnt)
    return bbox[2] - bbox[0]


def wrap_rtl(text: str, fnt: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = str(text).split()
    if not words:
        return []

    dummy = Image.new("RGB", (10, 10))
    draw = ImageDraw.Draw(dummy)
    lines: list[str] = []
    current = words[0]

    for word in words[1:]:
        candidate = current + " " + word
        if text_width(draw, rtl(candidate), fnt) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word

    lines.append(current)
    return lines


def draw_centered_plain_text(
    img: Image.Image,
    text: str,
    y: int,
    size: int,
    bold: bool = False,
    fill=(255, 255, 255),
) -> int:
    draw = ImageDraw.Draw(img)
    fnt = font(size, bold)
    bbox = draw.textbbox((0, 0), str(text), font=fnt)
    w = bbox[2] - bbox[0]
    draw.text(((WIDTH - w) // 2, y), str(text), font=fnt, fill=fill)
    return bbox[3] - bbox[1]


def draw_centered_text(
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
    line_gap = max(10, size // 5)
    total_h = len(lines) * size + max(0, len(lines) - 1) * line_gap
    cursor = y

    for line in lines:
        display_line = rtl(line)
        bbox = draw.textbbox((0, 0), display_line, font=fnt)
        w = bbox[2] - bbox[0]
        x = (WIDTH - w) // 2
        draw.text((x, cursor), display_line, font=fnt, fill=fill)
        cursor += size + line_gap

    return total_h


def background(seed: int) -> Image.Image:
    img = Image.new("RGB", (WIDTH, HEIGHT))
    px = img.load()

    for y in range(HEIGHT):
        t = y / (HEIGHT - 1)
        base = int(12 + 16 * (1 - t))
        gold = int(32 + 20 * t)
        for x in range(WIDTH):
            glow = int(18 * max(0, 1 - abs(x - WIDTH * 0.5) / (WIDTH * 0.5)))
            px[x, y] = (base + glow // 3, base + glow // 4, gold)

    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Soft abstract gold market lines.
    for i in range(8):
        y = 330 + i * 190
        points = []
        for x in range(0, WIDTH + 1, 90):
            yy = y + int(40 * __import__("math").sin((x / 120.0) + seed * 0.7 + i))
            points.append((x, yy))
        draw.line(points, fill=(238, 194, 73, 45), width=5)

    # Decorative circles.
    for i in range(14):
        x = (seed * 83 + i * 157) % WIDTH
        y = (seed * 47 + i * 223) % HEIGHT
        r = 3 + (i % 4) * 3
        draw.ellipse((x - r, y - r, x + r, y + r), fill=(248, 211, 100, 70))

    overlay = overlay.filter(ImageFilter.GaussianBlur(0.8))
    return Image.alpha_composite(img.convert("RGBA"), overlay)


def panel(img: Image.Image, xy: tuple[int, int, int, int], alpha: int = 210) -> None:
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle(xy, radius=34, fill=(7, 10, 18, alpha), outline=(231, 190, 76, 180), width=3)
    img.alpha_composite(layer)


def make_header(img: Image.Image, title: str, subtitle: str = "") -> None:
    draw_centered_text(img, title, 135, 62, True, 920, (248, 219, 132))
    if subtitle:
        draw_centered_text(img, subtitle, 225, 34, False, 900, (230, 232, 238))


def make_hook_slide(content: dict) -> Path:
    img = background(1)
    make_header(img, "أسعار الذهب اليوم", "تحديث ذهب وأسعار")
    panel(img, (70, 430, 1010, 1270))

    p21 = content["karats"]["21"]
    draw_centered_text(img, "عيار 21", 545, 58, True, 900, (236, 236, 240))
    draw_centered_text(
        img,
        f"{p21} جنيه",
        650,
        116,
        True,
        900,
        (255, 223, 113),
    )
    draw_centered_text(
        img,
        "سعر الجرام اليوم",
        820,
        42,
        False,
        900,
        (225, 225, 230),
    )
    draw_centered_text(
        img,
        "تابع الأسعار لحظة بلحظة",
        1030,
        48,
        True,
        900,
        (245, 245, 248),
    )

    title = "ذهب وأسعار"
    d = ImageDraw.Draw(img)
    f = font(40, True)
    display = rtl(title)
    w = text_width(d, display, f)
    d.text(((WIDTH - w) // 2, 1430), display, font=f, fill=(231, 190, 76))

    path = FRAMES / "01_hook.png"
    img.convert("RGB").save(path, quality=95)
    return path


def make_prices_slide(content: dict) -> Path:
    img = background(2)
    make_header(img, "أسعار الذهب اليوم", "السعر المرجعي للجرام في مصر")
    cards = [
        ("24", content["karats"]["24"]),
        ("22", content["karats"]["22"]),
        ("21", content["karats"]["21"]),
        ("18", content["karats"]["18"]),
    ]

    start_y = 390
    card_h = 285
    gap = 38

    for idx, (karat, value) in enumerate(cards):
        y1 = start_y + idx * (card_h + gap)
        panel(img, (85, y1, 995, y1 + card_h), 220)
        draw_centered_text(img, f"عيار {karat}", y1 + 42, 48, True, 820)
        draw_centered_text(
            img,
            f"{value} جنيه",
            y1 + 116,
            72,
            True,
            820,
            (255, 224, 116),
        )
        draw_centered_text(
            img,
            "للجرام",
            y1 + 210,
            30,
            False,
            820,
            (205, 208, 215),
        )

    path = FRAMES / "02_prices.png"
    img.convert("RGB").save(path, quality=95)
    return path


def make_trend_slide(content: dict) -> Path:
    img = background(3)
    make_header(img, "ما الجديد في سوق الذهب؟", "إشارة ترند مرتبطة بالذهب")
    panel(img, (75, 430, 1005, 1330))

    trends = content.get("trendSignals") or []
    if trends:
        draw_centered_text(
            img,
            trends[0],
            555,
            45,
            True,
            820,
            (245, 245, 248),
        )
    else:
        draw_centered_text(
            img,
            "تابع حركة الذهب والأسعار اليومية مع ذهب وأسعار.",
            620,
            52,
            True,
            820,
            (245, 245, 248),
        )

    # Keep the trend separate from the price claim.
    draw_centered_text(
        img,
        "تحقق من السعر الحالي قبل اتخاذ أي قرار شراء أو بيع.",
        1080,
        34,
        False,
        820,
        (210, 213, 220),
    )

    path = FRAMES / "03_trend.png"
    img.convert("RGB").save(path, quality=95)
    return path


def make_cta_slide() -> Path:
    img = background(4)
    make_header(img, "تابع ذهب وأسعار", "تحديثات الذهب اليومية")
    panel(img, (85, 520, 995, 1280))

    draw_centered_text(
        img,
        "أسعار 24 و22 و21 و18",
        660,
        62,
        True,
        850,
        (255, 224, 116),
    )
    draw_centered_text(
        img,
        "تتحدث يوميًا",
        805,
        58,
        True,
        850,
        (246, 246, 249),
    )
    draw_centered_text(
        img,
        "احفظ الفيديو وتابع التحديث القادم",
        1015,
        42,
        False,
        850,
        (220, 223, 230),
    )
    draw_centered_plain_text(
        img,
        "goldandrates.com",
        1165,
        48,
        True,
        (255, 224, 116),
    )
    draw_centered_text(
        img,
        "ذهب وأسعار",
        1240,
        44,
        True,
        850,
        (246, 246, 249),
    )

    path = FRAMES / "04_cta.png"
    img.convert("RGB").save(path, quality=95)
    return path


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
    segment = ARTIFACTS / f"segment_{index:02d}.mp4"
    # Slow zoom gives the still design a subtle motion effect without
    # distracting from the narrator.
    vf = (
        "zoompan="
        "z='min(zoom+0.0007,1.08)':"
        "x='iw/2-(iw/zoom/2)':"
        "y='ih/2-(ih/zoom/2)':"
        "d=1:s=1080x1920:fps=30,"
        "format=yuv420p"
    )
    run(
        [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            str(image_path),
            "-t",
            f"{duration:.3f}",
            "-vf",
            vf,
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "20",
            str(segment),
        ]
    )
    return segment


def concat_segments(segments: list[Path]) -> Path:
    list_file = ARTIFACTS / "segments.txt"
    list_file.write_text(
        "".join(f"file '{p.as_posix().replace(chr(39), chr(39) + chr(92) + chr(39) + chr(39))}'\n" for p in segments),
        encoding="utf-8",
    )
    silent = ARTIFACTS / "goldandrates_video_silent.mp4"
    run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-c",
            "copy",
            str(silent),
        ]
    )
    return silent


def mux_audio(video_path: Path, audio_path: Path, duration: float) -> None:
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-i",
            str(audio_path),
            "-t",
            f"{duration:.3f}",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-shortest",
            str(OUTPUT),
        ]
    )


def main() -> None:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise SystemExit("ffmpeg/ffprobe is required")
    if not CONTENT.exists():
        raise SystemExit("data/content.json not found")
    if not AUDIO.exists():
        raise SystemExit("artifacts/goldandrates_voice.mp3 not found")

    content = json.loads(CONTENT.read_text(encoding="utf-8"))
    if content.get("language") != "ar":
        raise SystemExit("Expected Arabic content.json")

    FRAMES.mkdir(parents=True, exist_ok=True)

    slides = [
        make_hook_slide(content),
        make_prices_slide(content),
        make_trend_slide(content),
        make_cta_slide(),
    ]

    total = audio_duration(AUDIO)

    # Proportions match the narrative structure. The final duration is adjusted
    # automatically so video and audio end together.
    weights = [0.22, 0.38, 0.24, 0.16]
    durations = [total * w for w in weights]
    durations[-1] += total - sum(durations)

    segments = [
        make_segment(slides[i], durations[i], i + 1)
        for i in range(len(slides))
    ]

    silent = concat_segments(segments)
    mux_audio(silent, AUDIO, total)

    metadata = {
        "generatedAt": content.get("generatedAtUtc") or content.get("generatedAt"),
        "video": str(OUTPUT.relative_to(ROOT)),
        "width": WIDTH,
        "height": HEIGHT,
        "fps": FPS,
        "durationSeconds": round(total, 3),
        "voiceGender": content.get("voiceGender"),
        "voiceName": content.get("voiceName"),
        "hook": content.get("hook"),
        "hashtags": content.get("hashtags", []),
    }

    (ARTIFACTS / "video.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Generated: {OUTPUT}")
    print(f"Duration: {total:.2f}s")


if __name__ == "__main__":
    main()
