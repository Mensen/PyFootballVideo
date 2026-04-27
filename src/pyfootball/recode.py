"""
Re-encode video with keyframe interval optimized for Dartfish.

Sets keyint=15 so Dartfish can seek accurately to any play boundary.
"""

import os
import subprocess
import logging

logger = logging.getLogger('pyfootball.recode')


def recode_video(video_path, video_name, max_keyframe_distance=15,
                 adjust_framerate=False):
    """
    Re-encode a video with a fixed keyframe interval.

    Args:
        video_path: Directory containing the video.
        video_name: Filename of the video.
        max_keyframe_distance: Maximum frames between keyframes.
        adjust_framerate: If True, set output to 30fps.
    """
    input_file = os.path.join(video_path, video_name)
    output_name = os.path.splitext(video_name)[0] + "_kf15.mp4"
    output_file = os.path.join(video_path, output_name)

    cmd = [
        "ffmpeg",
        "-i", input_file,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-x264opts", f"keyint={max_keyframe_distance}:min-keyint=1:no-scenecut",
        "-c:a", "copy",
    ]

    if adjust_framerate:
        cmd += ["-r", "30"]

    cmd.append(output_file)

    subprocess.run(cmd)
