# -*- encoding: utf-8 -*-
import logging
from enum import StrEnum
from pathlib import Path
from xml.etree import ElementTree

from enocean.utils import from_hex_string, get_bits_from_bytearray, get_bits_from_byte, set_bits_in_bytearray, set_bits_to_byte

logger = logging.getLogger("enocean.protocol.eep")


class SpecificShortcut(StrEnum):
    UNIT = "UN"
    MULTIPLIER = "SCM"
    DIVISOR = "DIV"
    COMMAND = "CMD"
    LEARN_BIT = "LRNB"
    HUMIDITY_AVAILABILITY = "HSN"
    TEMPERATURE_AVAILABILITY = "TSN"
    HUMIDITY = "HUM"
    TEMPERATURE = "TMP"


AVAILABILITY_FIELD_MAPPING = {
    SpecificShortcut.HUMIDITY_AVAILABILITY: SpecificShortcut.HUMIDITY,
    SpecificShortcut.TEMPERATURE_AVAILABILITY: SpecificShortcut.TEMPERATURE,
}


def parse_number_value(v):
    if v.startswith("0x"):
        return int(v, 16)
    elif "." in v:
        return float(v)
    else:
        return int(v)


class EEPLibraryInitError(Exception):
    """Error to init the EEP library is EEP.xml present ?"""


class ProfileField:

    def __init__(self, shortcut, raw_value, description, value=None, unit=None, status=False):
        self.shortcut = shortcut
        self.raw_value = raw_value
        self.description: str = description
        self._value = value
        self.unit = unit
        self.status = status

    @property
    def value(self):
        if self._value:
            return self._value
        return self.raw_value

    @value.setter
    def value(self, val):
        self._value = val

    @property
    def is_operator(self):
        if self.shortcut in (SpecificShortcut.MULTIPLIER, SpecificShortcut.DIVISOR):
            return True
        return False

    @property
    def is_unit(self):
        if self.shortcut == SpecificShortcut.UNIT:
            return True
        return False

    @property
    def is_command(self):
        if self.shortcut == SpecificShortcut.COMMAND:
            return True
        return False

    @property
    def is_sensor_availability(self):
        if self.shortcut in (SpecificShortcut.TEMPERATURE_AVAILABILITY, SpecificShortcut.HUMIDITY_AVAILABILITY):
            return True
        return False

    @property
    def is_internal(self):
        if self.is_operator or self.is_unit or self.is_command or self.is_sensor_availability:
            return True
        return False


class BaseDataElt:
    logger = logging.getLogger("enocean.protocol.eep.data")
    " Base class inherit from every value data telegram"

    def __init__(self, elt):
        self.description = elt.get("description", "")
        self.shortcut = elt.get("shortcut")
        self.offset = int(elt.get("offset")) if elt.get("offset") else None
        self.size = int(elt.get("size")) if elt.get("size") else None
        self.unit = elt.get("unit") if elt.get("unit") else ""
        self._raw_value = None

    def parse_raw(self, user_payload):
        """Get raw data as integer, based on offset and size"""
        # self.logger.debug(f"Parse raw data: {user_payload}")
        return get_bits_from_bytearray(user_payload, self.offset, self.size)

    def _set_raw(self, raw_value, bitarray):
        """put value into bit array"""
        set_bits_in_bytearray(bitarray, self.offset, self.size, raw_value)
        return bitarray


class DataStatus(BaseDataElt):
    """Status element
    ex: <status description="T21" shortcut="T21" offset="2" size="1" />
    """

    def __str__(self) -> str:
        return f"Data status for {self.description}"

    def parse(self, user_payload, status):
        """Get boolean value, based on the data in XML"""
        self._raw_value = get_bits_from_byte(status, self.offset)
        return ProfileField(self.shortcut, self._raw_value, self.description, value=bool(self._raw_value), unit=self.unit, status=True)

    def set_value(self, bit, b):
        """
        bit: value of bit to change
        b: byte to update
        """
        return set_bits_to_byte(b, self.offset, bit)


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

    ROUNDING = 3

    def __init__(self, elt):
        super().__init__(elt)
        if r := elt.find("range"):
            self.is_range = True
            self.range_min = parse_number_value(r.find("min").text)
            self.range_max = parse_number_value(r.find("max").text)
        if s := elt.find("scale"):
            self.scale = True
            self.scale_min = parse_number_value(s.find("min").text)
            self.scale_max = parse_number_value(s.find("max").text)
        try:
            self.multiplier = (self.scale_max - self.scale_min) / (
                self.range_max - self.range_min
            )
        except Exception:
            self.multiplier = 1

    def process_value(self, val):
        # p8 EEP profile documentation
        return round(
            self.multiplier * (val - self.range_min) + self.scale_min, self.ROUNDING
        )

    def parse(self, user_payload, status):
        self._raw_value = self.parse_raw(user_payload)
        return ProfileField(self.shortcut, self._raw_value, self.description,
                            value=self.process_value(self._raw_value), unit=self.unit)

    def set_value(self, data, bitarray):
        """set given numeric value to target field in bitarray"""
        # derive raw value
        value = self.process_value(data)
        return self._set_raw(int(value), bitarray)

    def __str__(self) -> str:
        return f"Data value for {self.description}"


class DataEnumItem:
    def __init__(self, elt):
        self.value = parse_number_value(elt.get("value"))
        self.description = elt.get("description", "")

    def __str__(self):
        return f"Enum Item {self.description}"

    def parse(self, val):
        return self.description
        # return self.description.replace(" ", "_").lower()


class DataEnumRangeItem:
    def __init__(self, elt):
        self.description = elt.get("description", "")
        range = elt.find("range")
        scale = elt.find("scale")
        self.multiplier = 1
        if range and scale:
            self.range_min = parse_number_value(range.find("min").text)
            self.range_max = parse_number_value(range.find("max").text)
            self.scale_min = parse_number_value(scale.find("min").text)
            self.scale_max = parse_number_value(scale.find("max").text)
            self.start = self.scale_min
            self.end = self.scale_max
            try:
                self.multiplier = (self.scale_max - self.scale_min) / (
                    self.range_max - self.range_min
                )
            except Exception:
                logger.debug("Unable to set multiplier")
        else:
            self.start = parse_number_value(elt.get("start"))
            self.end = parse_number_value(elt.get("end"))

    @property
    def limit(self):
        return (
            self.start,
            self.end,
        )

    def is_in(self, value):
        if self.start <= value <= self.end:
            return True

    def range(self):
        return range(self.start, self.end + 1)

    def __eq__(self, __value: object) -> bool:
        return super().__eq__(__value)

    def __str__(self):
        return f"Enum Range Item {self.description}"

    def parse(self, val):
        return val * self.multiplier
        # return self.description.replace(" ", "_").lower().format(value=val)


class DataEnum(BaseDataElt):
    """Base class used for Enum and EnumRange"""

    def __init__(self, elt):
        super().__init__(elt)
        self.items = dict()
        self.range_items = list()
        self.__first = None
        self.__last = None
        for item in elt.findall("item"):
            i = DataEnumItem(item)
            self.items[i.value] = i
        for ritem in elt.findall("rangeitem"):
            r = DataEnumRangeItem(ritem)
            self.range_items.append(r)

    @property
    def first(self):
        # Find the first valid value of enum
        if not self.__first:
            min = 256
            for i in self.items.keys():
                if i < min:
                    min = i
            for i in self.range_items:
                if i.start < min:
                    min = i.start
            self.__first = min
        return self.__first

    @property
    def last(self):
        # Find the last valid value of enum
        if not self.__last:
            max = 0
            for i in self.items.values():
                if i.value > max:
                    max = i.value
            for i in self.range_items:
                if i.end > max:
                    max = i.end
            self.__last = max
        return self.__last

    def __len__(self):
        return self.last - self.first

    def get(self, val=None, description=None):
        # self.logger.debug(f"Get enum item for value {val} and/or description {description}")
        if val is not None:
            if item := self.items.get(val):
                return item
            for r in self.range_items:
                if r.is_in(val):
                    return r
        elif description:  # Get instance based on description
            for item in self.items.values():
                if item.description == description:
                    return item
            for itemrange in self.range_items:
                if itemrange.description == description:
                    return itemrange

    def parse(self, user_payload, status):
        self._raw_value = self.parse_raw(user_payload)
        # Find value description
        item = self.get(int(self._raw_value))
        # self.logger.debug(f"Found item {item} for value {self._raw_value} in enum {self.description}")
        value = item.parse(self._raw_value)
        return ProfileField(self.shortcut, self._raw_value, self.description, value=value,
                            unit=self.unit)

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

    def __str__(self) -> str:
        return f"Data enum for {self.description} from {self.first} to {self.last}"


class ProfileCommand(DataEnum):
    """Used to define available commands"""

    def __str__(self) -> str:
        return f"Command enum: {self.description}"


class ProfileData:
    """"""

    logger = logging.getLogger("enocean.protocol.eep.profile")

    def __init__(self, elt):
        self.command = int(elt.get("command")) if elt.get("command") else None
        self.direction = int(elt.get("direction")) if elt.get("direction") else None
        self.bytes = int(elt.get("bits")) if elt.get("bits") else None
        self.items = list()
        # Specific items list for global message operations
        self._data_value = set()
        self._operator_fields = list()
        self._unit_fields = list()
        self._availability_fields = list()

        for e in elt.iter():
            if e.tag == "status":
                d = DataStatus(e)
            elif e.tag == "value":
                d = DataValue(e)
                self._data_value.add(d)
            elif e.tag == "enum":
                d = DataEnum(e)
            else:
                continue
            self.items.append(d)
            if d.shortcut in (SpecificShortcut.MULTIPLIER, SpecificShortcut.DIVISOR):
                self._operator_fields.append(d)
            elif d.shortcut == SpecificShortcut.UNIT:
                self._unit_fields.append(d)
            elif d.shortcut in (SpecificShortcut.TEMPERATURE_AVAILABILITY, SpecificShortcut.HUMIDITY_AVAILABILITY):
                self._availability_fields.append(d)

    def __str__(self):
        return f"Profile data with {len(self.items)} items | command:{self.command} direction:{self.direction} "

    def get(self, shortcut=None):
        """
        return: BaseDataElt
        """
        self.logger.debug(f"Get profile data for shortcut {shortcut}")
        for item in self.items:
            if item.shortcut == shortcut:
                return item

    @property
    def has_value(self):
        return bool(len(self._data_value))

    @property
    def has_global_operation(self):
        # if len(self._operator_fields) > 1:
        #     self.logger.debug("There is multiple operator for this EEP by omit calculation")
        # if len(self._unit_fields) > 1:
        #     self.logger.debug("There is multiple units for this EEP omit metric mapping")
        # Manage to operate EEP where only one operator and/or unit is specified
        # Unable to map specific operator or unit for speific field in multiple metrics context
        if self.has_value and (
            len(self._operator_fields) == 1 or len(self._unit_fields) == 1
        ):
            return True
        return False

    @property
    def unit(self):
        return self._unit_fields[0] if self._unit_fields else None

    @property
    def factor(self):
        return self._operator_fields[0] if self._operator_fields else None

    @property
    def values(self):
        return self._data_value if self._data_value else None

    @property
    def availability_fields(self):
        return self._availability_fields if self._availability_fields else None


class Profile:
    logger = logging.getLogger("enocean.protocol.eep.profile")

    def __init__(self, elt, rorg=None, func=None):
        self.rorg = rorg
        self.func = func
        self.type = int(elt.get("type", 0), 16)
        self.description = elt.get("description", "")
        if len(elt.findall("command")) > 1:
            raise ValueError("More then 1 command for profile")
        c = elt.find("command")
        if c is not None:
            self.commands = ProfileCommand(c)
        else:
            self.commands = None
        # Dict of multiple supported datas profile depending on direction or command
        self.datas = dict()
        for p in elt.findall("data"):
            # List all supported Profile data based organized on key (command, direction) (None, None) is default
            profile_data = ProfileData(p)
            profile_key = (profile_data.command, profile_data.direction)
            self.datas[profile_key] = profile_data

    @property
    def code(self):
        return f"{self.rorg:02X}-{self.func:02X}-{self.type:02X}"

    def __str__(self):
        txt = f"Profile {self.code} about {self.description}"
        if self.commands:
            txt += f" with {len(self.commands)} commands"
        return txt

    def get_telegram_form(self, command=None, direction=None):
        # if command and direction:
        #     # Must confirm this limitation
        #     self.logger.warning("Command and Direction are specified but only one at a time should be use")
        if command and not self.commands:
            self.logger.error("A command is specified but not supported by profile")
            # raise ValueError("A command is specified but not supported by profile")
        elif self.commands and not command:
            raise ValueError(
                "Command not specified but profile support multiple commands"
            )
            # self.logger.warning("Command is not specified but the profile support multiples commands")
        if self.commands and command:
            command_item = self.commands.get(val=command)
            command_shortcut = self.commands.shortcut
        else:
            command_item = None
            command_shortcut = None
        # Get the profile data that correspond to the telegram
        try:
            profile_data = self.datas[(command, direction)]
        except KeyError:
            # Handle case where direction is not defined in EEP
            profile_data = self.datas.get((command, None))
        return TelegramFunctionGroup(
            profile_data,
            command=command_item,
            command_shortcut=command_shortcut,
            direction=direction,
        )


class TelegramFunctionGroup:
    logger = logging.getLogger("enocean.protocol.eep.functiongroup")

    def __init__(
        self, profile_data, command=None, command_shortcut=None, direction=None
    ):
        self.profile_data = profile_data
        self.command_item = command
        self.command_shortcut = command_shortcut
        if command and not command_shortcut:  # Set command shortcut to default value if set
            self.command_shortcut = SpecificShortcut.COMMAND
        self.direction = direction

    def __str__(self):
        return f"Message {self.profile_data} with command {self.command_item}"

    @property
    def items(self):
        return self.profile_data.items

    @property
    def data_length(self):
        return int(self.profile_data.bytes)

    def get_values(self, user_payload, status, global_process=True):
        """Get keys and values from user_payload"""
        output = []
        bypass_list = []
        # Calculate the values that have unit or operator (multiplier or divisor) in the message
        if global_process and self.profile_data.has_global_operation:
            self.logger.debug("Profile data has global operation to perform")
            factor = 1
            unit = None
            operator_item = self.profile_data.factor
            unit_item = self.profile_data.unit
            values_item = self.profile_data.values
            if operator_item:
                bypass_list.append(operator_item)
                operator = operator_item.parse(user_payload, status)
                if operator.shortcut == SpecificShortcut.DIVISOR:
                    factor = 1 / float(operator.value)
                elif operator.shortcut == SpecificShortcut.MULTIPLIER:
                    factor = float(operator.value)
                self.logger.debug(f"Defined factor for profile data is {factor}")
            if unit_item:
                u = unit_item.parse(user_payload, status)
                unit = u.value
                self.logger.debug(f"Defined unit for profile data is {unit}")
            for v_i in values_item:
                bypass_list.append(v_i)
                v_i.unit = unit
                v = v_i.parse(user_payload, status)
                v.value = v.value * factor
                output.append(v)
        # Remove fields for device that have unavailable sensor
        if global_process and self.profile_data.availability_fields:
            try:
                self.logger.debug("Profile data has fields availability flags")
                for flag in self.profile_data.availability_fields:
                    availability_flag = flag.parse(user_payload, status)
                    self.logger.debug(
                        f"Field availability flags to process {availability_flag}"
                    )
                    if metric_shortcut := AVAILABILITY_FIELD_MAPPING.get(availability_flag.shortcut):
                        if availability_flag.raw_value == 0:
                            metric_field = [
                                v
                                for v in self.profile_data.values
                                if v.shortcut == metric_shortcut
                            ]
                            self.logger.debug(
                                f"Found value field to disable: {metric_field}"
                            )
                            bypass_list.append(metric_field[0])
                            bypass_list.append(flag)
            except IndexError:
                self.logger.warning("There is an error in unavailability field")
            except Exception:
                pass

        for source in self.items:
            # Manage to get the command related value as define in profile
            if source in bypass_list:
                self.logger.debug(f"Bypass {source} this it has already been handled")
                continue
            if source.shortcut == "CMD":
                output.append(ProfileField(SpecificShortcut.COMMAND, self.command_item.value, "Command identifier", value=self.command_item.description))
            else:
                output.append(source.parse(user_payload, status))
        return output

    def set_values(self, packet, values):
        """Update data based on data contained in properties
        """
        self.logger.debug(f"Set value for properties={values} to {self.profile_data}")

        for shortcut, value in values.items():
            target = self.profile_data.get(shortcut)
            if isinstance(target, DataStatus):
                packet._status = target.set_value(value, packet._status)
            else:
                packet.data_payload = target.set_value(value, packet.data_payload)


class EepLibraryLoader:
    """Class that is used to load the EEP file one time and avoid to load it each time EepLibrary is called"""

    logger = logging.getLogger("enocean.protocol.eep.library")

    def __init__(self, filepath=None):
        try:
            # TODO manage to check validity of the file
            eep_path = filepath or Path(__file__).parent.joinpath("EEP.xml")
            self.logger.info(f"load EEP xml file: {eep_path}")
            self.profiles = self.load_xml(eep_path)
            self.logger.debug("EEP loaded")
        except Exception as e:
            self.logger.warning("Cannot load protocol file!")
            self.logger.exception(e)
            raise EEPLibraryInitError("Unable to load EEP profile")

    @staticmethod
    def load_xml(file_path):
        tree = ElementTree.parse(file_path)
        tree_root = tree.getroot()
        # TODO: Use map() here
        return {
            from_hex_string(telegram.attrib["rorg"]): {
                from_hex_string(function.attrib["func"]): {
                    from_hex_string(profile.attrib["type"]): Profile(
                        profile,
                        rorg=from_hex_string(telegram.attrib["rorg"]),
                        func=from_hex_string(function.attrib["func"]),
                    )
                    for profile in function.findall("profile")
                }
                for function in telegram.findall("profiles")
            }
            for telegram in tree_root.findall("telegram")
        }


class EepLibrary:
    logger = logging.getLogger("enocean.protocol.eep")

    profiles = EepLibraryLoader().profiles

    @classmethod
    def get_eep(cls, eep_rorg, rorg_func, rorg_type):
        try:
            return cls.profiles[eep_rorg][rorg_func][rorg_type]
        except KeyError:
            cls.logger.warning(
                f"Cannot find rorg {eep_rorg:X} func {rorg_func:X} type {rorg_type:X} in EEP"
            )
            raise NotImplementedError(
                f"EEP {eep_rorg} func {rorg_func} type {rorg_type} is not supported"
            )
        except Exception as e:
            cls.logger.exception(e)

    @classmethod
    def load_library(cls):
        cls.profiles = EepLibraryLoader().profiles
