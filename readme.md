# Football Video Processing Tools

A collection of Python utilities for processing and analyzing football game footage, with support for converting between different formats used by coaching software such as Dartfish and Hudl.

## Overview

This toolkit was developed to streamline the workflow of coaching staff who need to analyze football game footage. It provides functionality for:

- Splitting large video files into individual play clips based on timing information
- Creating Dartfish-compatible analysis files (.dartclip) that tag plays with metadata
- Converting between different video formats and organizing metadata
- Batch processing of multiple video files
- Extracting frames from videos for further analysis

## Core Components

### Main Classes and Scripts

- **`VideoSplitter`** (video_splitter.py): The primary class for splitting videos and creating dartclip files
- **`script_to_split_video.py`**: Simplified script for basic video splitting operations
- **`script_concatenate_and_import_csv.py`**: Combines multiple clips and creates appropriate timing CSV
- **`script_recode_keyframes_framerate.py`**: Adjusts keyframes and framerate for compatibility
- **`extract_frames.py`**: Extracts frames from videos for image-based analysis

### Utility Modules

- **`pf_helpers.py`**: Common helper functions for file and folder selection
- **`pf_create_dartclip.py`**: Functions for creating Dartfish-compatible files
- **`py_random_functions.py`**: Miscellaneous OpenCV-based video processing utilities

## Installation

### Prerequisites

- Python 3.x
- FFmpeg (external command-line tool)
- Required Python packages:
  ```
  tkinter
  opencv-python (optional, for additional video processing)
  ```

### Setup

1. Clone this repository
2. Ensure FFmpeg is installed and available in your system PATH
3. Install required Python packages:
   ```
   pip install opencv-python
   ```

## Usage

### Video Splitting

```python
# Import the VideoSplitter class
from video_splitter import VideoSplitter

# Create a splitter with default configuration
splitter = VideoSplitter()

# Process a video file
output_folder = splitter.process_video('game_film.mp4', 'play_data.csv')
```

Or use the command-line interface:

```
python video_splitter.py
```

### Creating Dartclip Files for Existing Clips

```python
splitter = VideoSplitter({'split_video': False, 'create_dartclip': True})
count = splitter.process_video(csv_path='play_data.csv', clips_folder='Game Clips')
```

### Customizing the Process

```python
config = {
    'split_video': True,
    'create_dartclip': True,
    'reencode': True,
    'buffer': 1.0,  # Add 1 second buffer to end of each clip
    'skip': 5,      # Skip first 5 plays
    'time_offset': -0.5  # Adjust all timestamps by -0.5 seconds
}
splitter = VideoSplitter(config)
output_folder = splitter.process_video()  # Use interactive selection
```

### Extracting Frames for Analysis

```python
python extract_frames.py
```

## CSV Format

The CSV file should contain timing information and optional metadata for each play:

- **Required columns**: 
  - `Position` (start time in milliseconds)
  - `Duration` (length in milliseconds)
  
- **Optional columns for Dartfish**:
  - `Down` (football down)
  - `ODK` (offense/defense/kickoff)
  - `Play Type` (run, pass, etc.)

Example:
```csv
Name,Position,Duration,Down,ODK,Play Type
play 1,0,5000,1,O,Run
play 2,5000,6200,2,O,Pass
```

## Common Workflows

1. **Full Process** - Split a game film into individual plays and create dartclip files:
   ```
   python video_splitter.py  # Choose option 3
   ```

2. **Convert Existing Clips to Dartfish** - Create dartclip files for pre-existing clips:
   ```
   python video_splitter.py  # Choose option 2
   ```

3. **Batch Process Multiple Videos** - Use script_concatenate_and_import_csv.py to process multiple files.

## Extending the Toolkit

The modular design of this toolkit allows for several extension points:

- Support for additional video formats and codecs
- More sophisticated video processing (e.g., crop, resize, color correction)
- Additional metadata formats beyond Dartfish
- Integration with other analysis tools and platforms
- Development of a graphical user interface

## License

[Your chosen license]

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
