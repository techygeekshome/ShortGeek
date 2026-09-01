#!/usr/bin/env python3
"""Desktop entry point: runs the local web app in a background thread and
opens it in its own native window (via pywebview) instead of a browser tab.

If pywebview isn't installed (or its platform backend isn't available),
this falls back to just opening your default browser -- the app itself is
unaffected either way, since it's the same local web server underneath.
"""
from __future__ import annotations

import asyncio
import shutil
import sys
import threading
import time
import webbrowser

# Windows only: the default ProactorEventLoop logs a noisy (but harmless)
# "ConnectionResetError [WinError 10054]" traceback whenever a short-lived
# aiohttp connection is torn down -- which happens on every single edge-tts
# call, since it opens a fresh asyncio.run()/aiohttp session per synthesis
# request.
#
# An earlier build "fixed" this by switching the whole process to the
# SelectorEventLoop instead. That turned out to be the wrong fix: it changes
# the actual networking implementation edge-tts's websocket connection runs
# on, and is the likely cause of a narration occasionally coming out
# duplicated (the whole script spoken twice in one render) -- edge-tts has
# an internal retry path for its own connection hiccups, and a different
# event loop backend changes how/when those get triggered.
#
# This does the same silencing without touching the event loop at all: it
# patches the exact method from the traceback above to swallow only that
# specific, harmless teardown error, so the Proactor loop (and edge-tts's
# normal, known-working behaviour on it) is otherwise untouched.
if sys.platform == "win32":
    from asyncio.proactor_events import _ProactorBasePipeTransport

    _orig_call_connection_lost = _ProactorBasePipeTransport._call_connection_lost

    def _call_connection_lost_quiet(self, exc):
        try:
            _orig_call_connection_lost(self, exc)
        except ConnectionResetError:
            pass

    _ProactorBasePipeTransport._call_connection_lost = _call_connection_lost_quiet

try:
    import uvicorn
except ModuleNotFoundError:
    print(
        "\n[ShortGeek] Dependencies aren't installed yet (or the install\n"
        "didn't finish). Run 'run.bat' (Windows) or './run.sh' (macOS/Linux) from\n"
        "this folder instead of running desktop.py directly -- it creates the\n"
        "virtual environment and installs everything needed first.\n"
        "\n"
        "If you already ran run.bat and still see this, re-run it and check the\n"
        "'pip install' output near the top of the window for the real error.\n"
    )
    sys.exit(1)

HOST = "127.0.0.1"
PORT = 4173


def _run_server():
    uvicorn.run("app.main:app", host=HOST, port=PORT, log_level="warning")


def _check_ffmpeg() -> bool:
    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        return True
    print(
        "\n[ShortGeek] ffmpeg wasn't found on your PATH.\n"
        "The app will still open, but rendering will fail until it's installed.\n"
        "Install it with:  winget install ffmpeg\n"
        "...then close and reopen this app (or open a new terminal) so PATH updates.\n"
    )
    return False


def main():
    _check_ffmpeg()
    t = threading.Thread(target=_run_server, daemon=True)
    t.start()

    url = f"http://{HOST}:{PORT}"
    # Give uvicorn a moment to bind before we try to open a window against it.
    time.sleep(1.2)

    try:
        import webview

        # Off by default in pywebview; without it, clicking a download link
        # (e.g. "Download" in the Library) silently does nothing.
        webview.settings["ALLOW_DOWNLOADS"] = True

        webview.create_window("ShortGeek", url, width=1240, height=800, min_size=(980, 640))
        webview.start()
    except Exception as e:
        print(f"[ShortGeek] Couldn't open a native window ({e}); opening in your browser instead.")
        webbrowser.open(url, new=2)
        print(f"[ShortGeek] Running at {url} -- leave this window open while you use it.")
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
