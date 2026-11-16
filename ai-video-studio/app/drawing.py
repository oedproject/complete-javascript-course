"""Yazı tipi bulma, altyazı çizimi ve sahte (mock) kare üretimi."""
from __future__ import annotations

import hashlib
import textwrap
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter, ImageFont

_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
]


@lru_cache(maxsize=16)
def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def caption_overlay(size: tuple[int, int], text: str) -> Image.Image | None:
    """Videonun altına konacak, şeffaf arka planlı altyazı katmanı (RGBA)."""
    text = (text or "").strip()
    if not text:
        return None
    w, h = size
    fs = max(16, int(min(w, h) * 0.055))
    f = font(fs)
    chars = max(12, int(w / (fs * 0.55)))
    lines = textwrap.wrap(text, width=chars)[:3]
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    line_h = int(fs * 1.25)
    total = line_h * len(lines)
    y = h - total - int(h * 0.07)
    for line in lines:
        tw = d.textlength(line, font=f)
        x = (w - tw) / 2
        d.text((x, y), line, font=f, fill=(255, 255, 255, 255),
               stroke_width=max(2, fs // 12), stroke_fill=(0, 0, 0, 220))
        y += line_h
    return layer


def mock_image(prompt: str, size: tuple[int, int], seed: int) -> Image.Image:
    """AI olmadan test için: istemden türetilmiş renkli bir kare."""
    h = hashlib.sha256(f"{prompt}|{seed}".encode()).digest()
    c1 = (h[0], h[1], h[2])
    c2 = (h[3], h[4], h[5])
    w, hh = size
    img = Image.new("RGB", size, c1)
    top = Image.new("RGB", size, c2)
    mask = Image.linear_gradient("L").resize(size)
    img = Image.composite(top, img, mask)
    d = ImageDraw.Draw(img)
    for i in range(6):
        r = int(min(w, hh) * (0.08 + h[6 + i] / 255 * 0.2))
        cx = int(h[12 + i] / 255 * w)
        cy = int(h[18 + i] / 255 * hh)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(h[24 + i], h[i], h[30 - i]))
    img = img.filter(ImageFilter.GaussianBlur(radius=max(2, w // 120)))
    d = ImageDraw.Draw(img)
    fs = max(14, w // 26)
    f = font(fs)
    lines = textwrap.wrap(prompt or "(boş istem)", width=max(12, int(w / (fs * 0.6))))[:4]
    y = hh // 2 - len(lines) * fs // 2
    for line in lines:
        tw = d.textlength(line, font=f)
        d.text(((w - tw) / 2, y), line, font=f, fill="white", stroke_width=2, stroke_fill="black")
        y += int(fs * 1.3)
    d.text((10, 8), "MOCK", font=font(max(12, w // 40)), fill="white")
    return img
