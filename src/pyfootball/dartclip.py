"""Dartfish .dartclip XML file generation."""

import os
import xml.etree.ElementTree as ET


def _get_column_value(event, column_name, default="N/A"):
    """Case-insensitive column lookup in an event dict."""
    if column_name in event:
        return event[column_name]
    for key in event:
        if key.lower() == column_name.lower():
            return event[key]
    return default


def create_dartclip(event, output_name):
    """
    Creates a single .dartclip file for the given event.

    Handles case-insensitive column matching and gracefully handles
    missing columns.

    Args:
        event: Dictionary containing event metadata.
        output_name: Base name for the output file (without extension).
    """
    file_name = os.path.splitext(os.path.basename(output_name))[0]

    root = ET.Element("LIBRARY_ITEM")

    ET.SubElement(root, "NAME").text = file_name + '.mp4'
    ET.SubElement(root, "ID").text = "0"
    version = ET.SubElement(root, "VERSION")
    version.text = "2.0"
    version.set("subversion", "1")

    library_item = ET.SubElement(root, "LIBRARY_ITEM")
    library_item.set("Color", "Color2")
    library_item.set("IN", "0")
    library_item.set("ItemType", "Marker.Event")
    library_item.set("OUT", event['Duration'] + "0000")
    library_item.set("UNIT", "RefTime")

    categories = ET.SubElement(library_item, "CATEGORIES")

    category_names = ["Down", "ODK", "Play Type", "DIST", "RESULT"]
    for category in category_names:
        value = _get_column_value(event, category)
        if value != "N/A":
            ET.SubElement(categories, "CATEGORY", name=category).text = value

    for key in event:
        if key.lower() not in ['position', 'duration', 'name'] and key not in category_names:
            ET.SubElement(categories, "CATEGORY", name=key).text = event[key]

    md_properties = ET.SubElement(root, "Library.MDProperties")
    ET.SubElement(md_properties, "Property", Name="Title").text = file_name

    library_item2 = ET.SubElement(root, "LIBRARY_ITEM", ItemType="GameTime")
    ET.SubElement(library_item2, "ID").text = "0"

    ET.SubElement(root, "TYPE").text = "1"

    tree = ET.ElementTree(root)
    output_path = output_name + ".dartclip"
    tree.write(output_path)
