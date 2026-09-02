"""Picks the configured TTS engine and synthesizes narration, with an
automatic, transparent fallback to an offline engine if the primary choice
fails for any reason (no internet, endpoint hiccup, bad key). The caller
always gets a TTSResult back or a clear exception if literally nothing worked.

The offline engine is Kokoro, a neural voice that runs on this machine. eSpeak
is still here for anyone who already has it configured, but it is no longer
what the app falls back to on its own.

edge-tts remains the default, and that is on purpose rather than inertia:
Kokoro's ONNX build exposes no phoneme durations, so word timings from it are
estimated, while edge-tts reports real word boundaries. Captions timed from
the voice engine are the thing this app is for, so the engine that can do that
leads and the offline one catches it when it falls.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from . import edge_engine, espeak_engine, kokoro_engine
from .base import TTSResult

log = logging.getLogger("tgh.tts")


def _synthesize_offline(text: str, segments: Optional[List[str]], cfg: dict, out_path: str) -> TTSResult:
    """The offline voice. Kokoro if it can run, eSpeak if it cannot.

    Segment-aware synthesis keeps captions from drifting out of sync at each
    sentence pause, so it is used whenever the caller can give us the
    hook/beat/cta breakdown.
    """
    if kokoro_engine.is_available():
        try:
            voice = cfg.get("kokoro_voice", kokoro_engine.DEFAULT_VOICE)
            if segments:
                return kokoro_engine.synthesize_segments(segments, voice, out_path)
            return kokoro_engine.synthesize(text, voice, out_path)
        except Exception as e:
            log.warning("Kokoro failed (%s), falling back to eSpeak", e)
    return _synthesize_espeak(text, segments, cfg.get("espeak_voice", "en-gb"), out_path)


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
            log.warning("edge-tts failed (%s), falling back to the offline voice", e)
            result = _synthesize_offline(text, segments, cfg, out_path)
            result.fallback_used = True
            return result

    if engine == "kokoro":
        voice = cfg.get("kokoro_voice", kokoro_engine.DEFAULT_VOICE)
        if segments:
            return kokoro_engine.synthesize_segments(segments, voice, out_path)
        return kokoro_engine.synthesize(text, voice, out_path)

    # engine == "espeak" (explicit user choice)
    return _synthesize_espeak(text, segments, cfg.get("espeak_voice", "en-gb"), out_path)
