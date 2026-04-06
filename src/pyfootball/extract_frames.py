"""Extract random frames from videos for analysis or training data."""

import random
import subprocess
import json
import os
import logging

logger = logging.getLogger('pyfootball.extract_frames')


def get_video_info(video_path):
    """Get video stream info via ffprobe."""
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-print_format', 'json',
        '-show_streams',
        video_path
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return json.loads(result.stdout)


def get_video_files_from_folder(folder_path, extensions=None, filter_text=None):
    """
    Recursively find video files in a folder.

    Args:
        folder_path: Root folder to search.
        extensions: List of extensions to match (default: ['.mp4']).
        filter_text: Optional string that must appear in filename.

    Returns:
        List of matching video file paths.
    """
    if extensions is None:
        extensions = ['.mp4']

    video_files = []
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if any(file.lower().endswith(ext) for ext in extensions):
                if filter_text is None or filter_text in file:
                    video_files.append(os.path.join(root, file))
    return video_files


def extract_random_frames(video_path, output_dir, num_frames=50, presnap_flag=True):
    """
    Extract random frames from a video.

    Args:
        video_path: Path to the video file.
        output_dir: Directory to save extracted frames.
        num_frames: Number of frames to extract.
        presnap_flag: If True, only sample from the first 1/3 of the video.
    """
    video_info = get_video_info(video_path)

    if video_info is None:
        print(f"Skipping {video_path} due to ffprobe error.")
        return

    total_frames = int(video_info['streams'][0]['nb_frames'])
    avg_frame_rate_str = video_info['streams'][0]['avg_frame_rate']
    num, denom = avg_frame_rate_str.split('/')
    avg_frame_rate = float(num) / float(denom)

    video_name = os.path.splitext(os.path.basename(video_path))[0]

    if presnap_flag:
        total_frames = total_frames // 3
        random_frames = [1]
        random_frames += random.sample(range(2, total_frames + 1), num_frames - 1)
    else:
        random_frames = random.sample(range(1, total_frames + 1), num_frames)

    random_frames.sort()

    for i, frame_num in enumerate(random_frames):
        time_sec = frame_num / avg_frame_rate
        output_file = os.path.join(output_dir, f"{video_name}_frame_{i + 1}.png")
        cmd = [
            'ffmpeg',
            '-ss', str(time_sec),
            '-i', video_path,
            '-vframes', '1',
            output_file
        ]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
