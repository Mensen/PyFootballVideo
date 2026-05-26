"""TEMPLATE: split N continuous videos using their colocated .dartclip files.

Use case
--------
You have several full-length videos (different angles of the same game,
each cut from its own Dartfish dartclip file) and want to batch-split them
into per-play clips. Each input video must have a sibling `<video>.dartclip`
in the same folder; the dartclip's marker events drive the cuts. Output
folders are created per job under DST_BASE.

When to use vs. the menu CLI
----------------------------
The interactive `pyfootball` CLI handles single-file splits with a folder
picker. This script is preferable when:
* You want one command to process several videos in a row without prompts.
* You want the calls in version control as a record of how the clips were
  produced for a given game.

Limitations
-----------
* Stream copy only (`reencode: False`) — clip boundaries snap to the nearest
  preceding keyframe, so the cut is slightly imprecise but lossless and
  fast. Set `reencode: True` (plus an `encoding_preset`) if your downstream
  tooling needs exact frame boundaries.
* No dartclip output for the per-play clips (`create_dartclip: False`).
  Flip it on if your analysis tool needs them.

How to use
----------
Set the constants in the CONFIGURE block below — point SRC at the folder
with the .mp4 + .dartclip pairs and list the (video_name, output_subfolder)
jobs — then `python this_script.py`.

First applied: W06 Glarus (Sideline + EZN + EZF, three full-game files).
"""

import logging
import os

from pyfootball.splitter import VideoSplitter

logging.basicConfig(level=logging.INFO, format="%(message)s")

# ----- CONFIGURE ------------------------------------------------------------
# Folder containing the full-length videos and their colocated .dartclip files.
SRC = r"E:\Invaders\WXX Opponent\Continuous"

# Where the per-job output subfolders will be created.
DST_BASE = r"E:\Invaders\WXX Opponent"

# One entry per video to split: (filename in SRC, output subfolder name under DST_BASE).
JOBS = [
    ("WXX at Opponent - Sideline.mp4", "Sideline"),
    ("WXX at Opponent - EZN.mp4",      "EZN"),
    ("WXX at Opponent - EZF.mp4",      "EZF"),
]

# Splitter config. See VideoSplitter docstring + encoding.ENCODING_PRESETS
# for the full set of knobs.
SPLITTER_CONFIG = {
    "split_video": True,
    "create_dartclip": False,
    "reencode": False,           # stream copy; set True for keyframe-accurate cuts
    "encoding_preset": None,     # only used when reencode=True; None = default preset
    "clip_naming": "metadata",   # "Play_NNN_ODK_Type" from event fields; "auto" = "Play_NNN"
    "buffer": 0.5,               # extra seconds at clip end
}
# ----- END CONFIGURE --------------------------------------------------------


splitter = VideoSplitter(SPLITTER_CONFIG)

for video_name, out_subfolder in JOBS:
    video_path = os.path.join(SRC, video_name)
    dartclip_path = video_path + ".dartclip"
    out_folder = os.path.join(DST_BASE, out_subfolder)
    os.makedirs(out_folder, exist_ok=True)

    print(f"\n=== {video_name} -> {out_folder} ===")
    parsed = splitter.parse_dartclip(dartclip_path)
    events = parsed["events"]
    print(f"  {len(events)} events")

    created, _ = splitter._process_clips(
        events,
        ["-i", video_path],
        out_folder,
        label=video_name,
    )
    print(f"  created {created} clips")
