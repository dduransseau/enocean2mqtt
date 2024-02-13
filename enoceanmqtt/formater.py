
import re

VLD_UNIT_PATTERN = re.compile(r"\[(\w+)\]")

def packet_to_json(d):
    result_dict = dict()
    if "CMD" in d:
        result_dict["message"] = d["CMD"]["raw"]
    if "IO" in d:
        result_dict["channel"] = d["IO"]["raw_value"]
    if "UN" in d:
        if m := VLD_UNIT_PATTERN.match(d["UN"]["description"]):
            result_dict["unit"] = m.group(1)
    if "MV" in d:
        result_dict["value"] = d["MV"]["raw_value"]

    # if d[<shortcut>]["description"].endswith("Threshold"):
    #     value = d[<shortcut>]["description"].format(value=value)