"""Build packaging/shortgeek.ico from the app icon.

Called by the build workflow. If there is no source icon in the repo this is a
no-op rather than an error, so the build still produces a working (if plain)
executable.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def main() -> int:
    for name in ("icons/shortgeek.png", "icons/reelgeek.png", "assets/icon.png"):
        src = ROOT / name
        if src.exists():
            break
    else:
        print("No source icon found; skipping icon build.")
        return 0

    try:
        from PIL import Image
    except ImportError:
        print("Pillow not available; skipping icon build.")
        return 0

    out = ROOT / "packaging" / "shortgeek.ico"
    img = Image.open(src).convert("RGBA")
    img.save(out, format="ICO", sizes=SIZES)
    print(f"Wrote {out} from {src.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
