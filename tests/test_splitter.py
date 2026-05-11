"""Tests for VideoSplitter core logic."""

import os
import tempfile
import csv

from pyfootball.splitter import VideoSplitter


class TestConfig:
    def test_default_config(self):
        vs = VideoSplitter()
        assert vs.config['split_video'] is True
        assert vs.config['create_dartclip'] is True
        assert vs.config['buffer'] == 0.5
        assert vs.config['reencode'] is False
        assert vs.config['start_number'] == 1

    def test_config_override(self):
        vs = VideoSplitter({'buffer': 1.0, 'skip': 5})
        assert vs.config['buffer'] == 1.0
        assert vs.config['skip'] == 5
        # defaults preserved
        assert vs.config['split_video'] is True


class TestExtractEvents:
    def _write_csv(self, tmpdir, rows, fieldnames):
        path = os.path.join(tmpdir, "events.csv")
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
        return path

    def test_basic_extract(self):
        vs = VideoSplitter()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_csv(tmpdir, [
                {'Position': '1000', 'Duration': '5000', 'Name': 'Play 1'},
                {'Position': '8000', 'Duration': '4000', 'Name': 'Play 2'},
            ], ['Position', 'Duration', 'Name'])

            events = vs.extract_events(path)
            assert len(events) == 2
            assert events[0]['Position'] == '1000'
            assert events[1]['Name'] == 'Play 2'

    def test_missing_required_column_raises(self):
        vs = VideoSplitter()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_csv(tmpdir, [
                {'Position': '1000', 'Name': 'Play 1'},
            ], ['Position', 'Name'])

            try:
                vs.extract_events(path)
                assert False, "Should have raised ValueError"
            except ValueError as e:
                assert 'Duration' in str(e)

    def test_file_not_found_raises(self):
        vs = VideoSplitter()
        try:
            vs.extract_events("/nonexistent/path.csv")
            assert False, "Should have raised FileNotFoundError"
        except FileNotFoundError:
            pass

    def test_utf8_bom_handled(self):
        vs = VideoSplitter()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "events.csv")
            with open(path, 'w', encoding='utf-8-sig') as f:
                f.write("Position,Duration,Name\n")
                f.write("1000,5000,Play 1\n")

            events = vs.extract_events(path)
            assert len(events) == 1
            assert events[0]['Position'] == '1000'


class TestBuildFfmpegCmd:
    def test_stream_copy_mode(self):
        vs = VideoSplitter({'reencode': False})
        cmd = vs._build_ffmpeg_cmd(["-i", "video.mp4"], 1.5, 3.0, "out.mp4")

        assert cmd[0] == "ffmpeg"
        assert "-c:v" in cmd
        assert cmd[cmd.index("-c:v") + 1] == "copy"
        assert "-ss" in cmd
        assert cmd[cmd.index("-ss") + 1] == "1.5"
        assert "-t" in cmd
        assert cmd[cmd.index("-t") + 1] == "3.0"
        assert cmd[-1] == "out.mp4"

    def test_reencode_mode(self):
        vs = VideoSplitter({'reencode': True})
        cmd = vs._build_ffmpeg_cmd(["-i", "video.mp4"], 1.5, 3.0, "out.mp4")

        assert "-c:v" in cmd
        assert cmd[cmd.index("-c:v") + 1] == "libx264"
        assert "-crf" in cmd
        # all-intra: every frame a keyframe for frame-by-frame scrubbing
        assert "-g" in cmd
        assert cmd[cmd.index("-g") + 1] == "1"
        assert "-an" in cmd

    def test_concat_input(self):
        vs = VideoSplitter()
        input_args = ["-f", "concat", "-safe", "0", "-i", "filelist.txt"]
        cmd = vs._build_ffmpeg_cmd(input_args, 10.0, 5.0, "out.mp4")

        assert "-f" in cmd
        assert "concat" in cmd
        assert "filelist.txt" in cmd


class TestDetectFileBoundaries:
    def test_explicit_file_column(self):
        vs = VideoSplitter()
        events = [
            {'Position': '1000', 'Duration': '5000', 'File': 'vid1.mp4'},
            {'Position': '6000', 'Duration': '3000', 'File': 'vid1.mp4'},
            {'Position': '1000', 'Duration': '4000', 'File': 'vid2.mp4'},
        ]
        groups = vs.detect_file_boundaries(events)
        assert len(groups) == 2
        assert len(groups[0]) == 2
        assert len(groups[1]) == 1

    def test_auto_detect_position_reset(self):
        vs = VideoSplitter()
        events = [
            {'Position': '1000', 'Duration': '5000'},
            {'Position': '8000', 'Duration': '3000'},
            {'Position': '500', 'Duration': '4000'},   # reset
            {'Position': '6000', 'Duration': '2000'},
        ]
        groups = vs.detect_file_boundaries(events)
        assert len(groups) == 2
        assert len(groups[0]) == 2
        assert len(groups[1]) == 2

    def test_empty_events(self):
        vs = VideoSplitter()
        assert vs.detect_file_boundaries([]) == []

    def test_single_file(self):
        vs = VideoSplitter()
        events = [
            {'Position': '1000', 'Duration': '5000'},
            {'Position': '8000', 'Duration': '3000'},
        ]
        groups = vs.detect_file_boundaries(events)
        assert len(groups) == 1


class TestParseDartclip:
    def test_parse_dartclip_xml(self):
        vs = VideoSplitter()

        xml_content = """<?xml version="1.0" ?>
<LIBRARY_ITEM>
  <NAME>GX021660.MP4</NAME>
  <LIBRARY_ITEM Color="Color2" IN="175180000" OUT="251470000" ItemType="Marker.Event" UNIT="RefTime">
    <CATEGORIES>
      <CATEGORY name="ODK">O</CATEGORY>
      <CATEGORY name="Down">1</CATEGORY>
    </CATEGORIES>
    <Library.MDProperties>
      <Property Name="Title">Play (1)</Property>
    </Library.MDProperties>
  </LIBRARY_ITEM>
  <LIBRARY_ITEM Color="Color2" IN="300000000" OUT="350000000" ItemType="Marker.Event" UNIT="RefTime">
    <CATEGORIES>
      <CATEGORY name="ODK">D</CATEGORY>
    </CATEGORIES>
  </LIBRARY_ITEM>
</LIBRARY_ITEM>"""

        with tempfile.TemporaryDirectory() as tmpdir:
            dc_path = os.path.join(tmpdir, "test.dartclip")
            with open(dc_path, 'w') as f:
                f.write(xml_content)

            result = vs.parse_dartclip(dc_path)

            assert result['video_file'] == 'GX021660.MP4'
            assert len(result['events']) == 2

            e1 = result['events'][0]
            assert e1['Position'] == '17518'  # 175180000 // 10000
            assert e1['Duration'] == '7629'   # (251470000 - 175180000) // 10000
            assert e1['Name'] == 'Play (1)'
            assert e1['ODK'] == 'O'
            assert e1['Down'] == '1'

            e2 = result['events'][1]
            assert e2['ODK'] == 'D'
            assert 'Name' not in e2  # no title element
