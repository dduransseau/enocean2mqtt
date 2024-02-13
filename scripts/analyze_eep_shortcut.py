
import json

from pathlib import Path


with open(Path("shortcut_list.json"), "rt", encoding="utf-8") as list_file:
    l = json.load(list_file)
    for shortcut, k in l.items():
        # print(shortcut)
        if len(k) > 1:
            print(shortcut, k)