# Loaded automatically by Python before generate_video.py when src/video is on sys.path.
# Adds the supplied goldandrates logo after the background dimming layer, so the logo
# stays crisp while the photographic background remains soft.
import base64
from io import BytesIO

from PIL import Image

try:
    from logo_asset import LOGO_PNG_B64

    _original_alpha_composite = Image.Image.alpha_composite
    _logo = Image.open(BytesIO(base64.b64decode(LOGO_PNG_B64))).convert("RGBA")

    def _alpha_composite_with_logo(self, *args, **kwargs):
        result = _original_alpha_composite(self, *args, **kwargs)
        try:
            source = args[0] if args else kwargs.get("source")
            if (
                self.size == (1080, 1920)
                and source is not None
                and getattr(source, "size", None) == self.size
                and source.mode == "RGBA"
                and source.getpixel((0, 0))[:4] == (0, 0, 0, 95)
            ):
                logo = _logo.copy()
                target_width = 150
                target_height = max(1, int(logo.height * target_width / logo.width))
                logo = logo.resize((target_width, target_height), Image.Resampling.LANCZOS)
                x = (self.width - target_width) // 2
                y = 55
                plate = Image.new("RGBA", self.size, (0, 0, 0, 0))
                from PIL import ImageDraw
                draw = ImageDraw.Draw(plate)
                draw.rounded_rectangle(
                    (x - 22, y - 16, x + target_width + 22, y + target_height + 16),
                    radius=22,
                    fill=(4, 7, 12, 125),
                )
                self.alpha_composite(plate)
                self.alpha_composite(logo, (x, y))
        except Exception as exc:
            print(f"Logo overlay warning: {exc}", flush=True)
        return result

    Image.Image.alpha_composite = _alpha_composite_with_logo
except Exception as exc:
    print(f"Logo initialization warning: {exc}", flush=True)
