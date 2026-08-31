"""
Local settings storage for ShortGeek.

Everything lives in a single JSON file on disk (data/config.json). Nothing here
is ever sent anywhere except to the services you explicitly configure a key
for (and even then, only when you use that feature). There is no telemetry.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict

import os
import sys

_FROZEN = getattr(sys, "frozen", False)

if _FROZEN:
    # PyInstaller unpacks the read-only payload (app/, assets/) into _internal.
    BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    # Anything the app writes has to live somewhere the user can actually write
    # to. The install folder may be read-only, so settings, the render library
    # and the cache go under LOCALAPPDATA instead, and survive an uninstall.
    _root = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    DATA_DIR = Path(_root) / "ShortGeek"
else:
    BASE_DIR = Path(__file__).resolve().parent.parent
    DATA_DIR = BASE_DIR / "data"

CONFIG_PATH = DATA_DIR / "config.json"
LIBRARY_DIR = DATA_DIR / "library"
CACHE_DIR = DATA_DIR / "cache"

# Assets ship with the app and are only ever read.
ASSETS_DIR = BASE_DIR / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"

# Your own background clips and music are user content, so they live beside the
# rest of the user's data rather than inside the install folder.
CUSTOM_BG_DIR = (DATA_DIR / "backgrounds" / "custom") if _FROZEN else (ASSETS_DIR / "backgrounds" / "custom")
MUSIC_DIR = (DATA_DIR / "backgrounds" / "music") if _FROZEN else (ASSETS_DIR / "backgrounds" / "music")

DEFAULTS: Dict[str, Any] = {
    # Deliberately generic. ShortGeek stamps a name and handle onto the end card of
    # every video, so shipping a real person's brand here would mean strangers
    # publishing shorts under someone else's name. The app asks on first run and
    # sets brand_configured once the question has been answered.
    "brand_configured": False,
    "brand_name": "My Channel",
    "brand_handle": "",
    "site_url": "",
    "logo_letters": "MC",
    # Voice
    "voice_engine": "edge",          # "edge" | "espeak" | "elevenlabs"
    "edge_voice": "en-GB-RyanNeural",
    "espeak_voice": "en-gb",
    "elevenlabs_api_key": "",
    "elevenlabs_voice_id": "",
    # Script writing
    "llm_provider": "none",           # "none" | "anthropic" | "openai"
    "llm_api_key": "",
    "brand_style_notes": "Friendly, plain-English, no hype, no clickbait exaggeration.",
    # Visual defaults
    "caption_style": "bold_highlight",  # "bold_highlight" | "minimal" | "classic_subtitle"
    "background_style": "content_pan",  # article: content_pan (real per-beat images, panned)
                                          # still: gradient_motion | typing_loop | terminal_scroll | clean_light
                                          # motion: code_rain | bounce_orbit | sort_visualizer
                                          # yours: custom:<filename.mp4> | custom_random
    "resolution_w": 1080,
    "resolution_h": 1920,
    "fps": 30,
    "use_background_music": False,
}


class Config:
    def __init__(self):
        self._lock = threading.Lock()
        self._data: Dict[str, Any] = {}
        self._load()

    def _load(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        MUSIC_DIR.mkdir(parents=True, exist_ok=True)
        CUSTOM_BG_DIR.mkdir(parents=True, exist_ok=True)
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    on_disk = json.load(f)
            except (json.JSONDecodeError, OSError):
                on_disk = {}
        else:
            on_disk = {}
        merged = {**DEFAULTS, **on_disk}
        self._data = merged
        self._save()

    def _save(self):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    def all(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._data)

    def get(self, key: str, default=None):
        with self._lock:
            return self._data.get(key, default)

    def update(self, patch: Dict[str, Any]):
        with self._lock:
            for k, v in patch.items():
                if k in DEFAULTS:
                    self._data[k] = v
            self._save()
            return dict(self._data)

    # Convenience: keys safe to ever show back in a UI (never echo raw secrets
    # back into logs/exceptions).
    def public(self) -> Dict[str, Any]:
        d = self.all()
        for secret_key in ("elevenlabs_api_key", "llm_api_key"):
            if d.get(secret_key):
                d[secret_key] = "•" * 8
        return d


config = Config()
