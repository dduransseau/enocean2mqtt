# -*- encoding: utf-8 -*-
import logging
import time

import threading
import queue
from enocean.protocol.packet import Packet, UTETeachInPacket
from enocean.protocol.constants import PACKET, PARSE_RESULT, RETURN_CODE, COMMON_COMMAND


class BaseController(threading.Thread):
    '''
    Communicator base-class for EnOcean.
    Not to be used directly, only serves as base class for SerialCommunicator etc.
    '''
    logger = logging.getLogger('enocean.controller.BaseController')

    def __init__(self, callback=None, teach_in=True):
        super(BaseController, self).__init__()
        # Create an event to stop the thread
        self._stop_flag = threading.Event()
        # Input buffer
        self._buffer = []
        # Setup packet queues
        self.transmit = queue.Queue()
        self.receive = queue.Queue()
        # Set the callback method
        self.__callback = callback
        # Internal variable for the Base ID of the module.
        self._base_id = None
        # Should new messages be learned automatically? Defaults to True.
        # TODO: Not sure if we should use CO_WR_LEARNMODE??
        self.teach_in = teach_in
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
            if status == PARSE_RESULT.INCOMPLETE:
                return status

            # If message is OK, add it to receive queue or send to the callback method
            if status == PARSE_RESULT.OK and packet:
                packet.received = time.time()

                if isinstance(packet, UTETeachInPacket) and self.teach_in:
                    response_packet = packet.create_response_packet(self.base_id)
                    self.logger.info('Sending response to UTE teach-in.')
                    self.send(response_packet)

                if self.__callback is None:
                    self.receive.put(packet)
                else:
                    self.__callback(packet)
                self.logger.debug(packet)

    @property
    def base_id(self):
        ''' Fetches Base ID from the transmitter, if required. Otherwise returns the currently set Base ID. '''
        # If base id is already set, return it.
        if self._base_id is not None:
            return self._base_id

        # Send COMMON_COMMAND 0x08, CO_RD_IDBASE request to the module
        self.send(Packet(PACKET.COMMON_COMMAND, data=[COMMON_COMMAND.CO_RD_IDBASE]))
        # Loop over 5 times, to make sure we catch the response.
        # Thanks to timeout, shouldn't take more than a second.
        # Unfortunately, all other messages received during this time are ignored.
        for i in range(0, 5):
            try:
                packet = self.receive.get(block=True, timeout=0.1)
                # We're only interested in responses to the request in question.
                if packet.packet_type == PACKET.RESPONSE and packet.response == RETURN_CODE.OK and len(packet.response_data) == 4:  # noqa: E501
                    self.logger.debug(f"Get base info response {packet} | {packet.response_data}")
                    # Base ID is set in the response data.
                    self._base_id = packet.response_data
                    # Put packet back to the Queue, so the user can also react to it if required...
                    # self.receive.put(packet)
                    return self._base_id
                # Put other packets back to the Queue.
                self.receive.put(packet)
            except queue.Empty:
                continue
        # Return the current Base ID (might be None).
        return self._base_id

    @property
    def controller_info_details(self):
        # Send COMMON_COMMAND 0x03, CO_RD_VERSION request to the module
        self.send(Packet(PACKET.COMMON_COMMAND, data=[COMMON_COMMAND.CO_RD_VERSION]))
        # Loop over 5 times, to make sure we catch the response.
        # Thanks to timeout, shouldn't take more than a second.
        # Unfortunately, all other messages received during this time are ignored.
        for i in range(0, 5):
            try:
                packet = self.receive.get(block=True, timeout=0.1)
                # We're only interested in responses to the request in question.
                if packet.packet_type == PACKET.RESPONSE and packet.response == RETURN_CODE.OK:  # noqa: E501
                    self.logger.debug(f"Get gateway info response {packet} | {packet.response_data}")
                    self.app_version = ".".join([str(b) for b in packet.response_data[0:4]])
                    self.api_version = ".".join([str(b) for b in packet.response_data[4:8]])
                    self._chip_id = int.from_bytes(packet.response_data[8:12])
                    self._chip_version = int.from_bytes(packet.response_data[12:16])
                    self.app_description = "".join([chr(c) for c in packet.response_data[16:] if c])
                    return dict(app_version=self.app_version, api_version=self.api_version, app_description=self.app_description, id=hex(self._chip_id)[2:].upper())
                # Put other packets back to the Queue.
                self.receive.put(packet)
            except queue.Empty:
                continue
        return True

    @base_id.setter
    def base_id(self, base_id):
        ''' Sets the Base ID manually, only for testing purposes. '''
        self._base_id = base_id
