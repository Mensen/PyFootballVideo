#!/usr/bin/env python

import os
import glob
import csv
import subprocess
import numpy as np

# plotting tools
import pandas as pd
import matplotlib.pyplot as plt 

# use OpenCV for multimedia edits
import cv2

# for the user selection of the path / file
from tkinter import Tk
from tkinter import filedialog


def define_paths_breakdown():
  base_path = r"C:\Users\mensen\Bern Grizzlies\Coaches - Documents"
  game_path = r"NCAA Film\YoutubeBreakdowns"

  base_path = r"F:\Gamepass_Clips"
  base_path = r"F:\NCAA"
  game_path = r""
  
  video_name = "TestClip_BillsChiefs_DR_2021"
  video_name = "CoachesTape - 22 01 Florida O vs Utah"

  full_video_path = os.path.join(base_path, game_path, video_name + ".mp4")

  # Check existence
  if os.path.exists(full_video_path) == False:
    print("Error - File: " + full_video_path + " doesn't exist")
  else:
     print("Found it! " + full_video_path)


# OR user selection
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


def playing_video(video_file, start_frame, end_frame):
  # TODO: do something useful with this code
  
  start_frame = 4738
  end_frame = 6283
  
  # load video file
  cap = cv2.VideoCapture(video_file)
  
  cap.get(cv2.CAP_PROP_FPS)

  # check if camera opened successfully
  if (cap.isOpened()== False):
      print("Error opening video file")

  # set start frame
  cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
  
  # read until video is completed
  while(cap.isOpened()):
      
  # Capture frame-by-frame
      ret, frame = cap.read()

      # get current frame 
      c_frame = cap.get(cv2.CAP_PROP_POS_FRAMES)

      if c_frame == end_frame:
        break

      if ret == True:
      # Display the resulting frame
          cv2.imshow('Frame', frame)
          
      # Press Q on keyboard to exit
          if cv2.waitKey(1) & 0xFF == ord('q'):
              break
  
  # Break the loop
      else:
          break
  
  # When everything done, release
  # the video capture object
  cap.release()
  
  # Closes all the frames
  cv2.destroyAllWindows()

  ret, frame = cap.read()

  # release video object
  cap.release()
  cv2.destroyAllWindows()


def extract_columns(full_times_path):
    positions = []
    durations = []

    with open(full_times_path, 'r') as file:
        reader = csv.DictReader(file)

        # Check if the required columns exist in the CSV file
        if 'Position' not in reader.fieldnames or 'Duration' not in reader.fieldnames:
            raise ValueError("The 'Position' and 'Duration' columns are required but not found in the CSV file.")

        # Iterate over each row in the CSV file
        for row in reader:
            # Extract the values from the 'Position' and 'Duration' columns           
            position = row['Position']
            duration = row['Duration']
            positions.append(position)
            durations.append(duration)

    return positions, durations


def split_direct_cmd(full_video_path, positions, durations):
    # Default behavior
    flag_skip = 0
    flag_reencode = 0
    # Times offset? Trimmed video should aim to be 5s before actual kickoff (ball contact)
    offset = 0

    # Where should the clips go?
    video_folder = os.path.dirname(full_video_path)

    # Loop for each clip
    for index, time in enumerate(positions):
        # Skip some files...
        if index + 1 < flag_skip:
            continue

        starttime = float(positions[index]) / 1000 + offset
        duration = float(durations[index]) / 1000 + 0.5  # Add 500ms at the end for a little buffer

        # Output name with leading zeros to 3 digits (001, 010, 100)
        output_name = os.path.join(video_folder, f"play_{index + 1:03d}.mp4")

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

        subprocess.run(cmd)
    

def get_creation_time():
  # function to extract video creation times to use for splitting continuous files
  # e.g. one video angle used stop/start recording but others were continuous, so the creation times could serve to cut the others.

  # TODO: finish this code
  # get list of files
  file_list = glob.glob(sony_path + "**/*.mp4", recursive=True)

  video_duration = []
  video_createtimes = []
  for file in file_list:
    # probe video for info
    video_info = ffmpeg.probe(file)
    video_duration.append(video_info['streams'][0]['duration']) # in seconds

    create_datetime = video_info['streams'][0]['tags']['creation_time']
    # get date a time separately
    create_date, create_time = create_datetime.split("T", 1)
    create_time = create_time[0:-1]
    time_object = datetime.datetime.strptime(create_time, "%H:%M:%S.%f")


def main_split_pipeline():
  
  # choose the file to be split (somehow)
  video_path, video_name = select_file()

  # choose the file containing split times
  times_path, times_name = select_file()

  # combine to (re)create full path
  full_video_path = os.path.join(video_path, video_name)
  full_times_path = os.path.join(times_path, times_name)

  # get clip times from dartfish csv
  positions, durations = extract_columns(full_times_path)

  # split into specified clips
  split_direct_cmd(full_video_path, positions, durations)
