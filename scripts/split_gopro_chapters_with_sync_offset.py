"""TEMPLATE: split a GoPro chapter series using another camera's CSV,
with a single-point sync offset.

Use case
--------
You have play timings broken down on a continuous camera (e.g. a sideline
angle) and want to cut the same plays from a GoPro that recorded as a
chaptered series (GX01SSSS.MP4, GX02SSSS.MP4, ...). Identify one play you
can locate in one specific GoPro chapter, and this script:

  1. Sums chapter durations to put the reference play on an absolute
     GoPro timeline.
  2. Shifts every CSV event by ref_abs_gopro - ref_csv_position.
  3. Buckets each shifted event into the chapter that contains it and
     converts back to chapter-local Position.
  4. Calls VideoSplitter._process_clips per chapter (csv_per_file style,
     avoiding the csv_absolute path).

Limitations
-----------
* Single anchor only — see split_continuous_with_sync_offset.py for drift
  notes; same caveat applies here.
* Plays that span a chapter boundary get truncated at the boundary. The
  affected plays are logged at the end so you can re-cut them by hand or
  fall back to csv_absolute mode for just those plays.

How to use
----------
Set the constants in the CONFIGURE block below, then `python this_script.py`.
Values left in from the first run as a worked example.

First applied: W07 Pirates 2H, syncing the sideline CSV onto the GoPro
session 1678 chapters (Play 093 in chapter GX031678 at 3:45.00 -> offset
+810.120s, all 66 plays fit within single chapters).
"""

import csv
import logging
import os

from pyfootball.splitter import VideoSplitter
from pyfootball.sync_angle import (
    chapter_local_to_absolute,
    get_series_files,
    get_video_duration_ms,
    parse_timestamp,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")

# ----- CONFIGURE ------------------------------------------------------------
SIDELINE_CSV = r"E:\Invaders\W07 Pirates\Continuous\DF Sideline 2H - W07 vs Pirates.csv"
GOPRO_FOLDER = r"H:\DCIM\100GOPRO"
GOPRO_SESSION = "1678"  # the SSSS part of GXnnSSSS.MP4 filenames

# Sync anchor: a play in SIDELINE_CSV plus the GoPro chapter it falls in
# and its time within that chapter.
REF_PLAY_NAME = "Play 093"
REF_CHAPTER = "GX031678.MP4"
REF_LOCAL_TIME = "3:45.00"

OUT_FOLDER = r"E:\Invaders\W07 Pirates\GoPro\2H"
# ----- END CONFIGURE --------------------------------------------------------


def load_sideline_events(csv_path: str) -> list:
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def bucket_events_by_chapter(events: list, offset_ms: int,
                             chapter_paths: list) -> tuple:
    """Return (per_chapter_groups, crossings, dropped).

    per_chapter_groups: list parallel to chapter_paths, each entry a list of
        event dicts with Position rewritten to chapter-local ms.
    crossings: list of (event_name, chapter_basename, overflow_ms) for events
        whose [start, start+duration] extends past the chapter end.
    dropped: list of event_name for events that don't fall inside any chapter.
    """
    chapter_durations = [get_video_duration_ms(p) for p in chapter_paths]
    chapter_starts = []
    cumulative = 0.0
    for d in chapter_durations:
        chapter_starts.append(cumulative)
        cumulative += d
    total_ms = cumulative

    groups = [[] for _ in chapter_paths]
    crossings = []
    dropped = []

    for event in events:
        synced_abs = float(event["Position"]) + offset_ms
        duration_ms = float(event["Duration"])

        if synced_abs < 0 or synced_abs >= total_ms:
            dropped.append(event.get("Name", "?"))
            continue

        chapter_idx = 0
        for i, start in enumerate(chapter_starts):
            if synced_abs >= start:
                chapter_idx = i
            else:
                break

        chapter_end = chapter_starts[chapter_idx] + chapter_durations[chapter_idx]
        local_pos = synced_abs - chapter_starts[chapter_idx]
        if synced_abs + duration_ms > chapter_end:
            overflow = (synced_abs + duration_ms) - chapter_end
            crossings.append((event.get("Name", "?"),
                              os.path.basename(chapter_paths[chapter_idx]),
                              overflow))

        new_event = dict(event)
        new_event["Position"] = str(int(round(local_pos)))
        groups[chapter_idx].append(new_event)

    return groups, crossings, dropped


def main():
    print(f"Loading sideline CSV: {SIDELINE_CSV}")
    events = load_sideline_events(SIDELINE_CSV)
    print(f"  {len(events)} events")

    ref_event = next((e for e in events if e["Name"].strip() == REF_PLAY_NAME), None)
    if ref_event is None:
        raise ValueError(f"Reference play {REF_PLAY_NAME!r} not found in CSV")
    ref_csv_pos = float(ref_event["Position"])

    ref_local_ms = parse_timestamp(REF_LOCAL_TIME)
    ref_abs_gopro = chapter_local_to_absolute(
        GOPRO_FOLDER, REF_CHAPTER, ref_local_ms, session_id=GOPRO_SESSION
    )
    offset_ms = int(round(ref_abs_gopro - ref_csv_pos))
    print(f"\nReference: {REF_PLAY_NAME} CSV pos {ref_csv_pos:.0f}ms -> "
          f"GoPro abs {ref_abs_gopro:.0f}ms (chapter {REF_CHAPTER} + "
          f"{REF_LOCAL_TIME})")
    print(f"Offset: {offset_ms:+d}ms ({offset_ms / 1000:+.3f}s)\n")

    chapter_paths = get_series_files(GOPRO_FOLDER, session_id=GOPRO_SESSION)
    print(f"Bucketing events into {len(chapter_paths)} chapters...")
    groups, crossings, dropped = bucket_events_by_chapter(
        events, offset_ms, chapter_paths
    )

    for path, grp in zip(chapter_paths, groups):
        if grp:
            print(f"  {os.path.basename(path)}: {len(grp)} events "
                  f"({grp[0]['Name']} ... {grp[-1]['Name']})")
    if dropped:
        print(f"  Dropped (outside chapter range): {dropped}")

    os.makedirs(OUT_FOLDER, exist_ok=True)
    splitter = VideoSplitter({
        "split_video": True,
        "create_dartclip": False,
        "reencode": False,
        "clip_naming": "metadata",
        "buffer": 0.5,
    })

    total = 0
    for chapter_path, grp in zip(chapter_paths, groups):
        if not grp:
            continue
        print(f"\n=== {os.path.basename(chapter_path)} -> {OUT_FOLDER} ===")
        created, _ = splitter._process_clips(
            grp, ["-i", chapter_path], OUT_FOLDER,
            label=os.path.basename(chapter_path),
        )
        total += created

    print(f"\nDone: {total} clips in {OUT_FOLDER}")

    if crossings:
        print(f"\nWARNING: {len(crossings)} plays cross a chapter boundary "
              f"and were truncated at the boundary:")
        for name, chap, overflow in crossings:
            print(f"  {name} in {chap}: missing trailing "
                  f"{overflow / 1000:.2f}s")


if __name__ == "__main__":
    main()
