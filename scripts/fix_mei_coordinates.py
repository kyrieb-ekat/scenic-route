#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MEI Coordinate Fixing Script

This script checks and fixes empty zones in MEI files by comparing with the original JSOMR file.
"""

import json
import xml.etree.ElementTree as ET
import os
from typing import Dict, List, Optional, Any, Tuple

# Register the MEI namespace
MEI_NS = {"mei": "http://www.music-encoding.org/ns/mei"}
XML_NS = {"xml": "http://www.w3.org/XML/1998/namespace"}
ET.register_namespace('', MEI_NS["mei"])
ET.register_namespace('xml', XML_NS["xml"])

def fix_mei_coordinates(mei_file_path: str, jsomr_file_path: str, output_file_path: str) -> None:
    """
    Fix empty or incorrect zones in an MEI file by using coordinates from a JSOMR file.
    
    Args:
        mei_file_path: Path to the MEI file
        jsomr_file_path: Path to the JSOMR file with correct coordinates
        output_file_path: Path to save the fixed MEI file
    """
    try:
        # Load the MEI file
        mei_tree = ET.parse(mei_file_path)
        mei_root = mei_tree.getroot()
        
        # Load the JSOMR file
        with open(jsomr_file_path, 'r') as f:
            jsomr_data = json.load(f)
        
        # Get all zones in the MEI file
        zones = mei_root.findall(".//mei:zone", MEI_NS)
        
        # Get all staves from the JSOMR file
        staves = jsomr_data.get("staves", [])
        
        # Check if we have empty zones in the MEI file
        empty_zones = [
            zone for zone in zones 
            if int(zone.get("ulx", "0")) == 0 and 
               int(zone.get("uly", "0")) == 0 and 
               int(zone.get("lrx", "0")) == 0 and 
               int(zone.get("lry", "0")) == 0
        ]
        
        # If we have empty zones and enough staves, fix the coordinates
        if empty_zones and len(staves) >= len(empty_zones):
            print(f"Found {len(empty_zones)} empty zones to fix")
            
            # Get all sb (system break) elements
            sb_elements = mei_root.findall(".//mei:sb", MEI_NS)
            
            # Start fixing zones
            for i, zone in enumerate(zones):
                # Skip non-empty zones
                if (int(zone.get("ulx", "0")) != 0 or 
                    int(zone.get("uly", "0")) != 0 or 
                    int(zone.get("lrx", "0")) != 0 or 
                    int(zone.get("lry", "0")) != 0):
                    continue
                
                # If we have staves left, use their bounding box
                if i < len(staves):
                    staff = staves[i]
                    bb = staff["bounding_box"]
                    
                    # Set zone coordinates
                    zone.set("ulx", str(bb["ulx"]))
                    zone.set("uly", str(bb["uly"]))
                    
                    # Handle different bounding box formats
                    if "lrx" in bb and "lry" in bb:
                        zone.set("lrx", str(bb["lrx"]))
                        zone.set("lry", str(bb["lry"]))
                    else:
                        zone.set("lrx", str(bb["ulx"] + bb["ncols"]))
                        zone.set("lry", str(bb["uly"] + bb["nrows"]))
                    
                    # Find and fix corresponding sb element
                    if i < len(sb_elements):
                        sb = sb_elements[i]
                        zone_id = zone.get("{http://www.w3.org/XML/1998/namespace}id")
                        if zone_id:
                            sb.set("facs", f"#{zone_id}")
        
        # Find and check glyphs in the MEI file
        neumes = mei_root.findall(".//mei:neume", MEI_NS)
        for neume in neumes:
            # Get the facs attribute
            facs_attr = neume.get("facs", "")
            if facs_attr and facs_attr.startswith("#"):
                zone_id = facs_attr[1:]  # Remove the # character
                
                # Find the corresponding zone
                zone = mei_root.find(f".//mei:zone[@xml:id='{zone_id}']", {**MEI_NS, **XML_NS})
                
                # If zone exists but has invalid coordinates, look for matching glyph in JSOMR
                if zone is not None and (
                    int(zone.get("ulx", "0")) == 0 and 
                    int(zone.get("uly", "0")) == 0 and 
                    int(zone.get("lrx", "0")) == 0 and 
                    int(zone.get("lry", "0")) == 0
                ):
                    # Look for a matching glyph in the JSOMR file
                    for glyph in jsomr_data.get("glyphs", []):
                        # Here we'd need heuristics to match MEI neumes with JSOMR glyphs
                        # For now, we'll use a simple approach based on name
                        neume_name = neume.tag.split("}")[-1]
                        if neume_name.lower() in glyph["glyph"]["name"].lower():
                            bb = glyph["glyph"]["bounding_box"]
                            
                            # Update zone coordinates
                            zone.set("ulx", str(bb["ulx"]))
                            zone.set("uly", str(bb["uly"]))
                            zone.set("lrx", str(bb["ulx"] + bb["ncols"]))
                            zone.set("lry", str(bb["uly"] + bb["nrows"]))
                            break
        
        # Save the fixed MEI file
        mei_tree.write(output_file_path, encoding="utf-8", xml_declaration=True)
        print(f"Fixed MEI file saved to {output_file_path}")
        
    except Exception as e:
        print(f"Error fixing MEI coordinates: {e}")

def analyze_mei_structure(mei_file_path: str) -> None:
    """
    Analyze the structure of an MEI file to identify issues.
    
    Args:
        mei_file_path: Path to the MEI file
    """
    try:
        # Load the MEI file
        mei_tree = ET.parse(mei_file_path)
        mei_root = mei_tree.getroot()
        
        # Count elements of interest
        zones = mei_root.findall(".//mei:zone", MEI_NS)
        staves = mei_root.findall(".//mei:staff", MEI_NS)
        neumes = mei_root.findall(".//mei:neume", MEI_NS)
        sbs = mei_root.findall(".//mei:sb", MEI_NS)
        syllables = mei_root.findall(".//mei:syllable", MEI_NS)
        
        print(f"MEI Structure Analysis for {mei_file_path}:")
        print(f"  - Zones: {len(zones)}")
        print(f"  - Staves: {len(staves)}")
        print(f"  - System breaks: {len(sbs)}")
        print(f"  - Neumes: {len(neumes)}")
        print(f"  - Syllables: {len(syllables)}")
        
        # Check for empty zones
        empty_zones = [
            zone for zone in zones 
            if int(zone.get("ulx", "0")) == 0 and 
               int(zone.get("uly", "0")) == 0 and 
               int(zone.get("lrx", "0")) == 0 and 
               int(zone.get("lry", "0")) == 0
        ]
        print(f"  - Empty zones: {len(empty_zones)}")
        
        # Check for sb elements without facs attribute
        sb_no_facs = [sb for sb in sbs if not sb.get("facs")]
        print(f"  - SB elements without facs: {len(sb_no_facs)}")
        
        # Check for zones without xml:id
        zones_no_id = [zone for zone in zones if not zone.get("{http://www.w3.org/XML/1998/namespace}id")]
        print(f"  - Zones without xml:id: {len(zones_no_id)}")
        
    except Exception as e:
        print(f"Error analyzing MEI file: {e}")

def find_missing_sb_references(mei_file_path: str) -> None:
    """
    Find missing system break references in an MEI file.
    
    Args:
        mei_file_path: Path to the MEI file
    """
    try:
        # Load the MEI file
        mei_tree = ET.parse(mei_file_path)
        mei_root = mei_tree.getroot()
        
        # Get all zones and their IDs
        zones = mei_root.findall(".//mei:zone", MEI_NS)
        zone_ids = [zone.get("{http://www.w3.org/XML/1998/namespace}id") for zone in zones if zone.get("{http://www.w3.org/XML/1998/namespace}id")]
        
        # Get all system breaks and their references
        sbs = mei_root.findall(".//mei:sb", MEI_NS)
        sb_refs = []
        for sb in sbs:
            facs = sb.get("facs", "")
            if facs and facs.startswith("#"):
                sb_refs.append(facs[1:])
        
        # Find zones that are not referenced by system breaks
        unreferenced_zones = set(zone_ids) - set(sb_refs)
        if unreferenced_zones:
            print(f"Found {len(unreferenced_zones)} zones not referenced by system breaks:")
            for zone_id in unreferenced_zones:
                print(f"  - {zone_id}")
        else:
            print("All zones are properly referenced by system breaks.")
        
        # Find system breaks referencing non-existent zones
        invalid_refs = set(sb_refs) - set(zone_ids)
        if invalid_refs:
            print(f"Found {len(invalid_refs)} system breaks referencing non-existent zones:")
            for ref in invalid_refs:
                print(f"  - {ref}")
        else:
            print("All system break references point to existing zones.")
        
    except Exception as e:
        print(f"Error finding missing SB references: {e}")

def add_missing_sb_elements(mei_file_path: str, output_file_path: str) -> None:
    """
    Add missing system break elements to an MEI file.
    
    Args:
        mei_file_path: Path to the MEI file
        output_file_path: Path to save the updated MEI file
    """
    try:
        # Load the MEI file
        mei_tree = ET.parse(mei_file_path)
        mei_root = mei_tree.getroot()
        
        # Get all zones and their IDs
        zones = mei_root.findall(".//mei:zone", MEI_NS)
        zone_ids = []
        for zone in zones:
            zone_id = zone.get("{http://www.w3.org/XML/1998/namespace}id")
            if zone_id:
                zone_ids.append(zone_id)
        
        # Get all system breaks and their references
        sbs = mei_root.findall(".//mei:sb", MEI_NS)
        sb_refs = []
        for sb in sbs:
            facs = sb.get("facs", "")
            if facs and facs.startswith("#"):
                sb_refs.append(facs[1:])
        
        # Find zones that are not referenced by system breaks
        unreferenced_zones = set(zone_ids) - set(sb_refs)
        
        if unreferenced_zones:
            print(f"Adding {len(unreferenced_zones)} missing system break elements")
            
            # Find the first layer element
            layer = mei_root.find(".//mei:layer", MEI_NS)
            
            if layer is not None:
                # Add system break elements for each unreferenced zone
                for i, zone_id in enumerate(unreferenced_zones):
                    sb = ET.SubElement(layer, "{http://www.music-encoding.org/ns/mei}sb")
                    sb.set("n", str(len(sbs) + i + 1))
                    sb.set("facs", f"#{zone_id}")
                
                # Save the updated MEI file
                mei_tree.write(output_file_path, encoding="utf-8", xml_declaration=True)
                print(f"Updated MEI file saved to {output_file_path}")
            else:
                print("Error: Could not find a layer element in the MEI file")
        else:
            print("No missing system break elements found")
        
    except Exception as e:
        print(f"Error adding missing SB elements: {e}")

def main():
    """Main function to run the MEI coordinate fixing script."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Fix coordinates in MEI files")
    parser.add_argument("--mei", required=True, help="Path to the MEI file")
    parser.add_argument("--jsomr", required=True, help="Path to the JSOMR file")
    parser.add_argument("--output", required=True, help="Path to save the fixed MEI file")
    parser.add_argument("--analyze", action="store_true", help="Analyze the structure of the MEI file")
    parser.add_argument("--find-missing", action="store_true", help="Find missing system break references")
    parser.add_argument("--add-missing", action="store_true", help="Add missing system break elements")
    
    args = parser.parse_args()
    
    if args.analyze:
        analyze_mei_structure(args.mei)
    
    if args.find_missing:
        find_missing_sb_references(args.mei)
    
    if args.add_missing:
        add_missing_sb_elements(args.mei, args.output)
    
    if not any([args.analyze, args.find_missing, args.add_missing]):
        fix_mei_coordinates(args.mei, args.jsomr, args.output)

if __name__ == "__main__":
    main()