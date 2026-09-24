import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter, features

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
FONT_LATIN_REGULAR = None
FONT_LATIN_BOLD = None


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


def find_latin_font(bold: bool = False) -> str:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"
        if bold else "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return path
    result = subprocess.check_output(
        ["fc-match", "DejaVu Sans:style=Bold" if bold else "DejaVu Sans"],
        text=True,
    )
    path = result.split(":", 1)[0].strip()
    if Path(path).exists():
        return path
    raise FileNotFoundError("No Latin-capable font was found")


def font(size: int, bold: bool = False, latin: bool = False) -> ImageFont.FreeTypeFont:
    path = (
        FONT_LATIN_BOLD if bold else FONT_LATIN_REGULAR
        if latin
        else FONT_BOLD if bold else FONT_REGULAR
    )
    return ImageFont.truetype(path, size)


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
        bbox = draw.textbbox(
            (0, 0),
            candidate,
            font=fnt,
            direction="rtl",
            language="ar",
        )
        if (bbox[2] - bbox[0]) <= max_width:
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
        bbox = draw.textbbox(
            (0, 0),
            line,
            font=fnt,
            direction="rtl",
            language="ar",
        )
        width = bbox[2] - bbox[0]
        x = (WIDTH - width) // 2
        draw.text(
            (x, cursor),
            line,
            font=fnt,
            fill=fill,
            direction="rtl",
            language="ar",
        )
        cursor += size + gap

    return cursor - y


def draw_plain_center(
    img: Image.Image,
    text: str,
    y: int,
    size: int,
    bold: bool = False,
    fill=(255, 224, 116),
) -> None:
    draw = ImageDraw.Draw(img)
    fnt = font(size, bold, latin=True)
    bbox = draw.textbbox((0, 0), str(text), font=fnt)
    x = (WIDTH - (bbox[2] - bbox[0])) // 2
    draw.text((x, y), str(text), font=fnt, fill=fill)

