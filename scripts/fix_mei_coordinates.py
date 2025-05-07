import json
import xml.etree.ElementTree as ET
import os
from typing import Dict, List, Optional, Any, Tuple
import traceback

# Register the MEI namespace
# This is important for proper XML generation and XPath queries
MEI_NS = {"mei": "http://www.music-encoding.org/ns/mei"}
XML_NS = {"xml": "http://www.w3.org/XML/1998/namespace"}
ET.register_namespace('', MEI_NS["mei"])
ET.register_namespace('xml', XML_NS["xml"])

def parse_glyph_xml(xml_file_path: str) -> List[Dict[str, Any]]:
    """
    Parses the glyph data from a specific XML format.

    Extracts bounding box and classification information for each glyph.

    Args:
        xml_file_path: Path to the XML glyph file.

    Returns:
        A list of dictionaries, where each dictionary represents a glyph
        with its bounding box and name.
    """
    glyph_data = []
    try:
        xml_tree = ET.parse(xml_file_path)
        xml_root = xml_tree.getroot()

        # Find all glyph elements
        glyphs = xml_root.findall(".//glyph")

        for glyph in glyphs:
            # Extract bounding box
            ulx = int(glyph.get("ulx", "0"))
            uly = int(glyph.get("uly", "0"))
            nrows = int(glyph.get("nrows", "0"))
            ncols = int(glyph.get("ncols", "0"))

            # Calculate lrx and lry if nrows/ncols are present
            lrx = ulx + ncols if ncols > 0 else ulx
            lry = uly + nrows if nrows > 0 else uly


            # Extract glyph name (taking the name from the first id with state="AUTOMATIC")
            glyph_name = None
            ids_element = glyph.find("./ids[@state='AUTOMATIC']")
            if ids_element is not None:
                id_element = ids_element.find("./id")
                if id_element is not None:
                    glyph_name = id_element.get("name")

            if glyph_name: # Only include glyphs with a recognized name
                glyph_data.append({
                    "ulx": ulx,
                    "uly": uly,
                    "lrx": lrx,
                    "lry": lry,
                    "name": glyph_name
                })

    except Exception as e:
        print(f"Error parsing glyph XML file: {e}")
        traceback.print_exc()

    return glyph_data


def fix_mei_coordinates(mei_file_path: str, jsomr_file_path: str, xml_glyph_file_path: Optional[str], output_file_path: str) -> None:
    """
    Fix empty or incorrect zones in an MEI file by using coordinates from JSOMR and XML glyph data.

    This function:
    1. Finds zones with zero coordinates
    2. Updates them with staff coordinates from the JSOMR file (for staff zones)
    3. Updates them with glyph coordinates from the XML file (for glyph zones)
    4. Updates system break references to point to the correct zones

    Args:
        mei_file_path: Path to the MEI file
        jsomr_file_path: Path to the JSOMR file with correct coordinates
        xml_glyph_file_path: Optional path to an XML file with glyph bounding boxes.
        output_file_path: Path to save the fixed MEI file
    """
    try:
        # Load the MEI file
        mei_tree = ET.parse(mei_file_path)
        mei_root = mei_tree.getroot()

        # Load the JSOMR file
        jsomr_data = {}
        if jsomr_file_path and os.path.exists(jsomr_file_path):
            with open(jsomr_file_path, 'r', encoding='utf-8') as f:
                jsomr_data = json.load(f)

        # Load the XML glyph data
        xml_glyphs = []
        if xml_glyph_file_path and os.path.exists(xml_glyph_file_path):
            xml_glyphs = parse_glyph_xml(xml_glyph_file_path)

        # Get all zones in the MEI file
        zones = mei_root.findall(".//mei:zone", MEI_NS)

        # Get all staves from the JSOMR file
        staves = jsomr_data.get("staves", [])

        # Get all sb (system break) elements
        sb_elements = mei_root.findall(".//mei:sb", MEI_NS)

        # Attempt to fix zones with zero coordinates
        fixed_zones_count = 0
        jsomr_staff_index = 0
        xml_glyph_index = 0

        for zone in zones:
            # Check if the zone has zero coordinates
            if (int(zone.get("ulx", "0")) == 0 and
                int(zone.get("uly", "0")) == 0 and
                int(zone.get("lrx", "0")) == 0 and
                int(zone.get("lry", "0")) == 0):

                # Try to match with a JSOMR staff bounding box
                if jsomr_staff_index < len(staves):
                    staff = staves[jsomr_staff_index]
                    bb = staff["bounding_box"]
                    zone.set("ulx", str(bb["ulx"]))
                    zone.set("uly", str(bb["uly"]))
                    if "lrx" in bb and "lry" in bb:
                        zone.set("lrx", str(bb["lrx"]))
                        zone.set("lry", str(bb["lry"]))
                    else:
                        zone.set("lrx", str(bb["ulx"] + bb["ncols"]))
                        zone.set("lry", str(bb["uly"] + bb["nrows"]))
                    fixed_zones_count += 1
                    jsomr_staff_index += 1
                    continue # Move to the next zone after fixing

                # If not matched with a JSOMR staff, try to match with an XML glyph bounding box (sequential)
                if xml_glyph_index < len(xml_glyphs):
                     glyph = xml_glyphs[xml_glyph_index]
                     zone.set("ulx", str(glyph["ulx"]))
                     zone.set("uly", str(glyph["uly"]))
                     zone.set("lrx", str(glyph["lrx"]))
                     zone.set("lry", str(glyph["lry"]))
                     fixed_zones_count += 1
                     xml_glyph_index += 1
                     continue # Move to the next zone after fixing


        print(f"Fixed coordinates for {fixed_zones_count} zones.")


        # Update facs references in sb elements
        # This part remains largely the same, ensuring sbs point to their corresponding zones
        # based on the staff number and sequential order of zones in the file.
        # The coordinate fixing above should have updated the zones, so the references here
        # should now point to zones with correct coordinates.
        zone_id_list = [zone.get("{http://www.w3.org/XML/1998/namespace}id") for zone in zones if zone.get("{http://www.w3.org/XML/1998/namespace}id")]

        for i, sb in enumerate(sb_elements):
            if i < len(zone_id_list):
                sb.set("facs", f"#{zone_id_list[i]}")


        # Save the fixed MEI file
        mei_tree.write(output_file_path, encoding="utf-8", xml_declaration=True)
        print(f"Fixed MEI file saved to {output_file_path}")

    except (ET.ParseError, json.JSONDecodeError, ValueError) as e:
        print(f"Error fixing MEI coordinates: {e}")
        traceback.print_exc()


def add_clef_elements(mei_file_path: str, jsomr_file_path: str, xml_glyph_file_path: Optional[str], output_file_path: str) -> None:
    """
    Add clef elements to an MEI file based on clefs in the JSOMR and XML glyph files.

    This function:
    1. Identifies all clef glyphs in the JSOMR and XML files
    2. Creates new zones for each clef using coordinates from XML (if available) or JSOMR
    3. Creates proper MEI clef elements linked to these zones
    4. Positions clefs after their corresponding system breaks

    This ensures each staff has its clefs properly represented in the MEI.

    Args:
        mei_file_path: Path to the MEI file
        jsomr_file_path: Path to the JSOMR file
        xml_glyph_file_path: Optional path to an XML file with glyph bounding boxes and names.
        output_file_path: Path to save the updated MEI file
    """
    try:
        # Load the MEI file
        mei_tree = ET.parse(mei_file_path)
        mei_root = mei_tree.getroot()

        # Load the JSOMR file
        jsomr_data = {}
        if jsomr_file_path and os.path.exists(jsomr_file_path):
            with open(jsomr_file_path, 'r') as f:
                jsomr_data = json.load(f)

        # Load the XML glyph data
        xml_glyphs = []
        if xml_glyph_file_path and os.path.exists(xml_glyph_file_path):
            xml_glyphs = parse_glyph_xml(xml_glyph_file_path)

        # Get all staves and glyphs from JSOMR
        staves = jsomr_data.get("staves", [])
        jsomr_glyphs = jsomr_data.get("glyphs", [])

        # Filter for only clef glyphs from JSOMR
        jsomr_clef_glyphs = [g for g in jsomr_glyphs if
                      ("clef.f" in g["glyph"]["name"] or
                       "clef.c" in g["glyph"]["name"] or
                       "clef.g" in g["glyph"]["name"] or
                       "clef.not" in g["glyph"]["name"])]

        # Filter for only clef glyphs from XML
        xml_clef_glyphs = [g for g in xml_glyphs if
                           ("clef.f" in g["name"] or
                            "clef.c" in g["name"] or
                            "clef.g" in g["name"] or
                            "clef.not" in g["name"])]


        # Group clefs by staff (using JSOMR staff data as the primary source for staff association)
        # We'll try to match XML clefs to JSOMR staves based on spatial proximity later if needed,
        # but for now, we rely on JSOMR's staff association.
        clefs_by_staff: Dict[str, List[Dict[str, Any]]] = {}
        for glyph in jsomr_clef_glyphs:
            staff_num = glyph["pitch"]["staff"]
            if staff_num not in clefs_by_staff:
                clefs_by_staff[staff_num] = []
            clefs_by_staff[staff_num].append(glyph)

        # Find the facsimile element or create one if missing
        facsimile = mei_root.find(".//mei:facsimile", MEI_NS)
        if facsimile is None:
            music = mei_root.find(".//mei:music", MEI_NS)
            if music is None:
                print("Error: Could not find music element")
                return
            facsimile = ET.SubElement(music, "{http://www.music-encoding.org/ns/mei}facsimile")

        # Find the surface element or create one if missing
        surface = facsimile.find(".//mei:surface", MEI_NS)
        if surface is None:
            surface = ET.SubElement(facsimile, "{http://www.music-encoding.org/ns/mei}surface")

        # Find the layer element
        layer = mei_root.find(".//mei:layer", MEI_NS)
        if layer is None:
            print("Error: Could not find layer element")
            return

        # Create a mapping from staff number to associated SB element and zone
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
        for staff_num in sorted(clefs_by_staff.keys(), key=int):
             staff_clefs = clefs_by_staff[staff_num]

             if not staff_clefs:
                continue

             # Get the associated SB element and zone ID
             if str(staff_num) in sb_map:
                sb, zone_id = sb_map[str(staff_num)]

                # Find the corresponding system break in the layer
                try:
                    sb_index = list(layer).index(sb)
                except ValueError:
                    print(f"Warning: Could not find system break for staff {staff_num} in layer")
                    continue

                # For each clef, create a zone and clef element
                for i, clef_glyph_jsomr in enumerate(staff_clefs):
                    # Try to find a corresponding glyph in the XML data based on proximity
                    clef_glyph_xml = None
                    jsomr_bb = clef_glyph_jsomr.get("glyph", {}).get("bounding_box", {})
                    if jsomr_bb:
                        # Simple proximity check: find the closest XML glyph
                        min_distance = float('inf')
                        closest_xml_glyph = None
                        for xml_glyph in xml_clef_glyphs: # Search only among XML clef glyphs
                            xml_bb = xml_glyph
                            # Calculate distance between centers (simplified)
                            dist = ((jsomr_bb.get("ulx", 0) + jsomr_bb.get("lrx", 0))/2 - (xml_bb.get("ulx", 0) + xml_bb.get("lrx", 0))/2)**2 + \
                                   ((jsomr_bb.get("uly", 0) + jsomr_bb.get("lry", 0))/2 - (xml_bb.get("uly", 0) + xml_bb.get("lry", 0))/2)**2
                            if dist < min_distance:
                                min_distance = dist
                                closest_xml_glyph = xml_glyph

                        # Use the closest XML glyph if it's within a reasonable distance
                        # (Threshold needs to be determined empirically)
                        if closest_xml_glyph and min_distance < 10000: # Example threshold
                            clef_glyph_xml = closest_xml_glyph


                    # Determine bounding box to use (prefer XML if available)
                    bb_to_use = None
                    if clef_glyph_xml:
                        bb_to_use = clef_glyph_xml
                    elif jsomr_bb:
                        bb_to_use = jsomr_bb


                    if bb_to_use:
                        # Create a zone for the clef
                        clef_zone = ET.SubElement(surface, "{http://www.music-encoding.org/ns/mei}zone")
                        clef_zone_id = f"zone-clef-{staff_num}-{i+1}"
                        clef_zone.set("{http://www.w3.org/XML/1998/namespace}id", clef_zone_id)

                        # Set zone coordinates
                        clef_zone.set("ulx", str(bb_to_use.get("ulx", "0")))
                        clef_zone.set("uly", str(bb_to_use.get("uly", "0")))
                        clef_zone.set("lrx", str(bb_to_use.get("lrx", "0")))
                        clef_zone.set("lry", str(bb_to_use.get("lry", "0")))

                        # Determine clef shape based on name (Prefer XML name if matched)
                        clef_shape = "C"  # Default
                        glyph_name = None
                        if clef_glyph_xml:
                            glyph_name = clef_glyph_xml.get("name")
                        elif clef_glyph_jsomr.get("glyph"):
                            glyph_name = clef_glyph_jsomr["glyph"].get("name", "")


                        if glyph_name:
                            if "clef.f" in glyph_name:
                                clef_shape = "F"
                            elif "clef.c" in glyph_name:
                                clef_shape = "G"


                        # Create clef element with proper shape and line/octave/pname
                        clef = ET.SubElement(new_layer, "{http://www.music-encoding.org/ns/mei}clef")
                        clef.set("shape", clef_shape)
                        # Add pitch information from JSOMR if available
                        if "pitch" in clef_glyph_jsomr and clef_glyph_jsomr["pitch"] is not None:
                            if clef_glyph_jsomr["pitch"].get("clef_pos") is not None:
                                clef.set("line", str(clef_glyph_jsomr["pitch"].get("clef_pos")))
                            if clef_glyph_jsomr["pitch"].get("octave") is not None:
                                clef.set("oct", str(clef_glyph_jsomr["pitch"].get("octave")))
                            if clef_glyph_jsomr["pitch"].get("note") is not None:
                                clef.set("pname", clef_glyph_jsomr["pitch"].get("note"))

                        # Set facs attribute
                        clef.set("facs", f"#{clef_zone_id}")


                        # Insert the clef after the sb element
                        layer.insert(sb_index + i + 1, clef)
                        clefs_added += 1


        # Save the updated MEI file
        mei_tree.write(output_file_path, encoding="utf-8", xml_declaration=True)
        print(f"Added {clefs_added} clef elements to MEI file")
        print(f"MEI file with clef elements saved to {output_file_path}")

    except Exception as e:
        print(f"Error adding clef elements: {e}")
        traceback.print_exc()


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
        clefs = mei_root.findall(".//mei:clef", MEI_NS)
        syllables = mei_root.findall(".//mei:syllable", MEI_NS)

        print(f"MEI Structure Analysis for {mei_file_path}:")
        print(f"  - Zones: {len(zones)}")
        print(f"  - Staves: {len(staves)}")
        print(f"  - System breaks: {len(sbs)}")
        print(f"  - Clefs: {len(clefs)}")
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
        traceback.print_exc()

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
        traceback.print_exc()

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
        traceback.print_exc()

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
        staff_grp = mei_root.find(".//mei:staffGrp", MEI_NS)
        if staff_grp is not None:
            # Remove existing staffDef elements within this staffGrp
            for staff_def in staff_grp.findall("mei:staffDef", MEI_NS):
                 staff_grp.remove(staff_def)

            # Add new staffDef elements for each staff
            for i in range(1, num_staves + 1):
                new_staff_def = ET.SubElement(staff_grp, "{http://www.music-encoding.org/ns/mei}staffDef")
                new_staff_def.set("n", str(i))
                new_staff_def.set("lines", "4") # Assuming 4 lines for neume notation
                new_staff_def.set("notationtype", "neume")
                # Add default clef.line and clef.shape if not present in JSOMR or original MEI
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

            # Add page break to first staff if it exists and is not already added
            if staff_num == "1":
                 pb = mei_root.find(".//mei:pb", MEI_NS)
                 if pb is not None:
                     # Check if a pb element already exists in the new layer
                     if new_layer.find(".//mei:pb", MEI_NS) is None:
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
        traceback.print_exc()

def complete_staff_structure(mei_file_path: str, jsomr_file_path: str, output_file_path: str) -> None:
    """
    Complete the staff structure in an MEI file by adding missing staff elements
    based on the JSOMR file, using sequential mapping for zones.
    """
    try:
        # Load the MEI file
        mei_tree = ET.parse(mei_file_path)
        mei_root = mei_tree.getroot()

        # Load the JSOMR file
        with open(jsomr_file_path, 'r') as f:
            jsomr_data = json.load(f)

        # Get staves and glyphs from JSOMR
        staves = jsomr_data.get("staves", [])
        glyphs = jsomr_data.get("glyphs", [])

        # Find section and staff group elements
        section = mei_root.find(".//mei:section", MEI_NS)
        staff_grp = mei_root.find(".//mei:staffGrp", MEI_NS)

        if section is None or staff_grp is None:
             print("Error: Could not find section or staffGrp element")
             return


        # Get existing staff elements
        existing_staff_elements = section.findall("mei:staff", MEI_NS)
        existing_staff_nums = [staff.get("n") for staff in existing_staff_elements if staff.get("n")] # Ensure existing_staff_nums contains only valid staff numbers

        # Get zones and create a sequential list (including zero zones)
        zones = mei_root.findall(".//mei:zone", MEI_NS) # Define zones here
        zone_ids = []
        for zone in zones:
            zone_id = zone.get("{http://www.w3.org/XML/1998/namespace}id")
            if zone_id:
                zone_ids.append(zone_id)


        # Group glyphs by staff
        glyphs_by_staff: Dict[str, List[Dict[str, Any]]] = {} # Changed key to str to match staff_num
        for glyph in glyphs:
            # Ensure 'staff' key exists in 'pitch' and is not None
            if "pitch" in glyph and glyph["pitch"] is not None and "staff" in glyph["pitch"] and glyph["pitch"]["staff"] is not None:
                staff_num = str(glyph["pitch"]["staff"]) # Convert staff_num to string
                if staff_num not in glyphs_by_staff:
                    glyphs_by_staff[staff_num] = []
                glyphs_by_staff[staff_num].append(glyph)


        # Filter for clefs
        clefs_by_staff = {}
        for staff_num, staff_glyphs in glyphs_by_staff.items():
            clefs_by_staff[staff_num] = [
                g for g in staff_glyphs if
                ("clef.f" in g.get("glyph", {}).get("name", "") or # Added get with default for safety
                 "clef.c" in g.get("glyph", {}).get("name", "") or
                 "clef.g" in g.get("glyph", {}).get("name", "") or
                 "clef.not" in g.get("glyph", {}).get("name", ""))
            ]

        # Find or create surface element
        facsimile = mei_root.find(".//mei:facsimile", MEI_NS)
        if facsimile is None:
            music = mei_root.find(".//mei:music", MEI_NS)
            if music is None:
                print("Error: Could not find music element to create facsimile")
                return
            facsimile = ET.SubElement(music, "{http://www.music-encoding.org/ns/mei}facsimile")

        surface = facsimile.find(".//mei:surface", MEI_NS)
        if surface is None:
            surface = ET.SubElement(facsimile, "{http://www.music-encoding.org/ns/mei}surface")

        # Add missing staff elements using sequential zone mapping
        staves_added = 0
        for i in range(len(staves)): # Iterate based on the number of staves in JSOMR
            staff_num = str(i + 1)

            # Skip existing staff elements
            if staff_num in existing_staff_nums:
                continue

            print(f"Adding missing staff element for staff number: {staff_num}") # Added print for debugging

            # Create new staff element
            new_staff = ET.SubElement(section, "{http://www.music-encoding.org/ns/mei}staff")
            new_staff.set("n", staff_num)
            new_staff.set("xml:id", f"m-staff-{staff_num}")

            # Create layer for staff
            new_layer = ET.SubElement(new_staff, "{http://www.music-encoding.org/ns/mei}layer")
            new_layer.set("xml:id", f"m-layer-{staff_num}")

            # Add system break for this staff using sequential zone mapping
            if i < len(zone_ids):
                zone_id = zone_ids[i]
                sb = ET.SubElement(new_layer, "{http://www.music-encoding.org/ns/mei}sb")
                sb.set("n", staff_num)
                sb.set("facs", f"#{zone_id}")

            # Add page break to first staff if it exists and is not already added
            if staff_num == "1":
                pb = mei_root.find(".//mei:pb", MEI_NS)
                if pb is not None:
                    # Check if a pb element already exists in the new layer
                    if new_layer.find(".//mei:pb", MEI_NS) is None:
                         # Clone the pb element
                         pb_copy = ET.Element(pb.tag, pb.attrib)
                         new_layer.append(pb_copy)

            # Add clefs for this staff if they exist in the JSOMR data
            if staff_num in clefs_by_staff and clefs_by_staff[staff_num]:
                for clef_idx, clef_glyph in enumerate(clefs_by_staff[staff_num]):
                    # Create a zone for the clef
                    clef_zone = ET.SubElement(surface, "{http://www.music-encoding.org/ns/mei}zone")
                    clef_zone_id = f"zone-clef-{staff_num}-{clef_idx+1}"
                    clef_zone.set("{http://www.w3.org/XML/1998/namespace}id", clef_zone_id)

                    # Set zone coordinates
                    bb = clef_glyph.get("glyph", {}).get("bounding_box", {}) # Added get with default for safety
                    if bb: # Check if bounding box data exists
                        clef_zone.set("ulx", str(bb.get("ulx", "0")))
                        clef_zone.set("uly", str(bb.get("uly", "0")))
                        clef_zone.set("lrx", str(bb.get("lrx", str(int(bb.get("ulx", "0")) + int(bb.get("ncols", "0")))))) # Handle lrx/lry or ncols/nrows
                        clef_zone.set("lry", str(bb.get("lry", str(int(bb.get("uly", "0")) + int(bb.get("nrows", "0"))))))


                    # Determine clef shape based on name
                    clef_shape = "C"  # Default for medieval notation
                    glyph_name = clef_glyph.get("glyph", {}).get("name", "")
                    if "clef.f" in glyph_name:
                        clef_shape = "F"
                    elif "clef.g" in glyph_name:
                        clef_shape = "G"

                    # Create clef element with proper attributes
                    clef = ET.SubElement(new_layer, "{http://www.music-encoding.org/ns/mei}clef")
                    clef.set("shape", clef_shape)
                    # Ensure pitch and clef_pos exist before accessing
                    if "pitch" in clef_glyph and clef_glyph["pitch"] is not None:
                         clef.set("line", str(clef_glyph["pitch"].get("clef_pos", ""))) # Added get with default for safety
                         clef.set("oct", str(clef_glyph["pitch"].get("octave", "")))
                         clef.set("pname", clef_glyph["pitch"].get("note", ""))
                    clef.set("facs", f"#{clef_zone_id}")

            staves_added += 1

        # Ensure all staffDef elements have correct attributes
        for i in range(len(staves)):
            staff_num = str(i + 1)

            # Find or create staffDef
            staff_def = None
            for sd in staff_grp.findall("mei:staffDef", MEI_NS):
                if sd.get("n") == staff_num:
                    staff_def = sd
                    break

            if staff_def is None:
                staff_def = ET.SubElement(staff_grp, "{http://www.music-encoding.org/ns/mei}staffDef")
                staff_def.set("n", staff_num)
                staff_def.set("lines", "4")
                staff_def.set("notationtype", "neume")
                staff_def.set("xml:id", f"m-staffdef-{staff_num}")

            # Ensure staffDef has clef attributes if they are missing
            if "clef.shape" not in staff_def.attrib:
                staff_def.set("clef.shape", "C")
            if "clef.line" not in staff_def.attrib:
                 staff_def.set("clef.line", "4")


        # Save the completed MEI file
        mei_tree.write(output_file_path, encoding="utf-8", xml_declaration=True)
        print(f"Added {staves_added} missing staff elements")
        print(f"Completed MEI file saved to {output_file_path}")

    except Exception as e:
        print(f"Error completing staff structure: {e}")
        traceback.print_exc()

def main():
    """Main function to run the MEI coordinate fixing script."""
    import argparse

    parser = argparse.ArgumentParser(description="Fix coordinates and add clefs in MEI files")
    parser.add_argument("--mei", required=True, help="Path to the MEI file")
    parser.add_argument("--jsomr", required=True, help="Path to the JSOMR file")
    parser.add_argument("--xml-glyphs", help="Path to an XML file with glyph bounding boxes and names") # Added new argument
    parser.add_argument("--output", required=True, help="Path to save the fixed MEI file")
    parser.add_argument("--analyze", action="store_true", help="Analyze the structure of the MEI file")
    parser.add_argument("--find-missing", action="store_true", help="Find missing system break references")
    parser.add_argument("--add-missing", action="store_true", help="Add missing system break elements")
    parser.add_argument("--add-clefs", action="store_true", help="Add clef elements from JSOMR data")
    parser.add_argument("--skip-fix", action="store_true", help="Skip fixing coordinates")
    parser.add_argument("--restructure", action="store_true", help="Restructure MEI to have multiple staves")
    parser.add_argument("--complete", action="store_true", help="Complete the staff structure with missing staves")


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

    # Determine if any modification actions are requested
    modification_requested = any([args.add_missing, args.add_clefs, args.restructure, args.complete]) or (not args.skip_fix)

    # Only proceed with modifications if at least one modification action is requested
    if modification_requested:

        # Step 1: Fix coordinates (can use both JSOMR and XML glyphs)
        if not args.skip_fix:
            fix_mei_coordinates(current_file, args.jsomr, args.xml_glyphs, temp_file)
            current_file = temp_file

        # Step 2: Add missing system breaks if requested
        if args.add_missing:
            # Note: add_missing_sb_elements does not currently use XML glyph data
            add_missing_sb_elements(current_file, temp_file2)
            current_file = temp_file2
            # Swap temp files for next step
            temp_file, temp_file2 = temp_file2, temp_file

        # Step 3: Add clef elements (can use both JSOMR and XML glyphs)
        if args.add_clefs:
            add_clef_elements(current_file, args.jsomr, args.xml_glyphs, temp_file2)
            current_file = temp_file2
             # Swap temp files for next step
            temp_file, temp_file2 = temp_file2, temp_file


        # Step 4: Restructure MEI staves if requested
        if args.restructure:
            # Note: restructure_mei_staves does not currently use XML glyph data
            restructure_mei_staves(current_file, args.jsomr, temp_file2)
            current_file = temp_file2
            # Swap temp files for next step
            temp_file, temp_file2 = temp_file2, temp_file


        # Step 5: Complete staff structure if requested
        if args.complete:
            # Note: complete_staff_structure does not currently use XML glyph data
            complete_staff_structure(current_file, args.jsomr, temp_file2)
            current_file = temp_file2
            # Swap temp files for next step
            temp_file, temp_file2 = temp_file2, temp_file


        # If the last step was a modification, the current_file should be the final output
        # Otherwise, copy the potentially modified file to the final output path
        if current_file != args.output:
             # Ensure the directory exists
             os.makedirs(os.path.dirname(args.output), exist_ok=True)
             # Copy the content of the current file to the output path
             try:
                 with open(current_file, 'r', encoding='utf-8') as infile, open(args.output, 'w', encoding='utf-8') as outfile:
                     outfile.write(infile.read())
                 print(f"Final output copied to {args.output}")
             except Exception as e:
                 print(f"Error copying temporary file to final output: {e}")
                 traceback.print_exc()


    # Clean up temporary files
    for file in [temp_file, temp_file2]:
        # Ensure we don't delete the final output if it ended up being a temp file name
        if os.path.exists(file) and file != args.output:
             try:
                 os.remove(file)
                 print(f"Cleaned up temporary file: {file}")
             except Exception as e:
                 print(f"Error removing temporary file {file}: {e}")
                 traceback.print_exc()


    # If no specific actions were requested (neither analysis nor modification),
    # provide a message indicating what the default behavior would be.
    if not args.analyze and not args.find_missing and not modification_requested:
         print("No specific action requested. The script completed any default workflow or exited.")
         print("To perform the default complete workflow, use: python your_script.py --mei <mei_file> --jsomr <jsomr_file> --output <output_file>")
         print("Use --help for other options.")


if __name__ == "__main__":
    main()