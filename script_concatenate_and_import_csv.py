#!/usr/bin/env python

# system tools
import os
import glob
import csv
import subprocess
import re                       # regular expressions
import pandas as pd

# for the user selection of the path / file
from tkinter import Tk
from tkinter import filedialog


def define_paths_breakdown():
    base_path = r"F:\_In Processing"
    # on my laptop
    base_path = r"C:\Users\mense\AFC Zurich Renegades\Renegades General - Documents\Game_Film"
    # on my desktop
    base_path = r"F:\AFC Zurich Renegades\Renegades General - Documents\Game_Film"
    game_path = r"Gameday 04302023\NLA ZRvsGS"
    specific_path = r"Full game zoomed"
    working_path = os.path.join(base_path, game_path, specific_path)

    # Check existence
    if os.path.exists(working_path) == False:
        print("Error - File: " + working_path + " doesn't exist")
    else:
        print("Found it! " + working_path)


# OR user selection
def select_file():
    # Create an instance of Tkinter's Tk class
    root = Tk()

    # Hide the main window of Tkinter
    root.withdraw()

    # Open a dialog for file selection
    selected_folder = filedialog.askdirectory()

    # Return the selected file path and name
    return selected_folder


def make_filelist(working_path):
    # get all the mp4 files (with "Clip" in the name)
    file_list = glob.glob(working_path + "**/*DJI*.mp4", recursive=True)
    len(file_list)

    # write list as text file for later reference with concat
    with open(os.path.join(working_path, "mp4_list.txt"), "w") as output:
        output.writelines("file '%s'\n" % item for item in file_list)

    return file_list


def get_video_duration(working_path, file_list):

    clip_times_path = os.path.join(working_path, "clip_times.csv")

    # is ffmpeg-python installed?
    flag_ffmpeg = 0

    # loop over each file and get its duration
    video_duration = []
    video_name = []
    for file in file_list:

        video_name.append("clip "+ str(file_list.index(file)+1))

        if flag_ffmpeg == 1:
            video_info = ffmpeg.probe(file)
            video_duration.append(float(video_info['streams'][0]['duration'])) # in seconds

        else:
            # call ffprobe on the command line to find duration          
            ffprobe_cmd = ["ffprobe", 
                "-v", "error", 
                "-show_entries", "format=duration", 
                "-of", "default=noprint_wrappers=1:nokey=1", 
                "-i", file]
            output = subprocess.check_output(ffprobe_cmd, stderr=subprocess.STDOUT)

            # Convert the duration string to a float
            video_duration.append(float(output))

    # add durations to get each clip start time
    video_starttime = []
    video_starttime.append(float(0))
    for item in range(0, video_duration.__len__()-1):
        video_starttime.append(video_starttime[item] + video_duration[item])

    # write start time (i.e. clip position) and duration to csv file for DF import
    # combine the lists into a list of tuples
    rows = list(zip(video_name, video_starttime, video_duration))
    # open the output CSV file and write the data
    with open(clip_times_path, 'w', newline='') as csv_file:
        
        # using csv.writer method from CSV package
        write = csv.writer(csv_file)
        # write the header row
        write.writerow(['Name','Position', 'Duration'])

        for row in rows:
            write.writerow(row)


def concatenate_video(working_path):
    # concatenate the video

    # file with list of clips
    clips_file_path = os.path.join(working_path, "mp4_list.txt")
    output_file_path = os.path.join(working_path, "combined_clips.mp4")

    # Create a command string to concatenate the videos using ffmpeg
    ffmpeg_cmd = (
        'ffmpeg -hide_banner -loglevel error -y '
        '-f concat -safe 0 -i \"{}\" '
        '-map 0:v -c:v copy '
        '\"{}\"'
    ).format(clips_file_path, output_file_path)

    subprocess.run(ffmpeg_cmd, shell=True)


def merge_df_hudl():

    # save the xlsx file from hudl to csv manually (otherwise missing dependencies in pandas)
    hudl_export_path = r"Gameday 04302023\NLA ZRvsGS\hudl_export.csv"
    hudl_export_path = os.path.join(base_path, hudl_export_path)

    output_file_path = os.path.join(base_path, r"Gameday 04302023\NLA ZRvsGS\ready4DF.csv")

    # read in the csv and excel files as pandas dataframes
    clip_times = pd.read_csv(clip_times_path)
    hudl_export = pd.read_csv(hudl_export_path)

    # check that they have the same number of rows
    if len(clip_times) == len(hudl_export):
        # merge the two dataframes horizontally (i.e. add columns to the right)
        merged_df = pd.concat([clip_times, hudl_export], axis=1)
        
        # save the merged dataframe as a csv file
        merged_df.to_csv(output_file_path, index=False)
    else:
        print("Error: clip_times.csv and hudl_export.xlsx have different number of rows.")


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