#!/usr/bin/env python
#conda activate video_edits

import csv
import os
import xml.etree.ElementTree as ET

# own functions
from utils.pf_helpers import select_file

def create_dartclip(event, output_name):
    """
    Creates a single .dartclip file for the given event.
    
    This function creates a dartclip file with the available metadata.
    It handles case-insensitive column matching and gracefully handles missing columns.
    
    Args:
        event (dict): Dictionary containing event metadata
        output_name (str): Base name for the output file (without extension)
    """
    # Extract the base file name
    file_name = os.path.splitext(os.path.basename(output_name))[0]

    # Create the root element
    root = ET.Element("LIBRARY_ITEM")

    # Add child elements to the root
    ET.SubElement(root, "NAME").text = file_name+'.mp4'
    ET.SubElement(root, "ID").text = "0"
    version = ET.SubElement(root, "VERSION")
    version.text = "2.0"
    version.set("subversion", "1")

    # Add a nested LIBRARY_ITEM
    library_item = ET.SubElement(root, "LIBRARY_ITEM")
    library_item.set("Color", "Color2") # TODO: Different colors for O/D 
    library_item.set("IN", "0")
    library_item.set("ItemType", "Marker.Event")
    library_item.set("OUT", event['Duration'] + "0000")
    library_item.set("UNIT", "RefTime")

    # Case-insensitive column lookup helper function
    def get_column_value(column_name):
        # First try exact match
        if column_name in event:
            return event[column_name]
        
        # Try case-insensitive match
        for key in event:
            if key.lower() == column_name.lower():
                return event[key]
        
        # Return a default value if not found
        return "N/A"

    # Add CATEGORIES to the nested LIBRARY_ITEM
    categories = ET.SubElement(library_item, "CATEGORIES")
    
    # Add standard categories with case-insensitive column matching
    category_names = ["Down", "ODK", "Play Type", "DIST", "RESULT"]
    for category in category_names:
        value = get_column_value(category)
        if value != "N/A":  # Only add if we found a value
            ET.SubElement(categories, "CATEGORY", name=category).text = value

    # Add any additional columns as categories
    for key in event:
        # Skip Position and Duration as they are used for timing
        if key.lower() not in ['position', 'duration', 'name'] and key not in category_names:
            ET.SubElement(categories, "CATEGORY", name=key).text = event[key]

    # Add Library.MDProperties to the root
    md_properties = ET.SubElement(root, "Library.MDProperties")
    ET.SubElement(md_properties, "Property", Name="Title").text = file_name

    # Add another LIBRARY_ITEM to the root
    library_item2 = ET.SubElement(root, "LIBRARY_ITEM", ItemType="GameTime")
    ET.SubElement(library_item2, "ID").text = "0"

    # Add TYPE to the root
    ET.SubElement(root, "TYPE").text = "1"

    # Complete the file and save
    tree = ET.ElementTree(root)
    output_path = output_name + ".dartclip"
    tree.write(output_path)


def create_dartclip_v0(event, output_name):
    """
    Creates a single .dartclip file for the given event.
    
    This is the legacy version kept for compatibility.
    """
    # Extract the base file name
    file_name = os.path.splitext(os.path.basename(output_name))[0]
    
    # Create the root element
    root = ET.Element("LIBRARY_ITEM")

    # Add child elements
    ET.SubElement(root, "NAME").text = file_name+'.mp4'
    ET.SubElement(root, "ID").text = "0"
    ET.SubElement(root, "VERSION", subversion="1").text = "2.0"
    
    # Add marker event as attributes directly to LIBRARY_ITEM
    ET.SubElement(root, "LIBRARY_ITEM", ItemType="Marker.Event",
                              IN="0", OUT=event['Duration'] + "0000",
                              UNIT="RefTime", Color="Color2")
    
    # Add ODK and Play Type categories
    categories_elem = ET.SubElement(root, "CATEGORIES")
    
    # Case-insensitive column lookup helper function
    def get_column_value(column_name):
        # First try exact match
        if column_name in event:
            return event[column_name]
        
        # Try case-insensitive match
        for key in event:
            if key.lower() == column_name.lower():
                return event[key]
        
        # Return a default value if not found
        return "N/A"
    
    # Add standard categories with case-insensitive column matching
    odk_value = get_column_value("ODK")
    if odk_value != "N/A":
        ET.SubElement(categories_elem, "CATEGORY", name="ODK").text = odk_value
        
    play_type_value = get_column_value("Play Type")
    if play_type_value != "N/A":
        ET.SubElement(categories_elem, "CATEGORY", name="Play Type").text = play_type_value
    
    # Manually add closing tag for LIBRARY_ITEM
    ET.SubElement(root, "/LIBRARY_ITEM")
    
    # Add Library.MDProperties and Property elements
    md_properties = ET.SubElement(root, "Library.MDProperties")
    property_elem = ET.SubElement(md_properties, "Property", Name="Title")
    property_elem.text = file_name

    # Add the last LIBRARY_ITEM with ItemType="GameTime"
    game_time_item = ET.SubElement(root, "LIBRARY_ITEM", ItemType="GameTime")
    ET.SubElement(game_time_item, "ID").text = "0"
    # Add TYPE element to the last LIBRARY_ITEM
    ET.SubElement(root, "TYPE").text = "1"

    # Complete the file and save
    tree = ET.ElementTree(root)
    output_path = output_name + ".dartclip"
    tree.write(output_path)
    print(f"Generated {output_path} successfully!")