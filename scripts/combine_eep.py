from pathlib import Path
from xml.etree import ElementTree as ET

from pprint import pprint

SHORTCUT_CORRECTION = {
	"TMP": "Temperature",
	"HUM": "Humidity",
	"LRNB": "Learn Bit",
	"SVC": "Supply Voltage",
	"ILL": "Illumination",
	"Conc": "Concentration",
	"FAN": "Fan speed",
	"SP": "Set point (linear)",
	"DIV": "Divisor",
	"DWO": "Window open detection",
	"ACO": "Actuator obstructed",
	"SPS": "Set point selection",
	"SW": "Switching command",
	"CMD": "Command identifier",
	"LC": "Local control",
	"MAT": "Maximum time between two subsequent actuator messages",
	"MIT": "Minimum time between two subsequent actuator messages",
	"PM": "Pilot wireMode",
	"ANG": "Rotation angle",
	"LOCK": "Locking modes",
	"MT": "Message type",
	"EB": "Energy bow",
	"DT": "Current value or cumulative value"
}


def correct_shortcut_description(attribs):
    try:
        shortcut = attribs["shotcut"]
        corrected_desc = SHORTCUT_CORRECTION[shortcut]
        attribs["description"] = corrected_desc
        return attribs
    except:
        return attribs

def combine_xml_files(input_folder, output_file):
    arbo = dict()
    rorg_dict = dict()
    profiles_dict = dict()
    root = ET.Element("telegrams")
    root.attrib = dict(version="2.6.4", major_version="2", minor_version="6", revision="4")
    # root = None


    for file_path in input_folder.glob("**/*.xml"):
        tree = ET.parse(file_path)
        file_root = tree.getroot()
        file_telegram = file_root.find("telegram")
        telegram_key = (file_telegram.tag, tuple(sorted(file_telegram.attrib.keys())), tuple(sorted(file_telegram.attrib.values())))
        # print(file_telegram)
        file_profiles = file_telegram.find("profiles")
        profiles_key = (file_profiles.tag, tuple(sorted(file_profiles.attrib.keys())), tuple(sorted(file_profiles.attrib.values())))
        # print(file_profiles)
        file_profile = file_profiles.find("profile")
        profile_key = (file_profile.tag, tuple(sorted(file_profile.attrib.keys())), tuple(sorted(file_profile.attrib.values())))
        # print(file_profile)
        if telegram_key not in arbo.keys():
            arbo[telegram_key] = dict()
            # arbo[telegram_key][profiles_key] = [file_profile]
            # root.append(file_telegram)

            e = ET.Element(file_telegram.tag)
            # print(type(file_telegram.attrib), file_telegram.attrib)
            e.attrib = correct_shortcut_description(file_telegram.attrib)
            rorg_dict[telegram_key] = e

            # e2 = ET.Element(file_profiles.tag)
            # e2.attrib = file_profiles.attrib
            # profiles_dict[profiles_key] = e2

        if profiles_key not in arbo[telegram_key].keys():
            arbo[telegram_key][profiles_key] = set()
            arbo[telegram_key][profiles_key].add(file_profile)
            # print(file_profiles.attrib)
            func = file_profiles.attrib["func"]
            # e = root.find(f"telegram [@func='{func}']")
            # print(e)

            e = ET.Element(file_profiles.tag)
            e.attrib = correct_shortcut_description(file_profiles.attrib)
            profiles_dict[profiles_key] = e

        if profile_key not in arbo[telegram_key][profiles_key]:
            arbo[telegram_key][profiles_key].add(file_profile)

    # pprint(arbo)

    for rorg_key in arbo:
        rorg = rorg_dict[rorg_key]
        print(rorg_key)
        for func_key in arbo[rorg_key]:
            func = profiles_dict[func_key]
            print("\t", func_key)
            for p in arbo[rorg_key][func_key]:
                func.append(p)
            rorg.append(func)
        root.append(rorg)
        ET.indent(root, space=" ")

    combined_tree = ET.ElementTree(root)
    # with open(output_file, 'wt', encoding="utf-8") as file:
    #     file.write(ET.tostring(root, encoding="utf-8", xml_declaration=True).decode())
    combined_tree.write(output_file, encoding="utf-8", xml_declaration=True)

if __name__ == "__main__":
    input_folder = Path(r"../enocean/protocol/eep")
    output_file = "../enocean/protocol/EEP.xml"
    combine_xml_files(input_folder, output_file)
