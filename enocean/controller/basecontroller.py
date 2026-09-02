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
    ReturnCode,
    RESPONSE_FREQUENCY_FREQUENCY,
    RESPONSE_FREQUENCY_PROTOCOL,
    RESPONSE_REPEATER_MODE,
    RESPONSE_REPEATER_LEVEL,
)
from enocean.protocol import crc8
from enocean.utils import to_hex_string

class ControllerTimeoutError(Exception):
    """EnOcean controler does not respond to command within timeout period"""

class ControllerResponseMismatch(Exception):
    """EnOcean controler response does not match expected format"""

class BaseController(threading.Thread):
    """
    Communicator base-class for EnOcean.
    Not to be used directly, only serves as base class for SerialCommunicator etc.
    """

    logger = logging.getLogger("enocean.controller")
    COMMAND_TIMEOUT = 1.0
    SYNC_BYTE = b"\x55"

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
        self._pending_commands = {}
        self._pending_commands_lock = threading.Lock()
        self._wait_time = 0.01
        self._response_handlers = {
            CommandCode.CO_RD_VERSION: self._parse_version_response,
            CommandCode.CO_RD_IDBASE: self._parse_idbase_response,
            CommandCode.CO_GET_FREQUENCY_INFO: self._parse_frequency_response,
            CommandCode.CO_RD_REPEATER: self._parse_repeater_response,
            CommandCode.CO_GET_NOISETHRESHOLD: self._parse_noise_threshold_response,
            CommandCode.CO_RD_SYS_LOG: self._parse_syslog_response,
            CommandCode.CO_GET_STEPCODE: self._parse_stepcode_response,
            CommandCode.CO_WR_BIST: self._parse_builtin_sef_test_response,
        }

    @property
    def address(self):
        """Referring to EnOcean documentation (EURID-v1.2.pdf)
        EURID should be use as address, base id can be used for dev purpose"""
        # return self.base_id
        return self.chip_id

    def _parse_version_response(self, packet):
        response_data = packet.response_data
        if len(response_data) < 20:
            raise ControllerResponseMismatch("CO_RD_VERSION: unexpected response length")
        self.app_version = ".".join([str(b) for b in response_data[0:4]])
        self.api_version = ".".join([str(b) for b in response_data[4:8]])
        self.chip_id = response_data[8:12]
        self._chip_version = response_data[12:16]
        # self._chip_version = ".".join([str(b) for b in response_data[12:16]])
        self.app_description = "".join([chr(c) for c in response_data[16:] if c])
        self.logger.debug(
            f"Device info: app_version={self.app_version} api_version={self.api_version} "
            f"chip_id={to_hex_string(self.chip_id)} chip_version={to_hex_string(self._chip_version)}"
        )

    def _parse_idbase_response(self, packet):
        response_data = packet.response_data
        if len(response_data) < 4:
            raise ControllerResponseMismatch("CO_RD_IDBASE: unexpected response length")
        self._base_id = response_data
        self.logger.debug(
            f"Setup base ID as {to_hex_string(self._base_id)} remaining write {int(packet.optional[0])}"
        )

    def _parse_frequency_response(self, packet):
        response_data = packet.response_data
        if len(response_data) < 2:
            raise ControllerResponseMismatch("CO_GET_FREQUENCY_INFO: unexpected response length")
        try:
            frequency = RESPONSE_FREQUENCY_FREQUENCY[response_data[0]]
            protocol = RESPONSE_FREQUENCY_PROTOCOL[response_data[1]]
        except KeyError:
            raise ControllerResponseMismatch("CO_GET_FREQUENCY_INFO: unexpected value")
        self.frequency, self.protocol = frequency, protocol
        self.logger.info(
            f"Controller info: work on frequency {self.frequency} with protocol {self.protocol}"
        )

    def _parse_repeater_response(self, packet):
        response_data = packet.response_data
        if len(response_data) < 2:
            raise ControllerResponseMismatch("CO_RD_REPEATER: unexpected response length")
        try:
            mode = RESPONSE_REPEATER_MODE[response_data[0]]
            level = RESPONSE_REPEATER_LEVEL[response_data[1]]
        except KeyError:
            raise ControllerResponseMismatch("CO_RD_REPEATER: unexpected value")
        self.repeater_mode, self.repeater_level = mode, level
        self.logger.info(
            f"Controller info: repeater mode={self.repeater_mode} repeater level={self.repeater_level}"
        )

    def _parse_noise_threshold_response(self, packet):
        response_data = packet.response_data
        if len(response_data) < 4:
            raise ControllerResponseMismatch("CO_GET_NOISETHRESHOLD: unexpected response length")
        noise_threshold = int.from_bytes(response_data[0:4])
        self.logger.info(f"Controller info: noise threshold={noise_threshold}")

    def _parse_syslog_response(self, packet):
        self.logger.info(
            f"Controller log: {packet.response_data}\nOptional data: {packet.optional}"
        )

    def _parse_stepcode_response(self, packet):
        response_data = packet.response_data
        if len(response_data) < 2:
            raise ControllerResponseMismatch("CO_GET_STEPCODE: unexpected response length")
        step_code = hex(response_data[0])
        revision = hex(response_data[1])
        self.logger.info(
            f"Controller stepcode: {step_code} revision: {revision}\nOptional data: {packet.optional}"
        )

    def _parse_builtin_sef_test_response(self, packet):
        response_data = packet.response_data
        if len(response_data) < 1:
            raise ControllerResponseMismatch("CO_WR_BIST: unexpected response length")
        test_result = response_data[0]
        if test_result == 0:
            self.logger.info("Built-in self-test passed successfully.")
        else:
            self.logger.error(f"Built-in self-test failed with error code: {test_result}")

    def send(self, packet):
        if not isinstance(packet, Packet):
            self.logger.error(f"Object to send must be an instance of Packet, received {type(packet)}")
            raise ValueError("Object to send must be an instance of Packet")
        self.transmit.put(packet)
        return True

    def send_common_command(self, code, data=None, optional_data=None):
        with self._pending_commands_lock:
            self._pending_commands[code] = time.time()
        data = bytes([code]) + data if data is not None else bytes([code])
        self.send(Packet(PacketType.COMMON_COMMAND, data=data, optional=optional_data))
        self.command_queue.append(code)

    def _request_and_wait(self, code, attr_name, timeout=None):
        timeout = timeout if timeout is not None else self.COMMAND_TIMEOUT
        now = time.time()
        with self._pending_commands_lock:
            last_sent = self._pending_commands.get(code)
            already_pending = last_sent is not None and (now - last_sent) < timeout
        if not already_pending:
            self.send_common_command(code)

        deadline = now + timeout
        while getattr(self, attr_name) is None:
            if time.time() >= deadline:
                self.logger.warning(
                    f"Timeout waiting for response to command {code!r} "
                    f"(attribute {attr_name} still unset after {timeout}s)"
                )
                return False
            time.sleep(self._wait_time * 5)
        return True

    def stop(self):
        self._stop_flag.set()

    def read(self):
        """Parses messages and puts them to receive queue"""
        try:
            # Look for next frame Sync Byte
            sync_byte_index = self._buffer.find(self.SYNC_BYTE, self.next_sync_byte)
            header = self._buffer[1:5]
            received_crc_byte = self._buffer[5]
            # self.logger.warning(f"Check crc value for frame header for header={header} and crc={crc}")
            if crc8.calc(header) == received_crc_byte:
                # Start of an ESP3 packet, get frame
                data_len = int.from_bytes(self._buffer[1:3])
                opt_len = self._buffer[3]
                # Calculate packet header(4)+crc (2*1) = 7
                packet_len = 7 + data_len + opt_len
                if packet_len > len(self._buffer):
                    self.next_sync_byte = self.next_sync_byte + packet_len
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
            elif packet.packet_type == PacketType.RESPONSE:
                self.logger.debug(f"Received response packet: {packet}")
            elif packet.packet_type == PacketType.EVENT:
                self.logger.info(f"Received EVENT packet: {packet}")
            else:
                self.logger.info(f"Received packet type {packet.packet_type} {PacketType(packet.packet_type)}")
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
        if not self._request_and_wait(CommandCode.CO_RD_IDBASE, "_base_id"):
            raise ControllerTimeoutError("No response to CO_RD_IDBASE within timeout")
        return self._base_id

    @base_id.setter
    def base_id(self, base_id):
        """Sets the Base ID manually, only for testing purposes."""
        self._base_id = base_id

    @property
    def __controller_info(self):
        return dict(
            EURID=to_hex_string(self.chip_id),
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
        if not self._request_and_wait(CommandCode.CO_RD_VERSION, "chip_id"):
            self.logger.warning("Controller info incomplete: version/chip_id not received")
        if not self._request_and_wait(CommandCode.CO_GET_FREQUENCY_INFO, "frequency"):
            self.logger.warning("Controller info incomplete: frequency not received")
        return self.__controller_info

    def init_adapter(self):
        self.logger.info("Retrieving EnOcean adapter information")
        for code in (
            CommandCode.CO_RD_VERSION,
            CommandCode.CO_GET_FREQUENCY_INFO,
            # CommandCode.CO_RD_IDBASE,
            # CommandCode.CO_GET_NOISETHRESHOLD,
            # CommandCode.CO_RD_REPEATER,
            # CommandCode.CO_GET_STEPCODE,
        ):
            self.send_common_command(code)

    def enable_repeater(self, enable=True, level=1):
        """Enable or disable repeater mode on the EnOcean adapter."""
        if enable and (0 < level <= 2):
            self.logger.info(f"Enabling repeater mode with level {level}.")
            data = bytes([1, level])
        elif not enable:
            self.logger.info("Disabling repeater mode.")
            data = bytes([0, 0])
        else:
            self.logger.warning(f"Invalid repeater level {level}. Must be 1 or 2 when enabling, or 0 when disabling. Defaulting to level 1.")
            data = bytes([1, 1])
        self.send_common_command(CommandCode.CO_WR_REPEATER, data=data)
        self.logger.debug(f"Sent command to {'enable' if enable else 'disable'} repeater mode.")
        self.send_common_command(CommandCode.CO_RD_REPEATER)

    def perform_builtin_self_test(self):
        """Perform a built-in self-test on the EnOcean adapter."""
        self.logger.info("Performing built-in self-test.")
        self.send_common_command(CommandCode.CO_WR_BIST)

    def get_controller_logs(self):
        """Retrieve logs from the EnOcean controller."""
        self.logger.info("Retrieving controller logs.")
        self.send_common_command(CommandCode.CO_RD_SYS_LOG)

    def perform_controller_reset(self, parameters=False):
        """Perform a reset on the EnOcean controller."""
        self.logger.info("Performing controller reset.")
        optional_data = bytes([1]) if parameters else bytes([0])
        self.send_common_command(CommandCode.CO_WR_RESET, data=optional_data)

    def disable_repeater(self):
        """Disable repeater mode on the EnOcean adapter."""
        self.enable_repeater(enable=False)

    def parse_common_command_response(self, packet):
        for index, command_id in enumerate(self.command_queue):
            if packet.return_code == ReturnCode.NOT_SUPPORTED:
                self.logger.warning(
                    f"Received Not Supported response for command {hex(command_id)}"
                )
                del self.command_queue[: index + 1]
                return
            elif packet.return_code == ReturnCode.OK:
                handler = self._response_handlers.get(command_id)
                if handler is None:
                    self.logger.debug(f"Receive command response for command id {hex(command_id)} with content {packet.response_data}")
                    del self.command_queue[: index + 1]
                    return
                try:
                    handler(packet)
                except (ControllerResponseMismatch, IndexError, ValueError) as e:
                    self.logger.debug(f"Response does not match expected command {hex(command_id)}: {e}")
                    continue
                else:
                    if index > 0:
                        self.logger.warning(f"Resynchronized response queue, lost response for: {self.command_queue[:index]}")
                    del self.command_queue[: index + 1]
                    return
            else:
                self.logger.warning(f"Received error response for command {hex(command_id)}: {packet.return_code}")
                del self.command_queue[: index + 1]
                return
        self.logger.warning(f"Unable to match RESPONSE to any pending command in queue: {self.command_queue}")