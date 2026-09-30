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


def sheet(src: Path, size: int = 64) -> Image.Image:
    """An animated GIF as a strip of frames side by side (the game has no GIFs: the addon shows one
    frame at a time with SetTexCoord): every frame squared around the part any frame shows, scaled
    to size x size with premultiplied alpha. Width size * frames, rounded up to a power of two."""
    from PIL import ImageSequence
    frames = [f.convert("RGBA") for f in ImageSequence.Iterator(Image.open(src))]
    boxes = [f.getchannel("A").getbbox() for f in frames]
    l, t = min(b[0] for b in boxes), min(b[1] for b in boxes)
    r, b = max(bx[2] for bx in boxes), max(bx[3] for bx in boxes)
    side = max(r - l, b - t)
    cx, cy = (l + r) // 2, (t + b) // 2
    width = 1
    while width < size * len(frames):
        width *= 2
    out = Image.new("RGBA", (width, size), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        sq.paste(f.crop((cx - side // 2, cy - side // 2, cx - side // 2 + side, cy - side // 2 + side)), (0, 0))
        out.paste(sq.convert("RGBa").resize((size, size), Image.LANCZOS).convert("RGBA"), (i * size, 0))
    px = out.load()
    for y in range(out.height):  # (fully clear pixels: black, not leftover color)
        for x in range(out.width):
            if px[x, y][3] == 0:
                px[x, y] = (0, 0, 0, 0)
    return out


def badge(src: Path, size: int = 64, fill: float = 0.8) -> Image.Image:
    """A round button icon: the first frame of an animation (still), on a black circle, the art
    filling `fill` of it. Drawn 4x larger and scaled down (smooth circle edge)."""
    k = 4
    s = size * k
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse((k, k, s - k - 1, s - k - 1), fill=(0, 0, 0, 255))
    art = Image.open(src).convert("RGBA")  # (the first frame)
    l, t, r, b = art.getchannel("A").getbbox()
    side = max(r - l, b - t)
    cx, cy = (l + r) // 2, (t + b) // 2
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.paste(art.crop((cx - side // 2, cy - side // 2, cx - side // 2 + side, cy - side // 2 + side)), (0, 0))
    inner = round(s * fill)
    sq = sq.convert("RGBa").resize((inner, inner), Image.LANCZOS).convert("RGBA")
    im.alpha_composite(sq, ((s - inner) // 2, (s - inner) // 2))
    return im.convert("RGBa").resize((size, size), Image.LANCZOS).convert("RGBA")


# Street Guess's orcs, in the order of Game.lua's Gm.ORCS (Guess1.tga ... Guess5.tga)
GUESS_ORCS = ["guess.gif", "guess_maghar_brown.gif", "guess_olive_drab.gif", "guess_golden_yellow.gif",
              "guess_forest_green.gif"]


PORTRAIT_BG = (33, 19, 10)  # the game window's title bar brown (sampled from a screenshot, 2026-09-30)


def on_disk(art: Image.Image, color: tuple[int, int, int]) -> Image.Image:
    """`art` over a filled disk as wide as it (smooth-edged: drawn 4x and scaled down)."""
    size = art.size[0]
    big = Image.new("RGBA", (size * 4, size * 4), (0, 0, 0, 0))
    ImageDraw.Draw(big).ellipse((0, 0, size * 4 - 1, size * 4 - 1), fill=color + (255,))
    disk = big.convert("RGBa").resize((size, size), Image.LANCZOS).convert("RGBA")
    return Image.alpha_composite(disk, art)


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
        # the viewer's portrait: small enough that its round frame shows all of "StreetView", on a
        # disk of the title bar's brown (else the picture shows through around the logo)
        on_disk(fit(assets / "logo.png", 128, 0.76), PORTRAIT_BG).save(media / "Portrait.tga")
    # Street Guess's guesses on the map: the user's orc animations, one per player (Game.lua Gm.ORCS)
    for i, name in enumerate(GUESS_ORCS, 1):
        if (assets / name).exists():
            sheet(assets / name).save(media / f"Guess{i}.tga")
    if (assets / "guess.gif").exists():  # Street Guess's button on the map: the orc, still, on a black circle
        badge(assets / "guess.gif").save(media / "GameIcon.tga")
    old = media / "Guess.tga"
    if old.exists():
        old.unlink()
    print(f"wrote Figure.tga, Logo.tga, Portrait.tga, Arrow.tga, Guess1-{len(GUESS_ORCS)}.tga, GameIcon.tga and Probe.jpg in {media}")
