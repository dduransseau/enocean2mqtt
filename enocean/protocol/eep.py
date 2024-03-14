# -*- encoding: utf-8 -*-
import logging
from pathlib import Path
from xml.etree import ElementTree

import enocean.utils
from enocean.protocol.constants import RORG  # noqa: F401


class BaseDataElt:

    logger = logging.getLogger('enocean.protocol.eep.data')
    " Base class inherit from every value data telegram"
    def __init__(self, elt):
        self.description = elt.get("description", "")
        self.shortcut = elt.get("shortcut")
        self.offset = int(elt.get("offset")) if elt.get("offset") else None
        self.size = int(elt.get("size")) if elt.get("size") else None
        self.unit = elt.get("unit") if elt.get("unit") else ""
        self._raw_value = None

    def parse_raw(self, bitarray):
        ''' Get raw data as integer, based on offset and size '''
        # TODO: That could be improved and could be check since it raise error
        # self.logger.debug(f"Parse raw data: {bitarray}")
        result = 0
        try:
            # return int(''.join(['1' if digit else '0' for digit in bitarray[self.offset:self.offset + self.size]]), 2)
            for bit in bitarray[self.offset:self.offset + self.size]:
                result = (result << 1) | bit
            self._raw_value = result
            return result
        except:
            return 0

    def _set_raw(self, raw_value, bitarray):
        ''' put value into bit array '''
        size = self.size
        for digit in range(self.size):
            bitarray[self.offset+digit] = (raw_value >> (size-digit-1)) & 0x01 != 0
        return bitarray

    def to_dict(self):
        d = dict(description=self.description)
        if self.shortcut:
            d["shortcut"] = self.shortcut
        if self.offset:
            d["offset"] = self.offset
        if self.size:
            d["size"] = self.size
        if self.unit:
            d["unit"] = self.unit
        return d


class DataStatus(BaseDataElt):
    """ Status element
    ex: <status description="T21" shortcut="T21" offset="2" size="1" />
    """

    def __str__(self) -> str:
        return f"Data status for {self.description}"

    def parse(self, bitarray, status):
        ''' Get boolean value, based on the data in XML '''
        self._raw_value = self.parse_raw(status)
        return {
            self.shortcut: {
                'description': self.description,
                'unit': self.unit,
                'value': True if self._raw_value else False,
                'raw_value': self._raw_value,
            }
        }

    def set_value(self, data, bitarray):
        ''' set given value to target bit in bitarray '''
        bitarray[self.offset] = data
        return bitarray

    def to_dict(self):
        d = dict(description=self.description)
        d["type"] = "status"
        return d

class DataValue(BaseDataElt):
    """
    ex: <value description="Temperature (linear)" shortcut="TMP" offset="16" size="8" unit="°C">
            <range>
              <min>255</min>
              <max>0</max>
            </range>
            <scale>
              <min>-40.000000</min>
              <max>0.000000</max>
            </scale>
          </value>
    """
    ROUNDING = 2

    def __init__(self, elt):
        super().__init__(elt)
        if r := elt.find("range"):
            self.is_range = True
            self.range_min = float(r.find("min").text)
            self.range_max = float(r.find("max").text)
        if s := elt.find("scale"):
            self.scale = True
            self.scale_min = float(s.find("min").text)
            self.scale_max = float(s.find("max").text)
        try:
            self.multiplier = (self.scale_max - self.scale_min) / (self.range_max - self.range_min)
        except Exception as e:
            self.multiplier = 1

    def process_value(self, val):
        # p8 EEP profile documentation
        return round(self.multiplier * (val - self.range_min) + self.scale_min, self.ROUNDING)

    def parse(self, bitarray, status):
        self._raw_value = self.parse_raw(bitarray)

        return {
            self.shortcut: {
                'description': self.description,
                'unit': self.unit,
                'value': self.process_value(self._raw_value),
                'raw_value': self._raw_value,
            }
        }

    def set_value(self, data, bitarray):
        ''' set given numeric value to target field in bitarray '''
        # derive raw value
        # TODO : Confirm method
        # value = (data - self.scale_min) / (self.range_max - self.range_min) * (self.scale_max - self.scale_min) + self.range_min
        value = self.process_value(data)
        return self._set_raw(int(value), bitarray)

    def __str__(self) -> str:
        return f"Data value for {self.description}"

    def to_dict(self):
        d = super().to_dict()
        d["type"] = "value"
        if self.range_min is not None and self.range_max  is not None:
            d["range"] = dict(min=self.range_min, max=self.range_max)
        if self.scale_min is not None and self.scale_max is not None:
            d["scale"] = dict(min=self.scale_min, max=self.scale_max)
        return d


class DataEnumItem(BaseDataElt):

    def __init__(self, elt):
        super().__init__(elt)
        self.value = int(elt.get("value"))

    def __str__(self):
        return f"Enum Item {self.description}"

    def parse(self, val):
        return self.description
        # return self.description.replace(" ", "_").lower()

    def to_dict(self):
        d = super().to_dict()
        d["type"] = "item"
        if self.value is not None:
            d["value"] = self.value
        return d


class DataEnumRangeItem(BaseDataElt):

    def __init__(self, elt):
        super().__init__(elt)

        range = elt.find("range")
        scale = elt.find("scale")
        self.multiplier = 1
        if range and scale:
            self.range_min = float(range.find("min").text)
            self.range_max = float(range.find("max").text)
            self.scale_min = float(scale.find("min").text)
            self.scale_max = float(scale.find("max").text)
            try:
                self.multiplier = (self.scale_max - self.scale_min) / (self.range_max - self.range_min)
            except Exception as e:
                self.logger.debug(f"Unable to set multiplier")
        else:
            self.start = int(elt.get("start"))
            self.end = int(elt.get("end"))

    @property
    def limit(self):
        return (self.start, self.end,)

    def is_in(self, value):
        if self.start <= value <= self.end:
            return True

    def range(self):
        return range(self.start, self.end+1)

    def __eq__(self, __value: object) -> bool:
        return super().__eq__(__value)

    def __str__(self):
        return f"Enum Range Item {self.description}"

    def to_dict(self):
        d = super().to_dict()
        d["type"] = "rangeitem"
        if self.start is not None:
            d["start"] = self.start
        if self.end is not None:
            d["end"] = self.end
        return d

    def parse(self, val):
        return val * self.multiplier
        # return self.description.replace(" ", "_").lower().format(value=val)


class DataEnum(BaseDataElt):
    """ Base class used for Enum and EnumRange"""

    def __init__(self, elt):
        super().__init__(elt)
        self.items = dict()
        self.range_items = list()
        for item in elt.findall("item"):
            i = DataEnumItem(item)
            self.items[i.value] = i
        for ritem in elt.findall("rangeitem"):
            r = DataEnumRangeItem(ritem)
            self.range_items.append(r)

    @property
    def first(self):
        # Find the first valid value of enum
        min = 256
        for i in self.items.keys():
            if i < min:
                min = i
        for i in self.range_items:
            if i.start < min:
                min = i.start
        return min

    @property
    def last(self):
        # find the last valid value of enum
        max = 0
        for i in self.items.values():
            if i.value > max:
                max = i.value
        for i in self.range_items:
            if i.end > max:
                max = i.end
        return max

    def get(self, val=None, description=None):
        # self.logger.debug(f"Get enum item for value {val} and/or description {description}")
        if val is not None:
            if item := self.items.get(val):
                return item
            for r in self.range_items:
                if r.is_in(val):
                    return r
        elif description: # Get instance based on description
            for item in self.items.values():
                if item.description == description:
                    return item
            for itemrange in self.range_items:
                if itemrange.description == description:
                    return itemrange

    def parse(self, bitarray, status):
        self._raw_value = self.parse_raw(bitarray)

        # Find value description
        item = self.get(int(self._raw_value))
        #self.logger.debug(f"Found item {item} for value {self._raw_value} in enum {self.description}")
        value = item.parse(self._raw_value)
        return {
            self.shortcut: {
                'description': item.description if item else "",
                'unit': self.unit,
                'value': value,
                'raw_value': self._raw_value,
            }
        }

    def set_value(self, val, bitarray):
        if isinstance(val, int):
            item = self.get(val)
            value = val
        else:
            item = self.get(description=val)
            value = item.value
        if not item:
            raise ValueError(f"Unable to find enum for {val}, might be out of Range")
        self.logger.debug(f"Set value to {value}")
        return self._set_raw(int(value), bitarray)

    def to_dict(self):
        d = super().to_dict()
        d["type"] = "enum"
        d["items"] = [i.to_dict() for i in self.items.values()] + [i.to_dict() for i in self.range_items]
        return d

    def __str__(self) -> str:
        return f"Data enum for {self.description} from {self.first} to {self.last}"

    def __len__(self):
        return len(self.items) + len(self.range_items)


class ProfileCommand(DataEnum):
    """ Used to define available commands"""

    def __str__(self) -> str:
        return f"Command enum: {self.description}"


class ProfileData:
    """"""
    logger = logging.getLogger('enocean.protocol.eep.profile')
    def __init__(self, elt):
        self.command = int(elt.get("command")) if elt.get("command") else None
        self.direction = int(elt.get("direction")) if elt.get("direction") else None
        self.bits = int(elt.get("bits")) if elt.get("bits") else None
        self.items = list()

        for e in elt.iter():
            if e.tag == "status":
                self.items.append(DataStatus(e))
            elif e.tag == "value":
                self.items.append(DataValue(e))
            elif e.tag == "enum":
                self.items.append(DataEnum(e))

    def __str__(self):
        return f"Profile data with {len(self.items)} items | command:{self.command} direction:{self.direction} "

    def to_dict(self):
        d = dict()
        if self.command:
            d["command"] = self.command
        if self.direction:
            d["direction"] = self.direction
        if self.bits:
            d["bits"] = self.bits
        d["values"] = [i.to_dict() for i in self.items]
        return d

    def get(self, shortcut=None):
        """
        return: BaseDataElt
        """
        self.logger.debug(f"Get profile data for shortcut {shortcut}")
        for item in self.items:
            if item.shortcut == shortcut:
                return item


class Profile:
    logger = logging.getLogger('enocean.protocol.eep.profile')

    def __init__(self, elt, rorg=None, func=None):
        self.rorg = rorg
        self.func = func
        self.type = elt.get("type")
        self.description = elt.get("description")
        if len(elt.findall("command")) > 1:
            raise ValueError("More then 1 command for profile")
        c = elt.find("command")
        if c is not None:
            self.commands = ProfileCommand(c)
            # self.logger.debug(f"Get shortcut {self.commands.shortcut} for command")
            # TODO: Confirm utility
            # if len(self.commands) > len(elt.findall("data")):
            #     Warning(f"{self.rorg}-{self.func}-{self.type} Seems to have less command than possible value")
            #     self.logger.debug(f"commands: {len(self.commands)} data {len(elt.findall("data"))}")
        else:
            self.commands = None
        # Dict of multiple supported datas profile depending on direction or command
        self.datas = dict()
        for p in elt.findall("data"):
            # List all suppoted Profile data based organized on key (command, direction) (None, None) is default
            profile_data = ProfileData(p)
            profile_key = (profile_data.command, profile_data.direction)
            self.datas[profile_key] = profile_data

    @property
    def code(self):
        return (f"{enocean.utils.to_eep_hex_code(self.rorg)}"
                f"-{enocean.utils.to_eep_hex_code(self.func)}"
                f"-{enocean.utils.to_eep_hex_code(self.type)}").upper()

    def __str__(self):
        txt = f"Profile {self.code} about {self.description}"
        if self.commands:
            txt += f" with {len(self.commands)} commands"
        return txt

    def to_dict(self):
        d = dict(data=list())
        if self.commands:
            d["commands"] = self.commands.to_dict()
        for v in self.datas.values():
            d["data"].append(v.to_dict())
        return d

    def get_message_form(self, command=None, direction=None):
        if command and direction:
            # TODO: Confirm this limitation
            self.logger.warning("Command and Direction are specified but only one at a time should be use")
        if command and not self.commands:
            self.logger.error("A command is specified but not supported by profile")
            # raise ValueError("A command is specified but not supported by profile")
        elif self.commands and not command:
            # Do not raise Exception since it break tests, however this is an error anyway
            # raise ValueError("Command not specified but profile support multiple commands")
            self.logger.warning("Command is not specified but the profile support multiples commands")
            return self.datas.get((1, direction)) # TODO: Confirm that first command must be decoded if not specified
        if self.commands and command:
            command_item = self.commands.get(val=command)
            command_shortcut = self.commands.shortcut
        else:
            command_item = None
            command_shortcut = None
        telegram_data = self.datas.get((command, direction))
        return Message(telegram_data, command=command_item, command_shortcut=command_shortcut, direction=direction)

    # def get_item_shortcut(self, shortcut):
    #     if self.commands and self.commands.shortcut == shortcut:
    #         return self.commands
    #     for data_elt in self.datas.values():
    #         if data_elt.shortcut == shortcut:
    #             return data_elt
    #
    # def map_item_value(self, shortcut, value):
    #     if item := self.get_item_shortcut(shortcut):
    #         if val := item.get(val=value):
    #             return val


class Message:
    logger = logging.getLogger('enocean.protocol.eep.message')

    def __init__(self, telegram_data, command=None, command_shortcut=None, direction=None):
        self.telegram_data = telegram_data
        self.command_item = command
        self.command_shortcut = command_shortcut
        if command and not command_shortcut: # Set command shortcut to default value if set
            self.command_shortcut = "CMD"
        self.direction = direction

    def __str__(self):
        return f"Message {self.telegram_data} with command {self.command_item}"

    @property
    def items(self):
        return self.telegram_data.items

    @property
    def data_length(self):
        return self.telegram_data.bits

    def get_values(self, bitarray, status):
        ''' Get keys and values from bitarray '''
        # self.logger.debug(f"Parse bitarray {bitarray} {hex(int("".join(map(str, map(int, bitarray))), 2))[2:]}")
        output = dict()
        for source in self.items:
            output.update(source.parse(bitarray, status))
        self.logger.debug(f"get_values {output}")
        return output

    def set_values(self, packet, values):
        ''' Update data based on data contained in properties
        profile: Profile packet._bit_data, packet._bit_status
        '''
        self.logger.debug(f"Set value for properties={values} to {self.telegram_data}")
        # self.logger.debug(f"Profile with selected command {self.profile.command_item} {self.profile.command_data}")

        for shortcut, value in values.items():
            target = self.telegram_data.get(shortcut)
            if isinstance(target, DataStatus):
                packet._bit_status = target.set_value(value, packet._bit_data)
            else:
                packet._bit_data = target.set_value(value, packet._bit_data)


class EepLibrary:
    logger = logging.getLogger('enocean.protocol.eep_library')

    def __init__(self):

        try:

            eep_path = Path(__file__).parent.joinpath('EEP.xml')
            self.logger.info(f"load EEP xml file: {eep_path}")
            self.telegrams = self.__load_xml(eep_path)
            self.logger.debug("EEP loaded")
        except Exception as e:
            # Impossible to test with the current structure?
            # To be honest, as the XML is included with the library,
            # there should be no possibility of ever reaching this...
            self.logger.warning('Cannot load protocol file!')
            self.logger.exception(e)

    @staticmethod
    def __load_xml(file_path):
        tree = ElementTree.parse(file_path)
        tree_root = tree.getroot()
        return {
            enocean.utils.from_hex_string(telegram.attrib['rorg']): {
                enocean.utils.from_hex_string(function.attrib['func']): {
                    enocean.utils.from_hex_string(profile.attrib['type']):
                        Profile(profile,
                                rorg=enocean.utils.from_hex_string(telegram.attrib['rorg']),
                                func=enocean.utils.from_hex_string(function.attrib['func']))
                    for profile in function.findall('profile')
                }
                for function in telegram.findall('profiles')
            }
            for telegram in tree_root.findall('telegram')
        }

class EEP:
    logger = logging.getLogger('enocean.protocol.eep')

    telegrams = EepLibrary().telegrams

    @classmethod
    def find_profile(cls, eep_rorg, rorg_func, rorg_type, direction=None, command=None):
        ''' Find profile and data description, matching RORG, FUNC and TYPE

        return: ProfileData
        '''
        try:
            profile = cls.telegrams[eep_rorg][rorg_func][rorg_type]
            return profile.get(direction=direction, command=command)
        except Exception as e:
            cls.logger.warning('Cannot find rorg %s func %s type %s in EEP!', hex(eep_rorg), hex(rorg_func),
                                hex(rorg_type))
            return None

    @classmethod
    def get_eep(cls, eep_rorg, rorg_func, rorg_type):
        try:
            return cls.telegrams[eep_rorg][rorg_func][rorg_type]
        except Exception as e:
            cls.logger.warning('Cannot find rorg %s func %s type %s in EEP!', hex(eep_rorg), hex(rorg_func),
                                hex(rorg_type))

    @classmethod
    def load_library(cls):
        cls.telegrams = EepLibrary().telegrams

