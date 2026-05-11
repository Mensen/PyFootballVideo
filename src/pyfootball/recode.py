"""
Re-encode a video using the project's scrub-friendly all-intra settings.
"""

import os
import subprocess
import logging

from pyfootball.encoding import SCRUB_FRIENDLY_VIDEO_ARGS

logger = logging.getLogger('pyfootball.recode')


def recode_video(video_path, video_name, adjust_framerate=False):
    """
    Re-encode a video with all-intra H.264 for frame-accurate scrubbing.

    Args:
        video_path: Directory containing the video.
        video_name: Filename of the video.
        adjust_framerate: If True, set output to 30fps.
    """
    input_file = os.path.join(video_path, video_name)
    output_name = os.path.splitext(video_name)[0] + "_intra.mp4"
    output_file = os.path.join(video_path, output_name)

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        "-y",
        "-i", input_file,
        *SCRUB_FRIENDLY_VIDEO_ARGS,
        "-an",
    ]

    if adjust_framerate:
        cmd += ["-r", "30"]

    cmd.append(output_file)

    subprocess.run(cmd)
