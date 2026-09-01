#!/usr/bin/env python3
"""Entry point for the packaged Windows build of ShortGeek.

This exists alongside desktop.py rather than replacing it. desktop.py is for
running from source and still tells you to install ffmpeg yourself; this one is
for the frozen build, where Python and ffmpeg both travel with the app.

Three things it does that the source entry point does not:

  * puts the bundled ffmpeg on PATH, so nothing in the app has to know it is
    running from an installer rather than a checkout
  * stops the black console window flashing up while ffmpeg runs
  * picks a free port rather than assuming 4173 is available
"""
from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

APP_NAME = "ShortGeek"
PREFERRED_PORT = 4173


def _bundle_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent


def _add_bundled_ffmpeg_to_path() -> str | None:
    """ffmpeg and ffprobe ship inside the installer. Putting their folder on
    PATH means shutil.which() finds them and the rest of the app is unchanged."""
    for candidate in (_bundle_dir() / "ffmpeg", Path(sys.executable).parent / "ffmpeg"):
        exe = candidate / "ffmpeg.exe"
        if exe.exists():
            os.environ["PATH"] = str(candidate) + os.pathsep + os.environ.get("PATH", "")
            return str(exe)
    return None


def _silence_console_windows() -> None:
    """Windows gives a console child process its own window even when the parent
    is windowed, so every ffmpeg call flashes a black box. Wrapping Popen to add
    CREATE_NO_WINDOW fixes it for every caller at once, without touching the
    render code."""
    if sys.platform != "win32":
        return
    import subprocess

    flag = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    original = subprocess.Popen

    class _QuietPopen(original):  # type: ignore[misc, valid-type]
        def __init__(self, *args, **kwargs):
            kwargs["creationflags"] = kwargs.get("creationflags", 0) | flag
            super().__init__(*args, **kwargs)

    subprocess.Popen = _QuietPopen

    _orig_run = subprocess.run

    def _quiet_run(*args, **kwargs):
        kwargs["creationflags"] = kwargs.get("creationflags", 0) | flag
        return _orig_run(*args, **kwargs)

    subprocess.run = _quiet_run


def _silence_proactor_reset() -> None:
    """Same harmless-teardown fix desktop.py carries: the free Edge voice opens
    and closes a connection per request, and the Proactor loop logs a traceback
    for it. See desktop.py for why this is done here rather than by swapping the
    event loop."""
    if sys.platform != "win32":
        return
    from asyncio.proactor_events import _ProactorBasePipeTransport

    original = _ProactorBasePipeTransport._call_connection_lost

    def _quiet(self, exc):
        try:
            original(self, exc)
        except ConnectionResetError:
            pass

    _ProactorBasePipeTransport._call_connection_lost = _quiet


def _free_port(preferred: int = PREFERRED_PORT) -> int:
    for port in [preferred, *range(preferred + 1, preferred + 40)]:
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return 0


def main() -> int:
    _silence_console_windows()
    _silence_proactor_reset()
    _add_bundled_ffmpeg_to_path()

    import uvicorn

    port = _free_port()
    url = f"http://127.0.0.1:{port}"

    def _serve():
        uvicorn.run("app.main:app", host="127.0.0.1", port=port, log_level="warning")

    thread = threading.Thread(target=_serve, daemon=True)
    thread.start()

    # Wait for the server to actually accept a connection rather than guessing.
    for _ in range(200):
        with socket.socket() as s:
            s.settimeout(0.1)
            try:
                s.connect(("127.0.0.1", port))
                break
            except OSError:
                time.sleep(0.05)

    try:
        import webview
    except Exception:
        webbrowser.open(url, new=2)
        thread.join()
        return 0

    webview.settings["ALLOW_DOWNLOADS"] = True
    webview.create_window(APP_NAME, url, width=1240, height=860, min_size=(980, 640))
    webview.start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
