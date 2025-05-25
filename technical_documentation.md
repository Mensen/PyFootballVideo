# Football Video Processing Tools - Technical Documentation

## Architecture Overview

This toolkit implements a modular design that supports multiple video analysis workflows common in football coaching. The core architecture separates concerns between video processing, metadata management, and platform-specific integrations.

### Design Principles

1. **Unified Interface**: Single `VideoSplitter` class handles all operations through configuration
2. **Platform Agnostic**: Core functionality independent of specific coaching platforms
3. **Metadata Preservation**: Maintains data integrity across platform conversions
4. **Extensible Design**: Modular structure allows easy addition of new features
5. **Error Resilience**: Comprehensive error handling and logging throughout

## Core Components

### VideoSplitter Class (video_splitter.py)

The primary orchestrator that manages video splitting and metadata creation through a configurable interface.

**Key Design Features:**
- Configuration-driven behavior eliminates need for multiple scripts
- Case-insensitive CSV column matching for robust data handling
- Flexible timestamp management with offset and buffer support
- Integrated logging for debugging and monitoring

**Configuration Options:**
```python
config = {
    'split_video': bool,      # Enable video splitting
    'create_dartclip': bool,  # Enable dartclip generation
    'skip': int,              # Skip initial events
    'reencode': bool,         # Force re-encoding vs stream copy
    'time_offset': float,     # Global time adjustment (seconds)
    'buffer': float,          # End-of-clip buffer (seconds)
    'start_number': int,      # Starting number for clip enumeration
}
```

**Core Methods:**
- `extract_events()`: Robust CSV parsing with encoding detection
- `split_video()`: FFmpeg-based video segmentation
- `create_dartclips_for_folder()`: Batch dartclip generation
- `process_video()`: Unified entry point with smart workflow detection

### Helper Modules

#### pf_helpers.py
Provides platform-independent file system interactions:
- `select_file()`: Cross-platform file selection dialogs
- `select_folder()`: Directory selection with normalization
- `define_paths_breakdown()`: Path construction utilities

#### pf_create_dartclip.py
Handles Dartfish XML generation:
- Case-insensitive metadata extraction
- Standards-compliant XML structure
- Support for custom categories and properties
- Backward compatibility with legacy formats

#### py_random_functions.py
OpenCV-based utilities for advanced video processing:
- Frame-accurate video playback
- Metadata extraction from video files
- Foundation for future computer vision features

## Platform Integration Architecture

### Dartfish Integration

Dartfish uses XML-based `.dartclip` files for metadata storage. Our implementation creates fully compatible files that include:

**XML Structure:**
```xml
<LIBRARY_ITEM>
    <NAME>play_001.mp4</NAME>
    <ID>0</ID>
    <VERSION subversion="1">2.0</VERSION>
    <LIBRARY_ITEM Color="Color2" ItemType="Marker.Event" 
                  IN="0" OUT="50000000" UNIT="RefTime">
        <CATEGORIES>
            <CATEGORY name="Down">1</CATEGORY>
            <CATEGORY name="ODK">O</CATEGORY>
            <CATEGORY name="Play Type">Run</CATEGORY>
        </CATEGORIES>
    </LIBRARY_ITEM>
    <Library.MDProperties>
        <Property Name="Title">play_001</Property>
    </Library.MDProperties>
    <TYPE>1</TYPE>
</LIBRARY_ITEM>
```

**Key Features:**
- RefTime units (100-nanosecond intervals)
- Color coding support for visual organization
- Extensible category system for custom metadata
- Compatible with Dartfish's import/export workflows

### Hudl Integration

Hudl exports typically include:
- Individual MP4 files per play
- Excel spreadsheets with metadata
- Playlist information for game organization

**Conversion Strategy:**
1. Parse Excel exports using pandas (when available)
2. Map Hudl column names to our standardized format
3. Generate dartclip files maintaining metadata relationships
4. Preserve Hudl naming conventions where possible

## Video Processing Pipeline

### FFmpeg Integration

The toolkit leverages FFmpeg for all video operations, supporting both stream copying and re-encoding workflows:

**Stream Copy (Default - Fastest):**
```bash
ffmpeg -ss {start} -t {duration} -i {input} -c:v copy -an {output}
```

**Re-encoding (Quality/Compatibility):**
```bash
ffmpeg -ss {start} -t {duration} -i {input} 
       -vf "crop=iw:ih-600" -preset slow -crf 18 
       -x264-params "keyint=15:scenecut=0" {output}
```

**Design Considerations:**
- Start time (`-ss`) positioning for frame accuracy
- Duration (`-t`) vs end time (`-to`) for precision
- Audio handling (disabled by default for analysis clips)
- Keyframe optimization for Dartfish compatibility

### Timestamp Management

The system handles multiple timing formats and provides robust conversion:

**Input Formats:**
- Milliseconds (primary format)
- Seconds with decimal precision
- Frame numbers (with framerate conversion)

**Precision Handling:**
- Maintains microsecond precision through processing
- Accounts for video container timing variations
- Provides configurable buffer zones for clip boundaries

## Data Flow Architecture

### CSV Processing Pipeline

1. **Encoding Detection**: Handles UTF-8, UTF-8-BOM, and other encodings
2. **Column Mapping**: Case-insensitive matching for flexibility
3. **Data Validation**: Type checking and range validation
4. **Metadata Extraction**: Preserves all columns for dartclip generation

### Event Processing Workflow

```
CSV Input → Event Extraction → Timestamp Calculation → Video Segmentation
                                     ↓
Dartclip Generation ← Metadata Assembly ← Category Mapping
```

### File Organization Strategy

**Output Structure:**
```
{video_name} Clips/
├── Play_001.mp4          # Video clip
├── Play_001.dartclip     # Metadata file
├── Play_002.mp4
├── Play_002.dartclip
└── ...
```

**Naming Conventions:**
- Zero-padded numbering (001, 002, etc.)
- Configurable starting numbers for multi-game processing
- Consistent extensions for platform compatibility

## Advanced Features

### Scene Detection Integration (script_scenedetect.py)

Provides automated scene boundary detection for unbroken game footage:

**Detection Algorithm:**
- PySceneDetect integration with adaptive thresholding
- Configurable sensitivity for different video types
- Pattern recognition for football-specific scene structures
- Post-processing filters for play/non-play discrimination

**Use Cases:**
- Processing continuous recording into discrete plays
- Quality control for manual timestamp entry
- Automated preprocessing of raw game footage

### Frame Extraction (extract_frames.py)

Supports image-based analysis workflows:

**Features:**
- Random sampling with configurable density
- Pre-snap focus modes for tactical analysis
- Batch processing across multiple clips
- Integration with computer vision pipelines

### Concatenation Tools (script_concatenate_and_import_csv.py)

Enables reverse workflow (clips → continuous video):

**Applications:**
- Creating highlight reels from individual plays
- Generating space-efficient storage formats
- Platform migration between clip-based and timeline-based systems
- Piecing together continuous videos that was cut due to technical constraints (e.g. GoPro footage)

## Extension Points

### Video Processing Extensions

The modular FFmpeg integration supports easy addition of:
- Custom video filters (crop, scale, color correction)
- Multi-angle synchronization
- Advanced encoding parameters for specific platforms
- Real-time processing capabilities

### Metadata Format Extensions

The XML generation system can be extended for:
- Additional coaching platforms beyond Dartfish
- Custom metadata schemas for specific team needs
- Integration with statistical analysis systems
- Export formats for other video analysis tools

### Platform Integration Extensions

Current design supports adding:
- Direct API integration with Hudl/Dartfish
- Cloud storage synchronization
- Team management system integration
- Statistical analysis pipeline connections

## Performance Characteristics

### Processing Speed

**Stream Copy Mode:**
- ~50-100x real-time (limited by I/O)
- Minimal CPU usage
- Preserves original quality

**Re-encoding Mode:**
- ~1-5x real-time (depending on settings)
- Higher CPU usage
- Optimized quality/compatibility

### Memory Usage

- Minimal RAM requirements (< 100MB typical)
- Streaming processing avoids large memory allocations
- Scalable to very large input files

### Storage Efficiency

- Stream copy: No size penalty
- Re-encoding: 10-30% size reduction typical
- Dartclip files: <1KB per clip

## Testing and Quality Assurance

### Validation Strategies

1. **Timing Accuracy**: Frame-level verification of clip boundaries
2. **Metadata Preservation**: Round-trip testing through platforms
3. **Format Compatibility**: Cross-platform verification
4. **Error Handling**: Comprehensive failure mode testing

### Common Edge Cases

- Zero-duration events
- Overlapping timestamps
- Non-standard video formats
- Corrupted metadata files
- Missing dependencies

## Development Roadmap

### Immediate Enhancements

- GUI interface for non-technical users
- Automated dependency installation
- Enhanced error reporting and recovery
- Performance optimization for large batches

### Medium-term Goals

- Direct platform API integration
- Real-time processing capabilities
- Advanced video analysis features
- Statistical integration pipelines

### Long-term Vision

- Machine learning integration for automated tagging
- Multi-team collaboration features
- Cloud-native processing options
- Advanced computer vision analysis

## Contributing Guidelines

### Code Organization

- Maintain separation of concerns between modules
- Follow existing naming conventions
- Add comprehensive logging for new features
- Include error handling for all external dependencies

### Testing Requirements

- Unit tests for core functionality
- Integration tests with real video files
- Cross-platform compatibility verification
- Performance regression testing

### Documentation Standards

- Docstring documentation for all public methods
- README updates for user-facing changes
- Technical documentation for architectural changes
- Example usage for new features

This toolkit represents a mature, production-ready solution for football video analysis workflows, with a design that supports both current needs and future extensibility.