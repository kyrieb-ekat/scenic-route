import os
import xml.etree.ElementTree as ET

# === CONFIG ===
input_mei_path = "/Users/ekaterina/miyao_why/output_mei/checked_mei/checked_integrated_mei1.mei"
output_dir = "/Users/ekaterina/miyao_why/output_mei/checked_mei/"

# === NAMESPACE ===
ns = {"mei": "http://www.music-encoding.org/ns/mei"}
ET.register_namespace('', ns["mei"])

# === LOAD MEI ===
tree = ET.parse(input_mei_path)
root = tree.getroot()

# === Remove <clef> from inside <layer> ===
clefs_removed = 0
for layer in root.findall(".//mei:layer", ns):
    for clef in layer.findall("mei:clef", ns):
        layer.remove(clef)
        clefs_removed += 1

# === Check <staffDef> for missing clefs ===
staff_defs = root.findall(".//mei:staffDef", ns)
clefs_missing = 0
for staff_def in staff_defs:
    if staff_def.find("mei:clef", ns) is None:
        clefs_missing += 1
        print(f"⚠️ Warning: <staffDef> at line {staff_def.sourceline if hasattr(staff_def, 'sourceline') else 'unknown'} is missing a <clef> element.")

# === Output new file with incremented name ===
existing = [f for f in os.listdir(output_dir) if f.startswith("checked_integrated_mei") and f.endswith(".mei")]
nums = [int(f.split("checked_integrated_mei")[1].split(".mei")[0]) for f in existing if f.split("checked_integrated_mei")[1].split(".mei")[0].isdigit()]
next_num = max(nums, default=1) + 1
output_path = os.path.join(output_dir, f"checked_integrated_mei{next_num}.mei")

tree.write(output_path, encoding="utf8", xml_declaration=True)

# === Summary ===
print(f"✅ Wrote updated MEI to: {output_path}")
print(f"🧹 Removed {clefs_removed} invalid <clef> elements from <layer>")
if clefs_missing > 0:
    print(f"⚠️ {clefs_missing} <staffDef> elements are missing clefs — you may want to add them manually.")
else:
    print("✅ All <staffDef> elements contain a <clef>")
