"""TEMPLATE: split one continuous video file using another camera's CSV,
with a single-point sync offset.

Use case
--------
You have play timings broken down on Camera A (e.g. a sideline angle) and
want to cut the same plays from Camera B (e.g. an end-zone wide angle that
recorded as one continuous file). Identify one play you can locate in both
videos, and this script shifts every Position in A's CSV onto B's timeline
before running the splitter on B.

Limitations
-----------
* Single anchor point only — assumes the two cameras don't drift over time.
  For long halves with two cameras at different frame rates this can be off
  by a fraction of a second at the far end. The splitter's buffer
  (default 0.5s) typically absorbs that. If you need more accuracy, compute
  a per-event scaled offset using two anchors at opposite ends.

How to use
----------
Set the constants in the CONFIGURE block below, then `python this_script.py`.
The reference values were left in from the first run (W07 Pirates 2H, EZF
sync) as a worked example.

First applied: W07 Pirates 2H, syncing the sideline CSV onto EZF-Full.mp4
(Play 093 at 55520ms in the CSV mapped to 14:28.00 on EZF -> +812.480s).
"""

import csv
import logging
import os

from pyfootball.splitter import VideoSplitter

logging.basicConfig(level=logging.INFO, format="%(message)s")

# ----- CONFIGURE ------------------------------------------------------------
BASE = r"E:\Invaders\W07 Pirates\Continuous"
SRC_CSV = os.path.join(BASE, "DF Sideline 2H - W07 vs Pirates.csv")
# The video to be cut (the camera that needs syncing onto the source CSV):
EZF_VIDEO = os.path.join(BASE, "EZF-Full.mp4")

# Sync anchor: name of a play that's present in SRC_CSV and locatable in the
# target video, plus the play's timestamp on the target's timeline.
REF_PLAY_NAME = "Play 093"
REF_TIME_ON_EZF_MS = (14 * 60 + 28) * 1000  # 14:28.00

SYNCED_CSV = os.path.join(BASE, "DF Sideline 2H - W07 vs Pirates - EZF synced.csv")
OUT_FOLDER = r"E:\Invaders\W07 Pirates\EZF\2H"
# ----- END CONFIGURE --------------------------------------------------------


def write_synced_csv(src_csv: str, ref_play: str, ref_time_ms: int,
                     out_csv: str) -> int:
    with open(src_csv, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    ref_row = next((r for r in rows if r["Name"].strip() == ref_play), None)
    if ref_row is None:
        raise ValueError(f"Reference play {ref_play!r} not in {src_csv}")

    offset_ms = ref_time_ms - int(ref_row["Position"])
    print(f"Reference {ref_play}: CSV pos {ref_row['Position']}ms -> "
          f"EZF {ref_time_ms}ms, offset = {offset_ms:+d}ms "
          f"({offset_ms / 1000:+.3f}s)")

    fieldnames = list(rows[0].keys())
    written = 0
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            shifted = int(row["Position"]) + offset_ms
            if shifted < 0:
                print(f"  skipping {row['Name']}: shifted position {shifted}ms < 0")
                continue
            row["Position"] = str(shifted)
            writer.writerow(row)
            written += 1
    return written


def main():
    n = write_synced_csv(SRC_CSV, REF_PLAY_NAME, REF_TIME_ON_EZF_MS, SYNCED_CSV)
    print(f"Wrote {n} events to {SYNCED_CSV}\n")

    os.makedirs(OUT_FOLDER, exist_ok=True)
    splitter = VideoSplitter({
        "split_video": True,
        "create_dartclip": False,
        "reencode": False,
        "clip_naming": "metadata",
        "buffer": 0.5,
    })

    print(f"=== Splitting {EZF_VIDEO} -> {OUT_FOLDER} ===")
    result = splitter.process_video(
        csv_path=SYNCED_CSV,
        video_path=EZF_VIDEO,
        output_folder=OUT_FOLDER,
    )
    print(f"\nDone: {result}")


if __name__ == "__main__":
    main()
