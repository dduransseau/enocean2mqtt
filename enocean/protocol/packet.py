# -*- encoding: utf-8 -*-
import logging

from enocean.utils import (
    combine_hex,
    to_hex_string,
    to_bitarray,
    from_bitarray,
    address_to_bytes_list,
    read_bits_from_byte
)
from enocean.protocol import crc8
from enocean.protocol.constants import (
    PacketType,
    ReturnCode,
    EventCode,
    UteTeachInQueryRequestType,
    UteTeachInResponseRequestType,
    RORG,
    DB0,
    DB2,
    DB3,
    DB4,
    DB6,
    MANUFACTURER_CODE
)


class FrameParserError(Exception):
    """ Base error class for parser exception"""


class FrameIncompleteError(FrameParserError):
    """ Frame is not complete """


class CrcMismatchError(FrameParserError):
    """ Frame is corrupted, CRC mismatch"""


class Packet:
    """
    Base class for ESP Packet.
    """
    SYNC_BYTE = 0x55

    logger = logging.getLogger("enocean.protocol.packet")

    def __init__(self, packet_type, data=None, optional=None):
        self.packet_type = packet_type

        self.received = None
        self.data = data or []
        self.optional = optional or []

    def __str__(self):
        return f"{PacketType(self.packet_type).name} {[hex(o) for o in self.data]} {[hex(o) for o in self.optional]}"

    @property
    def _bit_data(self):
        # First and last 5 bits are always defined, so the data we're modifying is between them...
        # TODO: This is valid for the packets we're currently manipulating.
        # Needs the redefinition of Packet.data -> Packet.message.
        # Packet.data would then only have the actual, documented data-bytes.
        # Packet.message would contain the whole message.
        # See discussion in issue #14
        return to_bitarray(self.data[1 : len(self.data) - 5], (len(self.data) - 6) * 8)

    @_bit_data.setter
    def _bit_data(self, value):
        # The same as getting the data, first and last 5 bits are ommitted, as they are defined...)
        for byte in range(len(self.data) - 6):
            self.data[byte + 1] = from_bitarray(value[byte * 8 : (byte + 1) * 8])

    # # COMMENTED OUT, AS NOTHING TOUCHES _bit_optional FOR NOW.
    # # Thus, this is also untested.
    # @property
    # def _bit_optional(self):
    #     return to_bitarray(self.optional, 8 * len(self.optional))

    # @_bit_optional.setter
    # def _bit_optional(self, value):
    #     if self.rorg in [RORG.RPS, RORG.BS1]:
    #         self.data[1] = from_bitarray(value)
    #     if self.rorg == RORG.BS4:
    #         for byte in range(4):
    #             self.data[byte+1] =from_bitarray(value[byte*8:(byte+1)*8])

    @staticmethod
    def parse_frame(frame):
        """
        Parses packet from frame.
        returns:
            - Packet -object (if message was valid, else None)
        """
        try:
            data_len = (frame[1] << 8) | frame[2]
            # opt_len = frame[3] # Optional len, not use for now
            packet_type = frame[4]
            # Calculate packet header+crc =7
            # packet_len = 7 + data_len + opt_len
            # if len(frame) < packet_len:
            #     Packet.logger.warning(f"Received frame is incomplete packet len should be {packet_len}, frame len is {len(frame)}")
            #     return ParseResult.INCOMPLETE, None

            DATA_START = 6
            DATA_END = DATA_START + data_len  # header + checksum + data
            # Header: 6 bytes, data, optional data and data checksum
            data = frame[DATA_START:DATA_END]
            opt_data = frame[DATA_END:-1]
            # Header checksum has been checked into controller
            if frame[-1] != crc8.calc(frame[DATA_START:-1]):
                Packet.logger.warning(f"Data CRC error! {frame}")
                raise CrcMismatchError(f"Data CRC error on {frame}")
        except IndexError:
            Packet.logger.warning(
                "Packet incomplete, Index error"
            )  # check if it can be moved into controller
            # If the fields don't exist, message is incomplete
            raise FrameIncompleteError()
        if packet_type == PacketType.RADIO_ERP1:
            # Need to handle UTE Teach-in here, as it's a separate packet type...
            if data[0] == RORG.UTE:
                Packet.logger.warning(f"Received UTE packet data={data} opt={opt_data}")
                packet = UTETeachInPacket(data, opt_data)
            else:
                packet = RadioPacket(data, opt_data)
        elif packet_type == PacketType.RESPONSE:
            packet = ResponsePacket(data, opt_data)
        elif packet_type == PacketType.EVENT:
            packet = EventPacket(data, opt_data)
        else:
            Packet.logger.warning(f"Received unsupported packet type: {packet_type}")
            packet = Packet(packet_type, data, opt_data)
        # Packet.logger.debug(f"Parsed packet {packet}")
        packet.parse()
        return packet

    @staticmethod
    def validate_address(address):
        if isinstance(address, list) and len(address) == 4:
            if all(0 <= i <= 255 for i in address):
                return True
        return False

    def parse(self):
        """ Parse generic values and flag """
        self.logger.debug(f"Parsed packet {self}")

    def build(self):
        """Build Packet for sending to EnOcean controller"""
        data_length = len(self.data)
        ords = [
            self.SYNC_BYTE,
            (data_length >> 8) & 0xFF,
            data_length & 0xFF,
            len(self.optional),
            int(self.packet_type),
        ]
        ords.append(crc8.calc(ords[1:5]))
        ords.extend(self.data)
        ords.extend(self.optional)
        ords.append(crc8.calc(ords[6:]))
        return ords


class RadioPacket(Packet):

    DEFAULT_ADDRESS = [0xFF, 0xFF, 0xFF, 0xFF]
    DEFAULT_RSSI = 0xFF
    DEFAULT_SECURITY_LEVEL = 0
    DEFAULT_SUB_TEL_NUM = 3
    DEFAULT_STATUS = 0



    def __init__(self, data=None, optional=None, function_group=None):
        # If no optional data is passed on init, set default value for sending
        optional_data = optional or [self.DEFAULT_SUB_TEL_NUM] + self.DEFAULT_ADDRESS + [self.DEFAULT_RSSI] + [self.DEFAULT_SECURITY_LEVEL]
        # self._status = bytes(0)
        super().__init__(PacketType.RADIO_ERP1, data=data, optional=optional_data)
        # Default to learn == True, as some devices don't have a learn button
        self.learn = True
        self.function_group = function_group

    def __str__(self):
        packet_str = super().__str__()
        return (f"{to_hex_string(self.sender)}->{to_hex_string(self.destination)} "
                f"({self.dBm} dBm): {packet_str} status={self.status}")

    @classmethod
    def create_telegram(cls,
                        equipment,
                        direction=None,
                        command=None,
                        destination=None,
                        sender=None,
                        learn=False,
                        **kwargs,
                        ):
        Packet.logger.debug(f"Create packet for equipment profile {equipment.profile}")
        if equipment.rorg not in [RORG.RPS, RORG.BS1, RORG.BS4, RORG.VLD]:  # , RORG.MSC
            raise NotImplementedError("RORG not supported by this function.")

        if destination is None:
            if equipment.address:
                destination = address_to_bytes_list(equipment.address)
            else:
                destination = cls.DEFAULT_ADDRESS
                Packet.logger.warning("Replacing destination with broadcast address.")
        else:
            Packet.validate_address(destination)

        Packet.validate_address(sender)

        data = bytearray([equipment.rorg])
        function_group = equipment.profile.get_telegram_form(command=command, direction=direction)

        # Initialize data depending on the profile.
        # set learn bit of 1BS or 4BS to 1 if not learn
        if equipment.rorg in [RORG.RPS, RORG.BS1]:
            data.extend([0 if learn else 0 | 1 << 3])
        elif equipment.rorg == RORG.BS4:
            data.extend([0, 0, 0, 0 if learn else 0 | 1 << 3])
        else:  # For VLD extend the data variable len
            # Packet.logger.debug(f"Extend the size of packet by {packet.telegram.data_length} bits")
            data.extend(bytearray(1) * function_group.data_length)
        data.extend(sender)
        data.append(0)  # Add status byte
        Packet.logger.debug(f"Data length {len(data)}")
        packet = RadioPacket(data=data, optional=[], function_group=function_group)
        packet.destination = destination
        Packet.logger.debug(f"Packet data length {len(packet.data)} after set_eep")
        packet.parse()
        return packet

    @property
    def _status(self):
        if self.data:
            return self.data[-1]
        else:
            return self.DEFAULT_STATUS

    @property
    def data_payload(self):
        try:
            return self.data[1:-5]
        except IndexError:
            return bytearray()

    @property
    def destination(self):
        try:
            return self.optional[1:5]
        except IndexError:
            return None

    @destination.setter
    def destination(self, value):
        self.optional[1:5] = value[0:4]

    @property
    def sender(self):
        try:
            return self.data[DB0.BIT_4:DB0.BIT_0]
        except IndexError:
            return None

    # @sender.setter
    # def sender(self, value):

    @property
    def rorg(self):
        try:
            return self.data[0]
        except IndexError:
            return None

    @property
    def sub_tel_num(self):
        try:
            return self.optional[0]
        except IndexError:
            return None

    @property
    def dBm(self):
        try:
            return -self.optional[5]
        except IndexError:
            return None

    def parse(self):
        """Parse data from Packet"""
        # Parse status from telegrams
        # self._status = self.data[DB0.BIT_0]
        # if self.rorg in [RORG.RPS, RORG.BS1, RORG.BS4]:
        #     # These telegram types should have repeater count in the last for bits of status.
        #     self.repeater_count = from_bitarray(self._bit_status[4:])
        # parse learn bit and FUNC/TYPE, if applicable
        if self.rorg == RORG.BS1:
            self.learn = not self._bit_data[DB0.BIT_3]
        elif self.rorg == RORG.BS4:
            self.learn = not self._bit_data[DB0.BIT_3]
            if self.learn:
                contain_eep = self._bit_data[DB0.BIT_7]
                if contain_eep:
                    # Get rorg_func and rorg_type from an unidirectional learn packet
                    func = from_bitarray(
                        self._bit_data[DB3.BIT_7 : DB3.BIT_1]
                    )
                    variant = from_bitarray(
                        self._bit_data[DB3.BIT_1 : DB2.BIT_2]
                    )
                    rorg_manufacturer = from_bitarray(
                        self._bit_data[DB2.BIT_2 : DB0.BIT_7]
                    )
                    self.logger.info(
                        f"Received BS4 learn packet from {combine_hex(self.sender)} "
                        f"manufacturer={MANUFACTURER_CODE.get(rorg_manufacturer, rorg_manufacturer)}"
                        f" EEP={self.rorg:X}-{func:X}-{variant:X}"
                    )  # noqa: E501
        elif self.rorg == RORG.VLD or self.rorg == RORG.RPS:
            self.learn = False
        elif self.rorg == RORG.SIGNAL:
            self.logger.warning(f"Received SIGNAL telegram: {self}")
        super().parse()

    ## Method to parse ERP telegram from ESP packet

    @property
    def status(self):
        return ErpStatusByte(self._status)

    @property
    def _bit_status(self):
        return to_bitarray(self._status)

    @_bit_status.setter
    def _bit_status(self, value):
        if self.data:
            self.data[-1] = from_bitarray(value)
        else:
            self.data[0] = from_bitarray(value)

    def __get_command_id(self, profile):
        """interpret packet to retrieve command id from VLD packets"""
        if profile.commands:
            # self.logger.debug(f"Get command id in packet : {self.data}")
            command_id = profile.commands.parse_raw(self._bit_data)
            return command_id if command_id else None

    def parse_telegram(self, profile, direction=1):
        """Parse EEP based on FUNC and TYPE"""
        #Get the command id based on profile
        command_id = self.__get_command_id(profile)
        telegram_form = profile.get_telegram_form(command=command_id, direction=direction)
        values = telegram_form.get_values(self._bit_data, self._bit_status)
        # self.logger.debug(f"Parsed data values {values}")
        return values

    def build_telegram(self, data):
        self.function_group.set_values(self, data)
        return Packet.parse_frame(self.build())


class UTETeachInPacket(RadioPacket):

    REQUEST_TYPE = UteTeachInQueryRequestType
    RESPONSE_TYPE = UteTeachInResponseRequestType
    # Request types
    TEACH_IN = 0b00
    DELETE = 0b01
    NOT_SPECIFIC = 0b10

    # Response types
    NOT_ACCEPTED = [False, False]
    TEACHIN_ACCEPTED = [False, True]
    DELETE_ACCEPTED = [True, False]
    EEP_NOT_SUPPORTED = [True, True]

    unidirectional = False
    response_expected = False
    number_of_channels = 0xFF
    request_type = NOT_SPECIFIC
    channel = None

    contains_eep = True

    @property
    def bidirectional(self):
        return not self.unidirectional

    @property
    def teach_in(self):
        return self.request_type != self.DELETE

    @property
    def delete(self):
        return self.request_type == self.DELETE

    @property
    def eep_label(self):
        return f"{self.eep_rorg:X}-{self.eep_func:X}-{self.eep_type:X}"

    def parse(self):
        self.unidirectional = not self._bit_data[DB6.BIT_7]
        self.response_expected = not self._bit_data[DB6.BIT_6]
        self.request_type = from_bitarray(self._bit_data[DB6.BIT_5 : DB6.BIT_3])
        self.number_of_channels = from_bitarray(self._bit_data[8 : 16])
        self.man_id = from_bitarray(
            self._bit_data[DB3.BIT_2 : DB2.BIT_7]
            + self._bit_data[DB4.BIT_7 : DB3.BIT_7]
        )  # noqa: E501
        self.channel = self.data[2]
        self.eep_rorg = self.data[7]
        self.eep_func = self.data[6]
        self.eep_type = self.data[5]
        if self.teach_in:
            self.learn = True
        super().parse()
        # self.logger.info(
        #     f"Received UTE teach in packet from {to_hex_string(self.sender)} "
        #     f"manufacturer={MANUFACTURER_CODE.get(self.man_id, self.man_id)} "
        #     f"EEP={self.eep_label}"
        # )

    def create_response_packet(self, sender_id, response=RESPONSE_TYPE.ACCEPTED_REGISTRATION):
        # Create data:
        # - Respond with same RORG (UTE Teach-in)
        # - Always use bidirectional communication, set response code, set command identifier.
        # - Databytes 5 to 0 are copied from the original message
        # - Set sender id and status
        # Docs: EnOcean-Equipment-Profiles-3-1.pdf
        self.logger.debug(f"Preparing UTE response sender={to_hex_string(sender_id)} destination={to_hex_string(self.destination)} destination={to_hex_string(self.sender)}")

        data = bytearray(13)
        data[0] = self.rorg
        data[1] = 0b10000001 | (response << 4)
        data[2:8] = self.data[2:8]
        data[8:12] = sender_id
        data[12] = 0

        response_packet = UTETeachInPacket(data=data)
        response_packet.destination = self.sender
        return response_packet


class ResponsePacket(Packet):

    def __init__(self, data=None, optional=None):
        # If no optional data is passed on init, set default value for sending
        super().__init__(PacketType.RESPONSE, data=data, optional=optional)

    @property
    def return_code(self):
        try:
            return ReturnCode(self.data[0])
        except IndexError:
            return ReturnCode(1)

    @property
    def response_data(self):
        try:
            return self.data[1:]
        except IndexError:
            return []


class EventPacket(Packet):

    def __init__(self, data=None, optional=None):
        # If no optional data is passed on init, set default value for sending
        super().__init__(PacketType.EVENT, data=data, optional=optional)

    @property
    def event_code(self):
        try:
            return EventCode(self.data[0])
        except IndexError:
            return 0

    @property
    def event_data(self):
        try:
            return self.data[1:]
        except IndexError:
            return []


class ErpStatusByte:

    def __init__(self, b):
        # print("ErpStatus passed byte:", b, type(b), bin(b))
        # print(self, read_bits_from_byte(b, 5), read_bits_from_byte(b, 4), read_bits_from_byte(b, 0, 4))
        self.hash_type = "CRC" if read_bits_from_byte(b, 7) else "Checksum"
        self.rfu = int(read_bits_from_byte(b, 6))
        self.ptm_generation = "PTM 21X" if read_bits_from_byte(b, 5) else "other"
        self.ptm_identified = read_bits_from_byte(b, 4)
        self.repeater_info = read_bits_from_byte(b, 0, 4)

    def __str__(self):
        return (f"status:hash type={self.hash_type}, rfu={self.rfu}, ptm generation={self.ptm_generation}, "
                f"ptm pressed={self.ptm_identified}, repeater={self.repeater_info}")
