"""Source adapter for a free-typed topic prompt -- no source article at all.
There's nothing to extract, so this just wraps the prompt. The script writer
and visual pipeline both know how to handle a topic with zero real images
(they fall back to kinetic-typography cards instead of screenshot cards)."""
from __future__ import annotations

import hashlib

from .base import SourceItem


def make_item(topic_text: str) -> SourceItem:
    topic_text = topic_text.strip()
    _id = hashlib.sha1(topic_text.encode("utf-8")).hexdigest()[:12]
    return SourceItem(
        kind="topic",
        id=_id,
        title=topic_text,
        url="",
        summary=topic_text,
        steps=[],
        raw_text=topic_text,
    )
