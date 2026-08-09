"""Turns real content into styled 'cards' -- the actual visual that appears
on screen for each script beat. Three kinds, chosen automatically per beat:

  - screenshot card : a real image from the guide, framed like a browser/app
                       window with a drop shadow
  - code card       : the guide's own code/command text, shown as a styled
                       editor block with light keyword colouring
  - bullet card      : plain step text with no image, shown as a big bold
                       numbered callout

Nothing here is AI-generated -- every pixel is either a real downloaded
image or text drawn straight from the source/script.
"""
from __future__ import annotations

import io
import re
from pathlib import Path
from typing import List, Optional, Tuple

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from ..config import FONTS_DIR

CARD_W = 900
BRAND_ACCENT = (79, 70, 229)      # matches the mockup's indigo accent
BRAND_TEAL = (14, 165, 183)
CARD_BG = (245, 246, 248, 255)
CODE_BG = (15, 18, 26, 255)

_UA = "TGH-Shorts-Studio/1.0 (+local content tool)"

_FONT_CACHE: dict = {}


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    key = (name, size)
    if key not in _FONT_CACHE:
        _FONT_CACHE[key] = ImageFont.truetype(str(FONTS_DIR / name), size)
    return _FONT_CACHE[key]


def fetch_image(url: str, timeout: int = 20) -> Optional[Image.Image]:
    try:
        resp = requests.get(url, headers={"User-Agent": _UA}, timeout=timeout)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content))
        img = img.convert("RGB")
        return img
    except Exception:
        return None


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.ImageDraw) -> List[str]:
    words = text.split()
    lines: List[str] = []
    current = ""
    for word in words:
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


def _shadow_layer(w: int, h: int, radius: int, blur: int = 26, alpha: int = 130, pad: int = 60) -> Image.Image:
    canvas = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle([pad, pad, pad + w, pad + h], radius=radius, fill=(0, 0, 0, alpha))
    return canvas.filter(ImageFilter.GaussianBlur(blur))


def render_screenshot_card(image: Image.Image, out_path: str, max_w: int = CARD_W, max_h: int = 1300) -> Tuple[str, int, int]:
    """Real screenshot, framed like a browser/app window. Returns (path, w, h).

    Not called by the default render pipeline (video/assemble.py) -- full
    desktop-scale screenshots don't stay legible at 9:16 phone-viewing
    size, so every beat now renders as a code/bullet card instead. Left
    here (and fetch_image() below) in case a smaller inset-thumbnail
    treatment gets added later."""
    iw, ih = image.size
    scale = min(max_w / iw, max_h / ih, 1.0) if iw > max_w or ih > max_h else max_w / iw
    scale = min(scale, max_w / iw)
    body_w = max_w
    body_h = int(ih * (body_w / iw))
    body_h = min(body_h, max_h)
    image = image.resize((body_w, max(1, int(ih * body_w / iw))), Image.LANCZOS)
    if image.height > body_h:
        image = image.crop((0, 0, body_w, body_h))

    chrome_h = 42
    total_h = chrome_h + body_h
    radius = 22

    shadow = _shadow_layer(body_w, total_h, radius)
    pad = (shadow.width - body_w) // 2

    card = Image.new("RGBA", (body_w, total_h), (0, 0, 0, 0))
    mask = Image.new("L", (body_w, total_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, body_w, total_h], radius=radius, fill=255)

    flat = Image.new("RGBA", (body_w, total_h), CARD_BG)
    d = ImageDraw.Draw(flat)
    d.rectangle([0, 0, body_w, chrome_h], fill=(231, 233, 238, 255))
    for i, cx in enumerate([24, 46, 68]):
        d.ellipse([cx, chrome_h // 2 - 6, cx + 12, chrome_h // 2 + 6], fill=(198, 201, 210, 255))
    flat.paste(image, (0, chrome_h))
    card = Image.composite(flat, card, mask)

    out = Image.new("RGBA", shadow.size, (0, 0, 0, 0))
    out.alpha_composite(shadow)
    out.alpha_composite(card, (pad, pad))
    out.save(out_path)
    return out_path, out.width, out.height


_KEYWORDS = re.compile(
    r"\b(Get-|Set-|New-|Remove-|Start-|Stop-|Enable-|Disable-|Import-|Export-|sudo|apt|winget|systemctl|function|if|foreach|return)\S*",
    re.IGNORECASE,
)


def render_code_card(code_text: str, out_path: str, max_w: int = CARD_W) -> Tuple[str, int, int]:
    """The guide's own command/code text, styled like an editor. Light,
    regex-based keyword colouring -- not a full syntax highlighter, but
    enough to read as 'real code' rather than a wall of plain text."""
    pad_x, pad_y = 34, 30
    line_h = 40
    mono = _font("DejaVuSansMono.ttf", 26)
    mono_b = _font("DejaVuSansMono-Bold.ttf", 26)

    tmp = Image.new("RGB", (10, 10))
    tdraw = ImageDraw.Draw(tmp)
    raw_lines = code_text.strip().splitlines() or [code_text]
    wrapped: List[str] = []
    for rl in raw_lines:
        wrapped.extend(_wrap_text(rl, mono, max_w - pad_x * 2 - 40, tdraw) or [""])
    wrapped = wrapped[:9]

    body_h = pad_y * 2 + 40 + len(wrapped) * line_h
    radius = 20

    shadow = _shadow_layer(max_w, body_h, radius)
    pad = (shadow.width - max_w) // 2

    flat = Image.new("RGBA", (max_w, body_h), CODE_BG)
    d = ImageDraw.Draw(flat)
    d.rectangle([0, 0, max_w, 40], fill=(30, 34, 46, 255))
    for i, cx in enumerate([24, 46, 68]):
        d.ellipse([cx, 14, cx + 12, 26], fill=(70, 76, 92, 255))

    y = 40 + pad_y
    for line in wrapped:
        x = pad_x
        last = 0
        for m in _KEYWORDS.finditer(line):
            if m.start() > last:
                d.text((x, y), line[last:m.start()], font=mono, fill=(214, 217, 224, 255))
                x += d.textlength(line[last:m.start()], font=mono)
            d.text((x, y), m.group(), font=mono_b, fill=(94, 234, 212, 255))
            x += d.textlength(m.group(), font=mono_b)
            last = m.end()
        if last < len(line):
            d.text((x, y), line[last:], font=mono, fill=(214, 217, 224, 255))
        y += line_h

    mask = Image.new("L", (max_w, body_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, max_w, body_h], radius=radius, fill=255)
    card = Image.composite(flat, Image.new("RGBA", (max_w, body_h), (0, 0, 0, 0)), mask)

    out = Image.new("RGBA", shadow.size, (0, 0, 0, 0))
    out.alpha_composite(shadow)
    out.alpha_composite(card, (pad, pad))
    out.save(out_path)
    return out_path, out.width, out.height


def render_bullet_card(text: str, index: int, out_path: str, max_w: int = CARD_W) -> Tuple[str, int, int]:
    """Plain step text, no source image -- a big bold numbered callout
    (kinetic-typography style) instead of faking a screenshot."""
    pad_x, pad_y = 44, 44
    title_font = _font("Roboto-Black.ttf", 44)
    num_font = _font("Roboto-Black.ttf", 30)

    tmp = Image.new("RGB", (10, 10))
    tdraw = ImageDraw.Draw(tmp)
    lines = _wrap_text(text, title_font, max_w - pad_x * 2, tdraw)
    line_h = 56
    body_h = pad_y * 2 + 64 + len(lines) * line_h
    radius = 26

    shadow = _shadow_layer(max_w, body_h, radius, alpha=110)
    pad = (shadow.width - max_w) // 2

    flat = Image.new("RGBA", (max_w, body_h), (255, 255, 255, 255))
    d = ImageDraw.Draw(flat)
    d.rounded_rectangle([0, 0, 64, 64], radius=16, fill=BRAND_ACCENT)
    d.text((22, 14), str(index), font=num_font, fill=(255, 255, 255, 255))

    y = 64 + 24
    for line in lines:
        d.text((pad_x, y), line, font=title_font, fill=(24, 27, 33, 255))
        y += line_h

    mask = Image.new("L", (max_w, body_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, max_w, body_h], radius=radius, fill=255)
    card = Image.composite(flat, Image.new("RGBA", (max_w, body_h), (0, 0, 0, 0)), mask)

    out = Image.new("RGBA", shadow.size, (0, 0, 0, 0))
    out.alpha_composite(shadow)
    out.alpha_composite(card, (pad, pad))
    out.save(out_path)
    return out_path, out.width, out.height
