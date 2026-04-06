"""
Automated scene boundary detection using PySceneDetect.

Detects play boundaries in game film where multiple camera angles are
interleaved (e.g. scoreboard, all-22, endzone).
"""

import os
import csv
import logging

import scenedetect as sd

logger = logging.getLogger('pyfootball.scenedetect')


def scene_detection(full_video_path):
    """
    Detect scene boundaries in a video using adaptive detection.

    Args:
        full_video_path: Path to the video file.

    Returns:
        tuple: (scene_list, scene_file_path)
    """
    file_path, file_name = os.path.split(full_video_path)
    video_name = os.path.splitext(file_name)[0]

    stats_file = os.path.join(file_path, video_name + "_stats.csv")
    scene_file = os.path.join(file_path, video_name + "_scene.csv")

    video_stream = sd.open_video(full_video_path)
    stats_manager = sd.StatsManager()
    scene_manager = sd.SceneManager(stats_manager)

    scene_manager.add_detector(
        sd.AdaptiveDetector(
            adaptive_threshold=5,
            window_width=5,
            min_scene_len=20,
            min_content_val=15))

    scene_manager.detect_scenes(video=video_stream, show_progress=True)
    scene_list = scene_manager.get_scene_list()

    stats_manager.save_to_csv(csv_file=stats_file)

    return scene_list, scene_file


def print_scene_info(scene_list):
    """Print each detected scene to the terminal."""
    for i, scene in enumerate(scene_list):
        print(
            'Scene %2d: Start %s / Frame %.5d  ->  End %s / Frame %.5d -> Duration %s' % (
                i + 1,
                scene[0].get_timecode(), scene[0].get_frames(),
                scene[1].get_timecode(), scene[1].get_frames(),
                [scene[1].get_frames() - scene[0].get_frames()]))


def save_scene_list_to_csv(scene_list, csv_file, angle_count=3):
    """
    Save detected scenes to a CSV file with angle labels.

    Args:
        scene_list: List of scene tuples from PySceneDetect.
        csv_file: Output CSV path.
        angle_count: Number of camera angles per play (2 or 3).
    """
    if angle_count == 2:
        angle_values = ["All 22", "Endzone"]
    else:
        angle_values = ["Score Board", "All 22", "Endzone"]

    angle_index = 0

    with open(csv_file, 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['Name', 'Start Time', 'End Time', 'Duration', 'Angle'])

        count = 1
        for i, scene in enumerate(scene_list, start=1):
            start_time = scene[0].get_frames() / scene[0].get_framerate()
            end_time = scene[1].get_frames() / scene[0].get_framerate()
            duration_seconds = end_time - start_time

            angle_value = angle_values[angle_index]
            angle_index = (angle_index + 1) % len(angle_values)

            writer.writerow([f"Play {count}", start_time, end_time, duration_seconds, angle_value])

            if i % angle_count == 0:
                count += 1

    print(f"Scene list has been saved to {csv_file}.")


def filter_expected_scenes(scene_list):
    """
    Filter scenes matching the expected pattern: short scene followed by
    two longer ones of similar duration.
    """
    expected_scenes = []

    for i in range(len(scene_list) - 2):
        scene_a = scene_list[i]
        scene_b = scene_list[i + 1]
        scene_c = scene_list[i + 2]

        if is_expected_scene_pattern(scene_a, scene_b, scene_c):
            expected_scenes.append(scene_a)
            expected_scenes.append(scene_b)
            expected_scenes.append(scene_c)

    return expected_scenes


def is_expected_scene_pattern(scene_a, scene_b, scene_c):
    """Check if three scenes match the expected play pattern."""
    max_short_scene_duration = 2.5
    max_duration_difference = 0.3

    duration_a = scene_a[1].get_seconds() - scene_a[0].get_seconds()
    duration_b = scene_b[1].get_seconds() - scene_b[0].get_seconds()
    duration_c = scene_c[1].get_seconds() - scene_c[0].get_seconds()

    if (
        duration_a < max_short_scene_duration and
        abs(duration_b - duration_c) <= max_duration_difference * min(duration_b, duration_c)
    ):
        return True

    return False
