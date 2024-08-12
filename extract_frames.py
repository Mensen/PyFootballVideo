import random
import subprocess
import json
import os

# own tools
from utils.pf_helpers import select_folder
from utils.pf_helpers import select_file


def get_video_info(video_path):
    # use the subprocess and ffmpeg (ie ffprobe) to get the video info
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-print_format', 'json',
        '-show_streams',
        video_path
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return json.loads(result.stdout)

def get_video_files_from_folder(folder_path, extensions=['.mp4'], filter_text=None):
    video_files = []
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if any(file.lower().endswith(ext) for ext in extensions):
                if filter_text is None or filter_text in file:
                    video_files.append(os.path.join(root, file))
    return video_files


def extract_random_frames(video_path, output_dir, num_frames=50, presnap_flag=True):
    # Create the second filename by replacing "Endzone" with "Sideline"
    # note, both sideline and endzone video must be synchronised
    # sideline_video_path = video_path.replace("Endzone", "Sideline")
    
    # Get video info using ffmpeg command
    video_info = get_video_info(video_path)

    if video_info is None:
        print(f"Skipping {video_path} due to ffprobe error.")
        return

    total_frames = int(video_info['streams'][0]['nb_frames'])
    avg_frame_rate_str = video_info['streams'][0]['avg_frame_rate']
    num, denom = avg_frame_rate_str.split('/')
    avg_frame_rate = float(num) / float(denom)

    # Get the base name of the video file without extension
    video_name = os.path.splitext(os.path.basename(video_path))[0]

    # if we want to focus on the presnap phase, we'll crudely take frames from the first 1/3 of video
    if presnap_flag:
        total_frames = total_frames // 3
        # Ensure the first frame is included
        random_frames = [1]
        random_frames += random.sample(range(2, total_frames + 1), num_frames - 1)
    else:
        random_frames = random.sample(range(1, total_frames + 1), num_frames)
        
    random_frames.sort()

    # Extract frames using ffmpeg
    for i, frame_num in enumerate(random_frames):
        time_sec = frame_num / avg_frame_rate
        output_file = f"{output_dir}/{video_name}_frame_{i + 1}.png"
        cmd = [
            'ffmpeg',
            '-ss', str(time_sec),
            '-i', video_path,
            '-vframes', '1',
            output_file
        ]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


if __name__ == "__main__":

    # can either select frames for a single file, or subset of videos in a folder
    video_mode = "folder"
    use_subset = True  # Set to False to use all files, True to use a subset
    subset_size = 30  # Number of video files to process if using a subset

    # where to save the resulting images
    output_directory = select_folder(title="Choose the folder to save the images")

    if video_mode == "file":
        # single video breakdown
        video_dir, video_name = select_file(title="Choose the video file you want to cut")
        video_path = os.path.join(video_dir, video_name)

        extract_random_frames(video_path, output_directory)

    else:
        # videos in a folder breakdown
        folder_path = select_folder("Choose the folder where the video clips are located")

        filter_text = 'Endzone'  # Set this to None if no filtering is needed
        video_files = get_video_files_from_folder(folder_path, filter_text=filter_text)
    
        if use_subset:
            # Ensure the subset size does not exceed the number of available video files
            subset_size = min(subset_size, len(video_files))
            # Randomly select a subset of video files
            video_files = random.sample(video_files, subset_size)

        for video_path in video_files:
            extract_random_frames(video_path, 
                                  output_directory, 
                                  num_frames=3, 
                                  presnap_flag=True)