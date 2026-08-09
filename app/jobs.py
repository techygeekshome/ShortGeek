"""A deliberately simple in-process job queue. This is a single-user local
app, not a multi-tenant service -- a thread pool + an in-memory dict is all
that's needed, and it keeps the codebase easy to read and modify.
"""
from __future__ import annotations

import json
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Dict, Optional

from .config import LIBRARY_DIR

_executor = ThreadPoolExecutor(max_workers=2)
_jobs: Dict[str, "Job"] = {}
_lock = threading.Lock()


@dataclass
class Job:
    id: str
    title: str
    status: str = "queued"   # queued | running | done | error
    progress: float = 0.0
    message: str = ""
    result_path: Optional[str] = None
    created_at: float = field(default_factory=time.time)

    def public(self) -> dict:
        d = asdict(self)
        if d.get("result_path"):
            d["download_url"] = f"/api/library/file/{Path(d['result_path']).name}"
        return d


def submit(title: str, fn: Callable[["Job"], None]) -> Job:
    job = Job(id=uuid.uuid4().hex[:10], title=title)
    with _lock:
        _jobs[job.id] = job

    def _run():
        job.status = "running"
        try:
            fn(job)
            job.status = "done"
            job.progress = 1.0
        except Exception as e:  # noqa: BLE001 -- surface any failure to the UI
            job.status = "error"
            job.message = str(e)
            traceback.print_exc()

    _executor.submit(_run)
    return job


def get(job_id: str) -> Optional[Job]:
    with _lock:
        return _jobs.get(job_id)


def list_recent(limit: int = 20):
    with _lock:
        jobs = sorted(_jobs.values(), key=lambda j: j.created_at, reverse=True)
    return jobs[:limit]


# ---- Library (finished videos) persistence -------------------------------

_LIBRARY_INDEX = LIBRARY_DIR / "index.json"


def _load_library() -> list:
    if _LIBRARY_INDEX.exists():
        try:
            return json.loads(_LIBRARY_INDEX.read_text())
        except json.JSONDecodeError:
            return []
    return []


def _save_library(items: list):
    _LIBRARY_INDEX.write_text(json.dumps(items, indent=2))


def add_to_library(entry: dict):
    items = _load_library()
    items.insert(0, entry)
    _save_library(items)


def list_library() -> list:
    return _load_library()
