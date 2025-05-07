import os
import json
import xml.etree.ElementTree as ET

# Define your file paths
mei_input_path = "/Users/ekaterina/miyao_why/output_mei/checked_mei/checked_integrated_mei1.mei"
jsomr_path = "/Users/ekaterina/miyao_why/output_jsomr/integrated_jsomr/integrated_jsomr1.json"
output_dir = "/Users/ekaterina/miyao_why/output_mei/checked_mei/"

# Determine next available output number
existing_files = [f for f in os.listdir(output_dir) if f.startswith("checked_integrated_mei") and f.endswith(".mei")]
existing_nums = [int(f.split("checked_integrated_mei")[1].split(".mei")[0]) for f in existing_files if f.split("checked_integrated_mei")[1].split(".mei")[0].isdigit()]
next_num = max(existing_nums, default=1) + 1
output_path = os.path.join(output_dir, f"checked_integrated_mei{next_num}.mei")

# Load MEI
tree = ET.parse(mei_input_path)
root = tree.getroot()

# MEI namespace
ns = {"mei": "http://www.music-encoding.org/ns/mei"}
ET.register_namespace('', ns["mei"])

# Load JSOMR
with open(jsomr_path, "r", encoding="utf8") as f:
    jsomr = json.load(f)
staves = jsomr["staves"]

# Get zones
zones = root.findall(".//mei:zone", ns)
if len(zones) != len(staves):
    print(f"Warning: {len(zones)} zones found, but {len(staves)} staves in JSOMR.")

# Update zone coordinates
zone_ids = []
for i, (zone, staff) in enumerate(zip(zones, staves)):
    bbox = staff["bounding_box"]
    ulx = bbox["ulx"]
    uly = bbox["uly"]
    lrx = ulx + bbox["ncols"]
    lry = uly + bbox["nrows"]

    zone.set("ulx", str(ulx))
    zone.set("uly", str(uly))
    zone.set("lrx", str(lrx))
    zone.set("lry", str(lry))

    zone_id = zone.get("{http://www.w3.org/XML/1998/namespace}id")
    if not zone_id:
        zone_id = f"zone-{i+1}"
        zone.set("{http://www.w3.org/XML/1998/namespace}id", zone_id)
    zone_ids.append(zone_id)

# Insert <sb> elements
layer = root.find(".//mei:music//mei:layer", ns)
if layer is None:
    raise ValueError("No <layer> element found inside <music>.")

for i, zid in enumerate(zone_ids):
    sb = ET.Element("{http://www.music-encoding.org/ns/mei}sb", {
        "n": str(i + 1),
        "facs": f"#{zid}"
    })
    layer.append(sb)

# Save enriched MEI
tree.write(output_path, encoding="utf8", xml_declaration=True)
print(f"✅ Updated MEI written to: {output_path}")
