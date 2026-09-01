"""Version and changelog shown on the About page.

APP_VERSION is compared against the newest GitHub release when the user presses
Check for updates, so it must match the release tag. The GitHub Actions workflow
fails the build if it does not.

The app was called Shorts Studio up to 1.12.0 and was never released publicly.
Version numbering restarts at 1.0.0 for the first public ShortGeek release; the
older entries are kept below because the fixes in them are real."""

APP_VERSION = "1.0.2"

# Shown on the About page. Kept here so there is one place to change it if the
# licence ever changes.
APP_LICENCE = "Freeware"

CHANGELOG = [
    {
        "version": "1.0.2",
        "notes": [
            "Fixed the app failing to start with \"Unable to configure formatter 'default'\". A windowed app has no console, so it starts with nowhere to write; the web server tried to ask that nowhere whether it was a terminal and fell over. It now writes to a log file in your profile instead.",
            "The build check now runs the packaged app with its output taken away, which is the shape you actually get. The 1.0.1 check redirected the output to a file and hid this exact fault.",
        ],
    },
    {
        "version": "1.0.1",
        "notes": [
            "Fixed the app opening on a page saying the connection was refused. The build was leaving out the code that serves the screens, so there was nothing there to open. Nothing was wrong with your machine.",
            "If the app ever fails to start again it now says so, in a window, and writes the details to a file you can send in, instead of leaving the browser to report a refused connection.",
            "Added the application icon, which the 1.0.0 build shipped without.",
            "The build now starts the packaged app and asks it for a page before an installer is made, which is the check that would have caught all of this.",
        ],
    },
    {
        "version": "1.0.0",
        "notes": [
            "First public release, as ShortGeek. Same app, new name, and it now looks like the rest of the TechyGeeksHome range.",
            "Added a first-run setup that asks for your own name, handle and logo letters. Previously the app shipped with TechyGeeksHome's branding baked into the defaults, which meant anyone who installed it produced videos branded as somebody else.",
            "Added Check for updates and a Support panel to the sidebar, and rebuilt the About page to state plainly what the app will not do.",
            "Packaged as a Windows installer with Python and ffmpeg bundled. There is nothing to install first: no Python, no PATH ticking, no winget commands.",
        ],
    },
    {
        "version": "1.12.0 (pre-release, as Shorts Studio)",
        "notes": [
            "Added an explicit \"🧹 Clear\" button at the top of New Short, so you can queue up several videos back to back without waiting for each one to finish rendering or closing/reopening the app in between -- draft, hit Generate, hit Clear, draft the next one. Shows a quick \"Cleared ✓\" confirmation so it's obvious it worked. The queue panel itself is untouched by it, so everything you've got rendering or finished stays visible.",
        ],
    },
    {
        "version": "1.11.0",
        "notes": [
            "The app's own JS/CSS files are now loaded with a cache-busting version tag. If a fix ever seemed to \"not apply\" after unzipping a new build over an old one, this was very likely why -- the app window can hold onto the previous version's app.js in memory/cache rather than picking up the new one. Close the app fully and reopen it after unzipping an update to be sure you're on the new build.",
            "Fixed: clicking \"New Short\" while already on that screen (the normal case right after finishing a render) did nothing, because there was no view to switch to. It now always clears the script draft and source fields back to blank, whether or not the screen itself changes.",
        ],
    },
    {
        "version": "1.10.0",
        "notes": [
            "Fixed the real cause of the \"whole video plays twice\" bug: the Paste Script tab, not the voice engine. When pasted text had no actual line breaks (a normal paragraph, sentences separated by periods), it was used as BOTH the hook and the entire beat text -- so the script got spoken once with no card (as the hook), then again inside one giant card (as \"beat 1\"). It now splits a plain paragraph into sentences (same as Topic Prompt already did), so you get a real hook + separate beats. Also gives Paste Script a generic call-to-action, which it was previously missing entirely. (1.8.0's event-loop fix is left in place -- it's a real, unrelated fix -- but it was not the cause of this.)",
        ],
    },
    {
        "version": "1.9.0",
        "notes": [
            "Removed run_silently.vbs -- it needed elevation on some setups, which a .vbs file can't prompt for cleanly. Back to run.bat as the one and only way to start the app.",
        ],
    },
    {
        "version": "1.8.0",
        "notes": [
            "Fixed a regression from 1.6.0's console-noise fix that could cause the narration to come out duplicated (the whole script spoken twice in one render). The 1.6.0 fix worked by switching Windows to a different underlying network event loop; that turned out to occasionally confuse the free Edge voice's own retry logic. Replaced it with a narrower fix that silences the same console message without changing any networking behaviour.",
        ],
    },
    {
        "version": "1.7.0",
        "notes": [
            "Added run_silently.vbs -- an alternative to run.bat that opens the app with no visible console/cmd window (run.bat itself is unchanged, and is still needed once up front for the first-time setup).",
        ],
    },
    {
        "version": "1.6.0",
        "notes": [
            "Call-to-action lines are now generic (\"Follow for more\", etc.) instead of referencing a brand handle -- picked from a small rotating pool per video, so a run of videos doesn't all end on the identical line.",
            "Your own background video clips now start from a random point in the clip on every render (not always frame 0), so reusing the same clip across multiple videos no longer produces what looks like duplicate footage. When the clip is longer than the video needs, the random start point is chosen so the whole render plays out with no looping/wraparound.",
            "Fixed: a harmless but noisy 'ConnectionResetError [WinError 10054]' traceback could print to the console window on Windows during normal use (a known Windows asyncio quirk triggered by the free Edge voice). It no longer appears.",
        ],
    },
    {
        "version": "1.5.0",
        "notes": [
            "Fixed: Topic Prompt just echoed your whole prompt back as the hook and one throwaway beat, no matter what you typed. It now treats each sentence you write as its own beat, so a well-written multi-sentence prompt produces a real hook + multi-beat script -- without inventing any content that isn't in what you typed.",
        ],
    },
    {
        "version": "1.4.0",
        "notes": [
            "Fixed: your own background video clips could be clicked but never actually got selected (highlight/selection wasn't wired up for that section).",
            "Added a Backgrounds page: open your clips folder in one click, or upload an .mp4 straight from the app -- no more finding the folder yourself.",
            "Added this About page.",
        ],
    },
    {
        "version": "1.3.0",
        "notes": [
            "New default background: Article Images -- the guide's own real screenshots, panned slowly full-bleed behind each card.",
            "Fixed caption drift in the offline eSpeak voice on longer scripts (each part is now timed against its own real measured audio instead of one whole-script estimate).",
        ],
    },
    {
        "version": "1.2.0",
        "notes": [
            "Dropped screenshot cards -- illegible at 9:16 phone size no matter how they were sized -- in favour of consistent, always-legible code/text cards.",
            "Added three procedurally-animated backgrounds: Code Rain, Bounce Orbit, Sort Visualizer.",
            "Added support for your own background video clips (assets/backgrounds/custom/).",
            "Fixed: the render queue panel now stays visible while scrolling, and Generate jumps back to it.",
            "Fixed: the Download button in the Library did nothing (pywebview blocks downloads unless explicitly enabled).",
        ],
    },
    {
        "version": "1.1.0",
        "notes": [
            "Fixed the Windows install failing on Python 3.14 (lxml/Pillow had no prebuilt wheels for it yet).",
            "Fixed the free Edge voice failing with a 403 (edge-tts needed a version bump to match Microsoft's current endpoint).",
        ],
    },
    {
        "version": "1.0.0 (pre-release, as Shorts Studio)",
        "notes": ["Initial build."],
    },
]
