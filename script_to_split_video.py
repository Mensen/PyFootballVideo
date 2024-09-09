#!/usr/bin/env python

import os
import csv
import subprocess

# own functions
from utils.pf_helpers import select_folder
from utils.pf_helpers import select_file
from utils.pf_create_dartclip import create_dartclip


def extract_columns(full_times_path):
    events = []

    with open(full_times_path, 'r', encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)

        # Check if the required columns exist in the CSV file
        if 'Position' not in reader.fieldnames or 'Duration' not in reader.fieldnames:
            raise ValueError("The 'Position' and 'Duration' columns are required but not found in the CSV file.")

        # Iterate over each row in the CSV file
        for row in reader:
            events.append(row)

    return events


def split_direct_cmd(full_video_path, events):
    # Default behavior
    flag_skip = 0
    flag_reencode = 0
    flag_dartclip = 1
    time_offset = 0

    # Where should the clips go?
    video_folder = os.path.dirname(full_video_path)
    video_folder = select_folder()

    # Path to the new folder
    file_name = os.path.splitext(os.path.basename(full_video_path))[0]
    new_folder_name = file_name + " Clips"
    new_folder_path = os.path.join(video_folder, new_folder_name)

    # Create the new folder if it doesn't exist
    if not os.path.exists(new_folder_path):
      os.makedirs(new_folder_path)

    # Loop for each clip
    for index, time in enumerate(events):
        # Skip some files...
        if index + 1 < flag_skip:
            continue

        starttime = float(events[index]['Position']) / 1000 + time_offset
        duration = float(events[index]['Duration']) / 1000 + 0.5  # Add 500ms at the end for a little buffer

        # Output name with leading zeros to 3 digits (001, 010, 100)
        output_file = f"Play_{index + 1:03d}.mp4"
        output_name = os.path.join(new_folder_path, output_file)

        # create a dartclip file from the events
        if flag_dartclip:
            create_dartclip(events[index], output_name)

        if flag_reencode == 0:
            # Copy video and audio
            cmd = [
                "ffmpeg",
                "-ss", str(starttime),
                "-t", str(duration),
                "-i", full_video_path,
                "-c:v", "copy",             # disable audio
                "-an",
                "-v", "quiet",
                "-hide_banner",
                output_name
            ]
        else:
            # With re-encoding to H264 (5K seems to be a major problem for laptop and DF)
            cmd = [
                "ffmpeg",
                "-y",  # Overwrite output if exists
                "-ss", str(starttime),
                "-t", str(duration),
                "-i", full_video_path,
                '-vf', '"crop=iw:ih-600"',  # Crop 300 from top and bottom
                "-bsf:v", "h264_mp4toannexb",
                "-preset", "slow",  # Slow for generally best results
                "-crf", "18",
                "-x264-params", "keyint=15:scenecut=0",  # (keyint=__ = no. of frames)
                "-vcodec", "libx264",
                "-acodec", "copy",
                "-hide_banner",
                output_name
            ]

        # run the prepared command (cmd) in a terminal
        subprocess.run(cmd)
    

def main_split_pipeline():
  
  # choose the file to be split (somehow)
  video_path, video_name = select_file(title="Choose the video file you want to cut")

  # choose the file containing split times
  times_path, times_name = select_file(title="Choose the csv file with the breakdown information")

  # combine to (re)create full path
  full_video_path = os.path.join(video_path, video_name)
  full_times_path = os.path.join(times_path, times_name)

  # get clip times from dartfish csv output
  events = extract_columns(full_times_path)

  # split into specified clips
  split_direct_cmd(full_video_path, events)
