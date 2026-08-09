<div align="center">

# Shorts Studio

**Turns a source — one of your own guides, any RSS feed/URL, or a bare topic prompt — into a finished vertical short: narrated, captioned, and built from real code/commands and legible text cards.**

[![Version](https://img.shields.io/badge/version-1.12.0-4c9bff)](https://github.com/techygeekshome/Shorts-Studio/releases)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-0078d4)](#%EF%B8%8F-quick-start)
[![License](https://img.shields.io/badge/license-proprietary%20freeware-b7791f)](LICENSE)
[![Made by TechyGeeksHome](https://img.shields.io/badge/made%20by-TechyGeeksHome-b191f2)](https://techygeekshome.info)

[Quick start](#%EF%B8%8F-quick-start) · [Samples](#-samples) · [How it works](#-how-it-works) · [Settings](#settings) · [License](#-license)

</div>

---

Turns a source (one of your own guides, any RSS feed/URL, or a bare topic prompt) into a finished vertical short: narrated, captioned, built from real code/commands and legible text cards over the guide's own real screenshots (panned, full-bleed) or another genuinely animated background — never AI-generated imagery.

This replaces the old Reddit Video Maker Bot. It keeps the one thing that tool got right (compositing images onto a background with ffmpeg) and drops everything that made it fragile or off-brief: the Reddit login/scraping, the hardcoded selectors, the missing captions, and the reddit-only content model.

## 🎬 Samples

Two sample videos are included in `samples/` — both rendered end-to-end from real techygeekshome.info guides, so you can see exactly what the pipeline produces before running it yourself:

- [`sample-1-code-task-scheduler-sort-visualizer.mp4`](samples/sample-1-code-task-scheduler-sort-visualizer.mp4) — the Sort Visualizer procedural background
- [`sample-2-diskgeek-article-images.mp4`](samples/sample-2-diskgeek-article-images.mp4) — the default Article Images background (the guide's own real screenshots, panned)

## ⬇️ Quick start

**Windows**
1. Install Python if you don't already have it (tick "Add python.exe to PATH" during install). Any modern Python 3 version works — `run.bat` no longer requires a specific one.
2. Install ffmpeg: open PowerShell and run `winget install ffmpeg`, then close and reopen any terminal so PATH picks it up.
3. Optional but recommended: `winget install eSpeak-NG.eSpeak-NG` — this is the offline backup voice, used automatically if Microsoft's free Edge voice endpoint is ever unreachable (see "Voice" below).
4. Double-click `run.bat`. The first run creates a virtual environment and installs dependencies (takes a minute or two); after that it starts instantly.

The app opens in its own window. If a native window can't open for any reason, it falls back to opening in your default browser at http://127.0.0.1:4173.

**macOS/Linux:** run `./run.sh` instead (install ffmpeg via `brew install ffmpeg` or your package manager first).

### Using your own Anthropic (Claude) API key for the polish pass

By default, scripts are written entirely by the built-in heuristic writer — no API key, no external calls. If you'd like Claude to lightly reword the lines (same facts, same structure, just more spoken-sounding), add your own key:

1. Go to [console.anthropic.com](https://console.anthropic.com), sign in or create an account, and open API Keys (left sidebar) → Create Key. Note: this is a separate account/billing setup from a claude.ai subscription — API usage is billed per token, typically fractions of a cent per script here.
2. Copy the key (starts with `sk-ant-`).
3. In the app, open Settings, set LLM Provider to Anthropic (Claude), and paste the key into the API Key field. It's saved locally in `data/config.json` and only ever sent to Anthropic's API.

Every script drafted from then on runs through the polish pass automatically. Nothing about which sentences/images are chosen changes — only the wording.

## ✨ How it works

1. **Pick a source.** "My Guides" searches techygeekshome.info directly via WordPress's public API — no login, nothing scraped. "Website / RSS" accepts any RSS feed URL or a plain article URL, using a best-effort text+image extractor (quality varies more site to site than the WordPress adapter, since it doesn't have a clean structured API to work with). "Topic Prompt" skips a source entirely and drafts from a one-line idea.

2. **Script.** A heuristic writer condenses the source into a hook + 2-4 beats + a call-to-action, preferring steps paired with a real code/command block (these render as legible code cards) or a real image (a good signal of a concrete, well-described step, even though the image itself isn't shown) over plain prose. Nothing is invented — every claim comes from the source text. If you add an Anthropic or OpenAI key in Settings, an optional polish pass rewords the lines to sound more spoken without changing what they say. Everything is editable before you render.

3. **Voice.** Defaults to Microsoft Edge's free neural TTS (no signup). If it's ever unreachable, the app automatically falls back to the offline eSpeak NG voice rather than failing the render — you'll see a note in the render queue if that happened. The offline fallback only works if eSpeak NG is installed (see Quick start above). It's optional — skip it if you're fine with the render simply failing on the rare occasion Edge's endpoint is unreachable — but installing it costs nothing and means a render never hard-fails for that reason. ElevenLabs is available if you add your own API key and voice ID in Settings.

4. **Visuals.** Every beat becomes a "card": real code/commands (styled like an editor, with light keyword colouring), or a bold numbered text callout. Screenshots were dropped from this — a full desktop-scale UI capture never reads on a 9:16 clip at phone-viewing distance no matter how it's sized, so consistent, always-legible text/code cards replaced them entirely. Every card gets a subtle Ken-Burns zoom/pan instead of sitting static.

   Backgrounds have four flavours, all pickable in step 3:
   - **Article Images** (default) — the guide's own real screenshots, slowly panned full-bleed behind each card, one image per beat (falling back to a generated look for any beat with no image of its own, and for the hook/CTA). This is real content specific to that guide, not a generic loop.
   - **Procedural stills** — gradients, a terminal-scroll look, a typing-loop look, a clean-light look — panned/zoomed in code.
   - **Procedural motion** — genuinely animated loops rendered frame-by-frame (not just a pan on a still): Code Rain, Bounce Orbit, and Sort Visualizer (a real bubble sort running live on a bar chart) — for when you want something eye-catching but unrelated to the guide's own images, with zero footage-hunting or licensing risk.
   - **Your own clips** — drop `.mp4` loops into `assets/backgrounds/custom/` and they show up automatically in step 3. Any aspect ratio works — it's cropped to fill the frame, not stretched. This is the slot for gameplay footage — record it yourself, or source footage explicitly licensed for creator reuse. None of this is AI-generated or someone else's content passed off as yours.

5. **Captions.** Word-level timing comes straight from the TTS engine (Edge gives real per-word timestamps; eSpeak/ElevenLabs fall back to a proportional-by-length estimate). Burned in as styled subtitles — Bold Highlight (word-by-word colour pop), Minimal, or Classic Subtitle.

6. **Render.** ffmpeg composites background + cards + captions + your watermark + narration into a 1080×1920 mp4, saved to `data/library/`. The queue panel shows live progress; finished videos show up in the Library tab with a preview player and a download link.

## Settings

Everything is stored in `data/config.json`, created on first run (and excluded from this repo via `.gitignore`, since it's local machine state rather than source). Nothing is ever sent anywhere except to a service you've explicitly given a key for, and only when you use that feature. There's no telemetry, no account.

- **Brand** — your site URL (used for "My Guides"), the handle shown in the watermark/CTA line, and the watermark's logo letters.
- **Voices** — which Edge voice to use by default, and optional ElevenLabs credentials.
- **Script AI polish** — optional; leave the provider as "None" and everything still works with zero API keys.

## 🚀 What's next

Not built yet, but the architecture leaves room:

- Add an official Anthropic/OpenAI Python SDK integration instead of raw `requests` calls, if you end up leaning on the AI-polish step heavily.
- More procedural motion background styles alongside Code Rain, Bounce Orbit and Sort Visualizer, if those three aren't enough variety.
- Auto-generated thumbnails/preview scrubbing for the video player in the Library tab.
- Square (1:1) and landscape (16:9) export alongside the default 9:16, for platforms/placements that want them.
- Direct-upload APIs (YouTube/TikTok/Instagram) — deliberately left out for now, same reasoning the old tool had: those APIs are locked down, quota-limited, and change often. Exporting a finished file you upload yourself sidesteps all of that.

## 🛠️ Troubleshooting

- **"ffmpeg wasn't found"** — install it (`winget install ffmpeg`) and open a fresh terminal so PATH updates, then re-run `run.bat`.
- **Dependency install fails / a package fails to build from source** — this usually means pip picked a package version with no ready-made Windows wheel for your Python version. First try upgrading pip itself (`.venv\Scripts\python.exe -m pip install --upgrade pip`) and re-running `run.bat`. If it still fails, note which package failed in the pip output and bump that one pin in `requirements.txt` to a newer release.
- **`ModuleNotFoundError` when starting** — this means the dependency install didn't actually finish (check the terminal window for a pip error above it). Always launch via `run.bat` / `run.sh`, not `python desktop.py` directly, so the checks above run first.
- **A render fails immediately** — check the render queue's message text first; ffmpeg errors are also printed to the terminal window `run.bat` opened.
- **Edge voice sounds robotic, or you see "eSpeak NG isn't installed"** — the app tried the free Edge voice first and it failed (a 403 in the terminal is normal here — Microsoft's endpoint is unofficial and occasionally rejects requests, unrelated to your setup), so it tried to fall back to the offline eSpeak NG voice, which isn't installed. Run `winget install eSpeak-NG.eSpeak-NG` in PowerShell, reopen your terminal, and re-render — you'll always have a working fallback from then on, even on renders where Edge fails. If Edge keeps failing repeatedly rather than occasionally, configure ElevenLabs in Settings for a premium voice that doesn't depend on it at all.
- **The video looks text/code-card heavy with no screenshots** — that's by design, not a bug: real screenshots never stayed legible at 9:16 phone size, so every beat renders as a code or bold-text card instead of faking (or shrinking) a screenshot. If it still feels flat, try one of the Code Rain / Bounce Orbit / Sort Visualizer backgrounds, or drop your own clips into `assets/backgrounds/custom/`.

## Fonts

Roboto (Apache License 2.0) is reused from the old project's `fonts/` folder — see `assets/fonts/LICENSE.txt`. DejaVu Sans Mono (bundled with most Linux distros, permissively licensed) is used for code cards.

## 🐛 Support & contributing

Found a bug or have a request? [Open an issue](https://github.com/techygeekshome/Shorts-Studio/issues).

## 📄 License

Shorts Studio is free to download and use. This is proprietary freeware, not open source — see [LICENSE](LICENSE) for the full terms.

© 2026 TechyGeeksHome | Andrew Armstrong.

---

<div align="center">

Made with ❤️ by [**TechyGeeksHome**](https://techygeekshome.info)

[Website](https://techygeekshome.info) · [YouTube](https://www.youtube.com/channel/UCtEuFj1SMLiuRoucD1hv8dA) · [X](https://x.com/TechyGeeks1) · [Facebook](https://www.facebook.com/techygeeks.home) · [Instagram](https://www.instagram.com/techygeekshome/)

</div>
