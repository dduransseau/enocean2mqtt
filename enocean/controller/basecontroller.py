# -*- encoding: utf-8 -*-
import logging
import time

import threading
import queue
from enocean.protocol.packet import Packet, UTETeachInPacket, ResponsePacket
from enocean.protocol.constants import PacketTyoe, ParseResult, ReturnCode, CommandCode


class BaseController(threading.Thread):
    '''
    Communicator base-class for EnOcean.
    Not to be used directly, only serves as base class for SerialCommunicator etc.
    '''
    logger = logging.getLogger('enocean.controller.BaseController')

    def __init__(self, callback=None, teach_in=True, timestamp=True):
        super(BaseController, self).__init__()
        # Create an event to stop the thread
        self._stop_flag = threading.Event()
        # Input buffer
        self._buffer = []
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

    def _get_from_send_queue(self):
        ''' Get message from send queue, if one exists '''
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
            self.logger.error('Object to send must be an instance of Packet')
            return False
        self.transmit.put(packet)
        return True

    def stop(self):
        self._stop_flag.set()

    def parse(self):
        ''' Parses messages and puts them to receive queue '''
        # Loop while we get new messages
        while True:
            status, self._buffer, packet = Packet.parse_msg(self._buffer)
            # If message is incomplete -> break the loop
            if status == ParseResult.INCOMPLETE:
                return status

            # If message is OK, add it to receive queue or send to the callback method
            if status == ParseResult.OK and packet:
                if self.frame_timestamp:
                    packet.received = time.time()

                if isinstance(packet, UTETeachInPacket) and self.teach_in:
                    response_packet = packet.create_response_packet(self.base_id)
                    self.logger.info('Sending response to UTE teach-in.')
                    self.send(response_packet)
                elif isinstance(packet, ResponsePacket) and len(self.command_queue) > 0:
                    self.parse_common_command_response(packet)
                    continue # Bypass packet emit to avoid to log internal command
                if self.__callback is None:
                    # Add received packet into receive queue
                    self.receive.put(packet)
                else:
                    self.__callback(packet)
                # self.logger.debug(packet)

    @property
    def base_id(self):
        ''' Fetches Base ID from the transmitter, if required. Otherwise returns the currently set Base ID. '''
        # If base id is already set, return it.
        if self._base_id:
            return self._base_id

        # Send COMMON_COMMAND 0x08, CO_RD_IDBASE request to the module
        self.send(Packet(PacketTyoe.COMMON_COMMAND, data=[CommandCode.CO_RD_IDBASE]))
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
            return dict(app_version=self.app_version, api_version=self.api_version,
                        app_description=self.app_description, id=hex(self._chip_id)[2:].upper())
        # Send COMMON_COMMAND 0x03, CO_RD_VERSION request to the module
        self.send(Packet(PacketTyoe.COMMON_COMMAND, data=[CommandCode.CO_RD_VERSION]))
        self.command_queue.append(CommandCode.CO_RD_VERSION)
        # Loop over 5 times, to make sure we catch the response.
        # Thanks to timeout, shouldn't take more than a second.
        # Unfortunately, all other messages received during this time are ignored.
        for i in range(0, 5):
            if self._chip_id:
                return dict(app_version=self.app_version, api_version=self.api_version,
                            app_description=self.app_description, id=hex(self._chip_id)[2:].upper())
            time.sleep(0.1)
        return True

    @base_id.setter
    def base_id(self, base_id):
        ''' Sets the Base ID manually, only for testing purposes. '''
        self._base_id = base_id

    def init_adapter(self):
        for code in (CommandCode.CO_RD_IDBASE, CommandCode.CO_RD_VERSION):
            self.send(Packet(PacketTyoe.COMMON_COMMAND, data=[code]))
            self.command_queue.append(code)
        for i in range(10):
            if self._base_id and self._chip_id:
                return True
            time.sleep(0.1)
        raise TimeoutError("Unable get adapter information in time")

    def parse_common_command_response(self, packet):
        command_id = self.command_queue.pop(0)
        self.logger.info(f"Get packet response for command {command_id}")
        if command_id == CommandCode.CO_RD_VERSION:
            self.app_version = ".".join([str(b) for b in packet.response_data[0:4]])
            self.api_version = ".".join([str(b) for b in packet.response_data[4:8]])
            self._chip_id = int.from_bytes(packet.response_data[8:12])
            self._chip_version = int.from_bytes(packet.response_data[12:16])
            self.app_description = "".join([chr(c) for c in packet.response_data[16:] if c])
        elif command_id == CommandCode.CO_RD_IDBASE:
            # Base ID is set in the response data.
            self._base_id = packet.response_data