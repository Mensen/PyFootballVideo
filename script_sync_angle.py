#!/usr/bin/env python
"""
Sync Angle Tool

Given a GoPro series folder with dartclip files and a sync point on a second
camera angle, this script:
1. Stacks GoPro segment durations to build absolute play times
2. Applies a sync offset derived from a user-provided reference point
3. Outputs a CSV with play times mapped to the second camera's timeline

Usage:
    python script_sync_angle.py
"""

import os
import csv
import re
import glob
import json
import subprocess
import logging

from video_splitter import VideoSplitter

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('sync_angle')


def get_video_duration_ms(video_path: str) -> float:
    """Get video duration in milliseconds using ffprobe."""
    cmd = [
        'ffprobe', '-v', 'quiet', '-print_format', 'json',
        '-show_format', video_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    info = json.loads(result.stdout)
    return float(info['format']['duration']) * 1000


def get_series_files(folder: str, session_id: str = None) -> list:
    """
    Get all MP4 files in a GoPro series, sorted by chapter number.

    GoPro naming: GXnnSSSS.MP4 where nn=chapter, SSSS=session ID.
    If session_id is not provided, it is inferred from the dartclip files
    in the folder (the session with the most dartclips).

    Args:
        folder: Path to the GoPro folder.
        session_id: GoPro session ID to filter by (e.g. '1660').

    Returns:
        Sorted list of MP4 paths belonging to the series.
    """
    all_mp4s = sorted(glob.glob(os.path.join(folder, '*.MP4')))
    if not all_mp4s:
        all_mp4s = sorted(glob.glob(os.path.join(folder, '*.mp4')))

    # Auto-detect session from dartclip files if not specified
    if session_id is None:
        from collections import Counter
        session_counts = Counter()
        for f in all_mp4s:
            if os.path.exists(f + '.dartclip'):
                m = re.match(r'GX(\d{2})(\d{4})\.',
                             os.path.basename(f), re.IGNORECASE)
                if m:
                    session_counts[m.group(2)] += 1
        if session_counts:
            session_id = session_counts.most_common(1)[0][0]
            logger.info(f"Auto-detected GoPro session: {session_id}")
        else:
            logger.warning("Could not detect GoPro session, returning all files")
            return all_mp4s

    # Filter to the target session, sorted by chapter number
    series = []
    for f in all_mp4s:
        m = re.match(r'GX(\d{2})(\d{4})\.',
                     os.path.basename(f), re.IGNORECASE)
        if m and m.group(2) == session_id:
            series.append((int(m.group(1)), f))

    series.sort(key=lambda x: x[0])
    result = [f for _, f in series]
    logger.info(f"Found {len(result)} files in session {session_id}")
    return result


def build_absolute_timeline(folder: str) -> list:
    """
    Stack GoPro segment durations and place dartclip events on an absolute
    timeline. Only stacks segments up to and including the last segment
    that has a dartclip file.

    Args:
        folder: Path to the GoPro folder with MP4s and dartclip files.

    Returns:
        List of dicts with keys: Name, Position_abs_ms, Duration_ms,
        source_file, and all category columns from the dartclip.
    """
    all_files = get_series_files(folder)
    if not all_files:
        raise FileNotFoundError(f"No MP4 files found in {folder}")

    # Find which files have dartclips
    files_with_dartclips = set()
    for f in all_files:
        if os.path.exists(f + '.dartclip'):
            files_with_dartclips.add(f)

    if not files_with_dartclips:
        raise FileNotFoundError(f"No dartclip files found in {folder}")

    # Determine stacking ceiling: last file with a dartclip
    last_dartclip_file = max(f for f in all_files if f in files_with_dartclips)
    ceiling_idx = all_files.index(last_dartclip_file)
    files_to_stack = all_files[:ceiling_idx + 1]

    logger.info(f"Stacking {len(files_to_stack)} segments "
                f"(up to {os.path.basename(last_dartclip_file)})")

    # Get durations and parse dartclips
    vs = VideoSplitter()
    cumulative_ms = 0.0
    absolute_events = []

    for video_path in files_to_stack:
        duration_ms = get_video_duration_ms(video_path)
        dartclip_path = video_path + '.dartclip'

        if os.path.exists(dartclip_path):
            parsed = vs.parse_dartclip(dartclip_path)
            for event in parsed['events']:
                position_ms = float(event['Position'])
                abs_position = cumulative_ms + position_ms

                abs_event = {
                    'Name': event.get('Name', ''),
                    'Position_abs_ms': abs_position,
                    'Duration_ms': float(event['Duration']),
                    'source_file': os.path.basename(video_path),
                }
                # Carry over all category columns
                for key, value in event.items():
                    if key not in ('Position', 'Duration', 'Name'):
                        abs_event[key] = value

                absolute_events.append(abs_event)

        cumulative_ms += duration_ms
        logger.info(f"  {os.path.basename(video_path)}: "
                    f"duration={duration_ms/1000:.2f}s, "
                    f"cumulative={cumulative_ms/1000:.2f}s"
                    f"{' (has dartclip)' if os.path.exists(dartclip_path) else ''}")

    logger.info(f"Built timeline: {len(absolute_events)} events over "
                f"{cumulative_ms/1000:.1f}s")
    return absolute_events


def parse_timestamp(ts: str) -> float:
    """
    Parse a timestamp string like '2:01.20' or '121.20' into milliseconds.
    Supports formats: M:SS.ms, MM:SS.ms, SS.ms, or raw milliseconds.
    """
    ts = ts.strip()

    if ':' in ts:
        parts = ts.split(':')
        minutes = float(parts[0])
        seconds = float(parts[1])
        return (minutes * 60 + seconds) * 1000
    elif '.' in ts:
        return float(ts) * 1000
    else:
        return float(ts)


def calculate_sync_offset(absolute_events: list, ref_play_name: str,
                          ref_time_ms: float) -> float:
    """
    Calculate the offset between GoPro absolute time and the second camera.

    offset = camera2_time - gopro_absolute_time

    Args:
        absolute_events: Events with Position_abs_ms from build_absolute_timeline.
        ref_play_name: Name of the reference play (e.g. 'Play (2)').
        ref_time_ms: Time of that play on camera 2, in milliseconds.

    Returns:
        Offset in milliseconds.
    """
    ref_event = None
    for event in absolute_events:
        if event['Name'] == ref_play_name:
            ref_event = event
            break

    if ref_event is None:
        # Try partial match
        for event in absolute_events:
            if ref_play_name.lower() in event['Name'].lower():
                ref_event = event
                break

    if ref_event is None:
        raise ValueError(f"Reference play '{ref_play_name}' not found. "
                         f"Available: {[e['Name'] for e in absolute_events[:5]]}...")

    offset = ref_time_ms - ref_event['Position_abs_ms']
    logger.info(f"Sync: '{ref_event['Name']}' at GoPro abs "
                f"{ref_event['Position_abs_ms']/1000:.2f}s → camera2 "
                f"{ref_time_ms/1000:.2f}s → offset {offset/1000:+.2f}s")
    return offset


def export_synced_csv(absolute_events: list, offset_ms: float,
                      output_path: str) -> str:
    """
    Export a CSV with play times mapped to the second camera's timeline.
    The CSV uses Position/Duration in milliseconds, matching the format
    expected by VideoSplitter.

    Args:
        absolute_events: Events with Position_abs_ms.
        offset_ms: Sync offset in milliseconds.
        output_path: Path for the output CSV file.

    Returns:
        Path to the written CSV file.
    """
    # Determine all category columns present across events
    standard_cols = {'Name', 'Position_abs_ms', 'Duration_ms', 'source_file'}
    extra_cols = []
    for event in absolute_events:
        for key in event:
            if key not in standard_cols and key not in extra_cols:
                extra_cols.append(key)

    fieldnames = ['Name', 'Position', 'Duration', 'source_file',
                  'Position_abs_gopro'] + extra_cols

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for event in absolute_events:
            synced_position = event['Position_abs_ms'] + offset_ms
            row = {
                'Name': event['Name'],
                'Position': str(round(synced_position)),
                'Duration': str(round(event['Duration_ms'])),
                'source_file': event['source_file'],
                'Position_abs_gopro': str(round(event['Position_abs_ms'])),
            }
            for col in extra_cols:
                row[col] = event.get(col, '')

            writer.writerow(row)

    logger.info(f"Exported {len(absolute_events)} events to {output_path}")
    return output_path


def main():
    from utils.pf_helpers import select_folder, select_file

    print("=== Sync Angle Tool ===\n")

    # Step 1: Select GoPro folder
    gopro_folder = select_folder(title="Select GoPro folder with MP4s and dartclips")
    if not gopro_folder:
        print("No folder selected.")
        return

    # Step 2: Build absolute timeline
    print("\nBuilding absolute timeline from GoPro segments...")
    absolute_events = build_absolute_timeline(gopro_folder)
    print(f"Found {len(absolute_events)} plays\n")

    # Show first few for reference
    print("First plays on absolute timeline:")
    for e in absolute_events[:5]:
        mins = e['Position_abs_ms'] / 60000
        secs = (e['Position_abs_ms'] % 60000) / 1000
        print(f"  {e['Name']:15s} → {int(mins)}:{secs:05.2f} "
              f"({e['source_file']})")
    print("  ...")

    # Step 3: Get sync point
    ref_play = input("\nReference play name (e.g. 'Play (2)'): ").strip()
    ref_time_str = input("Time of that play on camera 2 (e.g. '2:01.20'): ").strip()
    ref_time_ms = parse_timestamp(ref_time_str)

    # Step 4: Calculate offset
    offset = calculate_sync_offset(absolute_events, ref_play, ref_time_ms)
    print(f"Calculated offset: {offset/1000:+.2f}s")

    # Step 5: Export CSV
    output_path = os.path.join(gopro_folder, "synced_angle_times.csv")
    custom_path = input(f"\nOutput CSV path [{output_path}]: ").strip()
    if custom_path:
        output_path = custom_path

    export_synced_csv(absolute_events, offset, output_path)
    print(f"\nDone! CSV written to: {output_path}")


if __name__ == "__main__":
    main()
