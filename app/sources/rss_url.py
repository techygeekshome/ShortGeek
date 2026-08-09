"""Generic source adapter for 'paste any RSS feed or any web page URL'.

Two entry points:
  - list_feed(feed_url): list recent entries from an RSS/Atom feed
  - fetch_url(url): pull a single page's real text + real images

Quality here will vary site to site (unlike the WordPress adapter, which has
a clean structured API to work with) -- this is a best-effort heuristic
extractor, documented as such in the README.
"""
from __future__ import annotations

from typing import List

import feedparser
import requests
import trafilatura

from .base import SourceItem
from .htmlutil import extract_steps, plain_text

_UA = "TGH-Shorts-Studio/1.0 (+local content tool)"
_TIMEOUT = 20


def list_feed(feed_url: str, limit: int = 20) -> List[dict]:
    parsed = feedparser.parse(feed_url)
    out = []
    for entry in parsed.entries[:limit]:
        out.append(
            {
                "id": entry.get("id") or entry.get("link"),
                "title": entry.get("title", "Untitled"),
                "link": entry.get("link", ""),
                "excerpt": plain_text(entry.get("summary", ""))[:160],
            }
        )
    return out


def fetch_url(url: str) -> SourceItem:
    resp = requests.get(url, headers={"User-Agent": _UA}, timeout=_TIMEOUT)
    resp.raise_for_status()
    html = resp.text

    # Real body images, in document order.
    steps = extract_steps(html, base_url=url)

    # Clean readable text via trafilatura as a fallback/summary source, in case
    # the structural extraction above missed something (very different site
    # layouts).
    extracted = trafilatura.extract(html, include_comments=False, include_tables=False) or ""

    title = ""
    try:
        meta = trafilatura.extract_metadata(html)
        if meta and meta.title:
            title = meta.title
    except Exception:
        pass
    if not title:
        title = url

    return SourceItem(
        kind="article",
        id=url,
        title=title,
        url=url,
        summary=extracted[:300],
        steps=steps if steps else [],
        raw_text=extracted or plain_text(html),
    )
