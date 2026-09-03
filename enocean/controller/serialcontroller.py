# -*- encoding: utf-8 -*-
import time
import logging

import serialx

from enocean.controller.basecontroller import BaseController, FrameIncompleteError


class SerialController(BaseController):
    """Serial port communicator class for EnOcean radio"""

    logger = logging.getLogger("enocean.controller.serial")

    def __init__(self, url="/dev/ttyAMA0", baudrate=57600, timeout=0.1, **kwargs):
        super().__init__(**kwargs)
        # Initialize serial port
        self.__url = url
        self.__baudrate = baudrate
        self._timeout = timeout
        try:
            self.__ser = serialx.serial_for_url(self.__url, self.__baudrate, read_timeout=self._timeout)
        except FileNotFoundError:
            raise RuntimeError("Controller is not available")

    def run(self):
        self.logger.info(
            f"SerialController started on path {self.__ser.path} with baudrate {self.__baudrate}"
        )
        self.__ser.read_until(expected=self.SYNC_BYTE)
        while not self._stop_flag.is_set():
            try:
                # If there's messages in transmit queue send them
                while not self.transmit.empty():
                    packet = self.transmit.get(block=False)
                    self.logger.debug(f"Sending: {packet}")
                    self.__ser.write(bytearray(packet.build()))
                # Read chars from serial port as hex numbers
                pending = self.__ser.num_unread_bytes()
                data = self.__ser.read(pending if pending else 1)
                if data:
                    self._buffer.extend(data)
            except FileNotFoundError:
                self.logger.error(
                    f"Serial port not found! (device disconnected or multiple access on port {self.__ser.path} ?)"
                )
                self.stop()
                continue
            try:
                self.read()
            except FrameIncompleteError:
                pass

        self.__ser.close()
        self.logger.info("SerialController stopped")
