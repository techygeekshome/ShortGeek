"""Procedurally generated (code-drawn, never AI-generated) background art.

Three kinds of background, all resolved through resolve_background():

  - procedural still  : one oversized image, animated later via the same
                         Ken-Burns zoompan technique used for cards
                         (video/assemble.py) -- gradients, terminal-scroll,
                         typing-loop, clean-light looks.
  - procedural motion  : a short (~8s), genuinely *animated* loop rendered
                          frame-by-frame in code and encoded to an mp4 loop
                          (code rain, bouncing orbits, a live sort
                          visualizer) -- built for cases where a slow pan
                          over a still image isn't stimulating enough.
  - your own clip      : real video you've dropped into
                          assets/backgrounds/custom/ (gameplay footage,
                          satisfying loops, whatever keeps attention) --
                          looped/trimmed to fit, picked by name or randomly.

Everything here is either drawn in code or supplied by you -- never AI art,
never scraped footage.
"""
from __future__ import annotations

import hashlib
import random
import subprocess
from pathlib import Path
from typing import Iterator, List

from PIL import Image, ImageDraw, ImageFont

from ..config import ASSETS_DIR, CACHE_DIR, FONTS_DIR

CUSTOM_DIR = ASSETS_DIR / "backgrounds" / "custom"
CUSTOM_DIR.mkdir(parents=True, exist_ok=True)

CANVAS_W, CANVAS_H = 2400, 4266  # oversized so zoompan has room to pan/zoom

# Procedural *motion* loops are rendered at a smaller working resolution
# (they already have their own motion, unlike the stills, so they don't
# need zoompan headroom) and cached as a short looping mp4 per content seed.
ANIM_W, ANIM_H = 540, 960
ANIM_FPS = 24
ANIM_SECONDS = 8
ANIM_N_FRAMES = ANIM_FPS * ANIM_SECONDS

BRAND_TEAL = (94, 234, 212)
BRAND_INDIGO = (129, 140, 248)
BRAND_ACCENT = (79, 70, 229)


def list_custom_backgrounds() -> List[str]:
    return sorted(str(p) for p in CUSTOM_DIR.glob("*.mp4"))


def _seeded_random(key: str) -> random.Random:
    seed = int(hashlib.sha1(key.encode()).hexdigest(), 16) % (2**32)
    return random.Random(seed)


def _probe_duration(path: str) -> float:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, check=True,
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def pick_random_start(path: str, seed_key: str, min_remaining: float = 0.0) -> float:
    """A background video reused across many renders would otherwise always
    start at frame 0 every time -- every video using it would open on
    identical footage, reading as duplicates even when the rest of the
    video is completely different. Pick a (seeded, so still reproducible
    for the same content) random point in the clip to start from instead.

    Prefers a start point with enough runway left to cover the whole video
    without ever needing to loop back around -- ffmpeg's -stream_loop does
    technically wrap a seeked input, but empirically the wrap-back point
    isn't a clean, predictable "true start of file" restart, so it's safer
    to just not rely on it when the clip is long enough to avoid it
    entirely (true for any real gameplay/b-roll compilation, which tend to
    run long). Only falls back to using the full clip range -- and
    whatever -stream_loop does with it -- when the clip itself is shorter
    than the video, since there's no way to avoid a wrap there regardless
    of where playback starts."""
    duration = _probe_duration(path)
    if duration <= 1.0:
        return 0.0
    rnd = _seeded_random(seed_key + "|bgstart")
    max_start = max(0.0, duration - min_remaining)
    if max_start <= 0.0:
        return 0.0
    return round(rnd.uniform(0, max_start), 3)


# ---------------------------------------------------------------- stills --

def _grid_overlay(im: Image.Image, step: int = 46, alpha: int = 10) -> Image.Image:
    grid = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(grid)
    for x in range(0, im.size[0], step):
        d.line([(x, 0), (x, im.size[1])], fill=(255, 255, 255, alpha), width=1)
    for y in range(0, im.size[1], step):
        d.line([(0, y), (im.size[0], y)], fill=(255, 255, 255, alpha), width=1)
    return Image.alpha_composite(im.convert("RGBA"), grid)


def _gradient_motion(seed_key: str) -> Image.Image:
    rnd = _seeded_random(seed_key)
    base = Image.new("RGB", (CANVAS_W, CANVAS_H), (15, 23, 42))
    draw = ImageDraw.Draw(base, "RGBA")
    accents = [(14, 165, 183), (79, 70, 229), (99, 102, 241)]
    for _ in range(3):
        cx = rnd.randint(int(CANVAS_W * 0.15), int(CANVAS_W * 0.85))
        cy = rnd.randint(int(CANVAS_H * 0.1), int(CANVAS_H * 0.4))
        color = rnd.choice(accents)
        r0 = rnd.randint(1100, 1500)
        for r in range(r0, 0, -14):
            t = r / r0
            alpha = int(42 * (1 - t))
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*color, alpha))
    return _grid_overlay(base)


def _terminal_scroll(seed_key: str) -> Image.Image:
    rnd = _seeded_random(seed_key)
    base = Image.new("RGB", (CANVAS_W, CANVAS_H), (10, 13, 20))
    draw = ImageDraw.Draw(base, "RGBA")
    y = 40
    while y < CANVAS_H - 40:
        line_w = rnd.randint(int(CANVAS_W * 0.08), int(CANVAS_W * 0.42))
        x = int(CANVAS_W * 0.08)
        color = rnd.choice([(94, 234, 212, 60), (148, 163, 184, 45), (79, 70, 229, 55)])
        draw.rounded_rectangle([x, y, x + line_w, y + 14], radius=6, fill=color)
        y += rnd.randint(30, 54)
    return _grid_overlay(base, alpha=6)


def _typing_loop(seed_key: str) -> Image.Image:
    rnd = _seeded_random(seed_key)
    base = Image.new("RGB", (CANVAS_W, CANVAS_H), (17, 24, 39))
    draw = ImageDraw.Draw(base, "RGBA")
    y = int(CANVAS_H * 0.3)
    for _ in range(9):
        line_w = rnd.randint(int(CANVAS_W * 0.15), int(CANVAS_W * 0.55))
        draw.rounded_rectangle(
            [int(CANVAS_W * 0.1), y, int(CANVAS_W * 0.1) + line_w, y + 20],
            radius=8, fill=(255, 255, 255, rnd.randint(18, 40)),
        )
        y += rnd.randint(46, 70)
    return _grid_overlay(base, alpha=8)


def _clean_light(seed_key: str) -> Image.Image:
    base = Image.new("RGB", (CANVAS_W, CANVAS_H), (246, 247, 250))
    draw = ImageDraw.Draw(base, "RGBA")
    draw.ellipse([-400, -400, CANVAS_W * 0.6, CANVAS_H * 0.35], fill=(79, 70, 229, 18))
    draw.ellipse([CANVAS_W * 0.4, CANVAS_H * 0.6, CANVAS_W + 400, CANVAS_H * 1.1], fill=(14, 165, 183, 16))
    return base.convert("RGBA")


_STILL_BUILDERS = {
    "gradient_motion": _gradient_motion,
    "terminal_scroll": _terminal_scroll,
    "typing_loop": _typing_loop,
    "clean_light": _clean_light,
}


def get_background_image(style: str, seed_key: str) -> str:
    style = style if style in _STILL_BUILDERS else "gradient_motion"
    out_path = CACHE_DIR / f"bg_{style}_{abs(hash(seed_key)) % 100000}.png"
    if out_path.exists():
        return str(out_path)
    img = _STILL_BUILDERS[style](seed_key).convert("RGB")
    img.save(out_path)
    return str(out_path)


# ------------------------------------------------------- procedural motion -

def _lerp_color(a: tuple, b: tuple, t: float) -> tuple:
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


_RAIN_CHARS = "01{}<>/\\;:=+-_#$%01010101ABCDEFHKMNPRSTXYZ"


def _code_rain_frames(rnd: random.Random, w: int, h: int, n: int) -> Iterator[Image.Image]:
    """Falling brand-tinted glyph columns -- a tech-flavoured take on the
    classic 'digital rain' look. Speeds are chosen so every column completes
    a whole number of falls across the clip, which makes the loop point
    seamless (frame n lands exactly back on frame 0)."""
    bg_color = (9, 12, 20)
    font_size = 22
    font = ImageFont.truetype(str(FONTS_DIR / "DejaVuSansMono.ttf"), font_size)
    col_spacing = 27
    char_h = int(font_size * 1.05)
    cols = []
    for c in range(max(1, w // col_spacing)):
        trail_len = rnd.randint(6, 14)
        trail_h = trail_len * char_h
        period = h + trail_h
        cycles = rnd.randint(2, 5)
        cols.append({
            "x": c * col_spacing + rnd.randint(-2, 2),
            "trail_h": trail_h,
            "period": period,
            "speed": period * cycles / n,
            "phase": rnd.uniform(0, period),
            "chars": [rnd.choice(_RAIN_CHARS) for _ in range(trail_len)],
        })

    for t in range(n):
        img = Image.new("RGB", (w, h), bg_color)
        draw = ImageDraw.Draw(img)
        for col in cols:
            lead_y = ((col["phase"] + col["speed"] * t) % col["period"]) - col["trail_h"]
            for i, ch in enumerate(col["chars"]):
                y = lead_y - i * char_h
                if -char_h <= y <= h:
                    color = _lerp_color(BRAND_TEAL, bg_color, i / max(1, len(col["chars"]) - 1))
                    draw.text((col["x"], y), ch, font=font, fill=color)
        yield img


def _bounce_orbit_frames(rnd: random.Random, w: int, h: int, n: int) -> Iterator[Image.Image]:
    """Soft brand-coloured dots bouncing around the frame with fading
    trails -- a 'satisfying visual' loop in the vein of the physics-toy
    clips that keep attention on their own, without needing any footage."""
    bg = (12, 16, 27)
    palette = [BRAND_TEAL, BRAND_INDIGO, BRAND_ACCENT]
    balls = []
    for _ in range(rnd.randint(9, 15)):
        balls.append({
            "x": rnd.uniform(0.1, 0.9) * w,
            "y": rnd.uniform(0.1, 0.9) * h,
            "vx": rnd.choice([-1, 1]) * rnd.uniform(2.4, 5.2),
            "vy": rnd.choice([-1, 1]) * rnd.uniform(2.4, 5.2),
            "r": rnd.randint(8, 22),
            "color": rnd.choice(palette),
        })

    canvas = Image.new("RGB", (w, h), bg)
    bg_img = canvas.copy()
    for _ in range(n):
        canvas = Image.blend(canvas, bg_img, 0.16)  # trail fade
        draw = ImageDraw.Draw(canvas)
        for b in balls:
            b["x"] += b["vx"]
            b["y"] += b["vy"]
            if b["x"] - b["r"] < 0 or b["x"] + b["r"] > w:
                b["vx"] *= -1
                b["x"] = min(max(b["x"], b["r"]), w - b["r"])
            if b["y"] - b["r"] < 0 or b["y"] + b["r"] > h:
                b["vy"] *= -1
                b["y"] = min(max(b["y"], b["r"]), h - b["r"])
            draw.ellipse([b["x"] - b["r"], b["y"] - b["r"], b["x"] + b["r"], b["y"] + b["r"]], fill=b["color"])
        yield canvas.copy()


def _bubble_sort_states(values: List[int]) -> List[List[int]]:
    arr = list(values)
    states = [list(arr)]
    n = len(arr)
    for i in range(n):
        for j in range(n - i - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
                states.append(list(arr))
    return states


def _sort_visualizer_frames(rnd: random.Random, w: int, h: int, n: int) -> Iterator[Image.Image]:
    """A live sort-in-progress bar chart -- a real bubble sort, not a fake
    animation, run on a freshly shuffled array each loop. This exact genre
    (sorting visualizers) is a staple 'oddly satisfying' background for a
    tech-leaning audience specifically."""
    bg_color = (13, 17, 28)
    bar_color = BRAND_TEAL
    highlight = BRAND_ACCENT
    n_bars = rnd.randint(26, 34)
    values = list(range(1, n_bars + 1))
    rnd.shuffle(values)
    states = _bubble_sort_states(values)
    max_v = max(values)
    bar_w = w / n_bars

    for t in range(n):
        idx = min(len(states) - 1, int((t / max(1, n - 1)) * (len(states) - 1)))
        arr = states[idx]
        prev = states[idx - 1] if idx > 0 else arr
        changed = {i for i in range(len(arr)) if arr[i] != prev[i]}
        img = Image.new("RGB", (w, h), bg_color)
        draw = ImageDraw.Draw(img)
        for i, v in enumerate(arr):
            bh = (v / max_v) * (h * 0.8)
            x0, x1 = i * bar_w + 1.5, (i + 1) * bar_w - 1.5
            color = highlight if i in changed else bar_color
            draw.rectangle([x0, h - bh, x1, h], fill=color)
        yield img


_ANIMATED_BUILDERS = {
    "code_rain": _code_rain_frames,
    "bounce_orbit": _bounce_orbit_frames,
    "sort_visualizer": _sort_visualizer_frames,
}


def _encode_frames_to_mp4(frames: Iterator[Image.Image], w: int, h: int, fps: int, out_path: str) -> None:
    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps),
        "-i", "-",
        "-c:v", "libx264", "-preset", "medium", "-pix_fmt", "yuv420p",
        out_path,
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        for frame in frames:
            if frame.mode != "RGB" or frame.size != (w, h):
                frame = frame.convert("RGB").resize((w, h))
            proc.stdin.write(frame.tobytes())
    finally:
        proc.stdin.close()
    proc.wait()
    if proc.returncode != 0:
        tail = proc.stderr.read().decode(errors="ignore")[-500:]
        raise RuntimeError(f"Failed to render animated background (exit {proc.returncode}):\n{tail}")


def get_animated_background_video(style: str, seed_key: str) -> str:
    out_path = CACHE_DIR / f"bg_{style}_{abs(hash(seed_key)) % 100000}.mp4"
    if out_path.exists():
        return str(out_path)
    rnd = _seeded_random(seed_key)
    frames = _ANIMATED_BUILDERS[style](rnd, ANIM_W, ANIM_H, ANIM_N_FRAMES)
    tmp_path = str(out_path) + ".tmp.mp4"
    _encode_frames_to_mp4(frames, ANIM_W, ANIM_H, ANIM_FPS, tmp_path)
    Path(tmp_path).replace(out_path)
    return str(out_path)


# --------------------------------------------------------------- resolver --

def resolve_background(style: str, seed_key: str) -> dict:
    """Turns whatever the user picked into {'kind': 'image'|'video', 'path'}.
    Falls back to the default procedural still if a custom clip / style
    reference no longer resolves to anything (e.g. the file was deleted)."""
    if style == "custom_random":
        clips = list_custom_backgrounds()
        if clips:
            rnd = _seeded_random(seed_key)
            return {"kind": "video", "path": rnd.choice(clips)}
        style = "gradient_motion"

    if style.startswith("custom:"):
        fname = style.split("custom:", 1)[1]
        path = CUSTOM_DIR / fname
        if path.exists():
            return {"kind": "video", "path": str(path)}
        style = "gradient_motion"

    if style in _ANIMATED_BUILDERS:
        return {"kind": "video", "path": get_animated_background_video(style, seed_key)}

    return {"kind": "image", "path": get_background_image(style, seed_key)}
