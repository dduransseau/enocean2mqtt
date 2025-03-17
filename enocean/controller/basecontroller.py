# -*- encoding: utf-8 -*-
import logging
import time

import threading
import queue
from enocean.protocol.packet import (
    Packet,
    FrameIncompleteError,
    CrcMismatchError,
)
from enocean.protocol.constants import (
    PacketType,
    RORG,
    CommandCode,
    Direction,
    RESPONSE_FREQUENCY_FREQUENCY,
    RESPONSE_FREQUENCY_PROTOCOL,
    RESPONSE_REPEATER_MODE,
    RESPONSE_REPEATER_LEVEL,
)
from enocean.protocol import crc8
from enocean.utils import to_hex_string


class BaseController(threading.Thread):
    """
    Communicator base-class for EnOcean.
    Not to be used directly, only serves as base class for SerialCommunicator etc.
    """

    logger = logging.getLogger("enocean.controller")

    def __init__(self, teach_in=True, set_timestamp=False):
        super().__init__()
        # Create an event to stop the thread
        self._stop_flag = threading.Event()
        # Input buffer
        self._buffer = bytearray()
        # Index of next Sync Byte that define next packet limit
        self.next_sync_byte = 1  # TODO: Probably at least 6 to pass header sequence
        # Setup packet queues
        self.transmit = queue.Queue()
        self.receive = queue.Queue()
        self.command_queue = list()
        self.learned_equipment = set()
        # Internal variable for the Base ID of the module.
        self._base_id = None
        # Should new messages be learned automatically? Defaults to True.
        # TODO: Not sure if we should use CO_WR_LEARNMODE??
        self.teach_in = teach_in
        self.set_timestamp = set_timestamp
        self.app_version = None
        self.api_version = None
        self.chip_id = None
        self._chip_version = None
        self.app_description = None
        self.repeater_mode = None
        self.repeater_level = None
        self.protocol = None
        self.frequency = None
        self.crc_errors = 0
        self._wait_time = 0.01

    @property
    def address(self):
        """Referring to EnOcean documentation (EURID-v1.2.pdf)
        EURID should be use as address, base id can be used for dev purpose"""
        # return self.base_id
        return self.chip_id

    def send(self, packet):
        # TODO: Evaluate this and raise Exception if relevant
        if not isinstance(packet, Packet):
            self.logger.error(f"Object to send must be an instance of Packet, received {type(packet)}")
            raise ValueError("Object to send must be an instance of Packet")
        self.transmit.put(packet)
        return True

    def send_common_command(self, code):
        self.send(Packet(PacketType.COMMON_COMMAND, data=[code]))
        self.command_queue.append(code)

    def stop(self):
        self._stop_flag.set()

    def read(self):
        """Parses messages and puts them to receive queue"""
        # Loop while we get new messages
        # while True:
        try:
            # Look for next frame Sync Byte
            sync_byte_index = self._buffer.find(b"\x55", self.next_sync_byte)
            header = self._buffer[1:5]
            received_crc_byte = self._buffer[5]
            # self.logger.warning(f"Check crc value for frame header for header={header} and crc={crc}")
            if crc8.calc(header) == received_crc_byte:
                # Start of an ESP3 packet, get frame
                # self.logger.warning("Header crc is valid !")
                data_len = int.from_bytes(self._buffer[1:3])
                opt_len = self._buffer[3]
                # Calculate packet header(4)+crc (2*1) = 7
                packet_len = 7 + data_len + opt_len
                # self.logger.debug(
                #     f"Packet {packet_type:0x} with data len {data_len} and optional len {opt_len} buffer len {len(self._buffer)}"
                # )
                if packet_len > len(self._buffer):
                    self.next_sync_byte = self.next_sync_byte + packet_len
                    # self.logger.debug(
                    #     f"Packet len {packet_len} is upper then buffer size={len(self._buffer)} "
                    #     f"frame incomplete set sync byte after {self.next_sync_byte} "
                    #     f"actual sync byte index={sync_byte_index}"
                    # )
                    raise FrameIncompleteError
                frame = self._buffer[0:packet_len]
                self.next_sync_byte = 1
                self._buffer = self._buffer[packet_len:]
                # self._frame_separator_index = 1
            else:
                self.logger.warning("Header CRC8 invalid, waiting for next Sync Byte")
                # Discard data
                self._buffer = self._buffer[sync_byte_index:]
                raise CrcMismatchError
            packet = Packet.parse_frame(frame)
            # TODO: Check if this shouldn't happened after filter check
            if self.set_timestamp:
                packet.timestamp = time.time()
            if packet.packet_type == PacketType.RADIO_ERP1:
                # Define direction of packed base on address
                self.logger.debug(
                    f"Compare sender address to gateway to check direction {bytes(packet.sender)} {bytes(packet.destination)}"
                )
                if packet.sender == self.address:
                    self.logger.debug("Identified TO packet")
                    direction = Direction.TO
                else:
                    self.logger.debug("Identified FROM packet")
                    direction = Direction.FROM
                packet.direction = direction
                # Check if the packet is UTE Teach-in to send response back if learn enable
                if packet.rorg == RORG.UTE:
                    if self.teach_in:
                        # Check if destination address is not controller address, might append when repeater installed
                        # If not detected it might cause loop by submitting request to itself
                        if self.address != packet.destination:
                            response_packet = packet.create_response_packet(self.address)
                            self.logger.info("Sending response to UTE teach-in.")
                            self.send(response_packet)
                        else:
                            self.logger.info(
                                "Received UTE teach-in packet from itself, probably caused by repeater, omit request"
                            )
                    else:
                        self.logger.debug(
                            "Received UTE teach-in packet, but teach_in is disabled."
                        )
                # TODO: Check if already known
                # self.learned_equipment.add(Equipment(combine_hex(packet.sender), rorg=packet.equipment_eep_rorg,
                #                                      variant=packet.equipment_eep_type, func=packet.equipment_eep_func))
                # Add received packet into receive queue
                self.receive.put(packet)
            elif packet.packet_type == PacketType.RESPONSE and self.command_queue:
                self.parse_common_command_response(packet)
            elif packet.packet_type == PacketType.EVENT:
                self.logger.warning(packet)
        except (ValueError, IndexError):
            raise FrameIncompleteError
        except CrcMismatchError:
            self.crc_errors += 1
            self.logger.info(f"Error to parse packet, remaining buffer {self._buffer}")

    @property
    def base_id(self):
        """Fetches Base ID from the transmitter, if required. Otherwise returns the currently set Base ID."""
        # If base id is already set, return it.
        if self._base_id:
            return self._base_id

        # Send COMMON_COMMAND 0x08, CO_RD_IDBASE request to the module
        self.send_common_command(CommandCode.CO_RD_IDBASE)
        # Loop over 5 times, to make sure we catch the response.
        while not self._base_id:
            time.sleep(self._wait_time * 5)
        return self._base_id

    @property
    def __controller_info(self):
        return dict(
            id=to_hex_string(self.chip_id),
            frequency= self.frequency,
            protocol = self.protocol,
            app_version=self.app_version,
            api_version=self.api_version,
            app_description=self.app_description,
        )

    @property
    def controller_info_details(self):
        if self.chip_id and self.frequency:
            return self.__controller_info
        # Send COMMON_COMMAND 0x03, CO_RD_VERSION request to the module
        self.send_common_command(CommandCode.CO_RD_VERSION)
        while not self.chip_id:
            time.sleep(self._wait_time * 5)
        self.send_common_command(CommandCode.CO_GET_FREQUENCY_INFO)
        while not self.frequency:
            time.sleep(self._wait_time * 5)
        return self.__controller_info

    @base_id.setter
    def base_id(self, base_id):
        """Sets the Base ID manually, only for testing purposes."""
        self._base_id = base_id

    def init_adapter(self):
        for code in (
            CommandCode.CO_RD_VERSION,
            CommandCode.CO_GET_FREQUENCY_INFO,
            CommandCode.CO_RD_IDBASE,
            CommandCode.CO_GET_NOISETHRESHOLD,
            CommandCode.CO_RD_REPEATER,
        ):
            self.send_common_command(code)
            # time.sleep(self._wait_time)
        # self.logger.info(f"Controller info: base id {to_hex_string(self.base_id)}")
        # self.logger.info(f"Controller info: {self.controller_info_details}")

    def parse_common_command_response(self, packet):
        command_id = self.command_queue.pop(0)
        # self.logger.info(f"Get packet response for command {command_id} with data {packet.response_data}")
        if command_id == CommandCode.CO_RD_VERSION:
            self.app_version = ".".join([str(b) for b in packet.response_data[0:4]])
            self.api_version = ".".join([str(b) for b in packet.response_data[4:8]])
            self.chip_id = packet.response_data[8:12]
            self._chip_version = ".".join([str(b) for b in packet.response_data[12:16]])
            self.app_description = "".join(
                [chr(c) for c in packet.response_data[16:] if c]
            )
            self.logger.debug(
                f"Device info: app_version={self.app_version} api_version={self.api_version} "
                f"chip_id={to_hex_string(self.chip_id)} chip_version={self._chip_version}"
            )
        elif command_id == CommandCode.CO_RD_IDBASE:
            # Base ID is set in the response data.
            self._base_id = packet.response_data
            self.logger.debug(
                f"Setup base ID as {to_hex_string(self._base_id)} remaining write {int(packet.optional[0])}"
            )
        elif command_id == CommandCode.CO_GET_FREQUENCY_INFO:
            self.frequency = RESPONSE_FREQUENCY_FREQUENCY[packet.response_data[0]]
            self.protocol = RESPONSE_FREQUENCY_PROTOCOL[packet.response_data[1]]
            self.logger.info(
                f"Controller info: work on frequency {self.frequency} with protocol {self.protocol}"
            )
        elif command_id == CommandCode.CO_RD_REPEATER:
            self.repeater_mode = RESPONSE_REPEATER_MODE[packet.response_data[0]]
            self.repeater_level = RESPONSE_REPEATER_LEVEL[packet.response_data[1]]
            self.logger.info(
                f"Controller info: repeater mode={self.repeater_mode} repeater level={self.repeater_level}"
            )
        elif command_id == CommandCode.CO_GET_NOISETHRESHOLD:
            noise_threshold = int.from_bytes(packet.response_data[0:4])
            self.logger.info(f"Controller info: noise threshold={noise_threshold}")
        elif command_id == CommandCode.CO_RD_SYS_LOG:
            self.logger.warning(
                f"Controller log: {packet.response_data}\nOptional data: {packet.optional}"
            )
        else:
            self.logger.debug(
                f"Receive command response for command id {command_id} with content {packet.response_data}"
            )
