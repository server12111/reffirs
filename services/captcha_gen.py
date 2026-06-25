import io
import random

from PIL import Image, ImageDraw, ImageFont

_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

_FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
]


def _load_font(size: int = 36) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in _FONT_PATHS:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def generate_code(length: int = 5) -> str:
    return "".join(random.choices(_CHARS, k=length))


def generate_image(code: str) -> bytes:
    W, H = 240, 85
    img = Image.new("RGB", (W, H), color=(248, 248, 248))
    draw = ImageDraw.Draw(img)

    # Background noise dots
    for _ in range(900):
        x = random.randint(0, W - 1)
        y = random.randint(0, H - 1)
        c = random.randint(170, 225)
        draw.point((x, y), fill=(c, c, c))

    # Distortion lines
    for _ in range(7):
        draw.line(
            [
                (random.randint(0, W), random.randint(0, H)),
                (random.randint(0, W), random.randint(0, H)),
            ],
            fill=(random.randint(90, 180),) * 3,
            width=1,
        )

    font = _load_font(36)
    char_w = W // (len(code) + 1)

    for i, ch in enumerate(code):
        x = int(char_w * (i + 0.55)) + random.randint(-4, 4)
        y = random.randint(8, 26)
        color = (
            random.randint(0, 90),
            random.randint(0, 90),
            random.randint(0, 90),
        )
        draw.text((x, y), ch, font=font, fill=color)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()
