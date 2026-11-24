"""Build the app icons from the supplied logo.

Usage: uv run --with pillow python scripts/make_pwa_icons.py

Reads frontend/public/brand/tulpar-original.png and writes the round badge, favicons,
the Apple touch icon and the PWA icons (any + maskable) into frontend/public.
"""

from pathlib import Path

from PIL import Image, ImageDraw

PUBLIC = Path(__file__).resolve().parent.parent / "frontend" / "public"
SOURCE = PUBLIC / "brand" / "tulpar-original.png"
# The emblem (sun-shanyrak, tulpar, taxi, mountains) above the «Tulpar Taxi» wordmark.
EMBLEM_BOX = (135, 105, 1175, 892)
GOLD = (244, 180, 0, 255)
PAPER = (253, 252, 253, 255)


def emblem() -> Image.Image:
    return Image.open(SOURCE).convert("RGB").crop(EMBLEM_BOX)


def badge(size: int, ring_ratio: float = 0.035, fill_ratio: float = 0.80) -> Image.Image:
    """The round logo: the emblem on white inside a gold ring, drawn 4x and scaled down."""
    big = size * 4
    out = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(out)
    ring = max(2, int(big * ring_ratio))
    draw.ellipse((0, 0, big - 1, big - 1), fill=GOLD)
    draw.ellipse((ring, ring, big - 1 - ring, big - 1 - ring), fill=PAPER)
    inner = emblem()
    inner.thumbnail((int(big * fill_ratio), int(big * fill_ratio)), Image.LANCZOS)
    layer = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    layer.paste(inner, ((big - inner.width) // 2, (big - inner.height) // 2 + int(big * 0.02)))
    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).ellipse((ring, ring, big - 1 - ring, big - 1 - ring), fill=255)
    out.alpha_composite(Image.composite(layer, Image.new("RGBA", (big, big)), mask))
    return out.resize((size, size), Image.LANCZOS)


def maskable(size: int) -> Image.Image:
    """Full-bleed white square; the badge stays inside the 80 % safe zone of maskable icons."""
    canvas = Image.new("RGBA", (size, size), PAPER)
    inner = badge(int(size * 0.72))
    offset = (size - inner.width) // 2
    canvas.alpha_composite(inner, (offset, offset))
    return canvas


def on_white(image: Image.Image) -> Image.Image:
    flat = Image.new("RGB", image.size, PAPER[:3])
    flat.paste(image, (0, 0), image)
    return flat


def main() -> None:
    icons = PUBLIC / "icons"
    icons.mkdir(exist_ok=True)
    badge(256).save(PUBLIC / "brand" / "tulpar-badge.png", optimize=True)
    badge(64, ring_ratio=0.05, fill_ratio=0.84).save(PUBLIC / "favicon.png", optimize=True)
    on_white(badge(180)).save(PUBLIC / "apple-touch-icon.png", optimize=True)
    badge(192).save(icons / "icon-192.png", optimize=True)
    badge(512).save(icons / "icon-512.png", optimize=True)
    maskable(512).save(icons / "icon-maskable-512.png", optimize=True)
    print("Icons written to", PUBLIC)


if __name__ == "__main__":
    main()
