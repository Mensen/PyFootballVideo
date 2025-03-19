# Video Processing Tools: Concept Document

## Overview

This document provides a high-level overview of the video processing tools for sports film analysis. The tools are built in Python and provide functionality for:

1. Splitting larger video files into individual play clips based on timing information
2. Creating Dartfish compatible analysis files (.dartclip) that tag plays with metadata
3. Various utility functions for video file handling and processing

## Core Components

### 1. VideoSplitter Class

The main component is the `VideoSplitter` class, which handles video splitting and dartclip file creation. 

**Key features:**
- Configurable behavior through options dictionary
- Unified interface for all operations
- Proper error handling and logging
- Interactive file selection dialogs

**Configuration options:**
- `split_video`: Whether to split the video into clips
- `create_dartclip`: Whether to create Dartfish compatible files
- `skip`: Number of initial events to skip
- `reencode`: Whether to re-encode video or use stream copying
- `time_offset`: Adjustment to apply to event times (in seconds)
- `buffer`: Extra time to add at end of clips (in seconds)

**Main methods:**
- `extract_events()`: Parse CSV files for timing information
- `split_video()`: Split video files into individual clips
- `create_dartclips_for_folder()`: Create .dartclip files for existing clips
- `process_video()`: Unified interface for all operations

### 2. Helper Modules

#### pf_helpers.py

Contains utility functions for file and folder selection:
- `select_file()`: Opens a file dialog for selecting a file
- `select_folder()`: Opens a dialog for selecting a folder
- `define_paths_breakdown()`: Helper for defining common paths

#### pf_create_dartclip.py

Contains functions for creating Dartfish compatible files:
- `create_dartclip()`: Creates XML files with metadata about plays
- `create_dartclip_v0()`: Legacy version (kept for compatibility)

### 3. Work Processes

The tools support three main workflows:

1. **Split video into clips**
   - Read a CSV file with timing information
   - Split large video file into individual play clips
   - No dartclip files created

2. **Create dartclip files for existing clips**
   - Read a CSV file with play metadata
   - Create .dartclip files for existing video clips
   - No video splitting performed

3. **Combined process**
   - Read a CSV file with timing and metadata
   - Split video into clips
   - Create .dartclip files as clips are created

## File Structure

```
video_splitter.py              # Main class and program entry point
utils/
  ├── pf_helpers.py            # Helper functions for UI and path handling
  ├── pf_create_dartclip.py    # Functions to create Dartfish compatible files
  └── py_random_functions.py   # Additional utilities (OpenCV functions, etc.)
```

## Data Flow

1. CSV file provides timing and metadata for each play
   - Required columns: 'Position' (start time in ms), 'Duration' (length in ms)
   - Optional columns: 'Down', 'ODK', 'Play Type' (used in dartclip files)

2. Video file is processed by FFmpeg
   - Start and duration calculated from CSV
   - Output clips created with standard naming pattern

3. Dartclip files (XML) are created alongside video clips
   - Contain metadata from CSV
   - Have same basename as video clips

## Common Usage Examples

### Example 1: Split video with dartclip files
```python
splitter = VideoSplitter({'split_video': True, 'create_dartclip': True})
output_folder = splitter.process_video('game_film.mp4', 'play_data.csv')
```

### Example 2: Create dartclip files for existing clips
```python
splitter = VideoSplitter({'split_video': False, 'create_dartclip': True})
count = splitter.process_video(csv_path='play_data.csv', clips_folder='Game Clips')
```

### Example 3: Split video with custom configuration
```python
config = {
    'split_video': True,
    'create_dartclip': True,
    'reencode': True,
    'buffer': 1.0,  # Add 1 second buffer to end of each clip
    'skip': 5       # Skip first 5 plays
}
splitter = VideoSplitter(config)
output_folder = splitter.process_video()  # Use interactive selection
```

## Extension Points

The design allows for future enhancements:
- Support for additional video formats and codecs
- More sophisticated video processing (e.g., crop, resize)
- Additional metadata formats beyond Dartfish
- Batch processing of multiple videos
- Potential GUI development

## Dependencies

- Python 3.x
- FFmpeg (external command-line tool)
- External Python packages:
  - tkinter (for UI dialogs)
  - Optional: OpenCV (for additional video processing)
