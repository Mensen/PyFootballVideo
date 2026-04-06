"""
Concatenate video clips and generate timing CSV.

Reverse workflow: join individual clips into a single video with a timing
CSV for re-import into Dartfish.
"""

import os
import glob
import csv
import subprocess
import logging

logger = logging.getLogger('pyfootball.concatenate')


def make_filelist(video_path, search_term=None, output_filename="mp4_filelist.txt"):
    """
    Create an FFmpeg concat demuxer filelist from MP4s in a folder.

    Args:
        video_path: Folder containing MP4 files.
        search_term: Optional filter string for filenames.
        output_filename: Name of the generated filelist.

    Returns:
        Sorted list of matching MP4 file paths.
    """
    file_list = sorted(glob.glob(os.path.join(video_path, "*.mp4")))

    if search_term:
        file_list = [f for f in file_list if search_term in os.path.basename(f)]

    output_file = os.path.join(video_path, output_filename)
    with open(output_file, "w") as output:
        output.writelines("file '%s'\n" % item for item in file_list)

    return file_list


def get_video_duration(file_list):
    """
    Get duration of each video file using ffprobe.

    Args:
        file_list: List of video file paths.

    Returns:
        tuple: (durations, names) - lists of durations in seconds and play names.
    """
    video_duration = []
    video_name = []

    total_files = len(file_list)
    processed_files = 0

    for file in file_list:
        video_name.append("play " + str(file_list.index(file) + 1))

        try:
            command = [
                'ffprobe', '-v', 'error', '-select_streams', 'v:0',
                '-show_entries', 'stream=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1', file
            ]
            result = subprocess.run(command, capture_output=True, text=True)
            duration = float(result.stdout.strip())
            video_duration.append(duration)
        except Exception as e:
            print(f"Error processing {file}: {str(e)}")

        processed_files += 1
        progress = processed_files / total_files * 100
        print(f"\rProgress: {progress:.2f}%", end='', flush=True)

    print()
    return video_duration, video_name


def calculate_video_starttime(video_duration):
    """Calculate cumulative start times from a list of durations."""
    video_starttime = [0.0]
    for duration in video_duration[:-1]:
        video_starttime.append(video_starttime[-1] + duration)
    return video_starttime


def write_clip_times_to_csv(working_path, video_name, video_starttime, video_duration):
    """Write clip timing data to a CSV file."""
    rows = zip(video_name, video_starttime, video_duration)

    with open(os.path.join(working_path, "clip_times.csv"), 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Name', 'Position', 'Duration'])
        for row in rows:
            writer.writerow(row)


def concatenate_video(video_path, output_name=None, input_file=None):
    """
    Concatenate video clips using FFmpeg concat demuxer.

    Args:
        video_path: Folder containing the clips.
        output_name: Output file path. Defaults to Concatenated_Video.mp4.
        input_file: Path to concat filelist. Defaults to mp4_list.txt.
    """
    if output_name is None:
        output_name = os.path.join(video_path, "Concatenated_Video.mp4")

    if input_file is None:
        input_file = os.path.join(video_path, "mp4_list.txt")

    cmd = [
        "ffmpeg",
        "-f", "concat",
        "-safe", "0",
        "-i", input_file,
        "-map", "0:v",
        "-vcodec", "copy",
        "-hide_banner",
        "-loglevel", "warning",
        output_name
    ]

    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True
    )

    while True:
        output = process.stdout.readline()
        if output == '' and process.poll() is not None:
            break
        if output:
            if "time=" in output:
                time_progress = output.split("time=")[1].split()[0]
                print(f"Progress: {time_progress}", end='\r', flush=True)

    print("Video concatenation completed.")
