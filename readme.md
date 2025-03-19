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

## Collaborative Analysis Workflow

The tools in this toolkit support a collaborative coaching workflow that leverages the strengths of both platforms:

1. **Initial Film Collection and Basic Breakdown in Hudl**:
   - Game footage is uploaded to Hudl where multiple coaches can simultaneously access it
   - Basic tagging and categorization happens quickly in Hudl's intuitive interface
   - All staff members have immediate access to this initial breakdown
   - The cloud-based approach facilitates rapid collaboration across the coaching staff

2. **Enhanced Analysis in Dartfish**:
   - For more sophisticated analysis, selected content is moved to Dartfish
   - Dartfish provides richer analysis capabilities for detailed technical breakdowns
   - This toolkit helps maintain metadata when moving between platforms
   - Coaches can add additional markers, annotations, and analysis in Dartfish

3. **Coaching Material Creation**:
   - Dartfish can be used to create enhanced clips with:
     - Text overlays highlighting specific elements
     - Visual markers for player positioning and movement
     - Synchronized multiple angles for comprehensive view
   - These enhanced clips can be used for team and individual player instruction

4. **Integrated Workflow**:
   - Initial quick breakdowns happen in Hudl where collaboration is easiest
   - Deeper analysis occurs in Dartfish where the tools are more powerful
   - The toolkit ensures that no metadata or analysis is lost when moving between systems

This combined approach allows coaches to use each platform for its strengths: Hudl for speed, simplicity, and collaboration; Dartfish for depth, detail, and advanced visual analysis.

## Technical Details

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

## Understanding Video Analysis Platforms

### Dartfish
Dartfish stores metadata about football games through .dartclip files, which are XML files that accompany the video content. These files are crucial for the analysis workflow:

- Each video file has an associated .dartclip file with the same base name
- The .dartclip files contain metadata about events (plays) in the video
- For individual play clips, typically only a single event is defined in the dartclip
- For full game footage, a single dartclip file can contain hundreds of events representing individual plays

The XML structure of a dartclip file includes:
- Basic video identification
- Timing information (IN and OUT points)
- Categories with football-specific metadata (Down, ODK, Play Type)
- Color coding for visual organization in Dartfish

When Dartfish opens a video file, it automatically looks for the associated .dartclip file to load the metadata and event markers.

### Hudl
Hudl takes a different approach as an online software platform:

- Plays are saved as individual video files rather than markers in a larger file
- Related plays are grouped into playlists (typically representing a game)
- Metadata is stored in Hudl's online database rather than in local files
- Users can export both video clips and accompanying Excel files with metadata

**Hudl Advantages:**
- Cloud-based platform provides immediate sharing with all team members
- Simpler, more intuitive interface for basic game breakdown
- Efficient workflow for quickly tagging and categorizing plays
- Real-time collaboration where multiple coaches can work simultaneously
- More accessible for coaches with limited technical expertise

These differences in approach between Dartfish and Hudl create complementary strengths - Hudl excels at quick, collaborative basic analysis, while Dartfish offers more powerful advanced analysis tools. This toolkit helps bridge these platforms to leverage the benefits of both.

## CSV Format

The CSV file should contain timing information and optional metadata for each play. When working with Hudl exports, you might need to convert their Excel format to match this structure:

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

### 1. Preparing Game Footage for Analysis

When starting with a complete game video file:

1. **Split into Individual Plays with Metadata** 
   ```
   python video_splitter.py  # Choose option 3
   ```
   This process:
   - Reads timing information from a CSV file
   - Splits the large video file into individual play clips
   - Creates a .dartclip file for each clip with appropriate metadata
   - Results in a folder of plays ready for Dartfish analysis

2. **Convert Existing Clips to Dartfish Format** 
   ```
   python video_splitter.py  # Choose option 2
   ```
   When you already have individual play clips (perhaps exported from Hudl):
   - Reads metadata from a CSV file (which could be converted from Hudl's Excel export)
   - Creates corresponding .dartclip files for each existing video clip
   - Preserves the original video files
   - Makes the clips compatible with Dartfish's analysis tools

3. **Combine Multiple Video Clips**
   ```
   python script_concatenate_and_import_csv.py
   ```
   When you have multiple clips (such as those exported from Hudl) that need to be combined:
   - Concatenates individual video files into a single continuous video
   - Calculates accurate timestamps for each original clip
   - Creates a CSV with timing information for future splitting if needed

## Cross-Platform Workflow

The toolkit supports bidirectional workflows between Dartfish and Hudl:

### Hudl to Dartfish

1. **Starting with Hudl**:
   - Receiving game footage and analysis in Hudl format
   - Exporting individual play clips and Excel metadata from Hudl

2. **Converting for Dartfish**:
   - Converting Hudl's Excel data to the required CSV format
   - Using `VideoSplitter({'split_video': False, 'create_dartclip': True})` to generate .dartclip files for the exported Hudl clips

3. **Analysis in Dartfish**:
   - Working with the converted clips in Dartfish's more advanced analysis tools
   - Adding additional metadata and annotations

### Dartfish to Hudl

1. **Breaking Down Game Film in Dartfish**:
   - Using Dartfish to review longer game footage
   - Creating event markers for each play within the continuous video
   - This extracts valuable play data while eliminating non-play time

2. **Generating Individual Clips**:
   - Exporting timing information as CSV from Dartfish
   - Using `VideoSplitter({'split_video': True, 'create_dartclip': False})` to extract just the relevant plays as individual clips

3. **Importing to Hudl**:
   - Dartfish can directly export CSV files in a format compatible with Hudl
   - Upload the individual play clips and CSV metadata to Hudl

4. **Optional - Creating Optimized Video**:
   - Using `script_concatenate_and_import_csv.py` to combine individual plays into a space-efficient continuous video
   - This removes dead time between plays while preserving all relevant footage

These workflows leverage the strengths of both platforms while maintaining metadata integrity throughout the analysis process.

## Extending the Toolkit

The modular design of this toolkit allows for several potential extensions:

- Support for additional video formats and codecs
- More sophisticated video processing (e.g., crop, resize, color correction)
- Game statistics reporting and analysis from the existing metadata
- Batch processing improvements for handling multiple games
- Development of a graphical user interface

The CSV files already contain comprehensive metadata for football analysis, making additional metadata formats unnecessary.

## License

[Your chosen license]

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
