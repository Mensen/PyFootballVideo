"""
Sync Angle Tool

Map play times from a GoPro series onto a second camera angle using a
single sync point. Outputs a CSV usable by VideoSplitter.
"""

import os
import csv
import re
import glob
import json
import subprocess
import logging
from collections import Counter

from pyfootball.splitter import VideoSplitter

logger = logging.getLogger('pyfootball.sync_angle')


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

    if session_id is None:
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
    timeline.

    Args:
        folder: Path to the GoPro folder with MP4s and dartclip files.

    Returns:
        List of dicts with keys: Name, Position_abs_ms, Duration_ms,
        source_file, and all category columns from the dartclip.
    """
    all_files = get_series_files(folder)
    if not all_files:
        raise FileNotFoundError(f"No MP4 files found in {folder}")

    files_with_dartclips = set()
    for f in all_files:
        if os.path.exists(f + '.dartclip'):
            files_with_dartclips.add(f)

    if not files_with_dartclips:
        raise FileNotFoundError(f"No dartclip files found in {folder}")

    last_dartclip_file = max(f for f in all_files if f in files_with_dartclips)
    ceiling_idx = all_files.index(last_dartclip_file)
    files_to_stack = all_files[:ceiling_idx + 1]

    logger.info(f"Stacking {len(files_to_stack)} segments "
                f"(up to {os.path.basename(last_dartclip_file)})")

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


def load_primary_events(source_path: str) -> list:
    """
    Load play events from a single full-length timing source.

    Use this when the primary recording is one continuous file (not a
    GoPro chapter series), and the play markings live in a single
    .dartclip or .csv file alongside it. The returned event list has
    the same shape as build_absolute_timeline()'s output, so it can be
    fed straight into calculate_sync_offset() and export_synced_csv().

    Args:
        source_path: Path to a .dartclip or .csv file with play markings.
            CSVs must have Position and Duration columns in milliseconds.

    Returns:
        List of dicts with keys: Name, Position_abs_ms, Duration_ms,
        source_file, plus any additional category columns.
    """
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Timing source not found: {source_path}")

    ext = os.path.splitext(source_path)[1].lower()
    vs = VideoSplitter()

    if ext == '.dartclip':
        parsed = vs.parse_dartclip(source_path)
        raw_events = parsed['events']
        source_file = parsed.get('video_file') or os.path.basename(source_path)
    elif ext == '.csv':
        raw_events = vs.extract_events(source_path)
        source_file = os.path.basename(source_path)
    else:
        raise ValueError(
            f"Unsupported timing source extension '{ext}'. "
            f"Expected .dartclip or .csv."
        )

    absolute_events = []
    for event in raw_events:
        abs_event = {
            'Name': event.get('Name', ''),
            'Position_abs_ms': float(event['Position']),
            'Duration_ms': float(event['Duration']),
            'source_file': source_file,
        }
        for key, value in event.items():
            if key not in ('Position', 'Duration', 'Name'):
                abs_event[key] = value
        absolute_events.append(abs_event)

    logger.info(f"Loaded {len(absolute_events)} events from "
                f"{os.path.basename(source_path)}")
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
        for event in absolute_events:
            if ref_play_name.lower() in event['Name'].lower():
                ref_event = event
                break

    if ref_event is None:
        raise ValueError(f"Reference play '{ref_play_name}' not found. "
                         f"Available: {[e['Name'] for e in absolute_events[:5]]}...")

    offset = ref_time_ms - ref_event['Position_abs_ms']
    logger.info(f"Sync: '{ref_event['Name']}' at GoPro abs "
                f"{ref_event['Position_abs_ms']/1000:.2f}s -> camera2 "
                f"{ref_time_ms/1000:.2f}s -> offset {offset/1000:+.2f}s")
    return offset


def export_synced_csv(absolute_events: list, offset_ms: float,
                      output_path: str) -> str:
    """
    Export a CSV with play times mapped to the second camera's timeline.

    Args:
        absolute_events: Events with Position_abs_ms.
        offset_ms: Sync offset in milliseconds.
        output_path: Path for the output CSV file.

    Returns:
        Path to the written CSV file.
    """
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
