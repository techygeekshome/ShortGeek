"""Shared HTML -> (text steps, real images) extraction used by every source
that hands us raw HTML (WordPress content.rendered, or a fetched web page).

The goal is always the same: pull out real, human-written content and real
images that already exist -- never invent anything.
"""
from __future__ import annotations

import re
from typing import List, Tuple
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import SourceImage, SourceStep


def _soup(html: str) -> BeautifulSoup:
    """BeautifulSoup with lxml, falling back to the stdlib parser if lxml
    isn't importable for any reason -- keeps the app running (with slightly
    less lenient HTML parsing) instead of hard-crashing on a missing dep."""
    try:
        return BeautifulSoup(html or "", "lxml")
    except Exception:
        return BeautifulSoup(html or "", "html.parser")

# Filenames/paths that are almost never "real content" -- logos, avatars,
# tracking pixels, ad units, social icons.
_SKIP_IMG_PATTERNS = re.compile(
    r"(logo|avatar|gravatar|icon|sprite|pixel|badge|banner-ad|advert|spinner|loading)",
    re.IGNORECASE,
)
_CODE_HINT = re.compile(r"(get-|set-|\$\w+|::|;\s*$|^\s*(if|foreach|function)\b)", re.IGNORECASE)


def _looks_like_code(text: str) -> bool:
    if len(text) > 400:
        return False
    hits = len(_CODE_HINT.findall(text))
    return hits >= 2 or text.strip().startswith(("$", "sudo ", "PS C:", ">"))


def extract_steps(html: str, base_url: str = "", min_chars: int = 25, max_steps: int = 60) -> List[SourceStep]:
    """Walk the body HTML top-to-bottom, in document order, and turn headings /
    paragraphs / list items / code blocks / images into an ordered list of
    SourceStep. Order matters -- it's what lets us pair a step's *nearby* image
    with its text rather than shuffling everything.
    """
    soup = _soup(html)

    # Drop obviously non-content blocks.
    for tag in soup.select("script, style, nav, .sharedaddy, .jp-relatedposts, .wp-block-embed"):
        tag.decompose()

    steps: List[SourceStep] = []
    pending_image: SourceImage | None = None
    pending_alt: str = ""

    def flush_text(text: str, is_code: bool = False):
        nonlocal pending_image, pending_alt
        if is_code:
            # Collapse spaces/tabs but keep real line breaks -- code needs
            # its line structure both to read sensibly on screen and so the
            # narration step can reliably find the leading '# comment' line.
            text = re.sub(r"[ \t]+", " ", text).strip()
            text = re.sub(r"\n\s*\n+", "\n", text)
        else:
            text = re.sub(r"\s+", " ", text).strip()
        if len(text) < min_chars:
            return
        steps.append(SourceStep(text=text, image=pending_image, is_code=is_code))
        pending_image = None
        pending_alt = ""

    def flush_image_via_alt():
        """Gallery images with no following paragraph (or another image right
        after) would otherwise be silently dropped -- use the image's own alt
        text as its caption instead, since WordPress alt text is usually a
        real description of what's in the screenshot."""
        nonlocal pending_image, pending_alt
        if pending_image is not None and len(pending_alt) >= min_chars:
            steps.append(SourceStep(text=re.sub(r"\s+", " ", pending_alt).strip(), image=pending_image))
        pending_image = None
        pending_alt = ""

    body = soup.body or soup
    for el in body.find_all(["h2", "h3", "p", "li", "pre", "img"], recursive=True):
        if len(steps) >= max_steps:
            break
        name = el.name
        if name == "img":
            src = el.get("src") or el.get("data-src") or ""
            if not src or _SKIP_IMG_PATTERNS.search(src):
                continue
            try:
                w = int(el.get("width") or 0)
                h = int(el.get("height") or 0)
            except ValueError:
                w = h = 0
            if (w and w < 160) or (h and h < 120):
                continue
            if pending_image is not None:
                # Back-to-back image with nothing in between -- don't just
                # overwrite and lose it.
                flush_image_via_alt()
            pending_image = SourceImage(url=urljoin(base_url, src), width=w or None, height=h or None)
            pending_alt = (el.get("alt") or "").strip()
            continue
        if name == "pre":
            text = el.get_text("\n", strip=True)  # preserve real line breaks for code
        else:
            text = el.get_text(" ", strip=True)
        if not text:
            continue
        if name == "pre" or _looks_like_code(text):
            flush_text(text, is_code=True)
        else:
            flush_text(text, is_code=False)

    flush_image_via_alt()  # don't drop a trailing gallery image with no closing paragraph
    return steps


def plain_text(html: str) -> str:
    soup = _soup(html)
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()
