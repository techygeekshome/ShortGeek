"""Default narration voice: Microsoft Edge's free neural TTS via the edge-tts
package. No API key, no signup, good quality. It talks to an unofficial
Microsoft endpoint, so it's the one piece of this app that depends on an
external, undocumented service -- if it's ever unreachable (offline, or the
endpoint changes), the app automatically falls back to the offline eSpeak
engine rather than failing the whole render (see tts/router.py).
"""
from __future__ import annotations

import asyncio
import subprocess

import edge_tts

from .base import TTSResult, WordTiming


def _probe_duration(path: str) -> float:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            check=True, capture_output=True, text=True,
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


async def _synthesize_async(text: str, voice: str, out_path: str) -> TTSResult:
    # edge-tts 7.x defaults to sentence-level boundaries; we need word-level
    # timing for the karaoke-style captions, so request it explicitly.
    communicate = edge_tts.Communicate(text, voice=voice, boundary="WordBoundary")
    words: list[WordTiming] = []
    with open(out_path, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / 1e7  # 100-ns units -> seconds
                dur = chunk["duration"] / 1e7
                words.append(WordTiming(word=chunk["text"], start=start, end=start + dur))

    duration = _probe_duration(out_path) or (words[-1].end if words else 0.0)

    return TTSResult(audio_path=out_path, duration=duration, words=words, engine_used="edge")


def synthesize(text: str, voice: str, out_path: str) -> TTSResult:
    """Synchronous wrapper -- callers (the job worker thread) don't need to
    know this is async under the hood."""
    return asyncio.run(_synthesize_async(text, voice, out_path))


async def list_voices(locale_prefix: str = "en") -> list[dict]:
    voices = await edge_tts.list_voices()
    return [v for v in voices if v["Locale"].startswith(locale_prefix)]
