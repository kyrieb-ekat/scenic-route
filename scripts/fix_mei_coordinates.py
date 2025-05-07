#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced MEI Coordinate Fixing Script

This script improves MEI files by:
1. Fixing empty zones by using coordinates from a JSOMR file
2. Adding proper clef elements to each staff based on JSOMR data
3. Providing analysis tools to diagnose MEI structure issues
"""

import json
import xml.etree.ElementTree as ET
import os
from typing import Dict, List, Optional, Any, Tuple

# Register the MEI namespace
# This is important for proper XML generation and XPath queries 
MEI_NS = {"mei": "http://www.music-encoding.org/ns/mei"}
XML_NS = {"xml": "http://www.w3.org/XML/1998/namespace"}
ET.register_namespace('', MEI_NS["mei"])
ET.register_namespace('xml', XML_NS["xml"])

def fix_mei_coordinates(mei_file_path: str, jsomr_file_path: str, output_file_path: str) -> None:
    """
    Fix empty or incorrect zones in an MEI file by using coordinates from a JSOMR file.
    
    This function:
    1. Finds zones with zero coordinates
    2. Updates them with staff coordinates from the JSOMR file
    3. Updates system break references to point to the correct zones
    
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
        # We define empty zones as those with all coordinate values set to zero
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
                # Skip non-empty zones - we only want to fix zones with zero coordinates
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
                    
                    # Handle different bounding box formats (some have lrx/lry, others have ncols/nrows)
                    if "lrx" in bb and "lry" in bb:
                        zone.set("lrx", str(bb["lrx"]))
                        zone.set("lry", str(bb["lry"]))
                    else:
                        zone.set("lrx", str(bb["ulx"] + bb["ncols"]))
                        zone.set("lry", str(bb["uly"] + bb["nrows"]))
                    
                    # Find and fix corresponding sb element
                    # This ensures system breaks point to the correct zones
                    if i < len(sb_elements):
                        sb = sb_elements[i]
                        zone_id = zone.get("{http://www.w3.org/XML/1998/namespace}id")
                        if zone_id:
                            sb.set("facs", f"#{zone_id}")
        
        # Save the fixed MEI file
        mei_tree.write(output_file_path, encoding="utf-8", xml_declaration=True)
        print(f"Fixed MEI file saved to {output_file_path}")
        
    except Exception as e:
        print(f"Error fixing MEI coordinates: {e}")

def add_clef_elements(mei_file_path: str, jsomr_file_path: str, output_file_path: str) -> None:
    """
    Add clef elements to an MEI file based on clefs in the JSOMR file.
    
    This function:
    1. Identifies all clef glyphs in the JSOMR file
    2. Creates new zones for each clef
    3. Creates proper MEI clef elements linked to these zones
    4. Positions clefs after their corresponding system breaks
    
    This ensures each staff has its clefs properly represented in the MEI.
    
    Args:
        mei_file_path: Path to the MEI file
        jsomr_file_path: Path to the JSOMR file
        output_file_path: Path to save the updated MEI file
    """
    try:
        # Load the MEI file
        mei_tree = ET.parse(mei_file_path)
        mei_root = mei_tree.getroot()
        
        # Load the JSOMR file
        with open(jsomr_file_path, 'r') as f:
            jsomr_data = json.load(f)
        
        # Get all staves and glyphs from JSOMR
        staves = jsomr_data.get("staves", [])
        glyphs = jsomr_data.get("glyphs", [])
        
        # Filter for only clef glyphs
        # We're specifically looking for clef glyphs as requested
        # This filter focuses on both directly named clefs (clef.f, clef.c, clef.g)
        # and the generic clef.not which also represents clefs
        clef_glyphs = [g for g in glyphs if 
                      ("clef.f" in g["glyph"]["name"] or 
                       "clef.c" in g["glyph"]["name"] or 
                       "clef.g" in g["glyph"]["name"] or
                       "clef.not" in g["glyph"]["name"])]
        
        # Group clefs by staff
        # This helps us organize which clefs belong to which staff
        clefs_by_staff = {}
        for glyph in clef_glyphs:
            staff_num = glyph["pitch"]["staff"]
            if staff_num not in clefs_by_staff:
                clefs_by_staff[staff_num] = []
            clefs_by_staff[staff_num].append(glyph)
        
        # Find the facsimile element or create one if missing
        # The facsimile element is required for storing zones
        facsimile = mei_root.find(".//mei:facsimile", MEI_NS)
        if facsimile is None:
            music = mei_root.find(".//mei:music", MEI_NS)
            if music is None:
                print("Error: Could not find music element")
                return
            facsimile = ET.SubElement(music, "{http://www.music-encoding.org/ns/mei}facsimile")
        
        # Find the surface element or create one if missing
        # The surface element contains zones
        surface = facsimile.find(".//mei:surface", MEI_NS)
        if surface is None:
            surface = ET.SubElement(facsimile, "{http://www.music-encoding.org/ns/mei}surface")
        
        # Find the layer element
        # The layer element contains musical content including clefs
        layer = mei_root.find(".//mei:layer", MEI_NS)
        if layer is None:
            print("Error: Could not find layer element")
            return
        
        # Create a mapping from staff number to associated SB element and zone
        # This helps us position clefs after their corresponding system breaks
        sb_elements = mei_root.findall(".//mei:sb", MEI_NS)
        sb_map = {}
        for sb in sb_elements:
            staff_num = sb.get("n")
            if staff_num:
                facs = sb.get("facs", "")
                if facs and facs.startswith("#"):
                    sb_map[staff_num] = (sb, facs[1:])
        
        # Add clefs for each staff
        clefs_added = 0
        for staff_num, staff_clefs in clefs_by_staff.items():
            # Skip empty staff clefs
            if not staff_clefs:
                continue
                
            # Get the associated SB element and zone ID
            if staff_num in sb_map:
                sb, zone_id = sb_map[staff_num]
                
                # Find the corresponding system break in the layer
                try:
                    sb_index = list(layer).index(sb)
                except ValueError:
                    print(f"Warning: Could not find system break for staff {staff_num} in layer")
                    continue
                
                # For each clef, create a zone and clef element
                for i, clef_glyph in enumerate(staff_clefs):
                    # Create a zone for the clef
                    clef_zone = ET.SubElement(surface, "{http://www.music-encoding.org/ns/mei}zone")
                    clef_zone_id = f"zone-clef-{staff_num}-{i+1}"
                    clef_zone.set("{http://www.w3.org/XML/1998/namespace}id", clef_zone_id)
                    
                    # Set zone coordinates from the glyph's bounding box
                    bb = clef_glyph["glyph"]["bounding_box"]
                    clef_zone.set("ulx", str(bb["ulx"]))
                    clef_zone.set("uly", str(bb["uly"]))
                    clef_zone.set("lrx", str(bb["ulx"] + bb["ncols"]))
                    clef_zone.set("lry", str(bb["uly"] + bb["nrows"]))
                    
                    # Determine clef shape based on name
                    # Default to C clef for medieval notation, but respect F and G clefs if found
                    clef_shape = "C"  # Default for medieval notation
                    if "clef.f" in clef_glyph["glyph"]["name"]:
                        clef_shape = "F"
                    elif "clef.g" in clef_glyph["glyph"]["name"]:
                        clef_shape = "G"
                    
                    # Create clef element with proper shape and line position
                    clef = ET.Element("{http://www.music-encoding.org/ns/mei}clef", {
                        "shape": clef_shape,
                        "line": clef_glyph["pitch"]["clef_pos"],
                        "facs": f"#{clef_zone_id}"
                    })
                    
                    # Insert the clef after the sb element
                    # This ensures logical ordering in the MEI file
                    layer.insert(sb_index + i + 1, clef)
                    clefs_added += 1
        
        # Save the updated MEI file
        mei_tree.write(output_file_path, encoding="utf-8", xml_declaration=True)
        print(f"Added {clefs_added} clef elements to MEI file")
        print(f"MEI file with clef elements saved to {output_file_path}")
        
    except Exception as e:
        print(f"Error adding clef elements: {e}")

def analyze_mei_structure(mei_file_path: str) -> None:
    """
    Analyze the structure of an MEI file to identify issues.
    
    This diagnostic function helps identify common structural problems
    such as empty zones, missing references, etc.
    
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
        clefs = mei_root.findall(".//mei:clef", MEI_NS)  # Added clef count
        syllables = mei_root.findall(".//mei:syllable", MEI_NS)
        
        print(f"MEI Structure Analysis for {mei_file_path}:")
        print(f"  - Zones: {len(zones)}")
        print(f"  - Staves: {len(staves)}")
        print(f"  - System breaks: {len(sbs)}")
        print(f"  - Clefs: {len(clefs)}")  # Show clef count
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
        
        # New: Check staff/clef consistency
        # This helps identify staves that are missing clefs
        sb_nums = [sb.get("n") for sb in sbs if sb.get("n")]
        clef_refs = {}
        for clef in clefs:
            facs = clef.get("facs", "")
            if facs and facs.startswith("#"):
                clef_id = facs[1:]
                # Find the zone
                zone = mei_root.find(f".//mei:zone[@xml:id='{clef_id}']", {**MEI_NS, **XML_NS})
                if zone is not None:
                    for sb in sbs:
                        sb_facs = sb.get("facs", "")
                        if sb_facs and sb_facs.startswith("#"):
                            sb_zone_id = sb_facs[1:]
                            sb_zone = mei_root.find(f".//mei:zone[@xml:id='{sb_zone_id}']", {**MEI_NS, **XML_NS})
                            if sb_zone is not None:
                                # Check if clef is near this staff zone
                                clef_uly = int(zone.get("uly", "0"))
                                sb_uly = int(sb_zone.get("uly", "0"))
                                sb_lry = int(sb_zone.get("lry", "0"))
                                
                                if clef_uly >= sb_uly and clef_uly <= sb_lry:
                                    staff_num = sb.get("n")
                                    if staff_num not in clef_refs:
                                        clef_refs[staff_num] = []
                                    clef_refs[staff_num].append(clef)
        
        # Report on clef distribution
        print("\nClef distribution by staff:")
        for staff_num in sorted(set(sb_nums), key=int):
            clef_count = len(clef_refs.get(staff_num, []))
            print(f"  - Staff {staff_num}: {clef_count} clefs")
        
        # Identify staves without clefs
        staves_without_clefs = set(sb_nums) - set(clef_refs.keys())
        if staves_without_clefs:
            print(f"\nWARNING: {len(staves_without_clefs)} staves have no clefs assigned:")
            for staff_num in sorted(staves_without_clefs, key=int):
                print(f"  - Staff {staff_num}")
        
    except Exception as e:
        print(f"Error analyzing MEI file: {e}")

def find_missing_sb_references(mei_file_path: str) -> None:
    """
    Find missing system break references in an MEI file.
    
    This function helps identify zones that aren't referenced by system breaks,
    and system breaks that reference non-existent zones.
    
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
    
    This function finds zones that aren't referenced by any system break
    and creates new system break elements for them.
    
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

def restructure_mei_staves(mei_file_path: str, jsomr_file_path: str, output_file_path: str) -> None:
    """
    Restructure an MEI file to have multiple staff elements based on system breaks.
    
    This function takes an MEI file that has all elements in a single staff and
    redistributes them across multiple staff elements based on the system breaks.
    This ensures each staff in the source manuscript gets its own representation
    in the MEI file.
    
    Args:
        mei_file_path: Path to the MEI file
        jsomr_file_path: Path to the JSOMR file
        output_file_path: Path to save the restructured MEI file
    """
    try:
        # Load the MEI file
        mei_tree = ET.parse(mei_file_path)
        mei_root = mei_tree.getroot()
        
        # Load the JSOMR file for staff information
        with open(jsomr_file_path, 'r') as f:
            jsomr_data = json.load(f)
        
        # Get the number of staves from the JSOMR file
        num_staves = len(jsomr_data.get("staves", []))
        print(f"Found {num_staves} staves in JSOMR file")
        
        # Find the section element
        section = mei_root.find(".//mei:section", MEI_NS)
        if section is None:
            print("Error: Could not find section element")
            return
        
        # Get the original staff and its layer
        original_staff = section.find(".//mei:staff", MEI_NS)
        if original_staff is None:
            print("Error: Could not find staff element")
            return
        
        original_layer = original_staff.find(".//mei:layer", MEI_NS)
        if original_layer is None:
            print("Error: Could not find layer element")
            return
        
        # Get all elements from the original layer
        layer_elements = list(original_layer)
        
        # Group elements by staff (based on sb elements with n attribute)
        staff_elements = {}
        current_staff = "1"
        
        for element in layer_elements:
            if element.tag == "{http://www.music-encoding.org/ns/mei}sb":
                current_staff = element.get("n", "1")
            
            # Initialize the staff list if needed
            if current_staff not in staff_elements:
                staff_elements[current_staff] = []
            
            # Clone the element to avoid reference issues
            element_copy = ET.Element(element.tag, element.attrib)
            for child in element:
                child_copy = ET.Element(child.tag, child.attrib)
                element_copy.append(child_copy)
            
            # Add to the current staff's elements
            staff_elements[current_staff].append(element_copy)
        
        # Remove the original staff from the section
        section.remove(original_staff)
        
        # Update the staff definition count to match number of staves
        staff_def = mei_root.find(".//mei:staffDef", MEI_NS)
        if staff_def is not None:
            # Create a staffGrp if it doesn't exist
            staff_grp = mei_root.find(".//mei:staffGrp", MEI_NS)
            if staff_grp is not None:
                # Remove the original staffDef
                staff_grp.remove(staff_def)
                
                # Add new staffDef elements for each staff
                for i in range(1, num_staves + 1):
                    new_staff_def = ET.SubElement(staff_grp, "{http://www.music-encoding.org/ns/mei}staffDef")
                    new_staff_def.set("n", str(i))
                    new_staff_def.set("lines", "4")
                    new_staff_def.set("notationtype", "neume")
                    new_staff_def.set("clef.line", "4")
                    new_staff_def.set("clef.shape", "C")
                    new_staff_def.set("xml:id", f"m-staffdef-{i}")
        
        # Create new staff elements for each staff
        for staff_num in sorted(staff_elements.keys(), key=int):
            # Skip staffs with no elements
            if not staff_elements[staff_num]:
                continue
                
            # Create new staff and layer
            new_staff = ET.SubElement(section, "{http://www.music-encoding.org/ns/mei}staff")
            new_staff.set("n", staff_num)
            new_staff.set("xml:id", f"m-staff-{staff_num}")
            
            new_layer = ET.SubElement(new_staff, "{http://www.music-encoding.org/ns/mei}layer")
            new_layer.set("xml:id", f"m-layer-{staff_num}")
            
            # Add page break to first staff if it exists
            if staff_num == "1":
                pb = mei_root.find(".//mei:pb", MEI_NS)
                if pb is not None:
                    # Clone the pb element
                    pb_copy = ET.Element(pb.tag, pb.attrib)
                    new_layer.append(pb_copy)
            
            # Add elements to the new layer
            for element in staff_elements[staff_num]:
                new_layer.append(element)
        
        # Save the restructured MEI file
        mei_tree.write(output_file_path, encoding="utf-8", xml_declaration=True)
        print(f"Restructured MEI file saved to {output_file_path}")
        
    except Exception as e:
        print(f"Error restructuring MEI staves: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Main function to run the MEI coordinate fixing script."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Fix coordinates and add clefs in MEI files")
    parser.add_argument("--mei", required=True, help="Path to the MEI file")
    parser.add_argument("--jsomr", required=True, help="Path to the JSOMR file")
    parser.add_argument("--output", required=True, help="Path to save the fixed MEI file")
    parser.add_argument("--analyze", action="store_true", help="Analyze the structure of the MEI file")
    parser.add_argument("--find-missing", action="store_true", help="Find missing system break references")
    parser.add_argument("--add-missing", action="store_true", help="Add missing system break elements")
    parser.add_argument("--add-clefs", action="store_true", help="Add clef elements from JSOMR data")
    parser.add_argument("--skip-fix", action="store_true", help="Skip fixing coordinates")
    parser.add_argument("--restructure", action="store_true", help="Restructure MEI to have multiple staves")
    
    args = parser.parse_args()
    
    # Analysis functions
    if args.analyze:
        analyze_mei_structure(args.mei)
    
    if args.find_missing:
        find_missing_sb_references(args.mei)
    
    # Modification functions
    temp_file = args.output + ".temp"
    temp_file2 = args.output + ".temp2"
    current_file = args.mei
    
    # Fix coordinates if not skipped
    if not args.skip_fix and not any([args.analyze, args.find_missing, args.add_missing, args.add_clefs, args.restructure]):
        fix_mei_coordinates(current_file, args.jsomr, temp_file)
        current_file = temp_file
    
    # Add missing system breaks if requested
    if args.add_missing:
        add_missing_sb_elements(current_file, temp_file2)
        current_file = temp_file2
    
    # Add clef elements if requested
    if args.add_clefs:
        add_clef_elements(current_file, args.jsomr, temp_file)
        current_file = temp_file
    
    # Restructure MEI staves if requested
    if args.restructure:
        restructure_mei_staves(current_file, args.jsomr, args.output)
    
    # Clean up temporary files
    for file in [temp_file, temp_file2]:
        if os.path.exists(file):
            os.remove(file)
    
    # If no specific actions were requested, do the complete workflow
    if not any([args.analyze, args.find_missing, args.add_missing, args.add_clefs, args.skip_fix, args.restructure]):
        # Step 1: Fix coordinates
        fix_mei_coordinates(args.mei, args.jsomr, temp_file)
        
        # Step 2: Add clef elements
        add_clef_elements(temp_file, args.jsomr, temp_file2)
        
        # Step 3: Restructure the MEI file to have multiple staves
        restructure_mei_staves(temp_file2, args.jsomr, args.output)
        
        # Clean up temporary files
        for file in [temp_file, temp_file2]:
            if os.path.exists(file):
                os.remove(file)

if __name__ == "__main__":
    main()