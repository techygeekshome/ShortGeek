"""Picks the configured TTS engine and synthesizes narration, with an
automatic, transparent fallback to the offline eSpeak engine if the primary
choice fails for any reason (no internet, endpoint hiccup, bad key). The
caller always gets a TTSResult back or a clear exception if literally nothing
worked.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from . import edge_engine, espeak_engine
from .base import TTSResult

log = logging.getLogger("tgh.tts")


def _synthesize_espeak(text: str, segments: Optional[List[str]], voice: str, out_path: str) -> TTSResult:
    # Segment-aware synthesis keeps captions from drifting out of sync at
    # each sentence/beat pause (see espeak_engine.synthesize_segments's
    # docstring) -- used whenever the caller can give us the hook/beat/cta
    # breakdown, falling back to single-shot estimation otherwise.
    if segments:
        return espeak_engine.synthesize_segments(segments, voice, out_path)
    return espeak_engine.synthesize(text, voice, out_path)


def synthesize(text: str, cfg: dict, out_path: str, segments: Optional[List[str]] = None) -> TTSResult:
    engine = cfg.get("voice_engine", "edge")

    if engine == "elevenlabs" and cfg.get("elevenlabs_api_key"):
        try:
            from . import elevenlabs_engine
            return elevenlabs_engine.synthesize(
                text, cfg.get("elevenlabs_voice_id", ""), cfg["elevenlabs_api_key"], out_path
            )
        except Exception as e:
            log.warning("ElevenLabs failed (%s), falling back to edge-tts", e)
            engine = "edge"

    if engine == "edge":
        try:
            result = edge_engine.synthesize(text, cfg.get("edge_voice", "en-GB-RyanNeural"), out_path)
            if result.duration > 0:
                return result
            raise RuntimeError("edge-tts returned no audio")
        except Exception as e:
            log.warning("edge-tts failed (%s), falling back to offline eSpeak voice", e)
            result = _synthesize_espeak(text, segments, cfg.get("espeak_voice", "en-gb"), out_path)
            result.fallback_used = True
            return result

    # engine == "espeak" (explicit user choice)
    return _synthesize_espeak(text, segments, cfg.get("espeak_voice", "en-gb"), out_path)
