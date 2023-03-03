#!/usr/bin/env python

# system tools
import os
import glob

# nice wrapper for direct ffmpeg functions (must have ffmpeg installed directly)
import ffmpeg

# --------------------------- #

# get the working directory
working_directory = os.path.dirname(os.path.realpath(__file__))

# define working path
base_path = r"F:\_In Processing\Game 6 - Winterthur\GP8"
working_path = os.path.join(base_path, r"Individual_Clips_GP8")

# get list of files
file_list = glob.glob(working_path + "**/*.mp4", recursive=True)

# probe video for info
video_info = ffmpeg.probe(file_list[0])
create_datetime = video_info['streams'][0]['tags']['creation_time']
video_duration = video_info['streams'][0]['duration'] # in seconds

# get date a time separately
create_date, create_time = create_datetime.split("T", 1)