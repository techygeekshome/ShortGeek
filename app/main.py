from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from . import jobs
from .config import BASE_DIR, CACHE_DIR, LIBRARY_DIR, config
from .scripting import writer
from .scripting.writer import Beat, Script
from .sources import rss_url, topic
from .sources.wordpress import WordPressSource
from .tts import router as tts_router
from .version import APP_LICENCE, APP_VERSION, CHANGELOG
from .video import assemble
from .visuals import backgrounds

app = FastAPI(title="ShortGeek")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    # app_version is used as a cache-busting query string on the static
    # JS/CSS includes (see index.html) -- otherwise a browser/WebView2 that
    # aggressively caches local assets can keep serving an old app.js after
    # a new build is unzipped over an old one, silently making a shipped
    # fix look like it never applied.
    return templates.TemplateResponse(request=request, name="index.html", context={"app_version": APP_VERSION})


# ---------------------------------------------------------------- sources --

@app.get("/api/guides")
def api_guides(search: str = "", per_page: int = 20):
    cfg = config.all()
    site = (cfg.get("site_url") or "").strip()
    # My Guides reads a WordPress site's public REST API. Until the user has told
    # us which site is theirs there is nothing to read, so say that plainly rather
    # than building a broken URL and reporting a connection error for it.
    if not site:
        return {
            "items": [],
            "notice": "Set your site address under Settings to pull in your own guides. "
                      "The other three source tabs work without it.",
        }
    src = WordPressSource(site)
    try:
        return {"items": src.search(search, per_page)}
    except Exception as e:
        raise HTTPException(502, f"Couldn't reach {site}: {e}")


class RssListIn(BaseModel):
    feed_url: str


@app.post("/api/rss/list")
def api_rss_list(body: RssListIn):
    try:
        return {"items": rss_url.list_feed(body.feed_url)}
    except Exception as e:
        raise HTTPException(502, f"Couldn't read that feed: {e}")


# ------------------------------------------------------------- script draft -

class DraftRequest(BaseModel):
    source_type: str  # "guide" | "rss_url" | "url" | "topic"
    guide_id: Optional[int] = None
    url: Optional[str] = None
    topic: Optional[str] = None


@app.post("/api/script/draft")
def api_script_draft(body: DraftRequest):
    cfg = config.all()
    if body.source_type == "guide":
        if not body.guide_id:
            raise HTTPException(400, "guide_id required")
        item = WordPressSource(cfg["site_url"]).fetch(body.guide_id)
    elif body.source_type in ("rss_url", "url"):
        if not body.url:
            raise HTTPException(400, "url required")
        item = rss_url.fetch_url(body.url)
    elif body.source_type == "topic":
        if not body.topic:
            raise HTTPException(400, "topic required")
        item = topic.make_item(body.topic)
    else:
        raise HTTPException(400, f"Unknown source_type: {body.source_type}")

    script = writer.draft_script(item)
    return writer.script_to_dict(script)


# ------------------------------------------------------------------ render -

class BeatIn(BaseModel):
    text: str
    image_url: Optional[str] = None
    is_code: bool = False
    code_display: Optional[str] = None


class ScriptIn(BaseModel):
    hook: str
    beats: List[BeatIn]
    cta: str
    source_title: str = ""


class RenderRequest(BaseModel):
    script: ScriptIn
    voice_engine: Optional[str] = None
    caption_style: Optional[str] = None
    background_style: Optional[str] = None


def _slugify(text: str) -> str:
    s = re.sub(r"[^\w\s-]", "", text).strip().lower()
    s = re.sub(r"[\s_-]+", "-", s)
    return s[:80] or "short"


@app.post("/api/render")
def api_render(body: RenderRequest):
    cfg = config.all()
    if body.voice_engine:
        cfg["voice_engine"] = body.voice_engine
    if body.caption_style:
        cfg["caption_style"] = body.caption_style
    if body.background_style:
        cfg["background_style"] = body.background_style

    script = Script(
        hook=body.script.hook,
        beats=[Beat(text=b.text, image_url=b.image_url, is_code=b.is_code, code_display=b.code_display) for b in body.script.beats],
        cta=body.script.cta,
        source_title=body.script.source_title,
    )

    slug = _slugify(script.source_title or script.hook)
    out_filename = f"{slug}-{int(time.time())}.mp4"

    def _do_render(job: jobs.Job):
        from .config import CACHE_DIR

        job.message = "Synthesizing narration…"
        narration_path = str(CACHE_DIR / f"narration_{job.id}.mp3")
        segments = [script.hook, *[b.text for b in script.beats], script.cta]
        tts_result = tts_router.synthesize(script.full_text, cfg, narration_path, segments=segments)
        job.progress = 0.12
        if tts_result.fallback_used:
            job.message = "Online voice unavailable - used the offline fallback voice."

        job.message = "Rendering video…"
        out_path = str(LIBRARY_DIR / out_filename)
        work_dir = CACHE_DIR / f"render_{job.id}"

        def _cb(p: float):
            job.progress = 0.12 + p * 0.88

        assemble.render_video(script, tts_result, cfg, out_path, work_dir=work_dir, progress_cb=_cb)
        job.result_path = out_path
        jobs.add_to_library(
            {
                "title": script.source_title or script.hook,
                "filename": out_filename,
                "created_at": time.time(),
                "duration": tts_result.duration,
                "voice_engine": tts_result.engine_used,
            }
        )

    job = jobs.submit(script.source_title or script.hook, _do_render)
    return {"job_id": job.id}


@app.get("/api/jobs")
def api_jobs():
    return {"items": [j.public() for j in jobs.list_recent()]}


@app.get("/api/jobs/{job_id}")
def api_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    return job.public()


# ----------------------------------------------------------------- library -

@app.get("/api/library")
def api_library():
    return {"items": jobs.list_library()}


@app.get("/api/library/file/{filename}")
def api_library_file(filename: str):
    path = LIBRARY_DIR / filename
    if not path.exists():
        raise HTTPException(404, "not found")
    return FileResponse(str(path), media_type="video/mp4", filename=filename)


# --------------------------------------------------------------- backgrounds -

_BG_THUMB_DIR = CACHE_DIR / "bg_thumbs"
_BG_THUMB_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/api/backgrounds/custom")
def api_backgrounds_custom():
    return {"items": [Path(p).name for p in backgrounds.list_custom_backgrounds()]}


@app.get("/api/backgrounds/custom/thumb/{filename}")
def api_backgrounds_custom_thumb(filename: str):
    src = backgrounds.CUSTOM_DIR / filename
    if not src.exists():
        raise HTTPException(404, "not found")
    thumb = _BG_THUMB_DIR / f"{filename}.jpg"
    if not thumb.exists():
        subprocess.run(
            ["ffmpeg", "-y", "-ss", "1", "-i", str(src), "-frames:v", "1", "-vf", "scale=200:-1", str(thumb)],
            capture_output=True,
        )
    if not thumb.exists():
        raise HTTPException(500, "couldn't generate a thumbnail for that clip")
    return FileResponse(str(thumb), media_type="image/jpeg")


@app.post("/api/backgrounds/custom/open-folder")
def api_backgrounds_open_folder():
    """Opens the clips folder in the OS file browser. Safe here because
    this server only ever runs locally on your own machine -- it's never
    reachable from anywhere else."""
    path = str(backgrounds.CUSTOM_DIR.resolve())
    try:
        if sys.platform == "win32":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", path], check=False)
        else:
            subprocess.run(["xdg-open", path], check=False)
    except Exception as e:
        raise HTTPException(500, f"Couldn't open the folder: {e}")
    return {"ok": True, "path": path}


_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


@app.post("/api/backgrounds/custom/upload")
async def api_backgrounds_custom_upload(file: UploadFile = File(...)):
    name = Path(file.filename or "clip.mp4").name
    if not name.lower().endswith(".mp4"):
        raise HTTPException(400, "Only .mp4 files are supported.")
    safe_name = _SAFE_FILENAME.sub("_", name) or "clip.mp4"
    dest = backgrounds.CUSTOM_DIR / safe_name
    if dest.exists():
        stem, suffix, i = dest.stem, dest.suffix, 2
        while dest.exists():
            dest = backgrounds.CUSTOM_DIR / f"{stem}-{i}{suffix}"
            i += 1
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"ok": True, "filename": dest.name}


@app.delete("/api/backgrounds/custom/{filename}")
def api_backgrounds_custom_delete(filename: str):
    path = backgrounds.CUSTOM_DIR / Path(filename).name  # .name strips any path components
    if not path.exists():
        raise HTTPException(404, "not found")
    path.unlink()
    thumb = _BG_THUMB_DIR / f"{path.name}.jpg"
    thumb.unlink(missing_ok=True)
    return {"ok": True}


# ---------------------------------------------------------------------- about -

@app.get("/api/about")
def api_about():
    return {"version": APP_VERSION, "changelog": CHANGELOG, "licence": APP_LICENCE}


# ----------------------------------------------------------------- settings -

@app.get("/api/settings")
def api_settings_get():
    return config.public()


@app.post("/api/settings")
def api_settings_post(body: dict):
    config.update(body)
    return config.public()


@app.get("/api/voices/edge")
async def api_voices_edge(locale: str = "en"):
    from .tts import edge_engine

    try:
        voices = await edge_engine.list_voices(locale)
        return {"items": [{"name": v["ShortName"], "gender": v["Gender"], "locale": v["Locale"]} for v in voices]}
    except Exception as e:
        raise HTTPException(502, f"Couldn't list voices (needs internet): {e}")
