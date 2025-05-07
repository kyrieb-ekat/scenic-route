import xml.etree.ElementTree as ET  # Import ElementTree


# Reload the updated MEI file
tree = ET.parse("/mnt/data/updated_output.mei")
root = tree.getroot()

# MEI namespace
ns = {"mei": "http://www.music-encoding.org/ns/mei"}
ET.register_namespace('', ns["mei"])

# Get all zone elements
zones = root.findall(".//mei:zone", ns)

# Assign xml:id to each zone if missing, and collect ids
zone_ids = []
for i, zone in enumerate(zones):
    zone_id = zone.get("{http://www.w3.org/XML/1998/namespace}id")
    if not zone_id:
        zone_id = f"zone-{i+1}"
        zone.set("{http://www.w3.org/XML/1998/namespace}id", zone_id)
    zone_ids.append(zone_id)

# Find the first <layer> element inside <music>
layer = root.find(".//mei:music//mei:layer", ns)

# Insert <sb> elements referencing each zone
# Insert <sb> elements referencing each zone
if layer is not None:
    for i, zid in enumerate(zone_ids):
        sb = ET.Element("{http://www.music-encoding.org/ns/mei}sb", {
            "n": str(i + 1),
            "facs": f"#{zid}"
        })
        layer.append(sb)
else:
    raise ValueError("No <layer> element found in the MEI file.")

# Save the new enriched MEI file
final_mei_path = "/Users/ekaterina/miyao_why/output_mei/final_enriched_output.mei"
# The final MEI file path is stored in final_mei_path
final_mei_path
