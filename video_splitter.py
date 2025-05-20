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
import subprocess
import logging
from typing import List, Dict, Optional, Tuple, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('video_splitter')

# Import helper functions
from utils.pf_helpers import select_folder, select_file
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
        flag_reencode = self.config['reencode']
        flag_dartclip = self.config['create_dartclip']
        time_offset = self.config['time_offset']
        buffer = self.config['buffer']
        start_number = self.config['start_number']  # Get the starting number from config
        
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
                
                # Prepare FFmpeg command based on re-encoding preference
                if not flag_reencode:
                    # Copy video and audio
                    cmd = [
                        "ffmpeg",
                        "-ss", str(starttime),
                        "-t", str(duration),
                        "-i", video_path,
                        "-c:v", "copy",  # Copy video codec
                        "-an",           # Disable audio
                        "-v", "quiet",
                        "-hide_banner",
                        output_path
                    ]
                else:
                    # With re-encoding to H264
                    cmd = [
                        "ffmpeg",
                        "-y",  # Overwrite output if exists
                        "-ss", str(starttime),
                        "-t", str(duration),
                        "-i", video_path,
                        '-vf', 'crop=iw:ih-600',  # Crop 300 from top and bottom
                        "-bsf:v", "h264_mp4toannexb",
                        "-preset", "slow",  # Slow for generally best results
                        "-crf", "18",
                        "-x264-params", "keyint=15:scenecut=0",
                        "-vcodec", "libx264",
                        "-acodec", "copy",
                        "-hide_banner",
                        output_path
                    ]
                
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
        
    def process_video(self, video_path: Optional[str] = None, 
                     csv_path: Optional[str] = None,
                     clips_folder: Optional[str] = None) -> Any:
        """
        Process a video file according to the configuration.
        
        This is the main entry point for all video processing operations.
        Based on configuration, this method can:
        - Split video only (split_video=True, create_dartclip=False)
        - Create dartclips only (split_video=False, create_dartclip=True)
        - Do both (split_video=True, create_dartclip=True)
        
        Args:
            video_path (str, optional): Path to the video file. Required if split_video=True.
            csv_path (str, optional): Path to the CSV file with events data. Always required.
            clips_folder (str, optional): Path to folder with existing clips. Required if split_video=False.
            
        Returns:
            str or int: Path to output folder if splitting video, or number of dartclips created.
        """
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
        
        choice = input("Enter choice (1-4): ")
        
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
                
        else:
            print("Invalid choice. Exiting.")
            
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()