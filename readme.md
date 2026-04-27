# Football Video Processing Tools

A toolkit for splitting game footage into individual play clips with metadata for coaching analysis software. Works with any video source (GoPro, broadcast, phone) and integrates with Dartfish for tagging and analysis.

## What it does

- **Split video into play clips** from a single file or a GoPro multi-file series
- **Generate Dartfish metadata** (`.dartclip` files) alongside each clip
- **Sync multiple camera angles** so the same plays can be cut from different sources
- **Auto-crop endzone footage** based on motion detection
- **Combine clips** back into a single video with timing metadata

## Getting started (for coaches)

If you've never used a command line before, follow these steps in order. You only need to do this once.

### 1. Download the project

- Go to the project's GitHub page.
- Click the green **Code** button → **Download ZIP**.
- Unzip it somewhere you can find again (e.g. `Documents\PyFootballVideo`).

### 2. Install Python

- Download Python 3.9 or newer from [python.org/downloads](https://www.python.org/downloads/).
- **Windows users:** during install, tick the box "Add Python to PATH" (very important).
- Verify by opening a new terminal (PowerShell on Windows, Terminal on Mac) and running:
  ```
  python --version
  ```
  You should see something like `Python 3.12.0`.

### 3. Install FFmpeg

FFmpeg is a separate program that does the actual video cutting.

- **Windows:** Open PowerShell and run `winget install ffmpeg`. Or download from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) and add the `bin` folder to your PATH.
- **macOS:** Install [Homebrew](https://brew.sh/), then run `brew install ffmpeg`.
- **Linux:** `sudo apt install ffmpeg` (Debian/Ubuntu) or the equivalent for your distro.

Verify by opening a **new** terminal and running:
```
ffmpeg -version
```
You should see version information. If you get "command not found" or "not recognized", FFmpeg is not on your PATH yet.

### 4. Install pyfootball

Open a terminal, navigate into the unzipped project folder, then run:

```
pip install -e .
```

**On Windows**, the easiest way to navigate there: open the folder in File Explorer, click the address bar, type `powershell`, and press Enter.

### 5. Run it

In the same terminal, type:

```
pyfootball
```

A menu will appear. Pick the tool you want.

## Using the tools

All tools are accessed through the same menu. Run `pyfootball` in a terminal and pick an option.

### Split a single video

1. Run `pyfootball` → Option 1: Split video into clips.
2. Pick your CSV file (exported from Dartfish) and your video file.
3. Clips appear in a new folder next to your video.

The CSV needs at minimum two columns:

| Column | Description |
|--------|-------------|
| `Position` | Start time in milliseconds |
| `Duration` | Length in milliseconds |

Other columns from Dartfish (`Down`, `ODK`, `Play Type`, etc.) are kept as tags on the clips.

### Split a GoPro series (multiple files from one game)

GoPro splits long recordings into chapters (`GX01xxxx.MP4`, `GX02xxxx.MP4`, ...). This tool handles them as one continuous game.

1. Run `pyfootball` → Option 1 → Option 5: Split video series.
2. Choose **(a) From Dartfish dartclip files**.
3. Select the folder containing your MP4s and `.dartclip` files.

> Note: Plays that span a chapter boundary will be silently truncated. See
> [docs/cross-chapter-plays.md](docs/cross-chapter-plays.md) for the recipe to
> re-cut them.

### Sync a second camera angle

If you filmed the same game from a second camera (e.g. endzone), this tool maps every play time from the first camera onto the second.

1. Run `pyfootball` → Option 2: Sync camera angle.
2. Select the GoPro folder for the second camera.
3. When prompted, give a reference play (e.g. `Play (1)`) and the timestamp where it actually happens on the second camera.
4. A CSV is exported with all play times mapped to the second camera. Use it with the splitter to cut the second angle.

### Auto-crop endzone footage

If your endzone camera is fixed and the action only fills part of the frame, this crops each clip to the action.

1. Run `pyfootball` → Option 3: Auto-crop clips.
2. Calibrate field boundaries once (you'll be walked through it).
3. Select the clips folder.

### Other tools

The menu also includes: combine clips back into one video, re-encode for Dartfish compatibility, extract random frames, and scene detection.

## Output

Clips are written to a `Game Clips/` folder next to your video, named sequentially:

```
Game Clips/
├── Play_001.mp4
├── Play_001.mp4.dartclip
├── Play_002.mp4
├── Play_002.mp4.dartclip
└── ...
```

Drop the whole folder into Dartfish to load the clips with their tags.

## Using these tools with an AI assistant

You don't need to memorize the menu options or read every section of this readme. A general-purpose AI assistant (ChatGPT, Claude, Gemini, etc.) pairs well with this toolkit — describe your situation in plain English and let the AI figure out which tool fits.

### How to do it

1. Open your AI assistant of choice.
2. Give it access to the project:
   - **Coding assistants with file access** (Claude Code, Gemini CLI, Cursor, etc.) can read this project directly — just point them at the project folder.
   - **Chat-only assistants** (the standard ChatGPT or Claude web app, etc.) — paste this readme into the conversation so the AI knows what the toolkit can do.
3. Describe your situation, for example:
   - *"I have a GoPro recording of a game split across 4 MP4 files, plus a Dartfish export of the plays. I also filmed the endzone on a second GoPro. How do I cut both angles?"*
   - *"My endzone clips have a lot of empty grass on the sides — can I crop them automatically?"*
   - *"I already cut all my clips but Dartfish won't load them — what do I do?"*
4. The AI will point you at the right tool, the right menu options, and the right inputs. If you get stuck on a step, paste the error message back and ask.

### What the AI is good at

- Picking the right tool for your situation.
- Explaining what a setting does before you change it.
- Helping read FFmpeg or Python errors.
- Walking you through unfamiliar steps (e.g. adding FFmpeg to PATH on Windows).

### What to double-check

- AI assistants sometimes invent commands or options that don't exist. If a step doesn't match what you see in the menu, trust the menu.
- Always confirm file paths and folder selections yourself — the AI can't see your filesystem.

## Troubleshooting

- **`pyfootball: command not found`** after install — close and reopen your terminal, or check that Python's Scripts folder is on your PATH.
- **`ffmpeg: command not found`** when running a tool — FFmpeg isn't on your PATH. Re-do step 3.
- **Clips are cut a bit short or long** — adjust the `buffer` setting (extra seconds added to each clip's end). The default is 0.5 seconds.

## For developers

Programmatic usage, configuration options, architecture, and the Dartfish format spec are in [technical_documentation.md](technical_documentation.md).

Run tests with:
```
pytest
```
