#!/usr/bin/env python

import os
import subprocess
# for the user selection of the path / file
from tkinter import Tk
from tkinter import filedialog


def select_file():
  # Create an instance of Tkinter's Tk class
  root = Tk()

  # Hide the main window of Tkinter
  root.withdraw()

  # Open a dialog for file selection
  selected_file = filedialog.askopenfilename()

  # Check if the user clicked "Cancel"
  if not selected_file:
    print("No file selected.")
    return None, None

  # Split the file path and name
  file_path, file_name = os.path.split(selected_file)

  # Return the selected file path and name
  return file_path, file_name


def process_video(video_path, video_name, max_keyframe_distance=15, adjust_framerate=False):
    
    # Output file path in the same folder with "_kf15" appended
    output_file = os.path.join(video_path, f"{video_name}_kf15.mp4")

    cmd = [
        "ffmpeg",
        "-i", video_path,
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-x264opts", f"keyint={max_keyframe_distance}:min-keyint=1:no-scenecut",
        "-c:a", "copy",
    ]

    if adjust_framerate:
        cmd += ["-r", "30"]  # Adjust the framerate to 30fps

    cmd.append(output_file)

    subprocess.run(cmd)


def main_recode_pipeline():
    # Choose the file to be split
    video_path, video_name = select_file()

    # Specify the maximum keyframe distance (optional, as it has a default value)
    max_keyframe_distance = 15

    # Adjust framerate option
    adjust_framerate = False  # Set to True to adjust framerate, False otherwise

    # Process the video with specified parameters
    process_video(video_path, video_name, max_keyframe_distance, adjust_framerate)


