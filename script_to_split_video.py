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

# import scenedetect # pip install scenedetect[opencv] --upgrade
  # bug in v0.6.0 so had to setup.py from git cloned master branch
# from scenedetect import detect, AdaptiveDetector, ContentDetector, video_splitter
import scenedetect

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



def split_direct_cmd():
  # ffmpeg -ss 00:00:01.1 -noaccurate_seek -i Game6WW_GP8.mp4 -t 00:00:02.003 -c copy output.mp4
  
  # default behaviour
  flag_skip = 0
  flag_reencode = 0
  # times offset? Trimmed video should aim to be 5s before actual kickoff (ball contact)
  offset = 0

  # open the file with the clip times and durations
  with open(times_file, 'r', encoding='utf-8-sig') as file: #utf-8-sig is required to eliminate the "ï»¿" in the first list item
    reader = csv.reader(file, delimiter=",")
    times = list(reader)
  # check for common header and delete if there
  if times[0][0]=='Position':
    times.pop(0)

  # change to mp4 directory
  # TODO: test fullpath scheme instead
  os.chdir(os.path.join(base_path, game_path, specific_path))

  # loop for each clip
  for time in times:
    
    # skip some files...
    if(times.index(time))+1 < flag_skip:
      continue
    
    starttime = float(time[0]) / 1000 + offset
    duration = float(time[1]) / 1000 + 0.5            # add 500ms at the end for a little buffer

    # output name with leading zeros to 3 digits (001, 010, 100)
    output_name = '"' + base_output + "{:03d}".format(times.index(time)+1) + '.mp4"'
    
    if flag_reencode == 0:
      # copy video and audio
      cmd = ["ffmpeg" +
      " -ss " + str(starttime) +
      " -t " + str(duration) +
      " -i " + ('"' + video_file + '"') +
      " -c copy " +
      " -hide_banner " +
      output_name]
      
    else:
      # with re-encoding to H264 (5K seems to be a major problem for laptop and DF)    
      cmd = ["ffmpeg" +
      " -y " +                                        # overwrite output if exists
      " -ss " + str(starttime) +
      " -t " + str(duration) +
      " -i " + ('"' + video_file + '"') +
      #  " -s:v 3840x2160 " +                         # enable if a 5k recording (5k is too much for the laptop it seems)
      ' -vf "crop=iw:ih-600" ' +                      # crop 300 from top and bottom
      " -bsf:v h264_mp4toannexb " + 
      " -preset slow " +                              # slow for generally best results
      " -crf 18 " +
      # " -force_key_frames expr:gte(t,n_forced*0.5) -sc_threshold 0 " +  # (n_forced*__ = interval in seconds)
      " -x264-params keyint=15:scenecut=0"            # (keyint=__ = no. of frames)
      " -vcodec libx264 " + 
      " -acodec copy " + 
      # " -map 0:v:0" +
      " -hide_banner " +
      output_name]

    subprocess.run(cmd[0], shell=True)
    


def split_using_ffmpeg():
  # use the python version of ffmpeg to perform the split
  # NOTE: generally works much smoother to simply create a command line message to ffmpeg directly

  # open the csv file and read as a list
  with open(times_file, 'r', encoding='utf-8-sig') as file: #utf-8-sig is required to eliminate the "ï»¿" in the first list item
    reader = csv.reader(file, delimiter=",")
    times = list(reader)

  # check for common header and delete if there
  if times[0][0]=='Position':
    times.pop(0)

  # loop each time and trim file
  # should we also just convert right now rather than using handbrake later?
  for time in times:
    starttime = float(time[0]) + offset
    duration = float(time[1]) + offset
    endtime = (starttime + duration)
    process = (
      ffmpeg
      .input(video_file)
      .trim(start=starttime, end=endtime)
      .output(os.path.join(base_path, base_output, str(times.index(time)+1) + ".mp4"))
      .run()
    )



def ffmpeg_scenedetect(video_file):
  # ffmpeg inputvideo.mp4 -filter_complex "select='gt(scene,0.3)',metadata=print:file=time.txt" -vsync vfr img%03d.png
  # doesn't work well, misses cuts and makes random cuts at optimal threshold

  cmd = ["ffmpeg" +
      " -i " + ('"' + video_file + '"') +
      " -y " +                                        # overwrite output if exists
      " -filter_complex \"select='gt(scene,0.6)',metadata=print:file=time.txt\"" +
      " -vsync vfr img%03d.png" +
      " -hide_banner "]

  subprocess.run(cmd[0], shell=True)



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


def main_pipeline():
  
  # choose the file to be split (somehow)
  video_path, video_name = select_file()

  # combine to (re)create full path
  full_video_path = video_file = os.path.join(video_path, video_name)

  # get the scene list
  scene_list, scene_file = scene_detection(full_video_path)

  # save to a csv file for DF
  save_scene_list_to_csv(scene_list, scene_file)
