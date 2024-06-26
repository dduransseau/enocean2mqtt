# -*- encoding: utf-8 -*-
import logging
import time

import threading
import queue
from enocean.protocol.packet import Packet, UTETeachInPacket, ResponsePacket
from enocean.protocol.constants import (
    PacketType,
    ParseResult,
    CommandCode,
    RESPONSE_FREQUENCY_FREQUENCY,
    RESPONSE_FREQUENCY_PROTOCOL,
    RESPONSE_REPEATER_MODE,
    RESPONSE_REPEATER_LEVEL,
)
from enocean.protocol import crc8


class BaseController(threading.Thread):
    """
    Communicator base-class for EnOcean.
    Not to be used directly, only serves as base class for SerialCommunicator etc.
    """

    logger = logging.getLogger("enocean.controller.BaseController")

    def __init__(self, callback=None, teach_in=True, timestamp=True):
        super(BaseController, self).__init__()
        # Create an event to stop the thread
        self._stop_flag = threading.Event()
        # Input buffer
        self._buffer = bytearray()
        # Index of next Sync Byte that define next packet limit
        self.next_sync_byte = 1
        # Setup packet queues
        self.transmit = queue.Queue()
        self.receive = queue.Queue()
        self.command_queue = list()
        # Set the callback method
        self.__callback = callback
        # Internal variable for the Base ID of the module.
        self._base_id = None
        # Should new messages be learned automatically? Defaults to True.
        # TODO: Not sure if we should use CO_WR_LEARNMODE??
        self.teach_in = teach_in
        self.frame_timestamp = timestamp
        self.app_version = None
        self.api_version = None
        self._chip_id = None
        self._chip_version = None
        self.app_description = None
        self.crc_errors = 0

    def _get_from_send_queue(self):
        """Get message from send queue, if one exists"""
        try:
            packet = self.transmit.get(block=False)
            # self.logger.debug(packet)
            self.logger.debug("Sending: %s", packet)
            return packet
        except queue.Empty:
            pass
        return None

    def send(self, packet):
        # TODO: Evaluate this and raise Exception if relevant
        if not isinstance(packet, Packet):
            self.logger.error("Object to send must be an instance of Packet")
            return False
        self.transmit.put(packet)
        return True

    def stop(self):
        self._stop_flag.set()

    def parse(self):
        """Parses messages and puts them to receive queue"""
        # Loop while we get new messages
        while True:
            try:
                # Look for next frame Sync Byte
                sync_byte_index = self._buffer.index(b"\x55", self.next_sync_byte)
                header = self._buffer[1:5]
                crc = self._buffer[5]
                # self.logger.warning(f"Check crc value for frame header for header={header} and crc={crc}")
                if crc8.calc(header) == crc:
                    # Start of an ESP3 packet, get frame
                    # self.logger.warning("Header crc is valid !")
                    data_len = int.from_bytes(self._buffer[1:3])
                    opt_len = self._buffer[3]
                    packet_type = self._buffer[3]
                    # Calculate packet header(4)+crc (2*1) = 7
                    packet_len = 7 + data_len + opt_len
                    self.logger.debug(
                        f"Packet {packet_type} with data len {data_len} and optionnal len {opt_len}"
                    )
                    if packet_len > len(self._buffer):
                        self.next_sync_byte = self.next_sync_byte + packet_len + 1
                        self.logger.debug(
                            f"Packet len {packet_len} is upper then buffer size={len(self._buffer)} "
                            f"frame incomplete set sync byte after {self.next_sync_byte} "
                            f"actual sync byte index={sync_byte_index}"
                        )
                        return ParseResult.INCOMPLETE
                    frame = self._buffer[0:packet_len]
                    self.next_sync_byte = 1
                    self._buffer = self._buffer[packet_len:]
                    # self._frame_separator_index = 1
                else:
                    self.logger.warning(
                        "Header CRC8 invalid, waiting for next Sync Byte"
                    )
                    self.crc_errors += 1
                    self._buffer = self._buffer[sync_byte_index:]
                    return ParseResult.INCOMPLETE
            except (ValueError, IndexError):
                return ParseResult.INCOMPLETE

            status, packet = Packet.parse_frame(frame)
            # If message is incomplete -> break the loop
            if status == ParseResult.INCOMPLETE:
                self.logger.warning("Frame parsed packet is incomplete")
                return status
            # If message is OK, add it to receive queue or send to the callback method
            elif status == ParseResult.OK and packet:
                if self.frame_timestamp:
                    packet.received = time.time()
                if isinstance(packet, UTETeachInPacket) and self.teach_in:
                    response_packet = packet.create_response_packet(self.base_id)
                    self.logger.info("Sending response to UTE teach-in.")
                    self.send(response_packet)
                elif isinstance(packet, ResponsePacket) and len(self.command_queue) > 0:
                    self.parse_common_command_response(packet)
                    continue  # Bypass packet emit to avoid to log internal command
                if self.__callback is None:
                    # Add received packet into receive queue
                    self.receive.put(packet)
                else:
                    self.__callback(packet)
                # self.logger.debug(packet)
            elif status == ParseResult.CRC_MISMATCH:
                self.crc_errors += 1
                self.logger.info(
                    f"Error to parse packet, remaining buffer {self._buffer}"
                )
                return status

    @property
    def base_id(self):
        """Fetches Base ID from the transmitter, if required. Otherwise returns the currently set Base ID."""
        # If base id is already set, return it.
        if self._base_id:
            return self._base_id

        # Send COMMON_COMMAND 0x08, CO_RD_IDBASE request to the module
        self.send(Packet(PacketType.COMMON_COMMAND, data=[CommandCode.CO_RD_IDBASE]))
        self.command_queue.append(CommandCode.CO_RD_IDBASE)
        # Loop over 5 times, to make sure we catch the response.
        # Thanks to timeout, shouldn't take more than a second.
        # Unfortunately, all other messages received during this time are ignored.
        for i in range(0, 5):
            if self._base_id:
                return self._base_id
            time.sleep(0.1)
        return self._base_id

    @property
    def controller_info_details(self):
        if self._chip_id:
            return dict(
                app_version=self.app_version,
                api_version=self.api_version,
                app_description=self.app_description,
                id=hex(self._chip_id)[2:].upper(),
            )
        # Send COMMON_COMMAND 0x03, CO_RD_VERSION request to the module
        self.send(Packet(PacketType.COMMON_COMMAND, data=[CommandCode.CO_RD_VERSION]))
        self.command_queue.append(CommandCode.CO_RD_VERSION)
        # Loop over 5 times, to make sure we catch the response.
        # Thanks to timeout, shouldn't take more than a second.
        # Unfortunately, all other messages received during this time are ignored.
        for i in range(0, 5):
            if self._chip_id:
                return dict(
                    app_version=self.app_version,
                    api_version=self.api_version,
                    app_description=self.app_description,
                    id=hex(self._chip_id)[2:].upper(),
                )
            time.sleep(0.1)
        return True

    @base_id.setter
    def base_id(self, base_id):
        """Sets the Base ID manually, only for testing purposes."""
        self._base_id = base_id

    def init_adapter(self):
        for code in (
            CommandCode.CO_RD_IDBASE,
            CommandCode.CO_RD_VERSION,
            CommandCode.CO_GET_FREQUENCY_INFO,
            CommandCode.CO_WR_BIST,
        ):
            self.send(Packet(PacketType.COMMON_COMMAND, data=[code]))
            self.command_queue.append(code)
            time.sleep(0.1)
        # for i in range(10):
        #     if self._base_id and self._chip_id:
        #         return True
        #     time.sleep(0.1)
        # raise TimeoutError("Unable get adapter information in time")

    def parse_common_command_response(self, packet):
        command_id = self.command_queue.pop(0)
        # self.logger.info(f"Get packet response for command {command_id} with data {packet.response_data}")
        if command_id == CommandCode.CO_RD_VERSION:
            self.app_version = ".".join([str(b) for b in packet.response_data[0:4]])
            self.api_version = ".".join([str(b) for b in packet.response_data[4:8]])
            self._chip_id = int.from_bytes(packet.response_data[8:12])
            self._chip_version = int.from_bytes(packet.response_data[12:16])
            self.app_description = "".join(
                [chr(c) for c in packet.response_data[16:] if c]
            )
            self.logger.debug(
                f"Device info: app_version={self.app_version} api_version={self.api_version} chip_id={self._chip_id} chip_version={self._chip_version}"
            )
        elif command_id == CommandCode.CO_RD_IDBASE:
            # Base ID is set in the response data.
            self._base_id = packet.response_data
            self.logger.debug(f"Setup base ID as {self._base_id}")
        elif command_id == CommandCode.CO_GET_FREQUENCY_INFO:
            frequency = RESPONSE_FREQUENCY_FREQUENCY[packet.response_data[0]]
            protocol = RESPONSE_FREQUENCY_PROTOCOL[packet.response_data[1]]
            self.logger.info(
                f"Device info: work on frequency {frequency} with protocol {protocol}"
            )
        elif command_id == CommandCode.CO_RD_REPEATER:
            repeater_mode = RESPONSE_REPEATER_MODE[packet.response_data[0]]
            repeater_level = RESPONSE_REPEATER_LEVEL[packet.response_data[1]]
            self.logger.info(
                f"Device info: repeater mode={repeater_mode} repeater level={repeater_level}"
            )
        else:
            self.logger.debug(
                f"Receive command response for command id {command_id} with content {packet.response_data}"
            )
