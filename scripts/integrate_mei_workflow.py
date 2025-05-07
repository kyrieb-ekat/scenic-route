import os
import json
import xml.etree.ElementTree as ET
from typing import Dict, List, Any

# Define namespaces
MEI_NS = {"mei": "http://www.music-encoding.org/ns/mei"}
XML_NS = {"xml": "http://www.w3.org/XML/1998/namespace"}
ET.register_namespace('', MEI_NS["mei"])
ET.register_namespace('xml', XML_NS["xml"])

def parse_glyph_xml(xml_file_path: str) -> List[Dict[str, Any]]:
    """Parse XML file containing glyph information."""
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
            
            # Calculate lrx and lry
            lrx = ulx + ncols if ncols > 0 else ulx
            lry = uly + nrows if nrows > 0 else uly
            
            # Extract glyph name (taking the first id with state="AUTOMATIC")
            glyph_name = None
            ids_element = glyph.find("./ids[@state='AUTOMATIC']")
            if ids_element is not None:
                id_element = ids_element.find("./id")
                if id_element is not None:
                    glyph_name = id_element.get("name")
            
            if glyph_name:  # Only include glyphs with a recognized name
                glyph_data.append({
                    "ulx": ulx,
                    "uly": uly,
                    "lrx": lrx,
                    "lry": lry,
                    "name": glyph_name
                })
    except Exception as e:
        print(f"Error parsing glyph XML file: {e}")
    
    return glyph_data

def assign_glyphs_to_staves(glyphs: List[Dict[str, Any]], staves: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Assign glyphs to staves based on spatial proximity."""
    staves_with_glyphs = {str(i+1): [] for i in range(len(staves))}
    
    for glyph in glyphs:
        # Skip certain glyph types if needed
        if "skip.edge" in glyph.get("name", ""):
            continue
        
        glyph_center_y = (glyph["uly"] + glyph["lry"]) / 2
        glyph_center_x = (glyph["ulx"] + glyph["lrx"]) / 2
        
        best_staff_num = None
        best_score = float('inf')
        
        for i, staff in enumerate(staves):
            bb = staff["bounding_box"]
            staff_ulx = bb["ulx"]
            staff_uly = bb["uly"]
            staff_lrx = staff_ulx + bb["ncols"]
            staff_lry = staff_uly + bb["nrows"]
            
            # Check horizontal overlap
            horiz_overlap = (glyph["ulx"] < staff_lrx and glyph["lrx"] > staff_ulx)
            
            if not horiz_overlap:
                continue
            
            # Calculate vertical distance
            staff_center_y = (staff_uly + staff_lry) / 2
            vert_distance = abs(glyph_center_y - staff_center_y)
            
            # Score incorporates both vertical distance and whether the glyph is fully within staff bounds
            within_staff_vertically = (glyph_center_y >= staff_uly and glyph_center_y <= staff_lry)
            score = vert_distance * (0.5 if within_staff_vertically else 1.0)
            
            if score < best_score:
                best_score = score
                best_staff_num = str(i + 1)  # 1-indexed
        
        # Only assign if a match was found
        if best_staff_num is not None:
            staves_with_glyphs[best_staff_num].append(glyph)
    
    return staves_with_glyphs

def create_mei_zones_from_staves(mei_root, staves, facsimile=None):
    """Create/update MEI zones from JSOMR staves."""
    # Find or create facsimile element
    if facsimile is None:
        facsimile = mei_root.find(".//mei:facsimile", MEI_NS)
        if facsimile is None:
            music = mei_root.find(".//mei:music", MEI_NS)
            if music is None:
                print("Error: Could not find music element")
                return None
            facsimile = ET.SubElement(music, "{http://www.music-encoding.org/ns/mei}facsimile")
    
    # Find or create surface element
    surface = facsimile.find(".//mei:surface", MEI_NS)
    if surface is None:
        surface = ET.SubElement(facsimile, "{http://www.music-encoding.org/ns/mei}surface")
    
    # Get existing zones
    zones = surface.findall(".//mei:zone", MEI_NS)
    
    # If zones exist and match staves count, update them
    # Otherwise, create new zones
    zone_ids = []
    
    if len(zones) == len(staves):
        for i, (zone, staff) in enumerate(zip(zones, staves)):
            bb = staff["bounding_box"]
            ulx = bb["ulx"]
            uly = bb["uly"]
            lrx = ulx + bb["ncols"]
            lry = uly + bb["nrows"]
            
            zone.set("ulx", str(ulx))
            zone.set("uly", str(uly))
            zone.set("lrx", str(lrx))
            zone.set("lry", str(lry))
            
            zone_id = zone.get("{http://www.w3.org/XML/1998/namespace}id")
            if not zone_id:
                zone_id = f"zone-staff-{i+1}"
                zone.set("{http://www.w3.org/XML/1998/namespace}id", zone_id)
            zone_ids.append(zone_id)
    else:
        # Remove existing zones
        for zone in zones:
            surface.remove(zone)
        
        # Create new zones
        for i, staff in enumerate(staves):
            bb = staff["bounding_box"]
            ulx = bb["ulx"]
            uly = bb["uly"]
            lrx = ulx + bb["ncols"]
            lry = uly + bb["nrows"]
            
            zone = ET.SubElement(surface, "{http://www.music-encoding.org/ns/mei}zone")
            zone_id = f"zone-staff-{i+1}"
            zone.set("{http://www.w3.org/XML/1998/namespace}id", zone_id)
            zone.set("ulx", str(ulx))
            zone.set("uly", str(uly))
            zone.set("lrx", str(lrx))
            zone.set("lry", str(lry))
            zone_ids.append(zone_id)
    
    return zone_ids, surface

def create_mei_zones_for_glyphs(mei_root, glyphs_by_staff, surface):
    """Create MEI zones for glyphs and link them to staves."""
    glyph_zones = {}
    
    for staff_num, staff_glyphs in glyphs_by_staff.items():
        for i, glyph in enumerate(staff_glyphs):
            # Skip certain glyph types if needed
            if "skip.edge" in glyph.get("name", ""):
                continue
            
            # Create zone for this glyph
            zone = ET.SubElement(surface, "{http://www.music-encoding.org/ns/mei}zone")
            zone_id = f"zone-glyph-{staff_num}-{i+1}"
            zone.set("{http://www.w3.org/XML/1998/namespace}id", zone_id)
            zone.set("ulx", str(glyph["ulx"]))
            zone.set("uly", str(glyph["uly"]))
            zone.set("lrx", str(glyph["lrx"]))
            zone.set("lry", str(glyph["lry"]))
            
            # Store the mapping - link to staff
            if staff_num not in glyph_zones:
                glyph_zones[staff_num] = []
            
            glyph_info = {
                "zone_id": zone_id,
                "name": glyph.get("name", "unknown"),
                "offset": glyph["ulx"]  # Horizontal position, useful for ordering
            }
            glyph_zones[staff_num].append(glyph_info)
    
    # Sort glyphs within each staff by horizontal position (left to right)
    for staff_num in glyph_zones:
        glyph_zones[staff_num].sort(key=lambda g: g["offset"])
    
    return glyph_zones

def create_system_breaks(mei_root, zone_ids):
    """Create/update system break elements referencing the staff zones."""
    # Find the first layer in the document
    layer = mei_root.find(".//mei:layer", MEI_NS)
    if layer is None:
        print("Error: Could not find layer element")
        return
    
    # Get existing system breaks
    sbs = layer.findall(".//mei:sb", MEI_NS)
    
    # Remove existing system breaks if they exist
    for sb in sbs:
        layer.remove(sb)
    
    # Add system breaks for staff zones
    for i, zone_id in enumerate(zone_ids):
        sb = ET.Element("{http://www.music-encoding.org/ns/mei}sb")
        sb.set("n", str(i + 1))
        sb.set("facs", f"#{zone_id}")
        layer.append(sb)

def add_glyph_elements(mei_root, glyph_zones, glyph_mappings=None):
    """Add appropriate MEI elements for the glyphs based on their type."""
    # Find the first layer
    layer = mei_root.find(".//mei:layer", MEI_NS)
    if layer is None:
        print("Error: Could not find layer element")
        return
    
    # Find all system breaks to determine insertion points
    sbs = layer.findall(".//mei:sb", MEI_NS)
    
    # Map staff number to system break index in layer
    sb_indices = {}
    for i, sb in enumerate(list(layer)):
        if sb.tag == "{http://www.music-encoding.org/ns/mei}sb":
            sb_num = sb.get("n")
            if sb_num:
                sb_indices[sb_num] = i
    
    # Add glyph elements for each staff
    for staff_num, glyphs in glyph_zones.items():
        if staff_num not in sb_indices:
            print(f"Warning: No system break found for staff {staff_num}")
            continue
        
        sb_index = sb_indices[staff_num]
        
        # Sort glyphs by x-position (left to right)
        glyphs_sorted = sorted(glyphs, key=lambda g: g["offset"])
        
        # Current insertion position
        current_pos = sb_index + 1
        
        # Add elements for each glyph
        for glyph in glyphs_sorted:
            glyph_name = glyph["name"]
            glyph_zone_id = glyph["zone_id"]
            
            # Determine what kind of MEI element to create based on glyph name
            if "clef" in glyph_name:
                # Create a clef element
                clef = ET.Element("{http://www.music-encoding.org/ns/mei}clef")
                
                # Determine clef shape
                if "clef.f" in glyph_name:
                    clef.set("shape", "F")
                elif "clef.c" in glyph_name:
                    clef.set("shape", "C")
                elif "clef.g" in glyph_name:
                    clef.set("shape", "G")
                else:
                    clef.set("shape", "C")  # Default for unknown clef types
                
                # Add facs attribute linking to zone
                clef.set("facs", f"#{glyph_zone_id}")
                
                # Insert at current position and increment
                layer.insert(current_pos, clef)
                current_pos += 1
            
            elif "note" in glyph_name or "neume" in glyph_name:
                # Create a note or neume element
                neume = ET.Element("{http://www.music-encoding.org/ns/mei}neume")
                neume.set("facs", f"#{glyph_zone_id}")
                
                layer.insert(current_pos, neume)
                current_pos += 1
            
            # Add other glyph types as needed

def integrate_mei_with_jsomr_and_glyphs(mei_path, jsomr_path, xml_path, output_path):
    """Main function to integrate MEI with JSOMR staff data and XML glyph data."""
    try:
        # Load MEI file
        mei_tree = ET.parse(mei_path)
        mei_root = mei_tree.getroot()
        
        # Load JSOMR file
        with open(jsomr_path, "r", encoding="utf8") as f:
            jsomr_data = json.load(f)
        staves = jsomr_data.get("staves", [])
        
        # Parse glyph data from XML
        glyphs = parse_glyph_xml(xml_path)
        
        # Assign glyphs to staves
        glyphs_by_staff = assign_glyphs_to_staves(glyphs, staves)
        
        # Create/update zones for staves
        staff_zone_ids, surface = create_mei_zones_from_staves(mei_root, staves)
        
        # Create zones for glyphs
        glyph_zones = create_mei_zones_for_glyphs(mei_root, glyphs_by_staff, surface)
        
        # Create system breaks for staves
        create_system_breaks(mei_root, staff_zone_ids)
        
        # Add glyph elements
        add_glyph_elements(mei_root, glyph_zones)
        
        # Save the updated MEI file
        mei_tree.write(output_path, encoding="utf8", xml_declaration=True)
        print(f"✅ Integrated MEI file written to: {output_path}")
        
        # Print summary of integration
        print(f"Summary:")
        print(f"  - {len(staves)} staves processed")
        print(f"  - {len(glyphs)} glyphs found in XML")
        
        total_assigned = sum(len(glyphs) for glyphs in glyphs_by_staff.values())
        print(f"  - {total_assigned} glyphs assigned to staves")
        
        if total_assigned < len(glyphs):
            print(f"  - {len(glyphs) - total_assigned} glyphs could not be assigned to any staff")
        
    except Exception as e:
        print(f"Error integrating MEI with JSOMR and glyphs: {e}")
        import traceback
        traceback.print_exc()

# Example usage
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Integrate MEI with JSOMR and XML glyph data")
    parser.add_argument("--mei", required=True, help="Path to the MEI file")
    parser.add_argument("--jsomr", required=True, help="Path to the JSOMR file")
    parser.add_argument("--xml", required=True, help="Path to the XML glyph file")
    parser.add_argument("--output", required=True, help="Path to save the integrated MEI file")
    
    args = parser.parse_args()
    
    integrate_mei_with_jsomr_and_glyphs(args.mei, args.jsomr, args.xml, args.output)