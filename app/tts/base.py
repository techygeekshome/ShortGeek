from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List


@dataclass
class WordTiming:
    word: str
    start: float  # seconds
    end: float    # seconds


@dataclass
class TTSResult:
    audio_path: str
    duration: float
    words: List[WordTiming] = field(default_factory=list)
    engine_used: str = ""
    fallback_used: bool = False


def estimate_word_timings(text: str, total_duration: float) -> List[WordTiming]:
    """Used when an engine can't give us real per-word timestamps (eSpeak,
    or ElevenLabs without alignment turned on). Distributes time across words
    proportional to character length, which tracks real speech pacing far
    better than an even split."""
    words = re.findall(r"\S+", text)
    if not words:
        return []
    weights = [max(len(w), 2) for w in words]
    total_weight = sum(weights)
    out: List[WordTiming] = []
    t = 0.0
    for w, weight in zip(words, weights):
        dur = total_duration * (weight / total_weight)
        out.append(WordTiming(word=w, start=t, end=t + dur))
        t += dur
    return out
