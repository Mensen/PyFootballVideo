#!/usr/bin/env python
"""
Video Splitter Tool

This module provides functionality to split video files based on timestamp information
from a CSV file. It also supports creating .dartclip files for Dartfish analysis.

Usage:
    python video_splitter.py

Author: [Your Name]
Date: [Current Date]
"""

import os
import csv
import glob
import subprocess
import logging
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional, Tuple, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('video_splitter')

# Import helper functions
from utils.pf_helpers import select_folder, select_file, select_files
from utils.pf_create_dartclip import create_dartclip


class VideoSplitter:
    """
    A class for splitting video files based on timestamp information from a CSV file.
    
    This class provides functionality to:
    1. Read event timestamps from a CSV file
    2. Split a video file into clips based on these timestamps
    3. Create .dartclip files for Dartfish analysis
    
    The behavior is controlled through configuration options, allowing you to:
    - Split video only
    - Create dartclip files only
    - Do both operations
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the VideoSplitter with configuration.
        
        Args:
            config (dict, optional): Configuration options.
                Possible keys:
                - split_video (bool): Whether to split the video into clips
                - create_dartclip (bool): Whether to create dartclip files
                - skip (int): Number of initial events to skip
                - reencode (bool): Whether to re-encode the video
                - time_offset (float): Offset to apply to event times
                - buffer (float): Extra time to add to the end of each clip in seconds
                - start_number (int): Starting number for clip filename enumeration
        """
        # Default configuration
        self.config = {
            'split_video': True,     # Whether to split the video into clips
            'create_dartclip': True, # Whether to create dartclip files
            'skip': 0,               # Number of initial events to skip
            'reencode': False,       # Whether to re-encode the video
            'time_offset': 0,        # Offset to apply to event times
            'buffer': 0.5,           # 500ms buffer at the end of each clip
            'start_number': 1,       # Starting number for clip filenames
            'video_series': False,          # Enable multi-file series mode
            'series_input_mode': 'dartclip', # 'dartclip', 'csv_per_file', or 'csv_absolute'
        }
        
        # Update with provided configuration
        if config:
            self.config.update(config)
            
        logger.info("VideoSplitter initialized with config: %s", self.config)
    
    def extract_events(self, csv_path: str) -> List[Dict[str, str]]:
        """
        Extract events data from a CSV file.
        
        Args:
            csv_path (str): Path to the CSV file containing event data.
            
        Returns:
            list: List of dictionaries where each dictionary represents an event.
            
        Raises:
            ValueError: If required columns are missing from the CSV file.
            FileNotFoundError: If the CSV file does not exist.
        """
        logger.info(f"Extracting events from {csv_path}")
        
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"CSV file not found: {csv_path}")
            
        events = []
        
        try:
            with open(csv_path, 'r', encoding="utf-8-sig") as file:
                reader = csv.DictReader(file)
                
                # Check if the required columns exist in the CSV file (case-insensitive)
                required_columns = ['Position', 'Duration']
                field_names_lower = [field.lower() for field in reader.fieldnames]
                missing_columns = [col for col in required_columns if col.lower() not in field_names_lower]
                
                if missing_columns:
                    raise ValueError(f"Required columns {missing_columns} not found in the CSV file.")
                
                # Iterate over each row in the CSV file
                for row in reader:
                    events.append(row)
        
        except Exception as e:
            logger.error(f"Error extracting events: {e}")
            raise
            
        logger.info(f"Extracted {len(events)} events")
        return events

    def _build_ffmpeg_cmd(self, input_args: List[str], starttime: float,
                          duration: float, output_path: str) -> List[str]:
        """
        Build an FFmpeg command for extracting a clip.

        Args:
            input_args: Input portion of the command, e.g. ["-i", path] or
                        ["-f", "concat", "-safe", "0", "-i", filelist_path].
            starttime: Seek position in seconds.
            duration: Clip duration in seconds.
            output_path: Path to the output file.

        Returns:
            Complete FFmpeg command as a list of strings.
        """
        if not self.config['reencode']:
            cmd = [
                "ffmpeg",
                "-ss", str(starttime),
                "-t", str(duration),
                *input_args,
                "-c:v", "copy",
                "-an",
                "-v", "quiet",
                "-hide_banner",
                output_path
            ]
        else:
            cmd = [
                "ffmpeg",
                "-y",
                "-ss", str(starttime),
                "-t", str(duration),
                *input_args,
                '-vf', 'crop=iw:ih-600',
                "-bsf:v", "h264_mp4toannexb",
                "-preset", "slow",
                "-crf", "18",
                "-x264-params", "keyint=15:scenecut=0",
                "-vcodec", "libx264",
                "-acodec", "copy",
                "-hide_banner",
                output_path
            ]
        return cmd

    def split_video(self, video_path: str, events: List[Dict[str, str]], output_folder: Optional[str] = None) -> str:
        """
        Split a video file into clips based on event timestamps.
        
        Args:
            video_path (str): Path to the video file.
            events (list): List of events with timing information.
            output_folder (str, optional): Path to the output folder. If None, a folder selection dialog will open.
            
        Returns:
            str: Path to the folder containing the generated clips.
            
        Raises:
            FileNotFoundError: If the video file does not exist.
            ValueError: If events list is empty.
            subprocess.CalledProcessError: If FFmpeg command fails.
        """
        logger.info(f"Splitting video {video_path}")
        
        # Extract configuration
        flag_skip = self.config['skip']
        flag_dartclip = self.config['create_dartclip']
        time_offset = self.config['time_offset']
        buffer = self.config['buffer']
        start_number = self.config['start_number']
        
        # Verify video file exists
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")
            
        # Verify events
        if not events:
            raise ValueError("No events provided for splitting")
        
        # Helper function for case-insensitive column lookup
        def get_column_value(event, column_name):
            # First try exact match
            if column_name in event:
                return event[column_name]
            
            # Try case-insensitive match
            for key in event:
                if key.lower() == column_name.lower():
                    return event[key]
            
            # If not found, raise exception
            raise KeyError(f"Required column '{column_name}' not found in event: {event}")
        
        # Where should the clips go?
        if output_folder is None:
            video_folder = select_folder(title="Select output folder for clips")
            if not video_folder:
                logger.error("No output folder selected")
                return None
        else:
            video_folder = output_folder
        
        # Path to the new folder
        file_name = os.path.splitext(os.path.basename(video_path))[0]
        new_folder_name = file_name + " Clips"
        new_folder_path = os.path.join(video_folder, new_folder_name)
        
        # Create the new folder if it doesn't exist
        if not os.path.exists(new_folder_path):
            os.makedirs(new_folder_path)
            logger.info(f"Created output folder: {new_folder_path}")
        
        # Loop for each clip
        clips_created = 0
        for index, event in enumerate(events):
            # Skip some files if requested
            if index + 1 < flag_skip:
                logger.info(f"Skipping clip {index + 1} as per configuration")
                continue
            
            try:
                # Calculate start time and duration using case-insensitive column lookup
                starttime = float(get_column_value(event, 'Position')) / 1000 + time_offset
                duration = float(get_column_value(event, 'Duration')) / 1000 + buffer
                
                # Output name with leading zeros to 3 digits (001, 010, 100)
                # Modified to use start_number as the base
                clip_number = index + start_number
                output_file = f"Play_{clip_number:03d}.mp4"
                output_path = os.path.join(new_folder_path, output_file)
                
                # Create a dartclip file from the event if requested
                if flag_dartclip:
                    try:
                        create_dartclip(event, os.path.splitext(output_path)[0])
                        logger.info(f"Created dartclip for Play_{clip_number:03d}")
                    except Exception as e:
                        logger.error(f"Error creating dartclip for Play_{clip_number:03d}: {e}")
                
                # Prepare FFmpeg command
                cmd = self._build_ffmpeg_cmd(
                    ["-i", video_path], starttime, duration, output_path
                )
                
                # Run the prepared command in a subprocess
                logger.info(f"Processing clip {clip_number}/{len(events) + start_number - 1}")
                subprocess.run(cmd, check=True)
                
                # Verify the output file exists
                if os.path.exists(output_path):
                    clips_created += 1
                    logger.info(f"Created clip: {output_file}")
                else:
                    logger.warning(f"Failed to create clip: {output_file}")
                    
            except KeyError as e:
                logger.error(f"Column error processing clip {index + start_number}: {e}")
            except subprocess.CalledProcessError as e:
                logger.error(f"FFmpeg error processing clip {index + start_number}: {e}")
            except Exception as e:
                logger.error(f"Unexpected error processing clip {index + start_number}: {e}")
        
        logger.info(f"Finished processing {clips_created} clips in {new_folder_path}")
        return new_folder_path
    
    def create_dartclips_for_folder(self, events: List[Dict[str, str]], clips_folder: str, 
                                   file_pattern: str = "Play_{:03d}.mp4") -> int:
        """
        Create dartclip files for existing video clips in a folder.
        
        Args:
            events (list): List of event dictionaries from CSV.
            clips_folder (str): Folder containing the video clips.
            file_pattern (str): Pattern for matching clip filenames.
            
        Returns:
            int: Number of dartclip files created.
        """
        logger.info(f"Creating dartclip files for clips in {clips_folder}")
        
        # Get start_number from config
        start_number = self.config['start_number']
        
        # Verify folder exists
        if not os.path.exists(clips_folder):
            logger.error(f"Clips folder not found: {clips_folder}")
            return 0
        
        dartclips_created = 0
        for index, event in enumerate(events):
            # Generate the expected filename based on the pattern and start_number
            clip_number = index + start_number
            clip_name = file_pattern.format(clip_number)
            clip_path = os.path.join(clips_folder, clip_name)
            
            # Skip if the clip doesn't exist
            if not os.path.exists(clip_path):
                logger.warning(f"Clip not found: {clip_path}")
                continue
            
            # Create the dartclip file
            try:
                # Use the filename without extension as the base for the dartclip
                base_path = os.path.splitext(clip_path)[0]
                create_dartclip(event, base_path)
                dartclips_created += 1
                logger.info(f"Created dartclip for {clip_name}")
            except Exception as e:
                logger.error(f"Error creating dartclip for {clip_name}: {e}")
        
        logger.info(f"Created {dartclips_created} dartclip files")
        return dartclips_created

    # ── Video series methods ──��──────────────────────────────────────────

    def parse_dartclip(self, dartclip_path: str) -> Dict[str, Any]:
        """
        Parse a Dartfish .dartclip XML file into a dict with the source video
        filename and a list of event dicts (same shape as CSV-parsed events).

        Args:
            dartclip_path: Path to the .dartclip file.

        Returns:
            dict with keys 'video_file' (str) and 'events' (list of dicts).
        """
        tree = ET.parse(dartclip_path)
        root = tree.getroot()

        video_file = root.findtext('NAME')
        events = []

        for item in root.findall("LIBRARY_ITEM[@ItemType='Marker.Event']"):
            in_reftime = int(item.get('IN', '0'))
            out_reftime = int(item.get('OUT', '0'))

            # RefTime (100-nanosecond units) → milliseconds
            position_ms = in_reftime // 10000
            duration_ms = (out_reftime - in_reftime) // 10000

            event = {
                'Position': str(position_ms),
                'Duration': str(duration_ms),
            }

            # Extract title from nested MDProperties
            md_props = item.find('Library.MDProperties')
            if md_props is not None:
                title_elem = md_props.find("Property[@Name='Title']")
                if title_elem is not None and title_elem.text:
                    event['Name'] = title_elem.text

            # Extract all categories
            categories = item.find('CATEGORIES')
            if categories is not None:
                for cat in categories.findall('CATEGORY'):
                    name = cat.get('name')
                    if name and cat.text:
                        event[name] = cat.text

            events.append(event)

        logger.info(f"Parsed {len(events)} events from {os.path.basename(dartclip_path)}")
        return {'video_file': video_file, 'events': events}

    def load_series_from_dartclips(self, folder_path: str) -> List[Dict[str, Any]]:
        """
        Scan a folder for .dartclip files and return series data.

        Args:
            folder_path: Folder containing .dartclip files (and their MP4s).

        Returns:
            List of dicts, each with 'video_path' (str) and 'events' (list).
        """
        dartclip_files = sorted(glob.glob(os.path.join(folder_path, '*.dartclip')))

        if not dartclip_files:
            logger.error(f"No .dartclip files found in {folder_path}")
            return []

        series_data = []
        for dc_path in dartclip_files:
            parsed = self.parse_dartclip(dc_path)
            if not parsed['events']:
                logger.warning(f"Skipping {os.path.basename(dc_path)} (no events)")
                continue

            # Video path is the dartclip path minus the .dartclip extension
            # e.g. GX021660.MP4.dartclip -> GX021660.MP4
            video_path = dc_path.rsplit('.dartclip', 1)[0]
            if not os.path.exists(video_path):
                logger.warning(f"Video file not found: {video_path}")
                continue

            series_data.append({
                'video_path': video_path,
                'events': parsed['events'],
            })

        logger.info(f"Loaded series with {len(series_data)} files, "
                     f"{sum(len(s['events']) for s in series_data)} total events")
        return series_data

    def detect_file_boundaries(self, events: List[Dict[str, str]]) -> List[List[Dict[str, str]]]:
        """
        Group events into per-file segments for CSV per-file timestamp mode.

        Uses an explicit 'File' column if present, otherwise auto-detects
        file boundaries when Position drops significantly.

        Args:
            events: List of event dicts from extract_events().

        Returns:
            List of event groups (one group per source file).
        """
        if not events:
            return []

        # Check for explicit File column (case-insensitive)
        file_col = None
        first_keys = list(events[0].keys())
        for key in first_keys:
            if key.lower() == 'file':
                file_col = key
                break

        if file_col:
            # Group by consecutive File column values
            groups = []
            current_group = [events[0]]
            current_file = events[0][file_col]
            for event in events[1:]:
                if event[file_col] == current_file:
                    current_group.append(event)
                else:
                    groups.append(current_group)
                    current_group = [event]
                    current_file = event[file_col]
            groups.append(current_group)
            logger.info(f"Grouped {len(events)} events into {len(groups)} files by '{file_col}' column")
            return groups

        # Auto-detect by Position resets
        groups = []
        current_group = [events[0]]
        prev_position = float(events[0]['Position'])

        for event in events[1:]:
            position = float(event['Position'])
            if position < prev_position * 0.5:
                groups.append(current_group)
                current_group = []
            current_group.append(event)
            prev_position = position

        groups.append(current_group)
        logger.info(f"Auto-detected {len(groups)} file boundaries from Position resets")
        return groups

    def _make_concat_filelist(self, video_paths: List[str], output_dir: str) -> str:
        """
        Create an FFmpeg concat demuxer input file.

        Args:
            video_paths: Ordered list of video file paths.
            output_dir: Directory to write the filelist to.

        Returns:
            Path to the generated filelist.
        """
        filelist_path = os.path.join(output_dir, '_concat_filelist.txt')
        with open(filelist_path, 'w') as f:
            for path in video_paths:
                f.write(f"file '{path}'\n")
        logger.info(f"Created concat filelist with {len(video_paths)} files")
        return filelist_path

    def split_video_series(self, series_data: List[Dict[str, Any]],
                           output_folder: Optional[str] = None) -> str:
        """
        Split clips from a series of video files.

        Args:
            series_data: List of dicts with 'video_path' and 'events' keys.
            output_folder: Base output folder. If None, a dialog will open.

        Returns:
            Path to the folder containing the generated clips.
        """
        if not series_data:
            raise ValueError("No series data provided")

        # Determine output folder
        if output_folder is None:
            output_folder = select_folder(title="Select output folder for clips")
            if not output_folder:
                logger.error("No output folder selected")
                return None

        # Name the clips folder after the first video
        first_name = os.path.splitext(os.path.basename(series_data[0]['video_path']))[0]
        new_folder_path = os.path.join(output_folder, first_name + " Series Clips")
        if not os.path.exists(new_folder_path):
            os.makedirs(new_folder_path)
            logger.info(f"Created output folder: {new_folder_path}")

        time_offset = self.config['time_offset']
        buffer = self.config['buffer']
        flag_skip = self.config['skip']
        flag_dartclip = self.config['create_dartclip']
        start_number = self.config['start_number']

        # Helper for case-insensitive column lookup
        def get_col(event, col):
            if col in event:
                return event[col]
            for key in event:
                if key.lower() == col.lower():
                    return event[key]
            raise KeyError(f"Column '{col}' not found in event")

        clips_created = 0
        global_index = 0

        for segment in series_data:
            video_path = segment['video_path']
            logger.info(f"Processing {os.path.basename(video_path)} "
                        f"({len(segment['events'])} events)")

            for event in segment['events']:
                global_index += 1

                if global_index < flag_skip:
                    logger.info(f"Skipping clip {global_index}")
                    continue

                try:
                    starttime = float(get_col(event, 'Position')) / 1000 + time_offset
                    duration = float(get_col(event, 'Duration')) / 1000 + buffer

                    clip_number = global_index - 1 + start_number
                    output_file = f"Play_{clip_number:03d}.mp4"
                    output_path = os.path.join(new_folder_path, output_file)

                    if flag_dartclip:
                        try:
                            create_dartclip(event, os.path.splitext(output_path)[0])
                            logger.info(f"Created dartclip for Play_{clip_number:03d}")
                        except Exception as e:
                            logger.error(f"Error creating dartclip for Play_{clip_number:03d}: {e}")

                    cmd = self._build_ffmpeg_cmd(
                        ["-i", video_path], starttime, duration, output_path
                    )

                    logger.info(f"Processing clip {clip_number} from {os.path.basename(video_path)}")
                    subprocess.run(cmd, check=True)

                    if os.path.exists(output_path):
                        clips_created += 1
                        logger.info(f"Created clip: {output_file}")
                    else:
                        logger.warning(f"Failed to create clip: {output_file}")

                except KeyError as e:
                    logger.error(f"Column error processing clip {global_index}: {e}")
                except subprocess.CalledProcessError as e:
                    logger.error(f"FFmpeg error processing clip {global_index}: {e}")
                except Exception as e:
                    logger.error(f"Unexpected error processing clip {global_index}: {e}")

        logger.info(f"Finished series: {clips_created} clips in {new_folder_path}")
        return new_folder_path

    def _split_absolute_series(self, filelist_path: str,
                               events: List[Dict[str, str]],
                               output_folder: str) -> str:
        """
        Split clips using FFmpeg concat demuxer for absolute timestamps.

        Args:
            filelist_path: Path to the concat demuxer input file.
            events: All events with absolute Position/Duration.
            output_folder: Base output folder.

        Returns:
            Path to the folder containing the generated clips.
        """
        new_folder_path = os.path.join(output_folder, "Series Clips")
        if not os.path.exists(new_folder_path):
            os.makedirs(new_folder_path)

        time_offset = self.config['time_offset']
        buffer = self.config['buffer']
        flag_skip = self.config['skip']
        flag_dartclip = self.config['create_dartclip']
        start_number = self.config['start_number']

        def get_col(event, col):
            if col in event:
                return event[col]
            for key in event:
                if key.lower() == col.lower():
                    return event[key]
            raise KeyError(f"Column '{col}' not found in event")

        clips_created = 0
        concat_input = ["-f", "concat", "-safe", "0", "-i", filelist_path]

        for index, event in enumerate(events):
            if index + 1 < flag_skip:
                continue
            try:
                starttime = float(get_col(event, 'Position')) / 1000 + time_offset
                duration = float(get_col(event, 'Duration')) / 1000 + buffer
                clip_number = index + start_number
                output_file = f"Play_{clip_number:03d}.mp4"
                output_path = os.path.join(new_folder_path, output_file)

                if flag_dartclip:
                    try:
                        create_dartclip(event, os.path.splitext(output_path)[0])
                    except Exception as e:
                        logger.error(f"Error creating dartclip for Play_{clip_number:03d}: {e}")

                cmd = self._build_ffmpeg_cmd(concat_input, starttime, duration, output_path)
                logger.info(f"Processing clip {clip_number} (absolute mode)")
                subprocess.run(cmd, check=True)

                if os.path.exists(output_path):
                    clips_created += 1
                    logger.info(f"Created clip: {output_file}")
                else:
                    logger.warning(f"Failed to create clip: {output_file}")

            except KeyError as e:
                logger.error(f"Column error processing clip {index + start_number}: {e}")
            except subprocess.CalledProcessError as e:
                logger.error(f"FFmpeg error processing clip {index + start_number}: {e}")
            except Exception as e:
                logger.error(f"Unexpected error processing clip {index + start_number}: {e}")

        logger.info(f"Finished absolute series: {clips_created} clips in {new_folder_path}")
        return new_folder_path

    # ── End of series methods ─────────────────────────────────────────

    def process_video(self, video_path: Optional[str] = None,
                     csv_path: Optional[str] = None,
                     clips_folder: Optional[str] = None,
                     video_paths: Optional[List[str]] = None,
                     series_folder: Optional[str] = None) -> Any:
        """
        Process a video file according to the configuration.

        This is the main entry point for all video processing operations.
        Based on configuration, this method can:
        - Split video only (split_video=True, create_dartclip=False)
        - Create dartclips only (split_video=False, create_dartclip=True)
        - Do both (split_video=True, create_dartclip=True)
        - Split a video series (video_series=True)

        Args:
            video_path (str, optional): Path to the video file.
            csv_path (str, optional): Path to the CSV file with events data.
            clips_folder (str, optional): Path to folder with existing clips.
            video_paths (list, optional): Ordered list of video file paths for series mode.
            series_folder (str, optional): Folder with .dartclip files for series mode.

        Returns:
            str or int: Path to output folder if splitting video, or number of dartclips created.
        """
        # ── VIDEO SERIES MODE ───────────────────────────────────────────
        if self.config['video_series']:
            mode = self.config['series_input_mode']

            if mode == 'dartclip':
                if not series_folder:
                    series_folder = select_folder(title="Select folder with .dartclip files")
                    if not series_folder:
                        logger.error("No folder selected")
                        return None
                series_data = self.load_series_from_dartclips(series_folder)
                if not series_data:
                    logger.error("No valid dartclip/video pairs found")
                    return None
                return self.split_video_series(series_data)

            elif mode == 'csv_per_file':
                if not csv_path:
                    csv_folder, csv_name = select_file(title="Choose the CSV file")
                    if not csv_folder or not csv_name:
                        logger.error("No CSV file selected")
                        return None
                    csv_path = os.path.join(csv_folder, csv_name)
                events = self.extract_events(csv_path)
                groups = self.detect_file_boundaries(events)
                if not video_paths:
                    video_paths = select_files(
                        title=f"Select {len(groups)} video files in order"
                    )
                    if not video_paths:
                        logger.error("No video files selected")
                        return None
                if len(groups) != len(video_paths):
                    raise ValueError(
                        f"CSV has {len(groups)} file segments but "
                        f"{len(video_paths)} video files were provided"
                    )
                series_data = [
                    {'video_path': vp, 'events': grp}
                    for vp, grp in zip(video_paths, groups)
                ]
                return self.split_video_series(series_data)

            elif mode == 'csv_absolute':
                if not csv_path:
                    csv_folder, csv_name = select_file(title="Choose the CSV file")
                    if not csv_folder or not csv_name:
                        logger.error("No CSV file selected")
                        return None
                    csv_path = os.path.join(csv_folder, csv_name)
                events = self.extract_events(csv_path)
                if not video_paths:
                    video_paths = select_files(title="Select all video files in order")
                    if not video_paths:
                        logger.error("No video files selected")
                        return None
                # Use concat demuxer — treat all files as one virtual input
                output_folder = select_folder(title="Select output folder for clips")
                if not output_folder:
                    logger.error("No output folder selected")
                    return None
                filelist = self._make_concat_filelist(video_paths, output_folder)
                try:
                    return self._split_absolute_series(
                        filelist, events, output_folder
                    )
                finally:
                    if os.path.exists(filelist):
                        os.remove(filelist)

            else:
                logger.error(f"Unknown series_input_mode: {mode}")
                return None

        # ── SINGLE FILE MODE (existing behavior) ───────────────────────
        # Select CSV file if not provided (needed for all operations)
        if not csv_path:
            csv_folder, csv_name = select_file(title="Choose the csv file with event data")
            if not csv_folder or not csv_name:
                logger.error("No CSV file selected")
                return None
            csv_path = os.path.join(csv_folder, csv_name)
        
        # Extract events from CSV
        try:
            events = self.extract_events(csv_path)
            if not events:
                logger.error("No events found in CSV file")
                return None
        except Exception as e:
            logger.error(f"Failed to extract events: {e}")
            return None
            
        # OPERATION 1: Split video into clips (with optional dartclip creation)
        if self.config['split_video']:
            # Select video file if not provided
            if not video_path:
                video_folder, video_name = select_file(title="Choose the video file you want to cut")
                if not video_folder or not video_name:
                    logger.error("No video file selected")
                    return None
                video_path = os.path.join(video_folder, video_name)
            
            # Split the video
            try:
                output_folder = self.split_video(video_path, events)
                return output_folder
            except Exception as e:
                logger.error(f"Failed to split video: {e}")
                return None
                
        # OPERATION 2: Create dartclip files for existing clips
        elif self.config['create_dartclip']:
            # Select clips folder if not provided
            if not clips_folder:
                clips_folder = select_folder(title="Select folder containing existing clips")
                if not clips_folder:
                    logger.error("No clips folder selected")
                    return None
            
            # Create dartclip files
            try:
                dartclips_created = self.create_dartclips_for_folder(events, clips_folder)
                return dartclips_created
            except Exception as e:
                logger.error(f"Failed to create dartclip files: {e}")
                return None
                
        # No operation selected
        else:
            logger.warning("No operation selected (split_video=False, create_dartclip=False)")
            return None


def main():
    """
    Main function to run the video splitter interactively.
    """
    try:
        print("Select operation:")
        print("1. Split video into clips")
        print("2. Create dartclip files for existing clips")
        print("3. Split video and create dartclip files")
        print("4. Advanced configuration")
        print("5. Split video series (multiple files)")

        choice = input("Enter choice (1-5): ")

        # Create a splitter with appropriate configuration
        if choice == '1':
            # Split video only
            splitter = VideoSplitter({'split_video': True, 'create_dartclip': False})
            result = splitter.process_video()
            if result:
                print(f"Successfully created clips in: {result}")
            else:
                print("Video splitting process was not completed successfully.")
                
        elif choice == '2':
            # Create dartclips only
            splitter = VideoSplitter({'split_video': False, 'create_dartclip': True})
            result = splitter.process_video()
            if result:
                print(f"Successfully created {result} dartclip files")
            else:
                print("Dartclip creation process was not completed successfully.")
                
        elif choice == '3':
            # Split video and create dartclips
            splitter = VideoSplitter({'split_video': True, 'create_dartclip': True})
            result = splitter.process_video()
            if result:
                print(f"Successfully created clips with dartclip files in: {result}")
            else:
                print("Video processing was not completed successfully.")
                
        elif choice == '4':
            # Advanced configuration
            print("\nAdvanced Configuration:")
            
            # Get configuration values from user
            start_number = int(input("Enter starting number for clips (default: 1): ") or 1)
            skip = int(input("Number of initial events to skip (default: 0): ") or 0)
            reencode = input("Re-encode video? (y/n, default: n): ").lower() == 'y'
            time_offset = float(input("Time offset in seconds (default: 0): ") or 0)
            buffer = float(input("Buffer time in seconds (default: 0.5): ") or 0.5)
            create_dartclip = input("Create dartclip files? (y/n, default: y): ").lower() != 'n'
            
            # Create configuration dictionary
            config = {
                'split_video': True,
                'create_dartclip': create_dartclip,
                'skip': skip,
                'reencode': reencode,
                'time_offset': time_offset,
                'buffer': buffer,
                'start_number': start_number
            }
            
            # Create splitter with custom configuration
            splitter = VideoSplitter(config)
            result = splitter.process_video()
            
            if result:
                print(f"Successfully processed video with custom configuration. Output in: {result}")
            else:
                print("Video processing with custom configuration was not completed successfully.")
                
        elif choice == '5':
            # Video series
            print("\nVideo series input mode:")
            print("  a. From Dartfish dartclip files (select folder)")
            print("  b. From CSV with per-file timestamps")
            print("  c. From CSV with absolute timestamps")

            sub = input("Enter choice (a/b/c, default: a): ").lower() or 'a'

            mode_map = {
                'a': 'dartclip',
                'b': 'csv_per_file',
                'c': 'csv_absolute',
            }
            input_mode = mode_map.get(sub, 'dartclip')

            config = {
                'video_series': True,
                'series_input_mode': input_mode,
                'split_video': True,
                'create_dartclip': True,
            }

            splitter = VideoSplitter(config)
            result = splitter.process_video()

            if result:
                print(f"Successfully created series clips in: {result}")
            else:
                print("Video series processing was not completed successfully.")

        else:
            print("Invalid choice. Exiting.")

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()