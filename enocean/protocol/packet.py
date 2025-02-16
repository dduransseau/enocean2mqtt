# -*- encoding: utf-8 -*-
import logging

from enocean.utils import (
    combine_hex,
    to_hex_string,
    to_bitarray,
    from_bitarray,
    address_to_bytes_list,
)
from enocean.protocol import crc8
from enocean.protocol.constants import (
    PacketType,
    ReturnCode,
    EventCode,
    RORG,
    DB0,
    DB2,
    DB3,
    DB4,
    DB6,
)


class FrameParserError(Exception):
    """ Base error class for parser exception"""


class FrameIncompleteError(FrameParserError):
    """ Frame is not complete """


class CrcMismatchError(FrameParserError):
    """ Frame is corrupted, CRC mismatch"""


class Packet(object):
    """
    Base class for ESP Packet.
    """

    logger = logging.getLogger("enocean.protocol.packet")

    def __init__(self, packet_type, data=None, optional=None, status=0):
        self.packet_type = packet_type
        self.rorg = RORG.UNDEFINED
        self.rorg_func = None
        self.rorg_type = None
        self.rorg_manufacturer = None

        self.received = None

        if data is None:
            self.logger.warning(
                f"Replacing Packet.data with default value, for packet type {self.packet_type}"
            )
            self.data = []
        else:
            self.data = data

        if optional is None:
            self.logger.debug(
                f"Replacing Packet.optional with default value, for packet type {self.packet_type}"
            )
            self.optional = []
        else:
            self.optional = optional

        self.status = status
        self.repeater_count = 0
        self._profile = None
        self.message = None

        # TODO: Confirm usage for mqtt to ESP
        self.parse()

    def __str__(self):
        return f"{PacketType(self.packet_type).name} {[hex(o) for o in self.data]} {[hex(o) for o in self.optional]}"

    def __eq__(self, other):
        return (
            self.packet_type == other.packet_type
            and self.rorg == other.rorg
            and self.data == other.data
            and self.optional == other.optional
        )

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

    @property
    def _bit_status(self):
        return to_bitarray(self.status)

    @_bit_status.setter
    def _bit_status(self, value):
        self.status = from_bitarray(value)

    @staticmethod
    def parse_frame(frame):
        """
        Parses packet from frame.
        returns:
            - PARSE_RESULT
            - Packet -object (if message was valid, else None)
        """
        try:
            frame = list(frame)  # Convert bytearray to list to easily manage index
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
            # print("DATA_LEN", data_len,"OPT len", opt_len, "len frame", len(frame))
            # Header: 6 bytes, data, optional data and data checksum
            data = frame[DATA_START:DATA_END]
            opt_data = frame[DATA_END:-1]
            # Header checksum has been checked into controller
            if frame[-1] != crc8.calc(frame[DATA_START:-1]):
                Packet.logger.warning(f"Data CRC error! {frame}")
                raise CrcMismatchError(f"Data CRC error on {frame}")
                # return ParseResult.CRC_MISMATCH, None
        except IndexError:
            Packet.logger.warning(
                "Packet incomplete, Index error"
            )  # check if it can be moved into controller
            # If the fields don't exist, message is incomplete
            raise FrameIncompleteError()
            # return ParseResult.INCOMPLETE, None
        if packet_type == PacketType.RADIO_ERP1:
            # Need to handle UTE Teach-in here, as it's a separate packet type...
            if data[0] == RORG.UTE:
                packet = UTETeachInPacket(packet_type, data, opt_data)
            else:
                packet = RadioPacket(packet_type, data, opt_data)
        elif packet_type == PacketType.RESPONSE:
            packet = ResponsePacket(packet_type, data, opt_data)
        elif packet_type == PacketType.EVENT:
            packet = EventPacket(packet_type, data, opt_data)
        else:
            packet = Packet(packet_type, data, opt_data)
        Packet.logger.debug(f"Successfully parsed packet {packet}")
        return packet

    @staticmethod
    def validate_address(address):
        if isinstance(address, list) and len(address) == 4:
            for i in address:
                if 0 > i > 255:
                    return False

    def parse(self):
        """ Parse generic values and flag """

    def build(self):
        """Build Packet for sending to EnOcean controller"""
        data_length = len(self.data)
        ords = [
            0x55,
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

    def build_message(self, data):
        self.message.set_values(self, data)
        return Packet.parse_frame(self.build())


class RadioPacket(Packet):
    destination = [0xFF, 0xFF, 0xFF, 0xFF]
    dBm = 0
    sender = [0xFF, 0xFF, 0xFF, 0xFF]
    learn = None

    def __str__(self):
        packet_str = super(RadioPacket, self).__str__()
        return "%s->%s (%d dBm): %s" % (
            self.sender_hex,
            self.destination_hex,
            self.dBm,
            packet_str,
        )

    @staticmethod
    def create_message(
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
                destination = [0xFF, 0xFF, 0xFF, 0xFF]
                Packet.logger.warning("Replacing destination with broadcast address.")
        else:
            Packet.validate_address(destination)

        # TODO: Should use the correct Base ID as default.
        #       Might want to change the sender to be an offset from the actual address?
        if sender is None:
            Packet.logger.warning("Replacing sender with default address.")
            sender = [0xDE, 0xAD, 0xBE, 0xEF]
        else:
            Packet.validate_address(sender)

        packet = Packet(PacketType.RADIO_ERP1, data=[], optional=[])
        packet.rorg = equipment.rorg
        packet.data = [packet.rorg]
        packet.message = equipment.profile.get_message_form(
            command=command, direction=direction
        )

        # Initialize data depending on the profile.
        if packet.rorg in [RORG.RPS, RORG.BS1]:
            packet.data.extend([0])
        elif packet.rorg == RORG.BS4:
            packet.data.extend([0, 0, 0, 0])
        else:  # For VLD extend the data variable len
            Packet.logger.debug(
                f"Extend the size of packet by {packet.message.data_length} bits"
            )
            packet.data.extend([0] * int(packet.message.data_length))
        packet.data.extend(sender)
        packet.data.extend([0])  # Add status byte
        Packet.logger.debug(f"Data length {len(packet.data)}")
        # Always use sub-telegram 3, maximum dbm (as per spec, when sending),
        # and no security (security not supported as per EnOcean Serial Protocol).
        # p18 ESP3: SubTelNum + Destination ID + dBm + Security level
        packet.optional = [3] + destination + [0xFF] + [0]

        if packet.rorg in [RORG.BS1, RORG.BS4] and not learn:
            if packet.rorg == RORG.BS1:
                packet.data[1] |= 1 << 3
            if packet.rorg == RORG.BS4:
                packet.data[4] |= 1 << 3
        packet.data[-1] = packet.status
        Packet.logger.debug(f"Packet data length {len(packet.data)} after set_eep")
        return packet

    @property
    def sender_int(self):
        return combine_hex(self.sender)

    @property
    def sender_hex(self):
        return to_hex_string(self.sender)

    @property
    def destination_int(self):
        return combine_hex(self.destination)

    @property
    def destination_hex(self):
        return to_hex_string(self.destination)

    def parse(self):
        """Parse data from Packet"""
        self.destination = self.optional[1:5]
        self.dBm = -self.optional[5]
        self.sender = self.data[DB0.BIT_4:DB0.BIT_0]
        # Default to learn == True, as some devices don't have a learn button
        self.learn = True
        self.rorg = self.data[0]
        # Parse status from messages
        # TODO: Investigate this logic
        self.status = self.data[-1]
        if self.rorg in [RORG.RPS, RORG.BS1, RORG.BS4]:
            # These message types should have repeater count in the last for bits of status.
            self.repeater_count = from_bitarray(self._bit_status[4:])
        # parse learn bit and FUNC/TYPE, if applicable
        if self.rorg == RORG.BS1:
            self.learn = not self._bit_data[DB0.BIT_3]
        elif self.rorg == RORG.BS4:
            self.learn = not self._bit_data[DB0.BIT_3]
            if self.learn:
                contain_eep = self._bit_data[DB0.BIT_7]
                if contain_eep:
                    # Get rorg_func and rorg_type from an unidirectional learn packet
                    self.rorg_func = from_bitarray(
                        self._bit_data[DB3.BIT_7 : DB3.BIT_1]
                    )
                    self.rorg_type = from_bitarray(
                        self._bit_data[DB3.BIT_1 : DB2.BIT_2]
                    )
                    self.rorg_manufacturer = from_bitarray(
                        self._bit_data[DB2.BIT_2 : DB0.BIT_7]
                    )
                    self.logger.info(
                        f"learn received, EEP detected, RORG: 0x{self.rorg:0x}, FUNC: 0x{self.rorg_func:0x}, "
                        f"TYPE: 0x{self.rorg_type:0x}, Manufacturer: 0x{self.rorg_manufacturer:0x}"
                    )  # noqa: E501
        elif self.rorg == RORG.VLD or self.rorg == RORG.RPS:
            self.learn = False

        return super(RadioPacket, self).parse()

    ## Method to parse ERP message from ESP packet

    def _get_command_id(self, profile):
        """interpret packet to retrieve command id from VLD packets"""
        if profile.commands:
            self.logger.debug(f"Get command id in packet : {self.data}")
            command_id = profile.commands.parse_raw(self._bit_data)
            return command_id if command_id else None

    def get_packet_fields(self, profile, direction):
        command_id = self._get_command_id(profile)
        return profile.get_message_form(command=command_id, direction=direction)

    def parse_erp_message(self, profile, direction=1):
        """Parse EEP based on FUNC and TYPE"""
        message_form = self.get_packet_fields(profile, direction)
        values = message_form.get_values(self._bit_data, self._bit_status)
        self.logger.debug(f"Parsed data values {values}, status={self.status}")
        return values


class UTETeachInPacket(RadioPacket):
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

    def parse(self):
        super(UTETeachInPacket, self).parse()
        self.unidirectional = not self._bit_data[DB6.BIT_7]
        self.response_expected = not self._bit_data[DB6.BIT_6]
        self.request_type = from_bitarray(self._bit_data[DB6.BIT_5 : DB6.BIT_3])
        self.rorg_manufacturer = from_bitarray(
            self._bit_data[DB3.BIT_2 : DB2.BIT_7]
            + self._bit_data[DB4.BIT_7 : DB3.BIT_7]
        )  # noqa: E501
        self.channel = self.data[2]
        self.rorg = RORG.UTE
        self.equipment_eep_rorg = self.data[7]
        self.equipment_eep_func = self.data[6]
        self.equipment_eep_type = self.data[5]
        if self.teach_in:
            self.learn = True
        self.logger.debug(
            f"Received UTE teach in packet from {self.sender} "
            f"manufacturer:{self.rorg_manufacturer} and EEP:{self.equipment_eep_label}"
        )
        # return self.parsed

    @property
    def equipment_eep_label(self):
        return f"{self.equipment_eep_rorg:0x}-{self.equipment_eep_func:0x}-{self.equipment_eep_type:0x}"

    def create_response_packet(self, sender_id, response=TEACHIN_ACCEPTED):
        # Create data:
        # - Respond with same RORG (UTE Teach-in)
        # - Always use bidirectional communication, set response code, set command identifier.
        # - Databytes 5 to 0 are copied from the original message
        # - Set sender id and status
        data = (
            [self.rorg]
            + [from_bitarray([True, False] + response + [False, False, False, True])]
            + self.data[2:8]
            + sender_id
            + [0]
        )

        # Always use 0x03 to indicate sending, attach sender ID, dBm, and security level
        optional = [0x03] + self.sender + [0xFF, 0x00]

        return RadioPacket(PacketType.RADIO_ERP1, data=data, optional=optional)


class ResponsePacket(Packet):
    # response = 0
    return_code = ReturnCode(0)
    response_data = []

    def parse(self):
        # self.response = self.data[0]
        self.return_code = ReturnCode(self.data[0])
        self.response_data = self.data[1:]
        return super(ResponsePacket, self).parse()


class EventPacket(Packet):
    event_code = None
    event_data = []

    def parse(self):
        self.event_code = EventCode(self.data[0])
        self.event_data = self.data[1:]
        return super(EventPacket, self).parse()
