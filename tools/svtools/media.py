"""The addon's own art, drawn here (no Blizzard files): the map figure and the JPEG test card."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FILL = (255, 196, 36, 255)
EDGE = (70, 44, 0, 255)


def figure(size: int = 64) -> Image.Image:
    """A little standing figure (the street view 'person'), drawn 4x larger and scaled down."""
    k = 4
    s = size * k
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    w = 5 * k  # outline width

    def shape(draw_fn):
        draw_fn(EDGE, w)
        draw_fn(FILL, 0)

    cx = s // 2
    head_r = 9 * k
    # legs, arms, body, head (outline first, then fill on top)
    for color, grow in ((EDGE, w), (FILL, 0)):
        g = grow
        d.rounded_rectangle((cx - 9 * k - g, 38 * k - g, cx - 2 * k + g, 60 * k + g), radius=3 * k, fill=color)
        d.rounded_rectangle((cx + 2 * k - g, 38 * k - g, cx + 9 * k + g, 60 * k + g), radius=3 * k, fill=color)
        d.rounded_rectangle((cx - 19 * k - g, 22 * k - g, cx - 12 * k + g, 42 * k + g), radius=3 * k, fill=color)
        d.rounded_rectangle((cx + 12 * k - g, 22 * k - g, cx + 19 * k + g, 42 * k + g), radius=3 * k, fill=color)
        d.rounded_rectangle((cx - 13 * k - g, 20 * k - g, cx + 13 * k + g, 44 * k + g), radius=6 * k, fill=color)
        d.ellipse((cx - head_r - g, 1 * k - g, cx + head_r + g, 1 * k + 2 * head_r + g), fill=color)
    return im.resize((size, size), Image.LANCZOS)


def probe_card() -> Image.Image:
    """256x128 test card: blue left, orange right, 'JPEG OK'."""
    im = Image.new("RGB", (256, 128), (20, 90, 200))
    d = ImageDraw.Draw(im)
    d.rectangle((128, 0, 255, 127), fill=(240, 140, 30))
    try:
        font = ImageFont.load_default(size=34)
    except TypeError:
        font = ImageFont.load_default()
    d.text((128, 64), "JPEG OK", fill=(255, 255, 255), font=font, anchor="mm", stroke_width=3,
           stroke_fill=(0, 0, 0))
    return im


def logo(src: Path, size: int = 128) -> Image.Image:
    """The StreetView logo (assets/logo.png, our own art) squared around its visible part and
    scaled with premultiplied alpha, so the see-through edges don't pick up stray colors."""
    im = Image.open(src).convert("RGBA")
    l, t, r, b = im.getchannel("A").getbbox()
    side = max(r - l, b - t)
    cx, cy = (l + r) // 2, (t + b) // 2
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.paste(im.crop((cx - side // 2, cy - side // 2, cx - side // 2 + side, cy - side // 2 + side)), (0, 0))
    out = sq.convert("RGBa").resize((size, size), Image.LANCZOS).convert("RGBA")
    px = out.load()
    for y in range(size):  # (fully clear pixels: black, not leftover color)
        for x in range(size):
            if px[x, y][3] == 0:
                px[x, y] = (0, 0, 0, 0)
    return out


def make(media: Path) -> None:
    media.mkdir(parents=True, exist_ok=True)
    figure().save(media / "Figure.tga")  # uncompressed 32-bit, like AzerothGPS's own art
    probe_card().save(media / "Probe.jpg", "JPEG", quality=90)
    src = media.parents[2] / "assets" / "logo.png"
    if src.exists():
        logo(src).save(media / "Logo.tga")
    print(f"wrote Figure.tga, Probe.jpg" + (" and Logo.tga" if src.exists() else "") + f" in {media}")
