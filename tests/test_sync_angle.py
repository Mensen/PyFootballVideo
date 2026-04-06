"""Tests for sync angle core logic."""

import os
import csv
import tempfile

from pyfootball.sync_angle import (
    parse_timestamp, calculate_sync_offset, export_synced_csv
)


class TestParseTimestamp:
    def test_minutes_seconds(self):
        assert parse_timestamp('2:01.20') == (2 * 60 + 1.20) * 1000

    def test_seconds_decimal(self):
        assert parse_timestamp('121.20') == 121.20 * 1000

    def test_raw_milliseconds(self):
        assert parse_timestamp('5000') == 5000.0

    def test_with_whitespace(self):
        assert parse_timestamp('  2:01.20  ') == (2 * 60 + 1.20) * 1000

    def test_zero(self):
        assert parse_timestamp('0') == 0.0

    def test_minutes_no_decimal(self):
        assert parse_timestamp('1:30') == 90 * 1000


class TestCalculateSyncOffset:
    def _make_events(self):
        return [
            {'Name': 'Play (1)', 'Position_abs_ms': 10000.0, 'Duration_ms': 5000.0, 'source_file': 'v1.mp4'},
            {'Name': 'Play (2)', 'Position_abs_ms': 20000.0, 'Duration_ms': 4000.0, 'source_file': 'v1.mp4'},
            {'Name': 'Play (3)', 'Position_abs_ms': 30000.0, 'Duration_ms': 6000.0, 'source_file': 'v2.mp4'},
        ]

    def test_exact_match(self):
        events = self._make_events()
        offset = calculate_sync_offset(events, 'Play (2)', 25000.0)
        assert offset == 5000.0  # 25000 - 20000

    def test_partial_match(self):
        events = self._make_events()
        offset = calculate_sync_offset(events, 'play (3)', 35000.0)
        assert offset == 5000.0

    def test_not_found_raises(self):
        events = self._make_events()
        try:
            calculate_sync_offset(events, 'NonExistent', 10000.0)
            assert False, "Should have raised ValueError"
        except ValueError:
            pass


class TestExportSyncedCsv:
    def test_csv_output(self):
        events = [
            {'Name': 'Play (1)', 'Position_abs_ms': 10000.0, 'Duration_ms': 5000.0,
             'source_file': 'v1.mp4', 'ODK': 'O'},
            {'Name': 'Play (2)', 'Position_abs_ms': 20000.0, 'Duration_ms': 4000.0,
             'source_file': 'v1.mp4', 'ODK': 'D'},
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "synced.csv")
            result = export_synced_csv(events, 5000.0, output_path)

            assert result == output_path
            assert os.path.exists(output_path)

            with open(output_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) == 2
            assert rows[0]['Position'] == '15000'   # 10000 + 5000
            assert rows[0]['Duration'] == '5000'
            assert rows[0]['Name'] == 'Play (1)'
            assert rows[0]['ODK'] == 'O'
            assert rows[1]['Position'] == '25000'   # 20000 + 5000
