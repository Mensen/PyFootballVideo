# PyFootballVideo

## What this project is

A video processing toolkit for splitting game footage into individual play clips, with metadata generation for coaching analysis platforms. Built around FFmpeg for video operations and Dartfish's `.dartclip` XML format for metadata.

The primary use case is football game film: a coach records a game (often with multiple cameras), marks plays in Dartfish, and uses these tools to extract individual clips with metadata preserved.

## Key files and their roles

### Core
- `video_splitter.py` — Main entry point. `VideoSplitter` class handles all splitting operations through a config dict. Supports single-file and multi-file (series) modes.
- `script_sync_angle.py` — Maps play times from a GoPro series onto a second camera angle using a single sync point. Outputs a CSV usable by VideoSplitter.
- `script_autocrop.py` — Auto-crops static endzone camera footage based on motion detection. Uses OpenCV for analysis, FFmpeg for cropping.

### Utilities
- `utils/pf_helpers.py` — Tkinter file/folder selection dialogs (`select_file`, `select_folder`, `select_files`).
- `utils/pf_create_dartclip.py` — Generates Dartfish `.dartclip` XML files from event dicts. `create_dartclip(event, output_name)` is the main function.

### Secondary scripts
- `script_concatenate_and_import_csv.py` — Reverse workflow: concatenate clips into a single video, generate timing CSV.
- `script_recode_keyframes_framerate.py` — Re-encode video with keyframe interval optimized for Dartfish (keyint=15).
- `script_scenedetect.py` — Automated scene boundary detection using PySceneDetect. Partially complete.
- `extract_frames.py` — Extract random frames from videos for analysis/training data.

### Legacy/test (can be ignored)
- `dfclip_test.py` — Old dartclip creation test file.
- `script_video_time_and_duration.py` — Stub, barely implemented.
- `utils/py_random_functions.py` — Incomplete OpenCV utilities.

## Patterns and conventions

### VideoSplitter config pattern
All behavior is controlled through a config dict passed to `VideoSplitter(config)`. Defaults are sensible — only override what you need. Key options:
- `split_video`, `create_dartclip` — what operations to perform
- `video_series`, `series_input_mode` — multi-file mode (`'dartclip'`, `'csv_per_file'`, `'csv_absolute'`)
- `reencode` — `False` (default) uses lossless `-c:v copy`; `True` re-encodes to H.264
- `buffer` — extra seconds at clip end (default 0.5)
- `time_offset`, `skip`, `start_number` — timing and numbering adjustments

### Event dict format
Events flow through the system as dicts with string values (matching CSV DictReader output):
```python
{'Position': '17518', 'Duration': '7639', 'Name': 'Play (2)', 'ODK': 'D', ...}
```
Position and Duration are always in **milliseconds**. All columns beyond Position/Duration are preserved and passed to dartclip generation as categories.

### Dartclip format
Dartfish uses RefTime units (100-nanosecond intervals). Conversion: `milliseconds * 10000 = RefTime`. The `.dartclip` XML structure wraps `LIBRARY_ITEM` elements with `Marker.Event` items containing `IN`/`OUT` attributes and `CATEGORY` elements.

### GoPro naming
GoPro files follow `GXnnSSSS.MP4` where `nn` = chapter (segment number) and `SSSS` = session ID. All segments of one recording share the same session ID. Dartclip files sit alongside as `GXnnSSSS.MP4.dartclip`.

### FFmpeg usage
- Always use subprocess with list args (no shell=True)
- `-ss` and `-t` are placed **before** `-i` for fast seeking with stream copy
- The `_build_ffmpeg_cmd()` method centralizes command construction
- Input args are parameterized: `["-i", path]` for single file, `["-f", "concat", "-safe", "0", "-i", filelist]` for concat demuxer

## Dependencies
- **FFmpeg** (system-wide, must be on PATH) — required for all video operations
- **Python standard library** — csv, subprocess, xml.etree, logging, tkinter, glob, json
- **OpenCV** (`cv2`) — only for script_autocrop.py and py_random_functions.py
- **NumPy** — only for script_autocrop.py and script_scenedetect.py
- **PySceneDetect** (`scenedetect`) — only for script_scenedetect.py
