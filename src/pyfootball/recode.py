"""
Re-encode a video using one of the shared encoding presets.
"""

import os
import subprocess
import logging

from pyfootball.encoding import get_encoding_args

logger = logging.getLogger('pyfootball.recode')


def recode_video(video_path, video_name, adjust_framerate=False,
                 encoding_preset=None):
    """
    Re-encode a video with one of the encoding presets.

    Args:
        video_path: Directory containing the video.
        video_name: Filename of the video.
        adjust_framerate: If True, set output to 30fps.
        encoding_preset: Name from encoding.ENCODING_PRESETS. None = default.
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
        *get_encoding_args(encoding_preset),
        "-an",
    ]

    if adjust_framerate:
        cmd += ["-r", "30"]

    cmd.append(output_file)

    subprocess.run(cmd)
