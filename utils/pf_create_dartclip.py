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

    # Add CATEGORIES to the nested LIBRARY_ITEM
    # TODO: Generalise to all/any columns
    categories = ET.SubElement(library_item, "CATEGORIES")
    ET.SubElement(categories, "CATEGORY", name="Down").text = event['Down']
    ET.SubElement(categories, "CATEGORY", name="ODK").text = event['ODK']
    ET.SubElement(categories, "CATEGORY", name="Play Type").text = event['Play Type']
    # ET.SubElement(categories, "CATEGORY", name="DIST").text = event['DIST']
    # ET.SubElement(categories, "CATEGORY", name="RESULT").text = event['RESULT']

    # Add Library.MDProperties to the root
    md_properties = ET.SubElement(root, "Library.MDProperties")
    ET.SubElement(md_properties, "Property", Name="Title").text = file_name

    # Add another LIBRARY_ITEM to the root
    library_item2 = ET.SubElement(root, "LIBRARY_ITEM", ItemType="GameTime")
    ET.SubElement(library_item2, "ID").text = "0"

    # Add TYPE to the root
    ET.SubElement(root, "TYPE").text = "1"

    # Generate the XML string
    # xml_str = ET.tostring(root, encoding='utf8').decode('utf8')
    # print(xml_str)

    # Complete the file and save
    tree = ET.ElementTree(root)
    output_path = output_name + ".dartclip"
    tree.write(output_path)


def create_dartclip_v0(event, output_name):
    """
    Creates a single .dartclip file for the given event.
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
    odk_category = ET.SubElement(categories_elem, "CATEGORY", name="ODK")
    odk_category.text = event['ODK']
    play_type_category = ET.SubElement(categories_elem, "CATEGORY", name="Play Type")
    play_type_category.text = event['Play Type']
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