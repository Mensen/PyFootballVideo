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
- Python 3.8+
- [FFmpeg](https://www.gyan.dev/ffmpeg/builds/) on your PATH

**Optional (for specific scripts):**
- OpenCV (`pip install opencv-python`) — for auto-crop
- PySceneDetect (`pip install scenedetect`) — for scene detection

## Usage

### Split a single video

```
python video_splitter.py
```

Follow the menu to select a video and a CSV file with play timing. The CSV needs at minimum:

| Column | Description |
|--------|-------------|
| `Position` | Start time in milliseconds |
| `Duration` | Length in milliseconds |

Optional columns (`Down`, `ODK`, `Play Type`, etc.) are preserved as Dartfish categories.

### Split a GoPro series (multiple files)

For cameras that auto-split recordings into segments (e.g. GoPro's ~5:20 chunks):

```
python video_splitter.py
→ Option 5: Split video series
→ (a) From Dartfish dartclip files
→ Select the folder containing MP4s and .dartclip files
```

Each `.dartclip` file maps to its source video automatically. No concatenation needed — clips are extracted directly from the correct segment.

### Sync a second camera angle

When you have multiple cameras recording the same game:

```
python script_sync_angle.py
→ Select the GoPro folder (with dartclip files)
→ Provide a reference play and its timestamp on camera 2
→ Exports a CSV with all play times mapped to camera 2
```

Then use `video_splitter.py` with the exported CSV to cut camera 2.

### Auto-crop endzone footage

For static camera setups where you want to zoom into the action:

```
python script_autocrop.py
→ Calibrate field boundaries (one-time per camera setup)
→ Select clips folder to process
```

### Other tools

| Script | Purpose |
|--------|---------|
| `script_concatenate_and_import_csv.py` | Combine individual clips into one video |
| `script_recode_keyframes_framerate.py` | Re-encode with Dartfish-optimized keyframes |
| `script_scenedetect.py` | Auto-detect scene boundaries |
| `extract_frames.py` | Extract random frames for analysis |

## Output structure

```
Game Clips/
├── Play_001.mp4
├── Play_001.dartclip
├── Play_002.mp4
├── Play_002.dartclip
└── ...
```

Clip numbering is sequential with zero-padded 3-digit names (`Play_001` through `Play_999`).

## Programmatic usage

```python
from video_splitter import VideoSplitter

# Single file
splitter = VideoSplitter({'split_video': True, 'create_dartclip': True})
splitter.process_video(video_path='game.mp4', csv_path='plays.csv')

# GoPro series from dartclip files
splitter = VideoSplitter({
    'video_series': True,
    'series_input_mode': 'dartclip',
})
splitter.process_video(series_folder='/path/to/DCIM/100GOPRO')

# Sync and split a second angle
from script_sync_angle import build_absolute_timeline, calculate_sync_offset, export_synced_csv, parse_timestamp

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

## Technical details

See [technical_documentation.md](technical_documentation.md) for architecture details, Dartfish format specifications, and development notes.
