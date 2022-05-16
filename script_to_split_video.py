#!/usr/bin/env python

from moviepy.video.io.ffmpeg_tools import ffmpeg_extract_subclip

# Replace the filename below.
required_video_file = "G4 GP9.mp4"

with open("times.txt") as f:
  times = f.readlines()

times = [x.strip() for x in times] 

for time in times:
  starttime = float(time.split(",")[0])
  duration = float(time.split(",")[1])
  endtime = (starttime + duration)
  ffmpeg_extract_subclip(
    required_video_file, 
    starttime, 
    endtime, 
    targetname="play "+str(times.index(time)+1)+" GP9.mp4")

    