

import re
from pathlib import Path
from xml.etree import ElementTree as ET


eep_file = "../enocean/protocol/EEP.xml"

vld_unit_pattern = re.compile(r"\[(\w+)\]")

tree = ET.parse(Path(f"./{eep_file}"))
file_root = tree.getroot()
# file_telegram = file_root.find("telegram")

unit_set = set()

for item in file_root.iter():
    if "unit" in item.attrib:
        # print(ET.tostring(item))
        description = item.attrib.get("description")
        unit = item.attrib.get("unit")
        unit_set.add((description, unit))
    if "shortcut" in item.attrib and item.attrib["shortcut"] == "UN":
        print(ET.tostring(item))



print(unit_set)