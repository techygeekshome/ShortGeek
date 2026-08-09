"""Final assembly: background + per-beat cards (each with its own Ken-Burns
zoom/pan) + burned-in word-highlight captions + watermark + narration audio,
combined in a single ffmpeg filter_complex call.

This deliberately mirrors the compositing approach of the original Reddit
Video Maker Bot (input images overlaid on a background with time-windowed
`enable='between(t,a,b)'`) -- that part of the old design was sound. What's
different: every visual is either a real screenshot or code-drawn (never an
AI image or a scraped, login-gated webpage), each gets Ken-Burns motion
instead of sitting static, and captions are burned in, which the old tool
never had at all.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Callable, List, Optional

from ..captions.ass_builder import build_ass
from ..config import CACHE_DIR, FONTS_DIR, MUSIC_DIR
from ..scripting.writer import Script
from ..tts.base import TTSResult, WordTiming
from ..visuals import backgrounds, cards, watermark

FPS_DEFAULT = 30


def _ff_path(path: str) -> str:
    """Escape a filesystem path for safe use *inside* an ffmpeg filter
    argument (subtitles=..., fontsdir=...). Handles Windows drive-letter
    colons, which otherwise get parsed as a filter-option separator."""
    p = str(Path(path).resolve()).replace("\\", "/")
    p = p.replace(":", "\\:")
    return p


def _split_words_by_beats(words: List[WordTiming], script: Script):
    def wc(text: str) -> int:
        return len(re.findall(r"\S+", text))

    idx = 0
    hook_n = wc(script.hook)
    hook_words = words[idx : idx + hook_n]
    idx += hook_n

    beat_word_lists = []
    for b in script.beats:
        n = wc(b.text)
        beat_word_lists.append(words[idx : idx + n])
        idx += n

    cta_words = words[idx : idx + wc(script.cta)]
    return hook_words, beat_word_lists, cta_words


def _beat_span(word_list: List[WordTiming], fallback_start: float, min_dur: float = 0.6):
    if not word_list:
        return fallback_start, fallback_start + min_dur
    start, end = word_list[0].start, word_list[-1].end
    if end - start < min_dur:
        end = start + min_dur
    return start, end


def _build_beat_card(beat, index: int, work_dir: Path) -> tuple[str, int, int]:
    # Real screenshots were dropped from the visual pipeline: source images
    # are desktop-scale UI captures, and no amount of on-screen sizing makes
    # their text legible on a 9:16 clip at phone-viewing distance. Every
    # beat now gets the same legible treatment instead -- a code card for
    # code/commands, a bold numbered text callout for everything else.
    out_path = str(work_dir / f"card_{index}.png")
    if beat.is_code:
        return cards.render_code_card(beat.code_display or beat.text, out_path)
    return cards.render_bullet_card(beat.text, index + 1, out_path)


def render_video(
    script: Script,
    tts: TTSResult,
    cfg: dict,
    out_path: str,
    work_dir: Optional[Path] = None,
    progress_cb: Optional[Callable[[float], None]] = None,
) -> str:
    W = int(cfg.get("resolution_w", 1080))
    H = int(cfg.get("resolution_h", 1920))
    fps = int(cfg.get("fps", FPS_DEFAULT))
    total_duration = max(tts.duration, 1.0)

    work_dir = work_dir or (CACHE_DIR / "render_tmp")
    work_dir.mkdir(parents=True, exist_ok=True)

    hook_words, beat_word_lists, cta_words = _split_words_by_beats(tts.words, script)

    # ---- Per-beat cards + their on-screen time windows ----
    beat_cards = []
    hook_end = hook_words[-1].end if hook_words else 0.0
    cursor = hook_end
    for i, (beat, word_list) in enumerate(zip(script.beats, beat_word_lists)):
        start, end = _beat_span(word_list, fallback_start=cursor)
        cursor = end
        path, w, h = _build_beat_card(beat, i, work_dir)
        beat_cards.append({"path": path, "w": w, "h": h, "start": start, "end": end, "image_url": beat.image_url})
    cta_start = cursor

    bg_style = cfg.get("background_style", "gradient_motion")

    # ---- Watermark ----
    wm_path = watermark.build_watermark(cfg.get("brand_handle", ""), cfg.get("logo_letters", "TGH"))

    # ---- Captions ----
    ass_path = str(work_dir / "captions.ass")
    build_ass(tts.words, cfg.get("caption_style", "bold_highlight"), ass_path, video_w=W, video_h=H)

    # ---- Build the ffmpeg command ----
    inputs: List[str] = []
    filters: List[str] = []

    if bg_style == "content_pan":
        # Real per-beat article images (when the beat has one), slowly
        # panned full-bleed behind the card/captions -- filling any gap
        # (no image for that beat, or the hook/CTA stretches) with the
        # standard procedural still so there's never a blank frame.
        fallback_path = backgrounds.get_background_image("gradient_motion", seed_key=script.source_title or script.hook)
        inputs += ["-loop", "1", "-t", f"{total_duration:.3f}", "-i", fallback_path]
        bg_frames = max(1, round(total_duration * fps))
        filters.append(
            f"[0:v]scale=w={int(W*1.5)}:h=-1,zoompan=z='min(zoom+0.0006,1.12)':d={bg_frames}:"
            f"s={W}x{H}:fps={fps}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'[bgz]"
        )
        current_label = "bgz"
        input_index = 1

        first_img = next((bc["image_url"] for bc in beat_cards if bc["image_url"]), None)
        last_img = next((bc["image_url"] for bc in reversed(beat_cards) if bc["image_url"]), None)
        pan_segments = [(0.0, hook_end, first_img)]
        pan_segments += [(bc["start"], bc["end"], bc["image_url"]) for bc in beat_cards]
        pan_segments.append((cta_start, total_duration, last_img))

        for i, (seg_start, seg_end, img_url) in enumerate(pan_segments):
            dur = seg_end - seg_start
            if not img_url or dur < 0.3:
                continue  # no real image for this stretch -- fallback still already shows through
            img = cards.fetch_image(img_url)
            if img is None:
                continue
            img_path = str(work_dir / f"bgpan_{i}.png")
            img.save(img_path)
            pan_frames = max(1, round(dur * fps))
            pan_label = f"pan{i}"
            filters.append(
                f"[{input_index}:v]scale=w={int(W*1.4)}:h=-1,zoompan=z='1.18':d={pan_frames}:"
                f"s={W}x{H}:fps={fps}:x='(iw-iw/zoom)*on/{max(1, pan_frames-1)}':"
                f"y='(ih-ih/zoom)*on/{max(1, pan_frames-1)}'[{pan_label}]"
            )
            inputs += ["-loop", "1", "-t", f"{dur:.3f}", "-i", img_path]
            next_label = f"panc{i}"
            filters.append(
                f"[{current_label}][{pan_label}]overlay=enable='between(t,{seg_start:.3f},{seg_end:.3f})':"
                f"x=0:y=0[{next_label}]"
            )
            current_label = next_label
            input_index += 1
    else:
        bg_seed = script.source_title or script.hook
        bg = backgrounds.resolve_background(bg_style, seed_key=bg_seed)
        if bg["kind"] == "video":
            # A real (or procedurally animated) clip already has its own
            # motion -- loop it to fill the narration length and crop-to-
            # cover instead of stretching, no zoompan needed. Start from a
            # random point in the clip (not always frame 0) so reusing the
            # same background file across many videos doesn't make them
            # look like duplicates of each other; -stream_loop wraps back
            # to the real start of the file once playback runs past the end.
            start_offset = backgrounds.pick_random_start(bg["path"], seed_key=bg_seed, min_remaining=total_duration)
            inputs += ["-stream_loop", "-1", "-ss", f"{start_offset:.3f}", "-t", f"{total_duration:.3f}", "-i", bg["path"]]
            filters.append(
                f"[0:v]fps={fps},scale={W}:{H}:force_original_aspect_ratio=increase,"
                f"crop={W}:{H}[bgz]"
            )
        else:
            inputs += ["-loop", "1", "-t", f"{total_duration:.3f}", "-i", bg["path"]]
            bg_frames = max(1, round(total_duration * fps))
            filters.append(
                f"[0:v]scale=w={int(W*1.5)}:h=-1,zoompan=z='min(zoom+0.0006,1.12)':d={bg_frames}:"
                f"s={W}x{H}:fps={fps}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'[bgz]"
            )
        current_label = "bgz"
        input_index = 1  # 0 was the background

    band_top = int(H * 0.20)
    for i, bc in enumerate(beat_cards):
        dur = max(0.5, bc["end"] - bc["start"])
        inputs += ["-loop", "1", "-t", f"{dur:.3f}", "-i", bc["path"]]
        frames = max(1, round(dur * fps))
        x = (W - bc["w"]) // 2
        y = band_top
        filters.append(
            f"[{input_index}:v]scale=w={int(bc['w']*1.3)}:h=-1,zoompan=z='min(zoom+0.0018,1.10)':d={frames}:"
            f"s={bc['w']}x{bc['h']}:fps={fps}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'[card{i}]"
        )
        next_label = f"comp{i}"
        filters.append(
            f"[{current_label}][card{i}]overlay=enable='between(t,{bc['start']:.3f},{bc['end']:.3f})':"
            f"x={x}:y={y}[{next_label}]"
        )
        current_label = next_label
        input_index += 1

    # Burn captions
    filters.append(f"[{current_label}]subtitles='{_ff_path(ass_path)}':fontsdir='{_ff_path(str(FONTS_DIR))}'[capd]")
    current_label = "capd"

    # Watermark (persistent, bottom-left safe area)
    wm_input_index = input_index
    inputs += ["-loop", "1", "-t", f"{total_duration:.3f}", "-i", wm_path]
    wm_x = int(W * 0.06)
    wm_y = int(H * 0.90)
    filters.append(f"[{current_label}][{wm_input_index}:v]overlay=x={wm_x}:y={wm_y}[vout]")
    input_index += 1

    # ---- Audio: narration (+ optional background music, ducked low) ----
    audio_input_index = input_index
    inputs += ["-i", tts.audio_path]
    audio_label = f"{audio_input_index}:a"
    input_index += 1

    music_files = list(MUSIC_DIR.glob("*.mp3"))
    if cfg.get("use_background_music") and music_files:
        music_input_index = input_index
        inputs += ["-stream_loop", "-1", "-t", f"{total_duration:.3f}", "-i", str(music_files[0])]
        filters.append(f"[{music_input_index}:a]volume=0.12[bgm]")
        filters.append(f"[{audio_input_index}:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]")
        audio_label = "aout"
        input_index += 1

    filter_complex = ";\n".join(filters)

    # A filter output (e.g. "aout") needs brackets in -map; a raw stream
    # reference (e.g. "5:a") does not.
    audio_map_arg = f"[{audio_label}]" if audio_label == "aout" else audio_label

    cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", filter_complex,
           "-map", "[vout]", "-map", audio_map_arg,
           "-c:v", "libx264", "-preset", "medium", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "160k", "-shortest",
           "-progress", "pipe:1", "-nostats",
           out_path]

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
    stderr_lines: List[str] = []
    import threading

    def _drain_stderr():
        for line in proc.stderr:
            stderr_lines.append(line)

    t = threading.Thread(target=_drain_stderr, daemon=True)
    t.start()

    for line in proc.stdout:
        if line.startswith("out_time_ms=") and progress_cb:
            try:
                ms = int(line.strip().split("=")[1])
                progress_cb(min(1.0, (ms / 1_000_000) / total_duration))
            except (ValueError, ZeroDivisionError):
                pass

    proc.wait()
    t.join(timeout=2)

    if proc.returncode != 0:
        tail = "".join(stderr_lines[-40:])
        raise RuntimeError(f"ffmpeg render failed (exit {proc.returncode}):\n{tail}")

    if progress_cb:
        progress_cb(1.0)

    return out_path
