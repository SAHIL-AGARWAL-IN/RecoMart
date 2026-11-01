"""Generate simple product images with Pillow.

Used for books and toys (DummyJSON has no photos for them) and as an offline
fallback when a product photo cannot be downloaded.
Every function returns WebP bytes for an 800x800 square image.
"""
import hashlib
import io

from PIL import Image, ImageDraw, ImageFilter, ImageFont

SIZE = 800

# Rich cover colours for books, bright playful colours for toys.
BOOK_COLOURS = ["#0F4C5C", "#7A1E3A", "#1F3A68", "#2E5E3A", "#5B2A86", "#8C3B12", "#22313F", "#00695C"]
TOY_COLOURS = ["#FF6B6B", "#FFB400", "#3DB2FF", "#2EC4B6", "#9B5DE5", "#F15BB5", "#00BB77", "#FF8C42"]
PASTELS = ["#FFF4E0", "#E8F6F3", "#EEF2FF", "#FDEDEC", "#F3E8FF", "#E9F7EF"]


def _pick(options, key):
    """Choose a colour deterministically, so re-seeding gives the same image."""
    digest = hashlib.md5(key.encode("utf-8")).hexdigest()
    return options[int(digest, 16) % len(options)]


def _font(size):
    try:
        return ImageFont.load_default(size=size)  # scalable font, Pillow >= 10.1
    except TypeError:
        return ImageFont.load_default()


def _wrap(draw, text, font, max_width):
    lines, current = [], ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _draw_lines(draw, lines, font, x, y, fill, line_gap=10, center_width=None):
    for line in lines:
        offset = 0
        if center_width:
            offset = (center_width - draw.textlength(line, font=font)) / 2
        draw.text((x + offset, y), line, font=font, fill=fill)
        y += font.size + line_gap
    return y


def _to_webp(image):
    buffer = io.BytesIO()
    image.save(buffer, format="WEBP", quality=88)
    return buffer.getvalue()


def _soft_shadow(canvas, box, radius=24):
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(box, radius=radius, fill=(0, 0, 0, 90))
    canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(22)))


def book_cover(title, author):
    """A standing book with a coloured cover, title and author."""
    canvas = Image.new("RGBA", (SIZE, SIZE), "#F4F1EC")
    cover = _pick(BOOK_COLOURS, title)
    left, top, width, height = 190, 70, 420, 640

    _soft_shadow(canvas, (left + 14, top + 22, left + width + 14, top + height + 22), radius=10)
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((left, top, left + width, top + height), radius=8, fill=cover)
    # Spine shading on the left edge.
    draw.rectangle((left, top, left + 26, top + height), fill=(0, 0, 0, 60))
    # Accent bars.
    draw.rectangle((left + 60, top + 70, left + width - 40, top + 76), fill="#F2B33D")
    draw.rectangle((left + 60, top + height - 120, left + width - 40, top + height - 117), fill="#F2B33D")

    title_font = _font(44 if len(title) < 30 else 36)
    lines = _wrap(draw, title, title_font, width - 110)[:6]
    _draw_lines(draw, lines, title_font, left + 60, top + 110, "#FFFFFF", line_gap=12)
    draw.text((left + 60, top + height - 95), author, font=_font(26), fill="#F7E7C6")
    return _to_webp(canvas.convert("RGB"))


def toy_image(name):
    """Playful geometric shapes on a pastel background, with the toy name."""
    canvas = Image.new("RGBA", (SIZE, SIZE), _pick(PASTELS, name))
    main = _pick(TOY_COLOURS, name)
    second = _pick(TOY_COLOURS, name[::-1])
    third = _pick(TOY_COLOURS, name + "x")

    _soft_shadow(canvas, (190, 160, 610, 560), radius=60)
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((190, 150, 610, 550), radius=60, fill=main)
    draw.ellipse((420, 90, 640, 310), fill=second)
    draw.polygon([(180, 560), (330, 330), (480, 560)], fill=third)
    draw.ellipse((300, 280, 340, 320), fill="#FFFFFF")
    draw.ellipse((460, 280, 500, 320), fill="#FFFFFF")

    font = _font(40)
    lines = _wrap(draw, name, font, SIZE - 160)[:2]
    _draw_lines(draw, lines, font, 80, 620, "#2B2B2B", center_width=SIZE - 160)
    return _to_webp(canvas.convert("RGB"))


def placeholder(name, category):
    """Offline fallback for catalog products whose photo could not be downloaded."""
    canvas = Image.new("RGBA", (SIZE, SIZE), _pick(PASTELS, category))
    draw = ImageDraw.Draw(canvas)
    accent = _pick(BOOK_COLOURS, category)
    draw.rounded_rectangle((120, 120, 680, 680), radius=48, outline=accent, width=6)
    draw.text((160, 170), category.upper(), font=_font(30), fill=accent)
    lines = _wrap(draw, name, _font(52), 480)[:4]
    _draw_lines(draw, lines, _font(52), 160, 300, "#1F2933", line_gap=14)
    return _to_webp(canvas.convert("RGB"))
