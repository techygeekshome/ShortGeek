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
import traceback
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


def _show_startup_failure(failure: list[str]) -> None:
    """Say what went wrong, in the window, instead of leaving the browser to report a
    refused connection. A crash report the user can read and send is worth more than a
    silent thread and an error page about proxies and firewalls."""
    detail = failure[0] if failure else "The server did not start and gave no reason."
    log = _crash_log_path()
    try:
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(detail, encoding="utf-8")
    except Exception:
        pass

    body = (
        "ShortGeek could not start.\n\n"
        "The part of the app that serves its screens failed to load, so there is "
        "nothing to show. This is a fault in the build rather than anything you did.\n\n"
        f"The details have been written to:\n{log}\n\n"
        "Please report it at github.com/techygeekshome/ShortGeek/issues and attach "
        "that file.\n\n"
        "-----\n\n" + detail
    )

    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, body, f"{APP_NAME} could not start", 0x10)
            return
        except Exception:
            pass
    print(body, file=sys.stderr)


def _crash_log_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_DATA_HOME")
    root = Path(base) if base else Path.home() / ".local" / "share"
    return root / "TechyGeeksHome" / APP_NAME / "startup-error.txt"


def main() -> int:
    _silence_console_windows()
    _silence_proactor_reset()
    _add_bundled_ffmpeg_to_path()

    import uvicorn

    port = _free_port()
    url = f"http://127.0.0.1:{port}"

    # The application object is imported here and handed to uvicorn directly, rather
    # than passing it the string "app.main:app". Uvicorn resolves a string by importing
    # it itself, and when that import fails inside a frozen build it prints one line to
    # a console nobody is looking at and the thread dies. The window then opens on a
    # browser page saying the connection was refused, which says nothing about what
    # actually went wrong. Importing here means a failure lands in the block below.
    failure: list[str] = []
    try:
        from app.main import app as asgi_app
    except Exception:
        failure.append(traceback.format_exc())
        asgi_app = None

    def _serve():
        try:
            uvicorn.run(asgi_app, host="127.0.0.1", port=port, log_level="warning")
        except Exception:
            failure.append(traceback.format_exc())

    if asgi_app is not None:
        thread = threading.Thread(target=_serve, daemon=True)
        thread.start()
    else:
        thread = None

    # Wait for the server to actually accept a connection rather than guessing.
    started = False
    for _ in range(200):
        if failure:
            break
        with socket.socket() as s:
            s.settimeout(0.1)
            try:
                s.connect(("127.0.0.1", port))
                started = True
                break
            except OSError:
                time.sleep(0.05)

    if not started:
        _show_startup_failure(failure)
        return 1

    # Used by the build check, which runs this executable on a machine with no desktop
    # and asks it for a page. It is the only way to find out whether the thing that was
    # packaged actually serves anything, which is the question a normal test cannot
    # answer and the one that matters.
    if os.environ.get("SHORTGEEK_NO_WINDOW"):
        print(url, flush=True)
        if thread is not None:
            thread.join()
        return 0

    try:
        import webview
    except Exception:
        webbrowser.open(url, new=2)
        if thread is not None:
            thread.join()
        return 0

    webview.settings["ALLOW_DOWNLOADS"] = True
    webview.create_window(APP_NAME, url, width=1240, height=860, min_size=(980, 640))
    webview.start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
