#!/usr/bin/env python

import os
import glob
import csv
import subprocess
import numpy as np
import pickle

# plotting tools
import pandas as pd
import matplotlib.pyplot as plt 

# use OpenCV for multimedia edits
import cv2

# import scenedetect # pip install scenedetect[opencv] --upgrade
  # bug in v0.6.0 so had to setup.py from git cloned 0.6.1 branch
# from scenedetect import detect, AdaptiveDetector, ContentDetector, video_splitter
import scenedetect



def define_paths_breakdown():
  base_path = r"C:\Users\mensen\Bern Grizzlies\Coaches - Documents"
  game_path = r"NCAA Film\YoutubeBreakdowns"

  base_path = r"F:\Gamepass_Clips"
  base_path = r"F:\NCAA"
  game_path = r""
  
  video_name = "TestClip_BillsChiefs_DR_2021"
  video_name = "CoachesTape - 22 01 Florida O vs Utah"

  video_file = os.path.join(base_path, game_path, video_name + ".mp4")

  # Check existence
  if os.path.exists(video_file) == False:
    print("Error - File: " + video_file + " doesn't exist")
  else:
     print("Found it! " + video_file)
      

def scene_detection(video_file):

  video_stream = scenedetect.open_video(video_file)
  stats_manager = scenedetect.StatsManager()
  scene_manager = scenedetect.SceneManager(stats_manager)

  scene_manager.add_detector(
    scenedetect.AdaptiveDetector(
    adaptive_threshold=5,                               # experimental value of 5 seems optimal
    window_width=5,                                     # average [int] frames before/after for running average 
    min_scene_len=20,                                   # at least 30 frames (0.5 seconds at 60fps)
    min_content_val=15))

  # indicate location of stats file
  stats_file = os.path.join(base_path, game_path, video_name+"_stats.csv")

  # detect the scenes using the defined settings
  scene_manager.detect_scenes(video=video_stream, show_progress=True)
  scene_list = scene_manager.get_scene_list()
 
  # print each scene in the terminal line-by-line 
  for i, scene in enumerate(scene_list):
    print(
      'Scene %2d: Start %s / Frame %.5d  ->  End %s / Frame %.5d' % (
      i+1,
      scene[0].get_timecode(), scene[0].get_frames(),
      scene[1].get_timecode(), scene[1].get_frames(),))

  # Store the frame metrics we calculated for the next time the program runs.
  stats_file_path = os.path.join(base_path, game_path, video_name + "_scenestats.csv")
  stats_manager.save_to_csv(csv_file=stats_file_path)

  


def scene_splitter(video_file, scene_manager):

  scene_list = scene_manager.get_scene_list()

  # NOTE: scene_list is a "two-column" list of start and end times (and frames) for each detected scene
  # get the starting/ending frames for each scene (in FrameTimeCode format native to PySceneDetect)
  # could also use .get_seconds() for the time 
  start_frames = np.array([row[0].get_frames() for row in scene_list])
  end_frames = np.array([row[1].get_frames() for row in scene_list])
  frame_rate = scene_list[0][0].get_framerate()
  scene_durations = np.divide(np.subtract(end_frames, start_frames), frame_rate)
  # print scene_durations
  for x in enumerate(scene_durations):
    print(x)

  # delete short scenes (not football plays)
  short_scenes = [idx for idx, val in enumerate(scene_durations) if val < 3]
  scene_list_cut = [element for i, element in enumerate(scene_list) if i not in short_scenes]

  # cut out every second scene for endzone only
  all22_scenes = scene_list_cut[0:-1:2]
  endzone_scenes = scene_list_cut[1:-1:2]             # first int should be either 0 or 1 / 3rd int is the space (e.g. 3 if scorebord present)
  for x in enumerate(endzone_scenes): 
    print(x)

  # split all video scenes with PySceneDetect
  scenedetect.video_splitter.split_video_ffmpeg(video_file, all22_scenes, output_file_template='$VIDEO_NAME-$SCENE_NUMBER-All22.mp4', show_progress=True)
  scenedetect.video_splitter.split_video_ffmpeg(video_file, endzone_scenes, output_file_template='$VIDEO_NAME-$SCENE_NUMBER-Endzone.mp4', show_progress=True)
  
  #TODO: specify output folder (currently does not work)
  output_dir = r'F:\Gamepass_Clips'
  output_template = os.path.join(os.path.join(output_dir,"Endzone-$SCENE_NUMBER.mp4"))
  print(output_template)
  scenedetect.video_splitter.split_video_ffmpeg(video_file, scene_list_cut,
    output_file_template=output_template)

  scenedetect.video_splitter.split_video_ffmpeg(video_file, scene_list[26:28], 
    output_file_template='Clip-$SCENE_NUMBER.mp4')


def explore_stats(video_file, scene_manager, video_stream):
  
  # you can get the metrics for any frame / metric 
  # 'adaptive_ratio (w=5)', 'content_val', 'delta_edges', 'delta_lum', 'delta_hue', 'delta_sat'
  x = scene_manager.stats_manager.get_metrics(922, ['adaptive ratio (w=5)'])[0]

  delta_edges = []
  for n in range(video_stream.frame_number):
    delta_edges.append(
      scene_manager.stats_manager.get_metrics(n, ['delta_edges'])[0])
  delta_edges = np.array(delta_edges, dtype=np.float64)
  edges_diff = np.diff(delta_edges, 1)
  edges_median = np.nanmedian(edges_diff)

  # plot the edge data and its differential 
  plt.plot(delta_edges)
  plt.plot(edges_diff, color='green')
  plt.show()

  # find where edges are 2x the median
  cut_indices = [idx for idx, val in enumerate(edges_diff) if val < 2*edges_median]


  # print stats for cut frames
  with open(stats_file, 'r') as f:
    stats_data = list(csv.reader(f, delimiter=";"))

  # print the stat lines for the "detected" scene cuts  
  for i in list(start_frames):
    print(stats_data[i])



def save_scene_list(video_file, scene_manager):
  # pickle/save the original scene list
  pickle_name = os.path.join(base_path, game_path, video_name+"_SceneManager.pkl")
  pickle_file = open(pickle_name, 'wb')
  pickle.dump(scene_manager, pickle_file)
  pickle_file.close()

  # load scene_list from pickled file
  tmp = open(pickle_name, 'rb')
  loaded_scene_list = pickle.load(tmp)
  tmp.close()





def playing_video(video_file, start_frame, end_frame):
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
    


def define_paths_Grizzlies():
  # Replace the filenames below.
  sony_path = r""

  base_path = r"F:\_In Processing"
  game_path = r"Game 11 - Basel at Calanda"
  specific_path = r""
  video_name = game_path + " - Livestream.mp4"
  video_file = os.path.join(base_path, game_path, specific_path, video_name)

  # split times should be saved with a comma delimination
  times_file = os.path.join(base_path, game_path, (game_path + " - PlayStarts.csv"))

  # output file base name
  base_output = game_path + " - " + specific_path + " - Clip " 



def split_using_ffmpeg():

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