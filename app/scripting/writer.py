"""The script data shapes shared by the editor and the renderer.

ShortGeek used to draft a script for you from a WordPress guide, an
RSS/URL article or a bare topic prompt -- all three were removed (see the
changelog): the extraction never reliably found more than a handful of
usable lines, and the "topic" mode couldn't actually write a script, only
echo back sentences you'd already written yourself. Paste Script is the one
mode that was always grounded in something real -- your own words -- so
it's the only way in now, and it's built entirely client-side
(app/static/app.js). This module just holds the shapes the render pipeline
still needs.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

WORDS_PER_SECOND = 2.5  # rough speaking pace used only for the up-front duration estimate


@dataclass
class Beat:
    text: str                          # what gets spoken -- always plain English
    image_url: Optional[str] = None    # "beatimg://<file>" for an attached screenshot, or empty
    is_code: bool = False
    code_display: Optional[str] = None  # the real code/command shown on screen (code beats only)


@dataclass
class Script:
    hook: str
    beats: List[Beat] = field(default_factory=list)
    cta: str = ""
    source_title: str = ""

    @property
    def full_text(self) -> str:
        lines = [self.hook] + [b.text for b in self.beats] + [self.cta]
        return "\n\n".join([l for l in lines if l.strip()])

    @property
    def estimated_seconds(self) -> float:
        words = len(re.findall(r"\w+", self.full_text))
        return round(words / WORDS_PER_SECOND, 1)
