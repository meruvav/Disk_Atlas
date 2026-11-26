#!/usr/bin/env python3
"""
Disk Atlas — Icon Generator

Renders the app icon (layered "atlas" glyph on the dark brand surface)
and writes all distribution formats into packaging/assets/:

    diskatlas.png          1024x1024 master
    diskatlas.ico          Windows (16..256 px, multi-size)
    diskatlas.icns         macOS (PNG-embedded entries)
    iconset/*.png          intermediate sizes

The glyph mirrors the in-app logo (feather "layers"): three stacked
layers colored by the app's size legend — cyan (small), amber (medium),
coral (large).

Usage:  python packaging/assets/make_icons.py
Requires: Pillow
"""
import struct
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ASSETS = Path(__file__).resolve().parent
MASTER = 1024

# Brand palette (src/web/style.css)
BG_TOP = (22, 29, 48)       # #161d30  (between --bg-card and --bg-card-hover)
BG_BOTTOM = (10, 13, 20)    # #0a0d14  (--bg-primary)
CYAN = (0, 240, 255)        # --accent-cyan
AMBER = (245, 158, 11)      # --accent-amber
CORAL = (239, 68, 68)       # --accent-coral

ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]
ICNS_ENTRIES = [  # (fourcc, pixel size)
    (b"ic07", 128), (b"ic08", 256), (b"ic09", 512), (b"ic10", 1024),
    (b"ic11", 32), (b"ic12", 64), (b"ic13", 512), (b"ic14", 1024),
]


def rounded_rect_mask(size, radius):
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return mask


def draw_background(size):
    """Dark brand surface: vertical gradient, soft top light, rounded corners."""
    col = Image.new("RGB", (1, size))
    for y in range(size):
        t = y / (size - 1)
        col.putpixel((0, y), tuple(
            int(BG_TOP[c] + (BG_BOTTOM[c] - BG_TOP[c]) * t) for c in range(3)))
    img = col.resize((size, size)).convert("RGBA")

    # Soft top light for depth
    light = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(light)
    d.ellipse([size * 0.08, -size * 0.42, size * 0.92, size * 0.34],
              fill=(80, 110, 170, 46))
    img.alpha_composite(light.filter(ImageFilter.GaussianBlur(radius=size * 0.05)))

    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(img, (0, 0), rounded_rect_mask(size, int(size * 0.225)))
    return out


def stroke_path(draw, points, color, width, closed=False, joint="curve"):
    draw.line(points, fill=color + (255,), width=width, joint=joint)
    if closed:
        draw.line([points[-1], points[0]], fill=color + (255,), width=width)


def draw_glyph(size):
    """The three stacked layers, stroked, with a soft glow."""
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx = size / 2
    w = max(2, int(size * 0.072))            # stroke width
    rx = size * 0.288                        # half-width of a layer
    ry = size * 0.144                        # half-height of the diamond
    y0 = size * 0.330                        # diamond center y
    gap = size * 0.144                       # vertical pitch between layers

    diamond = [(cx, y0 - ry), (cx + rx, y0), (cx, y0 + ry), (cx - rx, y0)]
    stroke_path(d, diamond, CYAN, w, closed=True)

    for i, color in enumerate((AMBER, CORAL), start=1):
        y = y0 + gap * i
        chevron = [(cx - rx, y), (cx, y + ry), (cx + rx, y)]
        stroke_path(d, chevron, color, w)

    # Soft glow behind the glyph
    glow = layer.filter(ImageFilter.GaussianBlur(radius=size * 0.016))
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.alpha_composite(glow)
    out.alpha_composite(glow)
    out.alpha_composite(layer)
    return out


def render_master():
    img = draw_background(MASTER)
    img.alpha_composite(draw_glyph(MASTER))
    return img


def write_ico(master, sizes):
    # Pillow generates every requested size from the master itself
    master.save(ASSETS / "diskatlas.ico", format="ICO",
                sizes=[(s, s) for s in sizes])


def write_icns(master):
    """Assemble a valid .icns container with PNG-compressed entries."""
    import io
    entries = []
    for fourcc, px in ICNS_ENTRIES:
        buf = io.BytesIO()
        master.resize((px, px), Image.LANCZOS).save(buf, format="PNG")
        data = buf.getvalue()
        entries.append(fourcc + struct.pack(">I", 8 + len(data)) + data)
    blob = b"".join(entries)
    (ASSETS / "diskatlas.icns").write_bytes(
        b"icns" + struct.pack(">I", 8 + len(blob)) + blob)


def main():
    master = render_master()
    master.save(ASSETS / "diskatlas.png")

    iconset = ASSETS / "iconset"
    iconset.mkdir(exist_ok=True)
    for s in sorted(set(ICO_SIZES + [px for _, px in ICNS_ENTRIES])):
        master.resize((s, s), Image.LANCZOS).save(iconset / f"icon_{s}x{s}.png")

    write_ico(master, ICO_SIZES)
    write_icns(master)

    print("Wrote:")
    for f in ["diskatlas.png", "diskatlas.ico", "diskatlas.icns"]:
        p = ASSETS / f
        print(f"  {p.name:16s} {p.stat().st_size / 1024:8.1f} KB")


if __name__ == "__main__":
    main()
