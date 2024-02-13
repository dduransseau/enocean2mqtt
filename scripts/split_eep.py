
from pathlib import Path

from xml.etree import ElementTree as ET
from xml.dom import minidom

import os

def prettify(elem):
    """Return a pretty-printed XML string for the Element."""
    rough_string = ET.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ", encoding="utf-8")

def strip_whitespace(elem):
    """Remove unnecessary whitespace from an Element and its children."""
    for element in elem.iter():
        if element.text:
            element.text = element.text.strip()
        if element.tail:
            element.tail = element.tail.strip()

def split_eep_file(input_file, output_folder):
    tree = ET.parse(input_file)
    root = tree.getroot()

    # for telegrams in root.findall('.//telegrams'):
    for telegram in root.findall('.//telegram'):
        rorg = telegram.get('rorg')[2:]

        for profiles in telegram.findall('.//profiles'):

            for profile in profiles.findall('.//profile'):
                func = profiles.get('func')[2:]
                profile_type = profile.get('type')[2:]
                sub_folder = output_folder.joinpath(f"{rorg}/{func}")
                sub_folder.mkdir(parents=True, exist_ok=True)
                output_file = sub_folder.joinpath(Path(f"{rorg}-{func}-{profile_type}.xml"))

                profiles_element = ET.Element('profiles')
                profiles_element.attrib = profiles.attrib

                profile_copy = ET.Element('profile')
                profile_copy.attrib = profile.attrib
                profile_copy.extend(profile)

                profiles_element.append(profile_copy)
                strip_whitespace(profiles_element)

                telegram_copy = ET.Element('telegram')
                telegram_copy.attrib = telegram.attrib
                telegram_copy.append(profiles_element)

                telegrams_copy = ET.Element('telegrams')
                telegrams_copy.attrib = root.attrib
                telegrams_copy.append(telegram_copy)

                # with open(output_file, 'wb') as file:
                #     # prettify(telegrams_copy, file)
                #     file.write(prettify(telegrams_copy))

if __name__ == "__main__":
    input_file = "../enocean/protocol/EEP.xml"
    output_folder = Path(f"../examples/export")
    split_eep_file(input_file, output_folder)
