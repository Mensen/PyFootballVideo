# PyFootballVideo

## What this project is

A video processing toolkit for splitting game footage into individual play clips, with metadata generation for coaching analysis platforms. Built around FFmpeg for video operations and Dartfish's `.dartclip` XML format for metadata.

The primary use case is football game film: a coach records a game (often with multiple cameras), marks plays in Dartfish, and uses these tools to extract individual clips with metadata preserved.

## Project structure

```
src/pyfootball/          # Installable Python package
  __init__.py            # Exports VideoSplitter, create_dartclip
  splitter.py            # VideoSplitter class — all splitting operations via config dict
  dartclip.py            # Dartfish .dartclip XML generation
  sync_angle.py          # Bidirectional sync between GoPro chapters and continuous cameras
  autocrop.py            # Auto-crop static endzone footage via motion detection (OpenCV)
  concatenate.py         # Reverse workflow: join clips into single video with timing CSV
  recode.py              # Re-encode a full video file with the shared scrub-friendly settings
  encoding.py            # Shared FFmpeg codec args used by every re-encode path
  extract_frames.py      # Extract random frames from videos
  scenedetect.py         # Automated scene boundary detection (PySceneDetect, partial)
  cli.py                 # CLI entry point — interactive menus, all UI/dialog calls live here
  ui/
    __init__.py
    dialogs.py           # Tkinter file/folder selection dialogs

tests/                   # pytest tests for core logic (no video files needed)
examples/                # Reference dartclip/CSV files
pyproject.toml           # Package config, deps, entry points
```

## Architecture: library vs UI separation

Core modules (`splitter.py`, `sync_angle.py`, `autocrop.py`, etc.) are pure library code:
- They accept paths as arguments and never open dialogs or prompt for input
- They never import from `pyfootball.ui`
- They raise `ValueError`/`FileNotFoundError` for missing arguments

All interactive behavior (tkinter dialogs, `input()` prompts, menus) lives exclusively in `cli.py`. This separation means any future GUI can import the library directly.

## Key patterns

### VideoSplitter config pattern
All behavior controlled through a config dict passed to `VideoSplitter(config)`. Key options:
- `split_video`, `create_dartclip` — what operations to perform
- `video_series`, `series_input_mode` — multi-file mode (`'dartclip'`, `'csv_per_file'`, `'csv_absolute'`)
- `reencode` — `False` (default) uses lossless `-c:v copy`; `True` re-encodes with the configured `encoding_preset`. Preset args come from `encoding.ENCODING_PRESETS` via `get_encoding_args()`, shared with `recode.py` and `autocrop.py`. Presets: `all_intra` (every frame a keyframe; biggest/slowest), `short_gop` (default — keyframe every ~0.5s; good scrub/size balance), `standard` (codec default GOP; smallest/fastest). Pass `'encoding_preset': 'name'` in the splitter config; `recode_video()`, `crop_video()`, `process_clips_folder()`, and `autocrop_from_manifest()` take an `encoding_preset=` kwarg. Add new presets to the dict instead of mutating existing ones — old callers may rely on current behavior
- `buffer` — extra seconds at clip end (default 0.5)
- `clip_naming` — `'auto'` (default) for sequential `Play_001`; `'metadata'` for `Play_005_O_Pass` from event data (Name, ODK, Play Type — missing fields become `X`)

### Interrupted-clip protection
`_process_clips` writes `<clip>.incomplete` next to the .mp4 right before invoking FFmpeg and deletes it only on confirmed success. If the process is killed (sleep, OOM, Ctrl+C) mid-encode, the marker survives — so the clip on disk may have valid mdat but no moov atom. The next run calls `_sweep_interrupted_markers(output_folder)` at the top of `_process_clips`, which deletes both the marker and the matching .mp4 so the events loop re-cuts cleanly. Clips outside the current run's event range (e.g. when `skip` is set to resume) are only deleted+warned, not auto-regenerated.

### Event dict format
Events flow as dicts with string values:
```python
{'Position': '17518', 'Duration': '7639', 'Name': 'Play (2)', 'ODK': 'D', ...}
```
Position and Duration are in **milliseconds**.

### Dartclip format
Dartfish uses RefTime units (100ns intervals). Conversion: `milliseconds * 10000 = RefTime`.

### GoPro naming
GoPro files follow `GXnnSSSS.MP4` where `nn` = chapter, `SSSS` = session ID.

### FFmpeg usage
- Always `subprocess` with list args (no `shell=True`)
- `-ss` and `-t` placed before `-i` for fast seeking with stream copy, **except** with concat demuxer where they must go after `-i` for accurate cross-segment seeking
- `_build_ffmpeg_cmd()` centralizes command construction and handles this automatically

### Dartclip file naming
- Dartfish expects `<video>.mp4.dartclip` (not `<video>.dartclip`) — the dartclip filename includes the `.mp4` extension

## Dependencies
- **FFmpeg** (system, on PATH) — required for all video operations
- **Python standard library** — csv, subprocess, xml.etree, logging, tkinter, glob, json
- **OpenCV** (`cv2`) + NumPy — only for `autocrop.py`
- **PySceneDetect** — only for `scenedetect.py`
- **pytest** — dev dependency for tests

## Git commits
- Never add Co-Authored-By or any AI attribution to commit messages

## Running tests
```bash
pytest
```
Tests cover: dartclip XML generation, CSV parsing, FFmpeg command building, file boundary detection, dartclip parsing, timestamp parsing, sync offset calculation, CSV export.
