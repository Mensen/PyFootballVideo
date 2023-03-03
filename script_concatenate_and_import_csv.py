#!/usr/bin/env python

# system tools
import os
import glob
import csv
import subprocess
# nice wrapper for direct ffmpeg functions (must have ffmpeg installed directly)
import ffmpeg
import time # just for timing processes and testing

# --------------------------- #

# define working path
# base_path = r"E:\one_drive\Bern Grizzlies\Coaches - Documents\NLA Game Film"
# specific_path = r"Game 5 - Calanda\Sony"

base_path = r"F:\_In Processing"
game_path = r"Game 10 - Zurich"
specific_path = r"GP9\IndividualClips"
working_path = os.path.join(base_path, game_path, specific_path)



def make_filelist(working_path):
    # get all the mp4 files (with "Clip" in the name)
    file_list = glob.glob(working_path + "**/*Clip*.mp4", recursive=True)

    # write list as text file for later reference with concat
    with open(os.path.join(working_path, "mp4_list.txt"), "w") as output:
        output.writelines("file '%s'\n" % item for item in file_list)


def get_video_duration(file_list):
    # loop over each file and get its duration
    video_duration = []
    video_name = []
    for file in file_list:

        video_name.append("play "+ str(file_list.index(file)+1))
        video_info = ffmpeg.probe(file)
        video_duration.append(float(video_info['streams'][0]['duration'])) # in seconds

    # check video length    
    # video_duration.__len__()

    # add durations to get each clip start time
    video_starttime = []
    video_starttime.append(float(0))
    for item in range(0, video_duration.__len__()-1):
        video_starttime.append(video_starttime[item] + video_duration[item])

    # write start time (i.e. clip position) and duration to csv file for DF import
    rows = zip(video_name, video_starttime, video_duration)
    with open(os.path.join(working_path, (game_path + " - clip_times.csv")), 'w', newline='') as f:
        
        # using csv.writer method from CSV package
        write = csv.writer(f)
        write.writerow(['Name','Position', 'Duration'])
        for row in rows:
            write.writerow(row)


def concatenate_video(working_path):
    # concatenate the video

    #https://github.com/kkroening/ffmpeg-python/issues/137
    (
        ffmpeg
        .input(os.path.join(working_path, "mp4_list.txt"), format='concat', safe=0)
        .output(os.path.join(working_path, 'concatenated_video.mp4'), map='0:0', vcodec = "copy")
        .run()
    )

    # ffmpeg -f concat -safe 0 -i mp4_list.txt -c copy Game6WW_GP8.mp4
    (
        ffmpeg
        .input(os.path.join(working_path, "mp4_list.txt"), format='concat', safe=0)
        .output(os.path.join(working_path, 'concatenated_video.mp4'), vcodec = "copy")
        .run()
    )

    # or call ffmpeg directly (might be faster, still to be tested)
    # ffmpeg -f concat -safe 0 -i temp_files.txt -c copy concatenated_video.mp4

    output_name = '"' + os.path.join(working_path, (game_path + " - Clipped Test GP9.mp4")) + '"'
    cmd = ["ffmpeg " +
    "-f concat " +
    "-safe 0 " +
    "-i " + '"' + os.path.join(working_path, "mp4_list.txt") + '" '
    "-map 0:v " +
    "-vcodec copy " +
    "-hide_banner " +
    output_name] 
    subprocess.run(cmd[0], shell=True)


def recode_video(working_path):
    
    video_file = game_path + " - Full GP9.mp4"
    required_video_file = os.path.join(working_path, video_file)
    
    # use ffplay to preview some options
    cmd = ["ffplay " + 
    ' -vf "crop=iw:ih-600, scale=1280:-1" ' + 
    ('"' + required_video_file + '"')]
    subprocess.run(cmd[0], shell=True)


    # fastest encoding to DF compatible
    output_name = '"' + os.path.join(working_path, (game_path + " - Small.mp4")) + '"'
    cmd = ["ffmpeg" +
    " -i " + ('"' + required_video_file + '"') +
    ' -vf "crop=iw:ih-300, scale=1280:-1" ' +       # crop the useless top and bottom of video off and downscale to 1280
    " -r 30 " +                                     # reduce framerate
    " -preset ultrafast " + 
    " -crf 25 " +                                   # general quality 0 (best) - 51 (worst)
    " -vcodec libx264" + 
    " -acodec copy" +
    " -hide_banner " +
    output_name]
    subprocess.run(cmd[0], shell=True)


    # or to "final" H264 video 
    # (suboptimal if cut files can be recoded instead)
    output_name = '"' + os.path.join(working_path, (game_path + " - Small.mp4")) + '"'
    cmd = ["ffmpeg" +
    " -i " + ('"' + required_video_file + '"') +
    " -vcodec libx264 -preset slow -crf 18 -acodec copy" +
    " -hide_banner " +
    output_name]
    subprocess.run(cmd[0], shell=True)

