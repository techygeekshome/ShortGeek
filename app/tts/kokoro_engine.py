"""Offline neural voice: Kokoro.

This replaces eSpeak NG as the offline engine. eSpeak needed a separate install
and sounded like 1998; Kokoro needs neither and sounds like a person.

It is deliberately NOT the default. Kokoro's ONNX build exposes no phoneme
durations, so `create_timed` returns nothing and word timings have to be
estimated. edge-tts gives real word boundaries, and captions timed from the
voice engine are the thing ShortGeek is actually for. So edge-tts stays the
default and this takes over when edge-tts cannot be reached.

To keep the estimate honest, narration is synthesised one segment at a time and
each segment's real measured duration anchors the words inside it. Captions
cannot drift across a sentence boundary, which is where drift is noticed.

The model is downloaded once, on first use, into
%LOCALAPPDATA%\\TechyGeeksHome\\ShortGeek\\voices. It is not bundled: at 92 MB
for the int8 build it would more than double the installer.
"""
from __future__ import annotations

import logging
import os
import subprocess
import threading
import urllib.request
from pathlib import Path
from typing import List, Optional

from .base import TTSResult, WordTiming, estimate_word_timings

log = logging.getLogger("tgh.tts.kokoro")

_RELEASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
_FILES = {
    "kokoro-v1.0.int8.onnx": f"{_RELEASE}/kokoro-v1.0.int8.onnx",
    "voices-v1.0.bin": f"{_RELEASE}/voices-v1.0.bin",
}
_USER_AGENT = "ShortGeek (+https://techygeekshome.info/shortgeek/)"

# British female. Picked as the default offline voice deliberately.
DEFAULT_VOICE = "bf_emma"
_GAP_SECONDS = 0.35

_lock = threading.Lock()
_engine = None


def voices_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~/.local/share")
    p = Path(base) / "TechyGeeksHome" / "ShortGeek" / "voices"
    p.mkdir(parents=True, exist_ok=True)
    return p


def is_downloaded() -> bool:
    return all((voices_dir() / name).exists() for name in _FILES)


def download(progress=None) -> None:
    """Fetch the model and the voice bank. Roughly 120 MB, once."""
    target = voices_dir()
    for name, url in _FILES.items():
        final = target / name
        if final.exists():
            continue
        part = final.with_suffix(final.suffix + ".part")
        request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(request, timeout=180) as r:
            total = int(r.headers.get("Content-Length") or 0)
            done = 0
            with open(part, "wb") as f:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if progress:
                        progress(name, done, total)
        part.replace(final)


def is_available() -> bool:
    try:
        import kokoro_onnx  # noqa: F401
    except ImportError:
        return False
    return True


def _load():
    global _engine
    with _lock:
        if _engine is None:
            from kokoro_onnx import Kokoro
            if not is_downloaded():
                download()
            d = voices_dir()
            _engine = Kokoro(str(d / "kokoro-v1.0.int8.onnx"), str(d / "voices-v1.0.bin"))
        return _engine


def _lang_for(voice: str) -> str:
    return "en-gb" if voice.startswith(("b",)) else "en-us"


def _write_mp3(samples, sample_rate: int, out_path: str) -> None:
    import wave
    import numpy as np

    wav_path = str(Path(out_path).with_suffix(".wav"))
    pcm = np.clip(samples, -1.0, 1.0)
    pcm = (pcm * 32767).astype("<i2")
    with wave.open(wav_path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm.tobytes())
    subprocess.run(
        ["ffmpeg", "-y", "-i", wav_path, "-codec:a", "libmp3lame", "-q:a", "3", out_path],
        check=True, capture_output=True,
    )
    Path(wav_path).unlink(missing_ok=True)


def synthesize(text: str, voice: str, out_path: str) -> TTSResult:
    """One block of text. Word timings are estimated across the whole clip."""
    k = _load()
    voice = voice or DEFAULT_VOICE
    samples, sample_rate = k.create(text, voice=voice, speed=1.0, lang=_lang_for(voice))
    _write_mp3(samples, sample_rate, out_path)
    duration = len(samples) / sample_rate
    return TTSResult(
        audio_path=out_path,
        duration=duration,
        words=estimate_word_timings(text, duration),
        engine_used=f"kokoro:{voice}",
    )


def synthesize_segments(segments: List[str], voice: str, out_path: str) -> TTSResult:
    """Synthesise each segment separately so captions cannot drift across a
    sentence boundary. Every segment's real measured length anchors the words
    inside it, which is the closest thing to true timing this model allows."""
    import numpy as np

    k = _load()
    voice = voice or DEFAULT_VOICE
    lang = _lang_for(voice)

    pieces: list = []
    words: List[WordTiming] = []
    sample_rate = 24000
    clock = 0.0

    for index, segment in enumerate(segments):
        if not segment.strip():
            continue
        samples, sample_rate = k.create(segment, voice=voice, speed=1.0, lang=lang)
        seg_duration = len(samples) / sample_rate
        for w in estimate_word_timings(segment, seg_duration):
            words.append(WordTiming(word=w.word, start=clock + w.start, end=clock + w.end))
        pieces.append(samples)
        clock += seg_duration
        if index < len(segments) - 1:
            gap = np.zeros(int(sample_rate * _GAP_SECONDS), dtype=samples.dtype)
            pieces.append(gap)
            clock += _GAP_SECONDS

    if not pieces:
        raise RuntimeError("There was nothing to narrate.")

    joined = np.concatenate(pieces)
    _write_mp3(joined, sample_rate, out_path)
    return TTSResult(
        audio_path=out_path,
        duration=len(joined) / sample_rate,
        words=words,
        engine_used=f"kokoro:{voice}",
    )
