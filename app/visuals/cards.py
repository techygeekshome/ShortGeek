"""Turns a script beat into the styled 'card' that appears on screen for it.

Two kinds, chosen automatically per beat:

  - code card  : the guide's own code/command text, shown as a styled editor
                 block with light keyword colouring
  - beat card  : the spoken line, as a numbered callout -- with a small
                 framed screenshot inset above the text when one has been
                 attached to that beat, or just the text on its own when it
                 hasn't

Nothing here is AI-generated -- every pixel is either a real image you
attached, or text drawn straight from the script. Visual language matches
TechyGeeksHome's own dark card component (the same one used for the
site's download cards): near-black card, thin border, cyan accent, light
grey/white text.
"""
from __future__ import annotations

import io
import re
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import urlparse

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from ..config import CACHE_DIR, FONTS_DIR

CARD_W = 900

# Same palette as the site's tgh-card download component, so anything
# ShortGeek renders reads as "the same brand" as the rest of TGH.
CARD_BG = (17, 17, 19, 255)       # #111113
CARD_BORDER = (35, 35, 39, 255)   # #232327
TEXT_PRIMARY = (229, 231, 235, 255)   # #E5E7EB
TEXT_MUTED = (156, 163, 175, 255)     # #9CA3AF
ACCENT = (56, 189, 248, 255)          # #38BDF8
ACCENT_DIM = (24, 92, 122, 255)       # darker cyan, used for the chip's shadow edge
NUM_TEXT = (7, 12, 17, 255)           # dark text on the accent chip, matching the site's icon badges
CODE_BG = (15, 18, 26, 255)

BEAT_IMAGE_DIR = CACHE_DIR / "beat_images"
BEAT_IMAGE_DIR.mkdir(parents=True, exist_ok=True)

_UA = "TGH-ShortGeek/1.0 (+local content tool)"

_FONT_CACHE: dict = {}


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    key = (name, size)
    if key not in _FONT_CACHE:
        _FONT_CACHE[key] = ImageFont.truetype(str(FONTS_DIR / name), size)
    return _FONT_CACHE[key]


def save_beat_image(data: bytes, suffix: str = ".png") -> str:
    """Saves an uploaded beat screenshot to local disk and returns a
    'beatimg://<filename>' reference -- never a URL, never sent anywhere.
    The reference is what gets stored on the beat and round-tripped through
    the script editor/render request."""
    import uuid

    suffix = suffix if suffix.lower() in (".png", ".jpg", ".jpeg", ".webp") else ".png"
    name = f"{uuid.uuid4().hex}{suffix}"
    (BEAT_IMAGE_DIR / name).write_bytes(data)
    return f"beatimg://{name}"


def beat_image_path(ref: str) -> Optional[Path]:
    if not ref.startswith("beatimg://"):
        return None
    name = ref[len("beatimg://"):]
    # Strip any path components -- this only ever names a file directly
    # inside BEAT_IMAGE_DIR, never a path elsewhere on disk.
    name = Path(name).name
    path = BEAT_IMAGE_DIR / name
    return path if path.exists() else None


def resolve_image(ref: str, timeout: int = 20) -> Optional[Image.Image]:
    """Loads a beat's attached image, whether it's a local upload
    (beatimg://...) or (for anything that still hands us a real URL) an
    http(s) link. Local files never touch the network."""
    if not ref:
        return None
    local_path = beat_image_path(ref)
    if local_path is not None:
        try:
            return Image.open(local_path).convert("RGB")
        except Exception:
            return None
    parsed = urlparse(ref)
    if parsed.scheme not in ("http", "https"):
        return None
    try:
        resp = requests.get(ref, headers={"User-Agent": _UA}, timeout=timeout)
        resp.raise_for_status()
        return Image.open(io.BytesIO(resp.content)).convert("RGB")
    except Exception:
        return None


# Back-compat alias -- older callers used this name for the same job.
fetch_image = resolve_image


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


def _shadow_layer(w: int, h: int, radius: int, blur: int = 28, alpha: int = 150, pad: int = 60) -> Image.Image:
    canvas = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle([pad, pad, pad + w, pad + h], radius=radius, fill=(0, 0, 0, alpha))
    return canvas.filter(ImageFilter.GaussianBlur(blur))


def _framed_inset(image: Image.Image, max_w: int, max_h: int, radius: int = 16, border: int = 3) -> Image.Image:
    """A real screenshot, scaled down to sit *inside* a beat card rather than
    behind it -- contain-fit (never cropped, since a popup/dialog screenshot
    is exactly as big as it needs to be and cropping it can cut off the
    thing being shown), with a thin accent border and its own soft shadow so
    it reads as a distinct inset rather than part of the card background."""
    iw, ih = image.size
    scale = min(max_w / iw, max_h / ih)
    tw, th = max(1, int(iw * scale)), max(1, int(ih * scale))
    resized = image.resize((tw, th), Image.LANCZOS)

    shadow = _shadow_layer(tw, th, radius, blur=18, alpha=120, pad=26)
    frame = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    mask = Image.new("L", (tw, th), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, tw, th], radius=radius, fill=255)
    frame.paste(resized.convert("RGBA"), (0, 0), mask)
    d = ImageDraw.Draw(frame)
    d.rounded_rectangle([border / 2, border / 2, tw - border / 2, th - border / 2], radius=radius, outline=ACCENT, width=border)

    out = Image.new("RGBA", shadow.size, (0, 0, 0, 0))
    pad = (shadow.width - tw) // 2
    out.alpha_composite(shadow)
    out.alpha_composite(frame, (pad, pad))
    return out


def _num_chip(index: int, size: int = 56) -> Image.Image:
    num_font = _font("Roboto-Black.ttf", 26)
    chip = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(chip)
    d.rounded_rectangle([0, 0, size, size], radius=14, fill=ACCENT)
    text = str(index)
    bbox = d.textbbox((0, 0), text, font=num_font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text((size / 2 - tw / 2 - bbox[0], size / 2 - th / 2 - bbox[1]), text, font=num_font, fill=NUM_TEXT)
    return chip


def render_beat_card(
    text: str,
    index: int,
    out_path: str,
    image: Optional[Image.Image] = None,
    max_w: int = CARD_W,
) -> Tuple[str, int, int]:
    """The default beat visual: a dark, on-brand card with a numbered chip,
    an optional small framed screenshot inset, and the spoken line as bold
    body text underneath."""
    pad_x, pad_y = 40, 34
    inner_w = max_w - pad_x * 2

    chip = _num_chip(index)
    kicker_font = _font("Roboto-Bold.ttf", 20)

    inset: Optional[Image.Image] = None
    if image is not None:
        # Capped well inside the safe band between the top-of-card position
        # and the caption strip lower on screen -- "small popup", not a
        # full-bleed screenshot.
        inset = _framed_inset(image, max_w=inner_w, max_h=460)

    body_font = _font("Roboto-Bold.ttf", 40 if inset is not None else 46)
    tmp = Image.new("RGB", (10, 10))
    tdraw = ImageDraw.Draw(tmp)
    lines = _wrap_text(text, body_font, inner_w, tdraw)
    line_h = 50 if inset is not None else 58

    header_h = max(chip.height, 34) + 26
    inset_h = (inset.height + 22) if inset is not None else 0
    body_h = len(lines) * line_h
    content_h = header_h + inset_h + body_h
    total_h = pad_y * 2 + content_h
    radius = 26

    shadow = _shadow_layer(max_w, total_h, radius)
    pad = (shadow.width - max_w) // 2

    flat = Image.new("RGBA", (max_w, total_h), CARD_BG)
    d = ImageDraw.Draw(flat)
    # Slim accent bar along the top edge -- the one bit of colour that's
    # always there, even on a plain text-only card.
    d.rounded_rectangle([0, 0, max_w, total_h], radius=radius, outline=CARD_BORDER, width=2)
    d.rounded_rectangle([18, 0, max_w - 18, 5], radius=3, fill=ACCENT)

    y = pad_y
    flat.alpha_composite(chip, (pad_x, y))
    kicker = f"STEP {index}"
    kb = d.textbbox((0, 0), kicker, font=kicker_font)
    d.text((pad_x + chip.width + 16, y + chip.height / 2 - (kb[3] - kb[1]) / 2 - kb[1]), kicker, font=kicker_font, fill=TEXT_MUTED)
    y += header_h

    if inset is not None:
        # inset already carries its own soft-shadow padding (see
        # _framed_inset), so placing it flush at y leaves a natural gap
        # above the visible screenshot rather than needing a fudge offset.
        ix = (max_w - inset.width) // 2
        flat.alpha_composite(inset, (ix, y))
        y += inset_h

    for line in lines:
        d.text((pad_x, y), line, font=body_font, fill=TEXT_PRIMARY)
        y += line_h

    mask = Image.new("L", (max_w, total_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, max_w, total_h], radius=radius, fill=255)
    card = Image.composite(flat, Image.new("RGBA", (max_w, total_h), (0, 0, 0, 0)), mask)

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
    line_h = 42
    mono = _font("DejaVuSansMono.ttf", 27)
    mono_b = _font("DejaVuSansMono-Bold.ttf", 27)

    tmp = Image.new("RGB", (10, 10))
    tdraw = ImageDraw.Draw(tmp)
    raw_lines = code_text.strip().splitlines() or [code_text]
    wrapped: List[str] = []
    for rl in raw_lines:
        wrapped.extend(_wrap_text(rl, mono, max_w - pad_x * 2 - 40, tdraw) or [""])
    wrapped = wrapped[:9]

    body_h = pad_y * 2 + 44 + len(wrapped) * line_h
    radius = 22

    shadow = _shadow_layer(max_w, body_h, radius)
    pad = (shadow.width - max_w) // 2

    flat = Image.new("RGBA", (max_w, body_h), CODE_BG)
    d = ImageDraw.Draw(flat)
    d.rounded_rectangle([0, 0, max_w, body_h], radius=radius, outline=(46, 51, 66, 255), width=2)
    d.rectangle([2, 2, max_w - 2, 44], fill=(26, 29, 40, 255))
    for i, cx in enumerate([26, 50, 74]):
        colour = [(255, 95, 86, 255), (255, 189, 46, 255), (39, 201, 63, 255)][i]
        d.ellipse([cx, 15, cx + 14, 29], fill=colour)

    y = 44 + pad_y
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
