"""Turns a SourceItem (a guide, an article, or a bare topic) into a short-form
script: a hook line, 2-4 body beats, and a call-to-action -- plus a mapping of
which beat pairs with which real image (or none, for a text/code beat).

Works with zero configuration (pure heuristic, no API key). If the user has
added an LLM key in Settings, the *wording* gets a light polish pass, but the
structure (which sentences, which images) is still decided here so the result
stays grounded in the real source rather than invented by the model.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import List, Optional

from ..config import config
from ..sources.base import SourceItem, SourceStep
from . import llm_client

WORDS_PER_SECOND = 2.5  # rough speaking pace used only for the up-front duration estimate

# Generic on purpose -- no brand handle, no "full guide linked in bio" claim
# that may not even be true for a topic-prompt video. Picked per-video from
# a small pool (seeded, so the same source always reproduces the same pick)
# so a run of videos doesn't all end on the identical line.
_CTA_POOL = [
    "Follow for more.",
    "Follow for more like this.",
    "Follow along for more.",
]


def _pick_cta(seed_key: str) -> str:
    seed = int(hashlib.sha1(seed_key.encode("utf-8")).hexdigest(), 16)
    return _CTA_POOL[seed % len(_CTA_POOL)]


@dataclass
class Beat:
    text: str                          # what gets spoken -- always plain English
    image_url: Optional[str] = None
    is_code: bool = False
    code_display: Optional[str] = None  # the real code/command shown on screen (code beats only)


@dataclass
class Script:
    hook: str
    beats: List[Beat] = field(default_factory=list)
    cta: str = ""
    source_title: str = ""
    used_llm: bool = False

    @property
    def full_text(self) -> str:
        lines = [self.hook] + [b.text for b in self.beats] + [self.cta]
        return "\n\n".join([l for l in lines if l.strip()])

    @property
    def estimated_seconds(self) -> float:
        words = len(re.findall(r"\w+", self.full_text))
        return round(words / WORDS_PER_SECOND, 1)


def _code_narration(code_text: str) -> str:
    """Code should never be read aloud verbatim -- it sounds like nonsense.
    These PowerShell/command snippets conveniently tend to start with a
    '# comment' describing what they do; reuse that as the spoken line.
    Falls back to a generic line if there's no leading comment."""
    first_line = code_text.strip().splitlines()[0].strip() if code_text.strip() else ""
    if first_line.startswith("#"):
        said = first_line.lstrip("#").strip().rstrip(".")
        if len(said) > 8:
            return said[0].upper() + said[1:] + "."
    return "Here's the command for it."


def _trim_sentence(text: str, max_words: int = 30) -> str:
    text = text.strip()
    # Prefer a clean sentence-boundary cut over a blind word-count chop.
    sentences = re.split(r"(?<=[.!?])\s+", text)
    first = sentences[0].strip()
    if len(first) > 15 and len(first.split()) <= max_words:
        return first
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]).rstrip(",;:-") + "…"


def _make_hook(item: SourceItem) -> str:
    title = item.title.strip()
    if re.match(r"^how to\s+", title, flags=re.IGNORECASE):
        rest = re.sub(r"^how to\s+", "", title, flags=re.IGNORECASE)
        return f"Here's how to {rest.rstrip('.')}"
    return title


def _heuristic_script(item: SourceItem, cfg: dict) -> Script:
    beats: List[Beat] = []

    if item.kind == "topic":
        # There's no source article to ground beats in here -- unlike every
        # other source, inventing 3-4 "facts" from a bare topic would break
        # the one rule this app holds everywhere else (never invent a claim
        # that isn't in the source). The honest way to still get a real,
        # multi-beat script with zero API key: treat each sentence *you*
        # already wrote in the prompt as its own beat, instead of just
        # echoing the whole prompt back as one flat line. Write the prompt
        # as a short hook line + a few short punchy follow-up sentences and
        # this naturally becomes a proper hook + beats + cta script.
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", item.title.strip()) if s.strip()]
        if len(sentences) >= 2:
            hook = _trim_sentence(sentences[0], 20)
            beats = [Beat(text=_trim_sentence(s, 26)) for s in sentences[1:5]]
            display_title = sentences[0]
        else:
            hook = item.title if len(item.title) < 90 else _trim_sentence(item.title, 14)
            beats = [Beat(text=f"Let's talk about {item.title.rstrip('.')}.")]
            display_title = item.title
        cta = _pick_cta(item.title)
        return Script(hook=hook, beats=beats, cta=cta, source_title=display_title)

    candidates = [s for s in item.steps if len(s.text) > 25]
    # A real screenshot or a real code/command block both make a far better
    # beat than plain prose -- prioritise either, but keep a lightweight
    # intro line and the original document order so it still reads as a
    # coherent walkthrough rather than a shuffled deck.
    visual = [s for s in candidates if s.image is not None or s.is_code]
    plain = [s for s in candidates if s.image is None and not s.is_code]

    if visual:
        chosen: List[SourceStep] = []
        first_visual_pos = item.steps.index(visual[0])
        intro = [s for s in plain if item.steps.index(s) < first_visual_pos]
        if intro:
            chosen.append(intro[0])
        for s in visual:
            if len(chosen) >= 4:
                break
            chosen.append(s)
        for s in plain:
            if len(chosen) >= 4:
                break
            if s not in chosen:
                chosen.append(s)
        chosen.sort(key=lambda s: item.steps.index(s))
        usable_steps = chosen[:4]
    else:
        usable_steps = candidates[:4]

    if not usable_steps and item.raw_text:
        # No structured steps (e.g. plain article) -- fall back to first ~3 sentences.
        sentences = re.split(r"(?<=[.!?])\s+", item.raw_text)
        usable_steps = [SourceStep(text=s) for s in sentences if len(s) > 25][:3]

    for step in usable_steps:
        if step.is_code:
            beats.append(Beat(text=_code_narration(step.text), is_code=True, code_display=step.text))
        else:
            beats.append(Beat(text=_trim_sentence(step.text), image_url=(step.image.url if step.image else None)))

    hook = _make_hook(item)
    cta = _pick_cta(item.title)
    return Script(hook=hook, beats=beats, cta=cta, source_title=item.title)


def draft_script(item: SourceItem) -> Script:
    cfg = config.all()
    script = _heuristic_script(item, cfg)

    provider = cfg.get("llm_provider", "none")
    api_key = cfg.get("llm_api_key", "")
    if provider != "none" and api_key:
        system_prompt = (
            "You rewrite short-form video scripts for a tech how-to brand. "
            "Keep every factual claim from the draft -- do not invent steps, numbers, "
            "or settings that aren't in the draft. Keep the same number of lines "
            "(hook / beats / CTA), one per input line. Make it punchier and more spoken, "
            "not more exaggerated. Style notes: " + cfg.get("brand_style_notes", "")
        )
        user_prompt = (
            "Rewrite these lines 1:1 (same count, same order), each on its own line, no numbering:\n\n"
            + "\n".join([script.hook] + [b.text for b in script.beats] + [script.cta])
        )
        polished = llm_client.polish_script(provider, api_key, system_prompt, user_prompt)
        if polished:
            lines = [l.strip() for l in polished.splitlines() if l.strip()]
            if len(lines) == len(script.beats) + 2:
                script.hook = lines[0]
                for b, new_text in zip(script.beats, lines[1:-1]):
                    b.text = new_text
                script.cta = lines[-1]
                script.used_llm = True

    return script


def script_to_dict(script: Script) -> dict:
    return {
        "hook": script.hook,
        "beats": [{"text": b.text, "image_url": b.image_url, "is_code": b.is_code, "code_display": b.code_display} for b in script.beats],
        "cta": script.cta,
        "full_text": script.full_text,
        "estimated_seconds": script.estimated_seconds,
        "used_llm": script.used_llm,
        "source_title": script.source_title,
    }
