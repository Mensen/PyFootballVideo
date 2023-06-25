#!/usr/bin/env python

# system tools
import os
import glob
import csv
import subprocess
# nice wrapper for direct ffmpeg functions (must have ffmpeg installed directly)
# import ffmpeg
import time # just for timing processes and testing

from tkinter import Tk, filedialog

# --------------------------- #


def specify_folder():
    base_path = r"F:\_In Processing"
    base_path = r"F:\AFC Zurich Renegades\Renegades General - Documents\Game_Film\Gameday 04302023"
    game_path = r"Gameday 04302023\NLA ZRvsGS"
    specific_path = r"Full game zoomed"
    working_path = os.path.join(base_path, game_path, specific_path)

    return working_path


def select_folder():
    # Create an instance of Tkinter's Tk class
    root = Tk()

    # Hide the main window of Tkinter
    root.withdraw()

    # Open a dialog for folder selection
    selected_folder = filedialog.askdirectory()

    # Check if the user clicked "Cancel"
    if not selected_folder:
        print("No folder selected.")
        return None
    
    # Normalize the selected folder path
    selected_folder = os.path.normpath(selected_folder)

    # Return the selected folder path
    return selected_folder


def make_filelist(video_path, search_term=None, output_filename="mp4_filelist.txt"):
    # Get all the mp4 files in the directory
    file_list = glob.glob(os.path.join(video_path, "*.mp4"))

    # Filter the file list based on the search term if provided
    if search_term:
        file_list = [file for file in file_list if search_term in os.path.basename(file)]

    # Write list as a text file for later reference with concatenation
    output_file = os.path.join(video_path, output_filename)
    with open(output_file, "w") as output:
        output.writelines("file '%s'\n" % item for item in file_list)

    return file_list


def get_video_duration(file_list):
    video_duration = []
    video_name = []

    total_files = len(file_list)  # Total number of files to process
    processed_files = 0  # Counter for processed files

    for file in file_list:
        video_name.append("play " + str(file_list.index(file) + 1))

        try:
            # Run ffprobe command to get video duration
            command = ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=duration', '-of', 'default=noprint_wrappers=1:nokey=1', file]
            result = subprocess.run(command, capture_output=True, text=True)
            duration = float(result.stdout.strip())
            video_duration.append(duration)
        except Exception as e:
            print(f"Error processing {file}: {str(e)}")

        processed_files += 1  # Increment processed files count
        progress = processed_files / total_files * 100  # Calculate progress percentage
        print(f"\rProgress: {progress:.2f}%", end='', flush=True)  # Print progress update, overwriting the previous line

    print()  # Print a newline after the progress updates

    return video_duration, video_name


def calculate_video_starttime(video_duration):
    video_starttime = [0.0]  # Initialize with 0 as the first start time

    for duration in video_duration[:-1]:
        previous_start_time = video_starttime[-1]
        start_time = previous_start_time + duration
        video_starttime.append(start_time)

    return video_starttime


def write_clip_times_to_csv(working_path, video_name, video_starttime, video_duration):
    # Prepare the rows for the CSV file
    rows = zip(video_name, video_starttime, video_duration)

    # Open the CSV file for writing
    with open(os.path.join(working_path, "clip_times.csv"), 'w', newline='') as f:
        # Create a CSV writer
        writer = csv.writer(f)
        
        # Write the header row
        writer.writerow(['Name', 'Position', 'Duration'])

        # Write the rows
        for row in rows:
            writer.writerow(row)


def concatenate_video(video_path, output_name=None, input_file=None):
    # Concatenate the video

    if output_name is None:
        output_name = os.path.join(video_path, "Concatenated_Video.mp4")

    if input_file is None:
        input_file = os.path.join(video_path, "mp4_list.txt")

    cmd = [
        "ffmpeg",                       # Command for FFmpeg
        "-f", "concat",                 # Input format: concatenate
        "-safe", "0",                   # Disable safety check for input file
        "-i", input_file,               # Input file
        "-map", "0:v",                  # Map video stream
        "-vcodec", "copy",              # Video codec: copy (no re-encoding)
        "-hide_banner",                 # Hide FFmpeg banner
        "-loglevel", "warning",         # Suppress FFmpeg output
        output_name                     # Output file name
    ]

    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True
    )

    # Process the output and display progress
    while True:
        output = process.stdout.readline()
        if output == '' and process.poll() is not None:
            break
        if output:
            # Check if the output contains progress information
            if "time=" in output:
                # Extract the time progress from the output
                time_progress = output.split("time=")[1].split()[0]
                print(f"Progress: {time_progress}", end='\r', flush=True)

    print("Video concatenation completed.")


def recode_video(working_path):

    # TODO: Completely refactor with chatGPT
    
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


def main_pipeline():
    
    # choose the file to be split (somehow)
    video_path = select_folder()

    file_list = make_filelist(video_path, output_filename="mp4_list.txt")

    # calculate the duration of each clip
    video_duration, video_name = get_video_duration(file_list)
    video_starttime = calculate_video_starttime(video_duration)

    # write the csv file for DartFish
    write_clip_times_to_csv(video_path, video_name, video_starttime, video_duration)

    # create a new video of all clips together
    concatenate_video(video_path)