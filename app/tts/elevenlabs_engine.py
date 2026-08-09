"""Optional premium voice via ElevenLabs. Only used if the user pastes their
own API key + voice id into Settings. Falls back to proportional word-timing
estimation (see base.estimate_word_timings) rather than ElevenLabs' separate
timestamps endpoint, to keep this simple -- swapping in real alignment later
is a small, isolated change if it turns out to matter.
"""
from __future__ import annotations

import requests

from .base import TTSResult, estimate_word_timings

_TIMEOUT = 60


def synthesize(text: str, voice_id: str, api_key: str, out_path: str) -> TTSResult:
    if not voice_id:
        raise RuntimeError("No ElevenLabs voice selected in Settings.")

    resp = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        headers={"xi-api-key": api_key, "content-type": "application/json"},
        json={"text": text, "model_id": "eleven_multilingual_v2"},
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    with open(out_path, "wb") as f:
        f.write(resp.content)

    import subprocess
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", out_path],
        check=True, capture_output=True, text=True,
    )
    duration = float(result.stdout.strip())
    words = estimate_word_timings(text, duration)
    return TTSResult(audio_path=out_path, duration=duration, words=words, engine_used="elevenlabs")
