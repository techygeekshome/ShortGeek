"""Persistent brand watermark, drawn once and cached -- appears on every video
so the channel reads as one consistent thing rather than one-off clips."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from ..config import CACHE_DIR, FONTS_DIR


def build_watermark(brand_handle: str, logo_letters: str = "TGH") -> str:
    out_path = CACHE_DIR / f"watermark_{abs(hash((brand_handle, logo_letters)))}.png"
    if out_path.exists():
        return str(out_path)

    pad = 14
    logo_box = 46
    font_handle = ImageFont.truetype(str(FONTS_DIR / "Roboto-Bold.ttf"), 26)
    font_logo = ImageFont.truetype(str(FONTS_DIR / "Roboto-Black.ttf"), 18)

    tmp = Image.new("RGB", (10, 10))
    tdraw = ImageDraw.Draw(tmp)
    text_w = tdraw.textlength(brand_handle, font=font_handle)

    w = int(pad * 3 + logo_box + text_w)
    h = logo_box + pad * 2

    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w, h], radius=h // 2, fill=(20, 22, 28, 150))
    d.rounded_rectangle([pad, pad, pad + logo_box, pad + logo_box], radius=12, fill=(79, 70, 229, 255))
    bbox = d.textbbox((0, 0), logo_letters, font=font_logo)
    lw, lh = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text((pad + (logo_box - lw) / 2, pad + (logo_box - lh) / 2 - bbox[1]), logo_letters, font=font_logo, fill=(255, 255, 255, 255))
    d.text((pad * 2 + logo_box, pad + (logo_box - 26) / 2), brand_handle, font=font_handle, fill=(255, 255, 255, 255))

    im.save(out_path)
    return str(out_path)
