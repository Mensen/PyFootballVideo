#!/usr/bin/env python

# system tools
import os
import glob
import csv

import subprocess

# nice wrapper for direct ffmpeg functions (must have ffmpeg installed directly)
import ffmpeg

# --------------------------- #

# define working path
# base_path = r"E:\one_drive\Bern Grizzlies\Coaches - Documents\NLA Game Film"
# specific_path = r"Game 5 - Calanda\Sony"

base_path = r"C:\temp\Calanda"
specific_path = r"GP9"

working_path = os.path.join(base_path, specific_path)

# get all the mp4 files
file_list = glob.glob(working_path + "**/*.mp4", recursive=True)

# write list as text file for later reference with concat
with open(os.path.join(working_path, "mp4_list.txt"), "w") as output:
    output.writelines("file '%s'\n" % item for item in file_list)


# loop over each file and get its duration
video_duration = []
for file in file_list:

    video_info = ffmpeg.probe(file)
    video_duration.append(float(video_info['streams'][0]['duration'])) # in seconds

video_duration.__len__()

# add durations to get each clip start time
video_starttime = []
video_starttime.append(float(0))
for item in range(0, video_duration.__len__()-1):
    video_starttime.append(video_starttime[item] + video_duration[item])

# write start time (i.e. clip position) and duration to csv file for DF import
rows = zip(video_starttime, video_duration)
with open(os.path.join(working_path, "import_4DF.csv"), 'w', newline='') as f:
      
    # using csv.writer method from CSV package
    write = csv.writer(f)
    
    write.writerow(['Position', 'Duration'])

    for row in rows:
        write.writerow(row)


# concatenate the video

""" v1 = ffmpeg.input(file_list[0]).video
v2 = ffmpeg.input(file_list[1]).video
(
    ffmpeg
    .concat(v1, v2)
    .output('concatenated_video.mp4', codec = "copy")
    .run()
)

inputs = [ffmpeg.input(file) for file in file_list]
(
    ffmpeg
    .concat(*inputs)
    .output('concatenated_video.mp4', codec = "copy")
    .run()
) """

#https://github.com/kkroening/ffmpeg-python/issues/137
(
    ffmpeg
    .input(os.path.join(working_path, "mp4_list.txt"), format='concat', safe=0)
    .output(os.path.join(working_path, 'concatenated_video.mp4'), map='0:0', vcodec = "copy")
    .run()
)