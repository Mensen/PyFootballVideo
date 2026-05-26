"""
Video Splitter

Split video files into clips based on timestamp information from CSV or
Dartfish dartclip files. Supports single-file and multi-file (series) modes.
"""

import os
import csv
import glob
import re
import subprocess
import logging
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional, Tuple, Any

from pyfootball.dartclip import create_dartclip, _get_column_value
from pyfootball.encoding import get_encoding_args

logger = logging.getLogger('pyfootball.splitter')

INCOMPLETE_MARKER_SUFFIX = '.incomplete'


class VideoSplitter:
    """
    Split video files based on timestamp information from a CSV file.

    All behavior is controlled through a config dict. Defaults are sensible
    -- only override what you need.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = {
            'split_video': True,
            'create_dartclip': True,
            'skip': 0,
            'reencode': False,
            'time_offset': 0,
            'buffer': 0.5,
            'start_number': 1,
            'video_series': False,
            'series_input_mode': 'dartclip',
            'clip_naming': 'auto',
            'encoding_preset': None,  # passed to get_encoding_args; None = DEFAULT_PRESET
        }
        if config:
            self.config.update(config)
        logger.info("VideoSplitter initialized with config: %s", self.config)

    def extract_events(self, csv_path: str) -> List[Dict[str, str]]:
        """
        Extract events data from a CSV file.

        Args:
            csv_path: Path to the CSV file containing event data.

        Returns:
            List of dicts where each dict represents an event.
        """
        logger.info(f"Extracting events from {csv_path}")

        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"CSV file not found: {csv_path}")

        events = []
        with open(csv_path, 'r', encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)

            field_names_lower = [field.lower() for field in reader.fieldnames]
            required_columns = ['Position', 'Duration']
            missing = [col for col in required_columns if col.lower() not in field_names_lower]
            if missing:
                raise ValueError(f"Required columns {missing} not found in the CSV file.")

            for row in reader:
                events.append(row)

        logger.info(f"Extracted {len(events)} events")
        return events

    def _build_ffmpeg_cmd(self, input_args: List[str], starttime: float,
                          duration: float, output_path: str) -> List[str]:
        """
        Build an FFmpeg command for extracting a clip.

        Args:
            input_args: Input portion of the command, e.g. ["-i", path] or
                        ["-f", "concat", "-safe", "0", "-i", filelist_path].
            starttime: Seek position in seconds.
            duration: Clip duration in seconds.
            output_path: Path to the output file.

        Returns:
            Complete FFmpeg command as a list of strings.
        """
        is_concat = "-f" in input_args and "concat" in input_args

        if not self.config['reencode']:
            if is_concat:
                # Concat demuxer: -ss/-t must be output options (after -i)
                # for accurate seeking across segment boundaries
                cmd = [
                    "ffmpeg",
                    *input_args,
                    "-ss", str(starttime),
                    "-t", str(duration),
                    "-c:v", "copy",
                    "-an",
                    "-v", "quiet",
                    "-hide_banner",
                    output_path
                ]
            else:
                cmd = [
                    "ffmpeg",
                    "-ss", str(starttime),
                    "-t", str(duration),
                    *input_args,
                    "-c:v", "copy",
                    "-an",
                    "-v", "quiet",
                    "-hide_banner",
                    output_path
                ]
        else:
            cmd = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel", "error",
                "-y",
                "-ss", str(starttime),
                *input_args,
                "-t", str(duration),
                *get_encoding_args(self.config['encoding_preset']),
                "-an",
                output_path
            ]
        return cmd

    def _build_clip_name(self, event: Dict[str, str], clip_number: int) -> str:
        """
        Build a clip filename (without extension) based on the naming mode.

        In 'metadata' mode, extracts the play number from the Name field,
        and includes ODK and Play Type. Missing fields become 'X'.

        Falls back to auto-numbering if Name has no extractable number.
        """
        if self.config['clip_naming'] != 'metadata':
            return f"Play_{clip_number:03d}"

        name = _get_column_value(event, 'Name', '')
        match = re.search(r'\d+', name)
        if not match:
            return f"Play_{clip_number:03d}"

        play_num = int(match.group())
        odk = _get_column_value(event, 'ODK', '') or 'X'
        play_type = _get_column_value(event, 'Play Type', '') or 'X'

        if odk in ('N/A', ''):
            odk = 'X'
        if play_type in ('N/A', ''):
            play_type = 'X'

        return f"Play_{play_num:03d}_{odk}_{play_type}"

    def _process_clips(self, events: List[Dict[str, str]],
                       input_args: List[str], output_folder: str,
                       global_offset: int = 0, label: str = "") -> Tuple[int, int]:
        """
        Core clip-processing loop used by all split methods.

        Args:
            events: List of event dicts with Position/Duration.
            input_args: FFmpeg input arguments (e.g. ["-i", path] or concat args).
            output_folder: Where to write clip files.
            global_offset: Number of events already processed (for series numbering).
            label: Log label for context.

        Returns:
            (clips_created, next_global_offset) tuple.
        """
        time_offset = self.config['time_offset']
        buffer = self.config['buffer']
        flag_skip = self.config['skip']
        flag_dartclip = self.config['create_dartclip']
        start_number = self.config['start_number']

        self._sweep_interrupted_markers(output_folder)

        clips_created = 0

        for index, event in enumerate(events):
            global_index = global_offset + index + 1

            if global_index < flag_skip:
                logger.info(f"Skipping clip {global_index}")
                continue

            try:
                starttime = float(_get_column_value(event, 'Position', None)) / 1000 + time_offset
                duration = float(_get_column_value(event, 'Duration', None)) / 1000 + buffer

                clip_number = global_offset + index + start_number
                clip_name = self._build_clip_name(event, clip_number)
                output_file = f"{clip_name}.mp4"
                output_path = os.path.join(output_folder, output_file)
                marker_path = output_path + INCOMPLETE_MARKER_SUFFIX

                if flag_dartclip:
                    try:
                        create_dartclip(event, output_path)
                        logger.info(f"Created dartclip for {clip_name}")
                    except Exception as e:
                        logger.error(f"Error creating dartclip for {clip_name}: {e}")

                cmd = self._build_ffmpeg_cmd(input_args, starttime, duration, output_path)

                log_label = f" from {label}" if label else ""
                logger.info(f"Processing {clip_name}{log_label}")
                # Marker is created BEFORE ffmpeg and removed only on confirmed
                # success. If the process dies mid-encode (kill, sleep, OOM)
                # the marker survives and the next run's sweep will re-cut.
                open(marker_path, 'w').close()
                subprocess.run(cmd, check=True)

                if os.path.exists(output_path):
                    clips_created += 1
                    logger.info(f"Created clip: {output_file}")
                    try:
                        os.remove(marker_path)
                    except OSError:
                        pass
                else:
                    logger.warning(f"Failed to create clip: {output_file}")

            except KeyError as e:
                logger.error(f"Column error processing clip {global_index}: {e}")
            except subprocess.CalledProcessError as e:
                logger.error(f"FFmpeg error processing clip {global_index}: {e}")
            except Exception as e:
                logger.error(f"Unexpected error processing clip {global_index}: {e}")

        return clips_created, global_offset + len(events)

    def _sweep_interrupted_markers(self, output_folder: str) -> None:
        """Detect and clean up clips left mid-encode by a previous run.

        Each clip is wrapped in a `<clip>.incomplete` marker between the
        ffmpeg launch and its successful exit. A surviving marker means the
        previous run died with that clip still being written -- the .mp4
        on disk may look complete but typically has no moov atom.

        Delete both the marker and the matching .mp4 here so the events
        loop recreates them from scratch. Clips outside this run's event
        range (e.g. when `skip` is set to resume) won't be regenerated and
        are reported in the warning so the operator can re-run them.
        """
        if not os.path.isdir(output_folder):
            return
        markers = [f for f in os.listdir(output_folder)
                   if f.endswith(INCOMPLETE_MARKER_SUFFIX)]
        for marker in markers:
            clip_file = marker[:-len(INCOMPLETE_MARKER_SUFFIX)]
            clip_path = os.path.join(output_folder, clip_file)
            marker_path = os.path.join(output_folder, marker)
            logger.warning(
                f"Detected interrupted clip from previous run: {clip_file}. "
                f"Deleting; will be re-cut if it is in this run's event range."
            )
            for p in (clip_path, marker_path):
                try:
                    if os.path.exists(p):
                        os.remove(p)
                except OSError as e:
                    logger.error(f"Could not remove {p}: {e}")

    def split_video(self, video_path: str, events: List[Dict[str, str]],
                    output_folder: str) -> str:
        """
        Split a video file into clips based on event timestamps.

        Args:
            video_path: Path to the video file.
            events: List of events with timing information.
            output_folder: Path to the output folder.

        Returns:
            Path to the folder containing the generated clips.
        """
        logger.info(f"Splitting video {video_path}")

        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")
        if not events:
            raise ValueError("No events provided for splitting")

        file_name = os.path.splitext(os.path.basename(video_path))[0]
        new_folder_path = os.path.join(output_folder, file_name + " Clips")
        os.makedirs(new_folder_path, exist_ok=True)
        logger.info(f"Output folder: {new_folder_path}")

        clips_created, _ = self._process_clips(
            events, ["-i", video_path], new_folder_path,
            label=os.path.basename(video_path),
        )

        logger.info(f"Finished processing {clips_created} clips in {new_folder_path}")
        return new_folder_path

    def create_dartclips_for_folder(self, events: List[Dict[str, str]], clips_folder: str,
                                    file_pattern: str = "Play_{:03d}.mp4") -> int:
        """
        Create dartclip files for existing video clips in a folder.

        Args:
            events: List of event dictionaries from CSV.
            clips_folder: Folder containing the video clips.
            file_pattern: Pattern for matching clip filenames.

        Returns:
            Number of dartclip files created.
        """
        logger.info(f"Creating dartclip files for clips in {clips_folder}")
        start_number = self.config['start_number']

        if not os.path.exists(clips_folder):
            logger.error(f"Clips folder not found: {clips_folder}")
            return 0

        dartclips_created = 0
        for index, event in enumerate(events):
            clip_number = index + start_number
            clip_name = file_pattern.format(clip_number)
            clip_path = os.path.join(clips_folder, clip_name)

            if not os.path.exists(clip_path):
                logger.warning(f"Clip not found: {clip_path}")
                continue

            try:
                create_dartclip(event, clip_path)
                dartclips_created += 1
                logger.info(f"Created dartclip for {clip_name}")
            except Exception as e:
                logger.error(f"Error creating dartclip for {clip_name}: {e}")

        logger.info(f"Created {dartclips_created} dartclip files")
        return dartclips_created

    # -- Video series methods --------------------------------------------------

    def parse_dartclip(self, dartclip_path: str) -> Dict[str, Any]:
        """
        Parse a Dartfish .dartclip XML file into a dict with the source video
        filename and a list of event dicts.

        Returns:
            dict with keys 'video_file' (str) and 'events' (list of dicts).
        """
        tree = ET.parse(dartclip_path)
        root = tree.getroot()

        video_file = root.findtext('NAME')
        events = []

        for item in root.findall("LIBRARY_ITEM[@ItemType='Marker.Event']"):
            in_reftime = int(item.get('IN', '0'))
            out_reftime = int(item.get('OUT', '0'))

            position_ms = in_reftime // 10000
            duration_ms = (out_reftime - in_reftime) // 10000

            event = {
                'Position': str(position_ms),
                'Duration': str(duration_ms),
            }

            md_props = item.find('Library.MDProperties')
            if md_props is not None:
                title_elem = md_props.find("Property[@Name='Title']")
                if title_elem is not None and title_elem.text:
                    event['Name'] = title_elem.text

            categories_elem = item.find('CATEGORIES')
            if categories_elem is not None:
                for cat in categories_elem.findall('CATEGORY'):
                    name = cat.get('name')
                    if name and cat.text:
                        event[name] = cat.text

            events.append(event)

        logger.info(f"Parsed {len(events)} events from {os.path.basename(dartclip_path)}")
        return {'video_file': video_file, 'events': events}

    def load_series_from_dartclips(self, folder_path: str) -> List[Dict[str, Any]]:
        """
        Scan a folder for .dartclip files and return series data.

        Returns:
            List of dicts, each with 'video_path' (str) and 'events' (list).
        """
        dartclip_files = sorted(glob.glob(os.path.join(folder_path, '*.dartclip')))

        if not dartclip_files:
            logger.error(f"No .dartclip files found in {folder_path}")
            return []

        series_data = []
        for dc_path in dartclip_files:
            parsed = self.parse_dartclip(dc_path)
            if not parsed['events']:
                logger.warning(f"Skipping {os.path.basename(dc_path)} (no events)")
                continue

            video_path = dc_path.rsplit('.dartclip', 1)[0]
            if not os.path.exists(video_path):
                logger.warning(f"Video file not found: {video_path}")
                continue

            series_data.append({
                'video_path': video_path,
                'events': parsed['events'],
            })

        logger.info(f"Loaded series with {len(series_data)} files, "
                     f"{sum(len(s['events']) for s in series_data)} total events")
        return series_data

    def detect_file_boundaries(self, events: List[Dict[str, str]]) -> List[List[Dict[str, str]]]:
        """
        Group events into per-file segments for CSV per-file timestamp mode.

        Uses an explicit 'File' column if present, otherwise auto-detects
        file boundaries when Position drops significantly.
        """
        if not events:
            return []

        file_col = None
        for key in events[0]:
            if key.lower() == 'file':
                file_col = key
                break

        if file_col:
            groups = []
            current_group = [events[0]]
            current_file = events[0][file_col]
            for event in events[1:]:
                if event[file_col] == current_file:
                    current_group.append(event)
                else:
                    groups.append(current_group)
                    current_group = [event]
                    current_file = event[file_col]
            groups.append(current_group)
            logger.info(f"Grouped {len(events)} events into {len(groups)} files by '{file_col}' column")
            return groups

        groups = []
        current_group = [events[0]]
        prev_position = float(events[0]['Position'])

        for event in events[1:]:
            position = float(event['Position'])
            if position < prev_position * 0.5:
                groups.append(current_group)
                current_group = []
            current_group.append(event)
            prev_position = position

        groups.append(current_group)
        logger.info(f"Auto-detected {len(groups)} file boundaries from Position resets")
        return groups

    def _make_concat_filelist(self, video_paths: List[str], output_dir: str) -> str:
        """Create an FFmpeg concat demuxer input file."""
        filelist_path = os.path.join(output_dir, '_concat_filelist.txt')
        with open(filelist_path, 'w') as f:
            for path in video_paths:
                f.write(f"file '{path}'\n")
        logger.info(f"Created concat filelist with {len(video_paths)} files")
        return filelist_path

    def split_video_series(self, series_data: List[Dict[str, Any]],
                           output_folder: str) -> str:
        """
        Split clips from a series of video files.

        Args:
            series_data: List of dicts with 'video_path' and 'events' keys.
            output_folder: Base output folder.

        Returns:
            Path to the folder containing the generated clips.
        """
        if not series_data:
            raise ValueError("No series data provided")

        first_name = os.path.splitext(os.path.basename(series_data[0]['video_path']))[0]
        new_folder_path = os.path.join(output_folder, first_name + " Series Clips")
        os.makedirs(new_folder_path, exist_ok=True)
        logger.info(f"Created output folder: {new_folder_path}")

        total_clips = 0
        global_offset = 0

        for segment in series_data:
            video_path = segment['video_path']
            logger.info(f"Processing {os.path.basename(video_path)} "
                        f"({len(segment['events'])} events)")

            created, global_offset = self._process_clips(
                segment['events'], ["-i", video_path], new_folder_path,
                global_offset=global_offset,
                label=os.path.basename(video_path),
            )
            total_clips += created

        logger.info(f"Finished series: {total_clips} clips in {new_folder_path}")
        return new_folder_path

    def split_absolute_series(self, filelist_path: str,
                              events: List[Dict[str, str]],
                              output_folder: str) -> str:
        """
        Split clips using FFmpeg concat demuxer for absolute timestamps.

        Args:
            filelist_path: Path to the concat demuxer input file.
            events: All events with absolute Position/Duration.
            output_folder: Base output folder.

        Returns:
            Path to the folder containing the generated clips.
        """
        new_folder_path = os.path.join(output_folder, "Series Clips")
        os.makedirs(new_folder_path, exist_ok=True)

        concat_input = ["-f", "concat", "-safe", "0", "-i", filelist_path]
        clips_created, _ = self._process_clips(
            events, concat_input, new_folder_path, label="absolute mode",
        )

        logger.info(f"Finished absolute series: {clips_created} clips in {new_folder_path}")
        return new_folder_path

    def process_video(self, video_path: Optional[str] = None,
                      csv_path: Optional[str] = None,
                      clips_folder: Optional[str] = None,
                      output_folder: Optional[str] = None,
                      video_paths: Optional[List[str]] = None,
                      series_folder: Optional[str] = None) -> Any:
        """
        Process a video file according to the configuration.

        This is the main entry point for all video processing operations.
        All path arguments are required for their respective modes --
        no interactive dialogs are opened.

        Args:
            video_path: Path to the video file (single-file mode).
            csv_path: Path to the CSV file with events data.
            clips_folder: Path to folder with existing clips (dartclip-only mode).
            output_folder: Base output folder for generated clips.
            video_paths: Ordered list of video file paths for series mode.
            series_folder: Folder with .dartclip files for series mode.

        Returns:
            Path to output folder if splitting video, or number of dartclips created.
        """
        # -- VIDEO SERIES MODE --
        if self.config['video_series']:
            mode = self.config['series_input_mode']

            if mode == 'dartclip':
                if not series_folder:
                    raise ValueError("series_folder is required for dartclip series mode")
                series_data = self.load_series_from_dartclips(series_folder)
                if not series_data:
                    raise ValueError("No valid dartclip/video pairs found")
                if not output_folder:
                    output_folder = series_folder
                return self.split_video_series(series_data, output_folder)

            elif mode == 'csv_per_file':
                if not csv_path:
                    raise ValueError("csv_path is required for csv_per_file series mode")
                events = self.extract_events(csv_path)
                groups = self.detect_file_boundaries(events)
                if not video_paths:
                    raise ValueError("video_paths is required for csv_per_file series mode")
                if len(groups) != len(video_paths):
                    raise ValueError(
                        f"CSV has {len(groups)} file segments but "
                        f"{len(video_paths)} video files were provided"
                    )
                series_data = [
                    {'video_path': vp, 'events': grp}
                    for vp, grp in zip(video_paths, groups)
                ]
                if not output_folder:
                    output_folder = os.path.dirname(video_paths[0])
                return self.split_video_series(series_data, output_folder)

            elif mode == 'csv_absolute':
                if not csv_path:
                    raise ValueError("csv_path is required for csv_absolute series mode")
                if not video_paths:
                    raise ValueError("video_paths is required for csv_absolute series mode")
                if not output_folder:
                    raise ValueError("output_folder is required for csv_absolute series mode")
                events = self.extract_events(csv_path)
                filelist = self._make_concat_filelist(video_paths, output_folder)
                try:
                    return self.split_absolute_series(filelist, events, output_folder)
                finally:
                    if os.path.exists(filelist):
                        os.remove(filelist)

            else:
                raise ValueError(f"Unknown series_input_mode: {mode}")

        # -- SINGLE FILE MODE --
        if not csv_path:
            raise ValueError("csv_path is required")

        events = self.extract_events(csv_path)
        if not events:
            raise ValueError("No events found in CSV file")

        if self.config['split_video']:
            if not video_path:
                raise ValueError("video_path is required for split_video mode")
            if not output_folder:
                output_folder = os.path.dirname(video_path)
            return self.split_video(video_path, events, output_folder)

        elif self.config['create_dartclip']:
            if not clips_folder:
                raise ValueError("clips_folder is required for dartclip-only mode")
            return self.create_dartclips_for_folder(events, clips_folder)

        else:
            logger.warning("No operation selected (split_video=False, create_dartclip=False)")
            return None
