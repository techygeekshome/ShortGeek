"""Source adapter for a WordPress site's public REST API -- no login, no
scraping, no scraping-fragility. Works for techygeekshome.info out of the box,
and for any other self-hosted or wordpress.com site with the REST API enabled
(which is the default).
"""
from __future__ import annotations

from typing import List, Optional

import requests

from .base import SourceItem
from .htmlutil import extract_steps, plain_text

_UA = "TGH-Shorts-Studio/1.0 (+local content tool)"
_TIMEOUT = 20


class WordPressSource:
    def __init__(self, site_url: str):
        self.site_url = site_url.rstrip("/")
        self.api = f"{self.site_url}/wp-json/wp/v2"

    def search(self, query: str = "", per_page: int = 20) -> List[dict]:
        """Lightweight listing for the picker UI: id, title, link, excerpt only."""
        params = {
            "per_page": per_page,
            "_fields": "id,title,link,excerpt,date",
            "orderby": "date",
        }
        if query:
            params["search"] = query
        resp = requests.get(f"{self.api}/posts", params=params, headers={"User-Agent": _UA}, timeout=_TIMEOUT)
        resp.raise_for_status()
        out = []
        for p in resp.json():
            out.append(
                {
                    "id": p["id"],
                    "title": _clean(p["title"]["rendered"]),
                    "link": p["link"],
                    "excerpt": plain_text(p.get("excerpt", {}).get("rendered", ""))[:160],
                }
            )
        return out

    def fetch(self, post_id: int) -> SourceItem:
        resp = requests.get(
            f"{self.api}/posts/{post_id}",
            params={"_fields": "id,title,link,content,excerpt"},
            headers={"User-Agent": _UA},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        p = resp.json()
        title = _clean(p["title"]["rendered"])
        html = p.get("content", {}).get("rendered", "")
        steps = extract_steps(html, base_url=p["link"])
        return SourceItem(
            kind="guide",
            id=str(post_id),
            title=title,
            url=p["link"],
            summary=plain_text(p.get("excerpt", {}).get("rendered", ""))[:300],
            steps=steps,
            raw_text=plain_text(html),
        )


def _clean(html_title: str) -> str:
    return plain_text(html_title)
