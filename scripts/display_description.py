
import json

from pprint import pprint
from enocean.protocol.eep import EEP

# eep = EEP()
r = None
f = None

d = dict()
for k1, rorg in EEP().telegrams.items():
    # r = hex(k1)[2:].zfill(2)
    r = int(k1)
    d[r] = dict()
    for k2, func in rorg.items():
        # f = hex(k2)[2:].zfill(2)
        f = int(k2)
        d[r][f] = dict()
        for t in func.values():
            # print(t)
            d[r][f][int(t.type, 16)] = t.to_dict() # t.type[2:].zfill(2)
            # pprint(t)

with open("description.json", "wt", encoding="utf-8") as json_file:
    json.dump(d, json_file, indent=4)