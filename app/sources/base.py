"""Shared data shapes for every content source (WordPress, RSS/URL, topic prompt)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SourceImage:
    url: str
    width: Optional[int] = None
    height: Optional[int] = None


@dataclass
class SourceStep:
    """One logical chunk of the source content (a paragraph, numbered step, or
    list item). The script writer turns a handful of these into script beats."""
    text: str
    image: Optional[SourceImage] = None
    is_code: bool = False


@dataclass
class SourceItem:
    """A single piece of source content, however it was found."""
    kind: str                      # "guide" | "article" | "topic"
    id: str
    title: str
    url: str = ""
    summary: str = ""
    steps: List[SourceStep] = field(default_factory=list)
    raw_text: str = ""

    @property
    def images(self) -> List[SourceImage]:
        return [s.image for s in self.steps if s.image is not None]

    @property
    def has_real_images(self) -> bool:
        return len(self.images) > 0
