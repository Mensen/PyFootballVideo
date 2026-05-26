"""TEMPLATE: multi-angle autocrop pipeline for a two-camera game.

Use case
--------
You have two synced angles of the same game (typically a wider angle and a
zoomed/tighter one shot from the same tripod), each split into matching
per-play clips named identically across folders. This script runs the
five-stage pipeline that picks the better angle per play and writes one
cropped/encoded clip per play to a final folder.

Stages (run in order, or `all` to chain them):
    calibrate   open a frame per angle, click the field polygon, save calibration
    analyze     motion-detect every clip in both angles (heatmaps + summary CSVs)
    select      apply the default angle-selection rule, write the manifest,
                render side-by-side comparison JPGs
    review      interactive viewer to override per-play selections
    encode      crop+encode the chosen angle for each play

Prerequisites
-------------
* Both angle folders contain matching .mp4 filenames (one clip per play, same
  name in both folders). The splitter templates in this folder produce that
  layout when both angles are cut from the same play CSV.

How to use
----------
Set the constants in the CONFIGURE block below, then:
    python scripts/multi_angle_autocrop.py calibrate
    python scripts/multi_angle_autocrop.py analyze
    python scripts/multi_angle_autocrop.py select
    python scripts/multi_angle_autocrop.py review
    python scripts/multi_angle_autocrop.py encode
Or `python scripts/multi_angle_autocrop.py all` to run sequentially (note:
calibrate and review are interactive — `all` will block on them).

First applied: W06 Glarus and W07 Pirates with WIDE=EZN and ZOOM=EZF.
"""

import logging
import os
import sys

from pyfootball.autocrop import (
    analyze_clips_folder,
    autocrop_from_manifest,
    calibrate_field,
    interactive_select_angle,
    render_angle_comparisons,
    select_best_angle,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")

# ----- CONFIGURE ------------------------------------------------------------
# Base folder holding the per-angle clip folders. The script expects two
# subfolders named after WIDE and ZOOM below.
BASE = r"E:\Invaders\WXX Opponent"

# Folder names of the two angles. WIDE is the first preference for the
# default selection rule (kicks + near plays); ZOOM gets the rest.
WIDE = "EZN"
ZOOM = "EZF"

# Encoding preset for the final crop+encode pass. See encoding.ENCODING_PRESETS:
#   "all_intra"  every frame a keyframe (largest, scrub-step friendly)
#   "short_gop"  keyframe every ~0.5s at 30fps (default, good balance)
#   "standard"   codec default GOP (smallest/fastest, playback only)
ENCODING_PRESET = "short_gop"

# Parallelism for the motion-analysis stage. None = os.cpu_count().
ANALYSIS_WORKERS = 8
# ----- END CONFIGURE --------------------------------------------------------


ANGLE_PRIORITY = [WIDE, ZOOM]

CLIPS = {
    WIDE: os.path.join(BASE, WIDE),
    ZOOM: os.path.join(BASE, ZOOM),
}
ANALYSIS = {
    WIDE: os.path.join(BASE, WIDE, "analysis"),
    ZOOM: os.path.join(BASE, ZOOM, "analysis"),
}
SUMMARIES = {a: os.path.join(ANALYSIS[a], "autocrop_summary.csv") for a in ANGLE_PRIORITY}
HEATMAPS  = {a: os.path.join(ANALYSIS[a], "heatmaps")              for a in ANGLE_PRIORITY}

CALIBRATIONS = {
    a: os.path.join(BASE, a, "field_calibration.json") for a in ANGLE_PRIORITY
}
MANIFEST    = os.path.join(BASE, "angle_manifest.csv")
COMPARE_DIR = os.path.join(BASE, "angle_compare")
FINAL_DIR   = os.path.join(BASE, "EZ Autocrop")


def _first_clip(folder):
    for f in sorted(os.listdir(folder)):
        if f.lower().endswith((".mp4", ".mov", ".avi")):
            return os.path.join(folder, f)
    raise FileNotFoundError(f"No video files in {folder}")


def stage_calibrate():
    for angle in ANGLE_PRIORITY:
        cal_path = CALIBRATIONS[angle]
        if os.path.exists(cal_path):
            print(f"[{angle}] calibration already exists: {cal_path} (delete it to redo)")
            continue
        sample_video = _first_clip(CLIPS[angle])
        print(f"[{angle}] calibrating on {sample_video}")
        polygon = calibrate_field(sample_video, output_json=cal_path)
        if polygon is None:
            print(f"[{angle}] calibration cancelled.")
            sys.exit(1)


def stage_analyze():
    for angle in ANGLE_PRIORITY:
        print(f"\n=== analyzing {angle} ===")
        analyze_clips_folder(
            clips_folder=CLIPS[angle],
            calibration_path=CALIBRATIONS[angle],
            output_folder=ANALYSIS[angle],
            workers=ANALYSIS_WORKERS,
        )


def stage_select():
    print(f"\n=== selecting best angle per play ===")
    select_best_angle(
        angle_summaries=SUMMARIES,
        output_csv=MANIFEST,
        angle_priority=ANGLE_PRIORITY,
    )
    print(f"\n=== rendering comparison images ===")
    render_angle_comparisons(
        manifest_csv=MANIFEST,
        angle_heatmap_folders=HEATMAPS,
        output_folder=COMPARE_DIR,
    )


def stage_review():
    print(f"\n=== interactive review (ENTER to save, ESC to exit) ===")
    interactive_select_angle(
        manifest_csv=MANIFEST,
        angle_heatmap_folders=HEATMAPS,
        angle_priority=ANGLE_PRIORITY,
    )


def stage_encode():
    print(f"\n=== encoding final clips to {FINAL_DIR} ===")
    autocrop_from_manifest(
        manifest_csv=MANIFEST,
        angle_clip_folders=CLIPS,
        angle_summaries=SUMMARIES,
        output_folder=FINAL_DIR,
        encoding_preset=ENCODING_PRESET,
    )


STAGES = {
    "calibrate": stage_calibrate,
    "analyze":   stage_analyze,
    "select":    stage_select,
    "review":    stage_review,
    "encode":    stage_encode,
}


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("Stages:", ", ".join(STAGES), "| all")
        sys.exit(1)

    requested = sys.argv[1:]
    if requested == ["all"]:
        requested = list(STAGES)

    for name in requested:
        if name not in STAGES:
            print(f"Unknown stage: {name}")
            sys.exit(1)
        STAGES[name]()


if __name__ == "__main__":
    main()
