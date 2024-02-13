
import json
from pathlib import Path
from xml.etree import ElementTree

class SetEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, set):
            return list(obj)
        return json.JSONEncoder.default(self, obj)

shortcut_list = set()
shortcut_dict = dict()

folder_path = eep_path = Path(r"C:\Users\Damien\Dev\enocean\enocean\protocol\\").absolute().joinpath('eep')
for file_path in folder_path.glob("**/*.xml"):
    print(file_path)
    tree = ElementTree.parse(file_path)
    tree_root = tree.getroot()
    for elt in tree_root.iter():
        shortcut = elt.get("shortcut")
        description = elt.get("description")
        if shortcut:
            shortcut_list.add((shortcut, description,))
            if shortcut not in shortcut_dict.keys():
                shortcut_dict[shortcut] = set((description,))
            else:
                shortcut_dict[shortcut].add(description)


# print(shortcut_list)
with open("shortcut_list.txt", "wt", encoding="utf-8") as list_file:
    for s in shortcut_list:
        list_file.write(str(s)+"\n")

with open("shortcut_list.json", "wt", encoding="utf-8") as list_file:
    json.dump(shortcut_dict, list_file, indent=4, cls=SetEncoder)