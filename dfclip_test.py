#!/usr/bin/env python

import xml.etree.ElementTree as ET

def create_dartclip(file_path, video_name, unique_id, version, marker_in, marker_out):
    # Create the root element
    root = ET.Element("LIBRARY_ITEM")

    # Add child elements
    ET.SubElement(root, "NAME").text = video_name
    ET.SubElement(root, "ID").text = unique_id
    ET.SubElement(root, "VERSION", subversion="1").text = version

    # Add marker event
    marker_event = ET.SubElement(root, "LIBRARY_ITEM", ItemType="Marker.Event")
    ET.SubElement(marker_event, "IN").text = str(marker_in)
    ET.SubElement(marker_event, "OUT").text = str(marker_out)
    ET.SubElement(marker_event, "UNIT").text = "RefTime"
    ET.SubElement(marker_event, "Color").text = "Color2"

    # Create an ElementTree from the root
    tree = ET.ElementTree(root)

    # Write the content to the specified file
    tree.write(file_path, xml_declaration=False, encoding="utf-8")

# Usage example
create_dartclip(
    file_path="my_video.dartclip",
    video_name="play_001_test.mp4",
    unique_id="12345",
    version="2.0",
    marker_in=0,
    marker_out=80000000
)
print("DartClip file created successfully.")