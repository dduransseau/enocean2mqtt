# -*- encoding: utf-8 -*-
import logging

from enocean.utils import (
    combine_hex,
    to_hex_string,
    address_to_bytes_list,
    get_bits_from_byte
)
from enocean.protocol import crc8
from enocean.protocol.constants import (
    PacketType,
    ReturnCode,
    EventCode,
    UteTeachInQueryRequestType,
    UteTeachInResponseRequestType,
    RORG,
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

    def __init__(self, packet_type, data=None, optional=None, data_length=0, optional_length=0):
        self.data_length = data_length
        self.optional_length = optional_length
        self.packet_type = packet_type
        self.received = None
        self.data = data or []
        self.optional = optional or []

    def __str__(self):
        return f"{PacketType(self.packet_type).name} {[hex(o) for o in self.data]} {[hex(o) for o in self.optional]}"

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
                packet = UTETeachInPacket(data=data, optional=opt_data)
            else:
                packet = RadioPacket(data=data, optional=opt_data)
        elif packet_type == PacketType.RESPONSE:
            packet = ResponsePacket(data=data, optional=opt_data)
        elif packet_type == PacketType.EVENT:
            packet = EventPacket(data=data, optional=opt_data)
        else:
            Packet.logger.warning(f"Received unsupported packet type: {packet_type}")
            packet = Packet(packet_type, data=data, optional=opt_data)
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


    def __init__(self, optional=None, function_group=None, **kwargs):
        # If no optional data is passed on init, set default value for sending
        optional_data = optional or [self.DEFAULT_SUB_TEL_NUM] + self.DEFAULT_ADDRESS + [self.DEFAULT_RSSI] + [self.DEFAULT_SECURITY_LEVEL]
        # self._status = bytes(0)
        super().__init__(PacketType.RADIO_ERP1, optional=optional_data, **kwargs)
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
        if equipment.rorg not in [RORG.RPS, RORG.BS1, RORG.BS4, RORG.VLD, RORG.MSC]:
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

    @_status.setter
    def _status(self, b):
        self.data[-1] = b

    @property
    def data_payload(self):
        try:
            return self.data[1:-5]
        except IndexError:
            return bytearray()

    @data_payload.setter
    def data_payload(self, payload):
        self.data[1:-5] = payload

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
            return self.data[-5:-1]
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

    @property
    def status(self):
        return ErpStatusByte(self._status)

    def parse(self):
        """Parse data from Packet"""
        # parse learn bit and FUNC/TYPE, if applicable
        if self.rorg == RORG.BS1:
            self.learn = not get_bits_from_byte(self.data[1], 3)
        elif self.rorg == RORG.BS4:
            self.learn = not get_bits_from_byte(self.data[4], 3)
            if self.learn:
                contain_eep = get_bits_from_byte(self.data[4], 7)
                if contain_eep:
                    # Get rorg_func and rorg_type from an unidirectional learn packet
                    func = (self.data[1] >> 2) % 0b111111
                    variant = ((self.data[1] << 8) | self.data[2]) >> 3 & 0b1111111
                    man_id = ((self.data[2] << 8) | self.data[3]) & 0b11111111111
                    self.logger.info(
                        f"Received BS4 learn packet from {combine_hex(self.sender)} "
                        f"manufacturer={MANUFACTURER_CODE.get(man_id, man_id)}"
                        f" EEP={self.rorg:X}-{func:X}-{variant:X}"
                    )
        elif self.rorg == RORG.VLD or self.rorg == RORG.RPS:
            self.learn = False
        elif self.rorg == RORG.SIGNAL:
            self.logger.warning(f"Received SIGNAL telegram: {self}")
        super().parse()

    def __get_command_id(self, profile):
        """interpret packet to retrieve command id from VLD packets"""
        if profile.commands:
            # self.logger.debug(f"Get command id in packet : {self.data}")
            command_id = profile.commands.parse_raw(self.data[1:5])
            return command_id if command_id else None

    def parse_telegram(self, profile, direction=1):
        """Parse EEP based on FUNC and TYPE"""
        #Get the command id based on profile
        command_id = self.__get_command_id(profile)
        telegram_form = profile.get_telegram_form(command=command_id, direction=direction)
        values = telegram_form.get_values(self.data_payload, self._status)
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
        # self.unidirectional = not self._bit_data[DB6.BIT_7]
        # self.response_expected = not self._bit_data[DB6.BIT_6]
        # self.request_type = from_bitarray(self._bit_data[DB6.BIT_5 : DB6.BIT_3])
        self.unidirectional = not get_bits_from_byte(self.data[1], 7)
        self.response_expected = not get_bits_from_byte(self.data[1], 6)
        self.request_type = get_bits_from_byte(self.data[1], 4, 2)
        self.number_of_channels = self.data[2]
        # self.number_of_channels = from_bitarray(self._bit_data[8 : 16])
        # assert not self._bit_data[DB6.BIT_7] == self.unidirectional
        # assert not self._bit_data[DB6.BIT_6] == self.response_expected
        # assert from_bitarray(self._bit_data[DB6.BIT_5 : DB6.BIT_3]) == read_bits_from_byte(self.data[1], 4, 2)
        # assert from_bitarray(self._bit_data[8 : 16]) == self.number_of_channels

        # man_id = from_bitarray(
        #     self._bit_data[DB3.BIT_2 : DB2.BIT_7]
        #     + self._bit_data[DB4.BIT_7 : DB3.BIT_7]
        # )  # noqa: E501

        # Get the 11 bits on byte 3 and 4
        self.man_id = ((self.data[4] << 8) | self.data[3]) & 0b0000011111111111
        # print(self.man_id, bin(self.man_id), man_id, bin(man_id), bin(self.data[4]), bin(self.data[3]), ((self.data[4] << 8) | self.data[3]))
        # assert self.man_id == man_id

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
        self.logger.debug(f"Preparing UTE response sender={to_hex_string(sender_id)} manu={MANUFACTURER_CODE.get(self.man_id, self.man_id)} destination={to_hex_string(self.sender)}")

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

    def __init__(self, **kwargs):
        # If no optional data is passed on init, set default value for sending
        super().__init__(PacketType.RESPONSE, **kwargs)

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

    def __init__(self, **kwargs):
        # If no optional data is passed on init, set default value for sending
        super().__init__(PacketType.EVENT, **kwargs)

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
        self.value = b
        self.hash_type = "CRC" if get_bits_from_byte(b, 7) else "Checksum"
        self.rfu = int(get_bits_from_byte(b, 6))
        self.ptm_generation = "PTM 21X" if get_bits_from_byte(b, 5) else "other"
        self.ptm_identified = get_bits_from_byte(b, 4)
        self.repeated = get_bits_from_byte(b, 0, 4)

    def __str__(self):
        return (f"status:hash type={self.hash_type}, rfu={self.rfu}, ptm generation={self.ptm_generation}, "
                f"ptm pressed={self.ptm_identified}, repeater={self.repeated}")

    def __repr__(self):
        return self.value
