#!/usr/bin/env python3
"""Erzeugt die Logo- und Listing-Bilder für das Microsoft-Store-MSIX."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
ICON = ROOT / "snap" / "gui" / "icon-store-512.png"
SHOT = ROOT / "packaging" / "appstream" / "screenshots" / "window.png"
PKG = ROOT / "packaging" / "msix" / "Assets"
LISTING = ROOT / "packaging" / "microsoft-store"
BG = (18, 18, 22)
FONT = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
FONT_REG = "/System/Library/Fonts/Supplemental/Arial.ttf"


def font(size, bold=True):
    path = FONT if bold else FONT_REG
    return ImageFont.truetype(path, size)


def fit_icon(size, margin=0):
    icon = Image.open(ICON).convert("RGBA")
    box = size - margin * 2
    icon.thumbnail((box, box), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    x = (size - icon.width) // 2
    y = (size - icon.height) // 2
    canvas.paste(icon, (x, y), icon)
    return canvas


def save_png(image, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGBA").save(path, "PNG")


def wide_logo(width, height):
    canvas = Image.new("RGBA", (width, height), (*BG, 255))
    icon = fit_icon(height - 16)
    canvas.paste(icon, (12, (height - icon.height) // 2), icon)
    draw = ImageDraw.Draw(canvas)
    draw.text((height + 8, height // 2 - 8), "Universal Downloader", font=font(max(18, height // 5)), fill=(240, 240, 240, 255), anchor="lm")
    return canvas


def poster():
    canvas = Image.new("RGBA", (720, 1080), (*BG, 255))
    icon = fit_icon(520)
    canvas.paste(icon, ((720 - icon.width) // 2, 160), icon)
    draw = ImageDraw.Draw(canvas)
    draw.text((360, 760), "Universal", font=font(64), fill=(255, 255, 255, 255), anchor="mm")
    draw.text((360, 840), "Downloader", font=font(64), fill=(255, 255, 255, 255), anchor="mm")
    draw.text((360, 940), "Musik, Hörbücher und Videos", font=font(28, bold=False), fill=(180, 180, 180, 255), anchor="mm")
    return canvas


def hero():
    canvas = Image.new("RGBA", (1920, 1080), (*BG, 255))
    icon = fit_icon(640)
    canvas.paste(icon, (140, (1080 - icon.height) // 2), icon)
    draw = ImageDraw.Draw(canvas)
    draw.text((860, 430), "Universal Downloader", font=font(72), fill=(255, 255, 255, 255), anchor="lm")
    draw.text((860, 530), "Musik, Hörbücher und Videos", font=font(36, bold=False), fill=(190, 190, 190, 255), anchor="lm")
    draw.text((860, 620), "Windows und Windows auf ARM", font=font(32, bold=False), fill=(140, 200, 140, 255), anchor="lm")
    return canvas


def crop_window():
    im = Image.open(SHOT).convert("RGB")
    # Unteren Systemleisten-Streifen abschneiden (Cinnamon-Panel).
    w, h = im.size
    return im.crop((0, 0, w, h - 36))


def screenshot():
    window = crop_window()
    canvas = Image.new("RGB", (1920, 1080), BG)
    scale = min(1760 / window.width, 980 / window.height)
    resized = window.resize((int(window.width * scale), int(window.height * scale)), Image.Resampling.LANCZOS)
    x = (1920 - resized.width) // 2
    y = (1080 - resized.height) // 2
    canvas.paste(resized, (x, y))
    return canvas


def main():
    PKG.mkdir(parents=True, exist_ok=True)
    LISTING.mkdir(parents=True, exist_ok=True)

    for size, name in (
        (50, "StoreLogo.png"),
        (44, "Square44x44Logo.png"),
        (150, "Square150x150Logo.png"),
        (310, "Square310x310Logo.png"),
        (300, "Square150x150Logo.scale-200.png"),
    ):
        save_png(fit_icon(size), PKG / name)

    for target in (16, 24, 32, 48, 256):
        save_png(fit_icon(target), PKG / f"Square44x44Logo.targetsize-{target}.png")

    save_png(wide_logo(310, 150), PKG / "Wide310x150Logo.png")
    save_png(wide_logo(620, 300), PKG / "Wide310x150Logo.scale-200.png")
    save_png(wide_logo(620, 300), PKG / "SplashScreen.png")

    save_png(fit_icon(300), LISTING / "app-tile-300.png")
    save_png(poster(), LISTING / "poster-720x1080.png")
    save_png(hero(), LISTING / "hero-1920x1080.png")
    screenshot().save(LISTING / "screenshot-hauptfenster-1920x1080.png", "PNG")
    print("Assets geschrieben nach", PKG, "und", LISTING)


if __name__ == "__main__":
    main()
