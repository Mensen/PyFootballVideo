# Football Video Processing Tools

A toolkit for splitting game footage into individual play clips with metadata for coaching analysis software. Works with any video source (GoPro, broadcast, phone) and integrates with Dartfish for tagging and analysis.

## What it does

- **Split video into play clips** from a single file or a GoPro multi-file series
- **Generate Dartfish metadata** (`.dartclip` files) alongside each clip
- **Sync multiple camera angles** so the same plays can be cut from different sources
- **Auto-crop endzone footage** based on motion detection
- **Combine clips** back into a single video with timing metadata

## Setup

**Requirements:**
- Python 3.9+
- [FFmpeg](https://www.gyan.dev/ffmpeg/builds/) on your PATH

**Install:**
```bash
pip install -e .
```

**Optional extras:**
```bash
pip install -e ".[autocrop]"      # OpenCV for auto-crop
pip install -e ".[scenedetect]"   # PySceneDetect for scene detection
pip install -e ".[dev]"           # pytest for running tests
```

## Usage

### CLI

After installing, run the unified CLI:

```bash
pyfootball
```

This presents a menu to select any tool (splitter, sync, autocrop, etc.).

### Split a single video

```bash
pyfootball
→ Option 1: Split video into clips
→ Select CSV file and video file
```

The CSV needs at minimum:

| Column | Description |
|--------|-------------|
| `Position` | Start time in milliseconds |
| `Duration` | Length in milliseconds |

Optional columns (`Down`, `ODK`, `Play Type`, etc.) are preserved as Dartfish categories.

### Split a GoPro series (multiple files)

```bash
pyfootball
→ Option 1 → Option 5: Split video series
→ (a) From Dartfish dartclip files
→ Select the folder containing MP4s and .dartclip files
```

> Plays that span a chapter boundary will be silently truncated in `dartclip`
> mode. See [docs/cross-chapter-plays.md](docs/cross-chapter-plays.md) for the
> recipe to re-cut them.

### Sync a second camera angle

```bash
pyfootball
→ Option 2: Sync camera angle
→ Select GoPro folder, provide a reference play and timestamp on camera 2
→ Exports a CSV with all play times mapped to camera 2
```

### Auto-crop endzone footage

```bash
pyfootball
→ Option 3: Auto-crop clips
→ Calibrate field boundaries (one-time), then select clips folder
```

## Programmatic usage

```python
from pyfootball import VideoSplitter

# Single file
splitter = VideoSplitter({'split_video': True, 'create_dartclip': True})
splitter.process_video(
    video_path='game.mp4',
    csv_path='plays.csv',
    output_folder='./output'
)

# GoPro series from dartclip files
splitter = VideoSplitter({
    'video_series': True,
    'series_input_mode': 'dartclip',
})
splitter.process_video(series_folder='/path/to/DCIM/100GOPRO')

# Sync and split a second angle
from pyfootball.sync_angle import (
    build_absolute_timeline, calculate_sync_offset,
    export_synced_csv, parse_timestamp
)

events = build_absolute_timeline('/path/to/DCIM/100GOPRO')
offset = calculate_sync_offset(events, 'Play (1)', parse_timestamp('4:41.22'))
export_synced_csv(events, offset, 'camera2_times.csv')
```

## Configuration options

| Option | Default | Description |
|--------|---------|-------------|
| `split_video` | `True` | Extract video clips |
| `create_dartclip` | `True` | Generate .dartclip metadata files |
| `reencode` | `False` | `False` = lossless stream copy (fast), `True` = H.264 re-encode |
| `buffer` | `0.5` | Extra seconds added to each clip's end |
| `time_offset` | `0` | Global offset applied to all start times (seconds) |
| `skip` | `0` | Number of initial events to skip |
| `start_number` | `1` | Starting number for clip filenames |
| `video_series` | `False` | Enable multi-file series mode |
| `series_input_mode` | `'dartclip'` | `'dartclip'`, `'csv_per_file'`, or `'csv_absolute'` |

## Output structure

```
Game Clips/
├── Play_001.mp4
├── Play_001.dartclip
├── Play_002.mp4
├── Play_002.dartclip
└── ...
```

## Running tests

```bash
pytest
```

## Technical details

See [technical_documentation.md](technical_documentation.md) for architecture details, Dartfish format specifications, and development notes.
