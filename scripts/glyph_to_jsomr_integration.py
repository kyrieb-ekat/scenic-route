#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Glyph Integration Script for MEI Workflow

This script integrates glyph information from XML files with staff information
in JSOMR files to create a complete input for MEI encoding.
"""

import json
import xml.etree.ElementTree as ET
import re
import os
import numpy as np
from typing import Dict, List, Tuple, Optional, Any

def parse_gamera_xml(xml_file_path: str) -> List[Dict[str, Any]]:
    """
    Parse Gamera XML file containing glyph information.
    
    Args:
        xml_file_path: Path to the Gamera XML file
        
    Returns:
        List of dictionaries containing glyph information
    """
    try:
        tree = ET.parse(xml_file_path)
        root = tree.getroot()
        
        glyphs = []
        
        # Find all glyph elements in the XML
        for glyph_elem in root.findall(".//glyph"):
            # Extract basic glyph attributes
            ulx = int(glyph_elem.get("ulx", 0))
            uly = int(glyph_elem.get("uly", 0))
            ncols = int(glyph_elem.get("ncols", 0))
            nrows = int(glyph_elem.get("nrows", 0))
            
            # Get the glyph ID (name)
            id_elem = glyph_elem.find(".//id")
            if id_elem is not None:
                glyph_name = id_elem.get("name", "unknown")
                confidence = float(id_elem.get("confidence", 0.0))
            else:
                glyph_name = "unknown"
                confidence = 0.0
            
            # Create a glyph dictionary
            glyph = {
                "bounding_box": {
                    "ulx": ulx,
                    "uly": uly,
                    "ncols": ncols,
                    "nrows": nrows
                },
                "name": glyph_name,
                "confidence": confidence
            }
            
            glyphs.append(glyph)
        
        return glyphs
        
    except Exception as e:
        print(f"Error parsing Gamera XML: {e}")
        return []

def assign_glyphs_to_staves(glyphs: List[Dict[str, Any]], staves: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Assign glyphs to staves based on vertical position.
    
    Args:
        glyphs: List of glyph dictionaries
        staves: List of staff dictionaries
        
    Returns:
        Updated list of glyph dictionaries with staff assignments
    """
    assigned_glyphs = []
    
    for glyph in glyphs:
        # Skip glyphs with certain names (like skip.edge)
        if glyph["name"] == "skip.edge":
            continue
            
        glyph_center_y = glyph["bounding_box"]["uly"] + (glyph["bounding_box"]["nrows"] / 2)
        
        # Find the closest staff
        closest_staff = None
        min_distance = float('inf')
        
        for i, staff in enumerate(staves):
            staff_center_y = staff["bounding_box"]["uly"] + (staff["bounding_box"]["nrows"] / 2)
            distance = abs(glyph_center_y - staff_center_y)
            
            if distance < min_distance:
                min_distance = distance
                closest_staff = i
        
        if closest_staff is not None:
            # Create a complete glyph entry for JSOMR
            jsomr_glyph = {
                "pitch": {
                    "staff": str(closest_staff + 1),  # 1-indexed staff number
                    "offset": str(glyph["bounding_box"]["ulx"]),
                    "strt_pos": "1",  # Default value, may need adjustment
                    "note": "c",  # Default value, should be determined by position
                    "octave": "4",  # Default value, should be determined by position
                    "clef_pos": "None",  # Placeholder
                    "clef": "None"  # Placeholder
                },
                "glyph": {
                    "bounding_box": glyph["bounding_box"],
                    "state": "AUTOMATIC",
                    "name": glyph["name"]
                }
            }
            
            assigned_glyphs.append(jsomr_glyph)
    
    return assigned_glyphs

def estimate_pitch_from_position(glyph: Dict[str, Any], staff: Dict[str, Any]) -> Tuple[str, str]:
    """
    Estimate pitch (note and octave) based on vertical position relative to staff lines.
    
    Args:
        glyph: Glyph dictionary
        staff: Staff dictionary
        
    Returns:
        Tuple of (note, octave)
    """
    # Get the vertical position of the glyph relative to the staff
    glyph_center_y = glyph["glyph"]["bounding_box"]["uly"] + (glyph["glyph"]["bounding_box"]["nrows"] / 2)
    
    # Get the positions of the staff lines
    line_positions = staff["line_positions"]
    
    # Calculate average y-position for each staff line
    line_centers = []
    for line in line_positions:
        line_y_values = [point[1] for point in line]
        line_centers.append(np.mean(line_y_values))
    
    # Find the closest line
    closest_line_idx = np.argmin([abs(glyph_center_y - line_center) for line_center in line_centers])
    
    # Get staff information
    num_lines = staff.get("num_lines", 4)  # Default to 4 if not specified
    
    # Create a dynamic pitch map based on the clef information
    # This is a placeholder - in a real implementation, you would extract 
    # clef information from the staff or nearby clef glyphs
    base_note = "c"  # Default base note
    base_octave = 4   # Default base octave
    
    # Scale degrees for the traditional medieval scale (adjust as needed)
    scale_degrees = ["c", "d", "e", "f", "g", "a", "b"]
    
    # Create the pitch map dynamically
    pitch_map = {}
    for i in range(num_lines):
        # Calculate the scale degree: Start with base_note and go up the scale
        degree_idx = (scale_degrees.index(base_note) + i) % len(scale_degrees)
        note = scale_degrees[degree_idx]
        
        # Calculate octave (increment when passing from B to C)
        octave = base_octave
        if i > 0 and degree_idx <= scale_degrees.index(base_note):
            octave += 1
            
        pitch_map[i] = (note, str(octave))
    
    # If the glyph is significantly above or below the staff
    if closest_line_idx == 0 and glyph_center_y < line_centers[0]:
        # Calculate the note below the lowest line
        lowest_note, lowest_octave = pitch_map[0]
        idx = scale_degrees.index(lowest_note) - 1
        if idx < 0:
            idx = len(scale_degrees) - 1
            below_octave = int(lowest_octave) - 1
        else:
            below_octave = int(lowest_octave)
        return (scale_degrees[idx], str(below_octave))
        
    elif closest_line_idx == len(line_centers) - 1 and glyph_center_y > line_centers[-1]:
        # Calculate the note above the highest line
        highest_note, highest_octave = pitch_map[num_lines - 1]
        idx = (scale_degrees.index(highest_note) + 1) % len(scale_degrees)
        above_octave = int(highest_octave)
        if idx == 0:  # If we've wrapped around to C, increment octave
            above_octave += 1
        return (scale_degrees[idx], str(above_octave))

    # Ensure closest_line_idx is a Python int
    closest_line_idx = int(closest_line_idx)  # Ensure closest_line_idx is an int
    
    # Default to the closest line's pitch
    return pitch_map.get(int(closest_line_idx), (base_note, str(base_octave)))  # Explicitly cast to int for dictionary key

def update_glyph_pitch_info(glyphs: List[Dict[str, Any]], staves: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Update glyph pitch information based on position relative to staff lines.
    
    Args:
        glyphs: List of glyph dictionaries
        staves: List of staff dictionaries
        
    Returns:
        Updated list of glyph dictionaries with pitch information
    """
    updated_glyphs = []
    
    for glyph in glyphs:
        staff_idx = int(glyph["pitch"]["staff"]) - 1  # Convert to 0-indexed
        
        if staff_idx < len(staves):
            staff = staves[staff_idx]
            
            # Skip updating pitch for certain glyph types like clefs, custos, etc.
            if any(keyword in glyph["glyph"]["name"].lower() for keyword in ["clef", "custos", "accid", "divLine"]):
                # For these specific types, we may need special handling
                if "clef" in glyph["glyph"]["name"].lower():
                    glyph["pitch"]["clef"] = "C"  # Default for neume notation
                    glyph["pitch"]["clef_pos"] = "4"  # Default position
            else:
                # For neumes and other pitch-related glyphs
                note, octave = estimate_pitch_from_position(glyph, staff)
                glyph["pitch"]["note"] = note
                glyph["pitch"]["octave"] = octave
        
        updated_glyphs.append(glyph)
    
    return updated_glyphs

def integrate_glyphs_with_jsomr(jsomr_file_path: str, xml_file_path: str, output_file_path: str):
    """
    Integrate glyph information from XML with staff information in JSOMR.
    
    Args:
        jsomr_file_path: Path to the JSOMR file
        xml_file_path: Path to the XML file with glyph information
        output_file_path: Path to save the integrated JSOMR file
    """
    try:
        # Load the JSOMR file
        with open(jsomr_file_path, 'r') as f:
            jsomr_data = json.load(f)
        
        # Extract staff information
        staves = jsomr_data.get("staves", [])
        
        # Parse glyph information from XML
        glyphs = parse_gamera_xml(xml_file_path)
        
        # Assign glyphs to staves
        assigned_glyphs = assign_glyphs_to_staves(glyphs, staves)
        
        # Update glyph pitch information
        updated_glyphs = update_glyph_pitch_info(assigned_glyphs, staves)
        
        # Update the JSOMR data with the integrated glyphs
        jsomr_data["glyphs"] = updated_glyphs
        
        # Save the updated JSOMR file
        with open(output_file_path, 'w') as f:
            json.dump(jsomr_data, f, indent=2)
            
        print(f"Successfully integrated glyphs and saved to {output_file_path}")
        
    except Exception as e:
        print(f"Error integrating glyphs with JSOMR: {e}")

def main():
    """Main function to run the glyph integration script."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Integrate glyph information with JSOMR files")
    parser.add_argument("jsomr_file", help="Path to the JSOMR file")
    parser.add_argument("xml_file", help="Path to the XML file with glyph information")
    parser.add_argument("output_file", help="Path to save the integrated JSOMR file")
    
    args = parser.parse_args()
    
    integrate_glyphs_with_jsomr(args.jsomr_file, args.xml_file, args.output_file)

if __name__ == "__main__":
    main()