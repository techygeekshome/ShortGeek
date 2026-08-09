"""Builds an .ass subtitle file from TTS word timings, in one of three styles
matching the approved mockup:

  - bold_highlight : short phrases, current word picked out in the accent
                      colour, one snapshot per word (the flagship style)
  - minimal        : same phrase grouping, plain bold white, no highlight
  - classic_subtitle: smaller, single-line-at-a-time, traditional subtitle look

Burned in via ffmpeg's `subtitles` filter with `fontsdir` pointed at
assets/fonts, so it renders identically on a machine that's never had these
fonts installed.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List

from ..tts.base import WordTiming

ACCENT_COLOR_ASS = "&H00D4FF&"   # ASS is &HBBGGRR& -- this is #FFD400 (brand highlight yellow)
WHITE_ASS = "&HFFFFFF&"

_BRACE_STRIP = re.compile(r"[{}]")


def _clean(word: str) -> str:
    return _BRACE_STRIP.sub("", word).strip()


def _ts(t: float) -> str:
    if t < 0:
        t = 0
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _group_lines(words: List[WordTiming], max_words: int = 4) -> List[List[WordTiming]]:
    lines: List[List[WordTiming]] = []
    current: List[WordTiming] = []
    for w in words:
        current.append(w)
        ends_sentence = bool(re.search(r"[.!?]$", w.word))
        if len(current) >= max_words or (ends_sentence and len(current) >= 2):
            lines.append(current)
            current = []
    if current:
        lines.append(current)
    return lines


_STYLE_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.601

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
{style_lines}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def build_ass(
    words: List[WordTiming],
    style: str,
    out_path: str,
    video_w: int = 1080,
    video_h: int = 1920,
) -> str:
    words = [w for w in words if _clean(w.word)]
    if not words:
        Path(out_path).write_text(_STYLE_HEADER.format(w=video_w, h=video_h, style_lines=_style_line(style)))
        return out_path

    lines = _group_lines(words, max_words=4 if style != "classic_subtitle" else 6)

    events: List[str] = []
    if style == "bold_highlight":
        for line in lines:
            words_clean = [_clean(w.word) for w in line]
            for i, w in enumerate(line):
                parts = []
                for j, wc in enumerate(words_clean):
                    if j == i:
                        parts.append("{\\c" + ACCENT_COLOR_ASS + "}" + wc + "{\\c" + WHITE_ASS + "}")
                    else:
                        parts.append(wc)
                text = " ".join(parts)
                events.append(f"Dialogue: 0,{_ts(w.start)},{_ts(w.end)},Cap,,0,0,0,,{text}")
    elif style == "minimal":
        for line in lines:
            text = " ".join(_clean(w.word) for w in line)
            events.append(f"Dialogue: 0,{_ts(line[0].start)},{_ts(line[-1].end)},Cap,,0,0,0,,{text}")
    else:  # classic_subtitle
        for line in lines:
            text = " ".join(_clean(w.word) for w in line)
            events.append(f"Dialogue: 0,{_ts(line[0].start)},{_ts(line[-1].end)},Cap,,0,0,0,,{text}")

    content = _STYLE_HEADER.format(w=video_w, h=video_h, style_lines=_style_line(style)) + "\n".join(events) + "\n"
    Path(out_path).write_text(content, encoding="utf-8")
    return out_path


def _style_line(style: str) -> str:
    # Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour,
    #         Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle,
    #         BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
    if style == "classic_subtitle":
        return "Style: Cap,Roboto Medium,46,&H00FFFFFF,&H000000FF,&H00161616,&H00000000,0,0,0,0,100,100,0,0,1,3,1,2,80,80,140,1"
    # bold_highlight & minimal share the same big-bold-centered look; only the
    # per-word colour markup differs (handled in build_ass above).
    return "Style: Cap,Roboto Black,58,&H00FFFFFF,&H000000FF,&H00161616,&H00000000,1,0,0,0,100,100,0,0,1,4,2,2,70,70,430,1"
