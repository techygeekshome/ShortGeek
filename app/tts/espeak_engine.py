"""Offline fallback voice: eSpeak NG. Robotic, but it needs no internet
connection and no account, so the app can still produce a video with zero
network dependency. Also used automatically if the default edge-tts engine
is unreachable.

Requires the `espeak-ng` command to be on PATH. On Windows: `winget install
--id eSpeak-NG.eSpeak-NG` (documented in the README).
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

from .base import TTSResult, WordTiming, estimate_word_timings

_GAP_SECONDS = 0.35  # silence inserted between segments, matches natural speech pauses


def is_available() -> bool:
    return shutil.which("espeak-ng") is not None or shutil.which("espeak") is not None


def _require_binary() -> str:
    binary = shutil.which("espeak-ng") or shutil.which("espeak")
    if not binary:
        raise RuntimeError(
            "eSpeak NG isn't installed, so the offline fallback voice isn't available. "
            "Install it (see README) or configure edge-tts / ElevenLabs instead."
        )
    return binary


def synthesize(text: str, voice: str, out_path: str) -> TTSResult:
    """Single-shot synthesis of one block of text. Word timings are a
    proportional-by-length *estimate* across the whole clip -- fine for a
    short single sentence, but for anything with multiple sentences/beats
    prefer synthesize_segments() below, which keeps captions from drifting
    out of sync at each natural pause."""
    binary = _require_binary()
    wav_path = str(Path(out_path).with_suffix(".wav"))
    subprocess.run(
        [binary, "-v", voice or "en-gb", "-s", "165", "-w", wav_path, text],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["ffmpeg", "-y", "-i", wav_path, "-codec:a", "libmp3lame", "-q:a", "3", out_path],
        check=True,
        capture_output=True,
    )
    Path(wav_path).unlink(missing_ok=True)

    duration = _probe_duration(out_path)
    words = estimate_word_timings(text, duration)
    return TTSResult(audio_path=out_path, duration=duration, words=words, engine_used="espeak")


def synthesize_segments(segments: List[str], voice: str, out_path: str) -> TTSResult:
    """Synthesizes each segment (hook, each beat, cta) as its own clip,
    measures each one's *real* rendered duration, and stitches them
    together with a fixed silence gap in between.

    estimate_word_timings() only distributes time proportionally within
    whatever text it's given -- if handed the whole script as one string,
    it has no idea eSpeak actually pauses at every sentence/beat break, so
    those un-budgeted pauses accumulate and captions drift further out of
    sync the further into the video you get. Measuring each segment's real
    duration separately keeps every segment boundary exactly on time; only
    the (much smaller) estimate *within* a single segment is approximate.
    """
    binary = _require_binary()
    segments = [s.strip() for s in segments if s and s.strip()]
    if not segments:
        raise RuntimeError("Nothing to synthesize -- the script is empty.")

    work_dir = Path(out_path).with_suffix("")
    work_dir_wav = Path(str(work_dir) + "_segs")
    work_dir_wav.mkdir(parents=True, exist_ok=True)

    gap_path = work_dir_wav / "_gap.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", f"anullsrc=r=24000:cl=mono", "-t", f"{_GAP_SECONDS}", str(gap_path)],
        check=True, capture_output=True,
    )

    seg_wavs: List[Path] = []
    words: List[WordTiming] = []
    cursor = 0.0
    for i, text in enumerate(segments):
        seg_wav = work_dir_wav / f"seg_{i}.wav"
        subprocess.run(
            [binary, "-v", voice or "en-gb", "-s", "165", "-w", str(seg_wav), text],
            check=True, capture_output=True,
        )
        seg_dur = _probe_duration(str(seg_wav))
        for wt in estimate_word_timings(text, seg_dur):
            words.append(WordTiming(word=wt.word, start=wt.start + cursor, end=wt.end + cursor))
        cursor += seg_dur
        seg_wavs.append(seg_wav)
        if i < len(segments) - 1:
            seg_wavs.append(gap_path)
            cursor += _GAP_SECONDS

    concat_list = work_dir_wav / "_concat.txt"
    concat_list.write_text("".join(f"file '{p.resolve()}'\n" for p in seg_wavs))
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
         "-codec:a", "libmp3lame", "-q:a", "3", out_path],
        check=True, capture_output=True,
    )

    duration = _probe_duration(out_path)
    for p in seg_wavs:
        if p != gap_path:
            p.unlink(missing_ok=True)
    gap_path.unlink(missing_ok=True)
    concat_list.unlink(missing_ok=True)
    try:
        work_dir_wav.rmdir()
    except OSError:
        pass

    return TTSResult(audio_path=out_path, duration=duration, words=words, engine_used="espeak")


def _probe_duration(path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())
