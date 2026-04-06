"""Tests for dartclip XML generation."""

import os
import tempfile
import xml.etree.ElementTree as ET

from pyfootball.dartclip import create_dartclip, _get_column_value


class TestGetColumnValue:
    def test_exact_match(self):
        event = {'Position': '1000', 'ODK': 'O'}
        assert _get_column_value(event, 'ODK') == 'O'

    def test_case_insensitive(self):
        event = {'position': '1000', 'odk': 'D'}
        assert _get_column_value(event, 'Position') == '1000'
        assert _get_column_value(event, 'ODK') == 'D'

    def test_missing_returns_default(self):
        event = {'Position': '1000'}
        assert _get_column_value(event, 'Missing') == 'N/A'
        assert _get_column_value(event, 'Missing', 'custom') == 'custom'


class TestCreateDartclip:
    def test_creates_valid_xml(self):
        event = {
            'Position': '5000',
            'Duration': '3000',
            'Name': 'Play (1)',
            'ODK': 'O',
            'Down': '1',
            'Play Type': 'Run',
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_base = os.path.join(tmpdir, "Play_001")
            create_dartclip(event, output_base)

            output_path = output_base + ".dartclip"
            assert os.path.exists(output_path)

            tree = ET.parse(output_path)
            root = tree.getroot()

            assert root.tag == 'LIBRARY_ITEM'
            assert root.findtext('NAME') == 'Play_001.mp4'

            marker = root.find("LIBRARY_ITEM[@ItemType='Marker.Event']")
            assert marker is not None
            assert marker.get('OUT') == '30000000'  # 3000 * 10000
            assert marker.get('IN') == '0'

            cats = marker.find('CATEGORIES')
            cat_dict = {c.get('name'): c.text for c in cats.findall('CATEGORY')}
            assert cat_dict['ODK'] == 'O'
            assert cat_dict['Down'] == '1'
            assert cat_dict['Play Type'] == 'Run'

    def test_missing_optional_columns(self):
        event = {
            'Position': '1000',
            'Duration': '2000',
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_base = os.path.join(tmpdir, "Play_002")
            create_dartclip(event, output_base)

            output_path = output_base + ".dartclip"
            assert os.path.exists(output_path)

            tree = ET.parse(output_path)
            root = tree.getroot()
            marker = root.find("LIBRARY_ITEM[@ItemType='Marker.Event']")
            cats = marker.find('CATEGORIES')
            # No standard categories should be present
            assert len(cats.findall('CATEGORY')) == 0

    def test_extra_columns_become_categories(self):
        event = {
            'Position': '1000',
            'Duration': '2000',
            'Custom Field': 'custom_value',
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_base = os.path.join(tmpdir, "Play_003")
            create_dartclip(event, output_base)

            tree = ET.parse(output_base + ".dartclip")
            root = tree.getroot()
            marker = root.find("LIBRARY_ITEM[@ItemType='Marker.Event']")
            cats = marker.find('CATEGORIES')
            cat_dict = {c.get('name'): c.text for c in cats.findall('CATEGORY')}
            assert cat_dict['Custom Field'] == 'custom_value'
