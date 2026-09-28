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


def fit(src: Path, size: int, scale: float = 1.0) -> Image.Image:
    """Our own art from assets/ (logo.png, figure.png) squared around its visible part and
    scaled with premultiplied alpha, so the see-through edges don't pick up stray colors.
    scale < 1 leaves a clear margin: the art fills that share of the square."""
    im = Image.open(src).convert("RGBA")
    l, t, r, b = im.getchannel("A").getbbox()
    side = max(r - l, b - t)
    cx, cy = (l + r) // 2, (t + b) // 2
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.paste(im.crop((cx - side // 2, cy - side // 2, cx - side // 2 + side, cy - side // 2 + side)), (0, 0))
    inner = max(1, round(size * scale))
    art = sq.convert("RGBa").resize((inner, inner), Image.LANCZOS).convert("RGBA")
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(art, ((size - inner) // 2, (size - inner) // 2))
    px = out.load()
    for y in range(size):  # (fully clear pixels: black, not leftover color)
        for x in range(size):
            if px[x, y][3] == 0:
                px[x, y] = (0, 0, 0, 0)
    return out


def arrow(size: int = 64) -> Image.Image:
    """The viewer's white chevron pointing up (the way to go), with a soft dark shadow so it
    reads on sky and on sand alike. Drawn 4x larger and scaled down."""
    from PIL import ImageFilter

    k = 4
    s = size * k
    chevron = [(128, 30), (242, 144), (194, 192), (128, 126), (62, 192), (14, 144)]
    pts = [(x * s / 256, y * s / 256) for x, y in chevron]
    shadow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).polygon([(x, y + 3 * k) for x, y in pts], fill=(0, 0, 0, 170))
    shadow = shadow.filter(ImageFilter.GaussianBlur(4 * k))
    im = Image.alpha_composite(Image.new("RGBA", (s, s), (0, 0, 0, 0)), shadow)
    d = ImageDraw.Draw(im)
    d.polygon(pts, fill=(255, 255, 255, 255), outline=(40, 40, 40, 255), width=2 * k)
    return im.convert("RGBa").resize((size, size), Image.LANCZOS).convert("RGBA")


def make(media: Path) -> None:
    """Media/: Figure.tga (64x64, the map's drag figure: assets/figure.png, else drawn here),
    Logo.tga and Portrait.tga (128x128, assets/logo.png; the portrait with a margin) and Probe.jpg. TGAs are uncompressed 32-bit, like
    AzerothGPS's own art."""
    media.mkdir(parents=True, exist_ok=True)
    assets = media.parents[2] / "assets"
    fig = assets / "figure.png"
    (fit(fig, 64) if fig.exists() else figure()).save(media / "Figure.tga")
    probe_card().save(media / "Probe.jpg", "JPEG", quality=90)
    arrow().save(media / "Arrow.tga")  # the viewer's way-to-go chevrons
    if (assets / "logo.png").exists():
        fit(assets / "logo.png", 128).save(media / "Logo.tga")  # the addon list icon
        fit(assets / "logo.png", 128, 0.76).save(media / "Portrait.tga")  # the viewer's portrait: small enough that its round frame shows all of "StreetView"
    print(f"wrote Figure.tga, Logo.tga, Portrait.tga, Arrow.tga and Probe.jpg in {media}")
