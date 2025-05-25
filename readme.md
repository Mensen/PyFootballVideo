# 🏈 Football Video Processing Tools

A simple toolkit for coaches to split game footage and convert between Hudl and Dartfish formats.

## What This Does

**In simple terms:** Turn your game footage into individual play clips that work with coaching software.

### Common Use Cases
- **Split full game video** → Individual play clips for analysis
- **Convert Hudl clips** → Dartfish-compatible format with metadata
- **Organize game footage** → Consistent naming and metadata across platforms

### Supported Workflows
- **Hudl → Dartfish**: Convert exported Hudl clips to work with Dartfish analysis tools
- **Game Film → Individual Plays**: Split long recordings into manageable play-by-play clips
- **Batch Processing**: Handle multiple games or large amounts of footage efficiently

## Quick Start

### 1. One-Time Setup (15 minutes)

**Install Python:**
- Download from [python.org](https://www.python.org/downloads/)
- ⚠️ **Important**: Check "Add Python to PATH" during installation
- Test: Open Command Prompt → type `python --version`

**Install FFmpeg:**
- Download from [gyan.dev/ffmpeg](https://www.gyan.dev/ffmpeg/builds/)
- Extract to `C:\ffmpeg`
- Add `C:\ffmpeg\bin` to your Windows PATH
- Test: Open Command Prompt → type `ffmpeg -version`

**Get the Tools:**
- Download/clone this repository
- Put the folder somewhere easy to find

### 2. Running the Tools

**Main Tool:**
- Run: `python video_splitter.py`
- Follow the menu prompts to choose your workflow

## How to Use

### Option 1: Convert Hudl Clips to Dartfish
**When:** You have individual clips from Hudl and want to analyze them in Dartfish

**You Need:**
- Folder with your .mp4 clips from Hudl
- CSV file with play information (can convert from Hudl Excel export)

**Result:** Same clips + .dartclip files that Dartfish can read

### Option 2: Split Full Game Video
**When:** You have one large game video and want individual play clips

**You Need:**
- Full game video file (.mp4)
- CSV with timing information (start time and duration for each play)

**Result:** Individual play clips + Dartfish-compatible metadata files

### Option 3: Quick Split
**When:** You just need clips split quickly, don't need Dartfish files

**You Need:**
- Full game video file (.mp4)
- CSV with timing information

**Result:** Individual play clips only (fastest processing)

## CSV File Format

Your CSV needs these columns:
- `Position` - Start time in milliseconds
- `Duration` - Length in milliseconds

Optional (for enhanced Dartfish analysis):
- `Down`, `ODK`, `Play Type`, `Distance`, `Result`

**Example:**
```csv
Name,Position,Duration,Down,ODK,Play Type
Play 1,0,5000,1,O,Run
Play 2,5000,6200,2,O,Pass
Play 3,11200,4800,3,O,Pass
```

**Need help with CSV?** Run: `python script_to_split_video.py` (includes CSV handling examples)

## Troubleshooting

**"Python is not recognized"**
- Reinstall Python with "Add to PATH" checked

**"ffmpeg is not recognized"**
- Follow FFmpeg setup steps again
- Make sure `C:\ffmpeg\bin` is in your PATH

**Clips are wrong length**
- Check CSV timing (should be milliseconds, not seconds)
- Tool adds small buffer by default

**Need to skip certain plays**
- Use advanced options to set starting number or skip plays

## Platform Integration

### Dartfish Integration
- Creates `.dartclip` files alongside video clips
- Preserves metadata (down, distance, play type, etc.)
- Compatible with Dartfish's event markers and categories
- Supports color coding and custom annotations

### Hudl Integration  
- Reads exported Hudl clip folders
- Converts Hudl Excel metadata to Dartfish format
- Maintains play sequencing and naming conventions
- Preserves game and team information

## File Organization

The tool creates organized output:
```
Game Clips/
├── Play_001.mp4
├── Play_001.dartclip
├── Play_002.mp4
├── Play_002.dartclip
└── ...
```

## Getting Help

- **Setup Issues**: Check the troubleshooting section above
- **CSV Problems**: Use `python csv_helper.py`
- **Advanced Features**: See `project_details.md`
- **Bug Reports**: Contact [maintainer] or create an issue

## What's Included

- `video_splitter.py` - Main splitting tool with interactive menu
- `script_to_split_video.py` - Alternative simplified splitting script  
- `extract_frames.py` - Extract frames from videos for analysis
- `script_concatenate_and_import_csv.py` - Combine clips into full video
- `utils/` - Helper functions and Dartfish integration

## Contributing

Contributions welcome! This tool is actively used by coaching staff and improvements benefit the entire football analysis community.

See `project_details.md` for technical architecture and development information.