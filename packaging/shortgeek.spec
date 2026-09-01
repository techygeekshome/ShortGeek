# -*- mode: python ; coding: utf-8 -*-
"""One-folder PyInstaller build for ShortGeek.

One-folder rather than one-file on purpose: a one-file build unpacks itself to a
temp folder on every launch, which is slow with a payload this size and is a
well-known trigger for antivirus heuristics. This range is already unsigned, so
there is no sense in adding a second reason to be flagged.
"""
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).parent

datas = [
    (str(ROOT / "app" / "templates"), "app/templates"),
    (str(ROOT / "app" / "static"), "app/static"),
    (str(ROOT / "assets" / "fonts"), "assets/fonts"),
]

# ffmpeg and ffprobe are fetched by the workflow and travel with the app.
for exe in ("ffmpeg.exe", "ffprobe.exe"):
    p = ROOT / "ffmpeg" / exe
    if p.exists():
        datas.append((str(p), "ffmpeg"))

# The stock background clips in assets/backgrounds/custom are NOT bundled.
# They are third-party stock footage; redistributing them inside an installer
# is not something the stock licences allow. The app creates an empty custom
# folder under the user's own data directory and they add their own clips.

datas += collect_data_files("edge_tts")

hiddenimports = (
    collect_submodules("uvicorn")
    + collect_submodules("app")
    + [
        "anyio",
        "h11",
        "starlette",
        "fastapi",
        "jinja2",
        "edge_tts",
        "lxml",
        "lxml._elementpath",
        "PIL",
        "PIL._tkinter_finder",
    ]
)

a = Analysis(
    [str(ROOT / "packaged.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "unittest", "pydoc_data", "test", "matplotlib", "numpy.testing"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ShortGeek",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(ROOT / "packaging" / "shortgeek.ico") if (ROOT / "packaging" / "shortgeek.ico").exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="ShortGeek",
)
