# -*- encoding: utf-8 -*-
import time
import logging

import serial

from enocean.controller.basecontroller import BaseController, FrameIncompleteError


class SerialController(BaseController):
    """Serial port communicator class for EnOcean radio"""

    logger = logging.getLogger("enocean.controller.serial")

    def __init__(self, port="/dev/ttyAMA0", baudrate=57600, timeout=0, **kwargs):
        super().__init__(**kwargs)
        # Initialize serial port
        self.__port = port
        self.__baudrate = baudrate
        try:
            self.__ser = serial.Serial(port, baudrate, timeout=timeout)
        except serial.serialutil.SerialException:
            raise RuntimeError("Controller is not available")

    def run(self):
        self.logger.info(
            f"SerialCommunicator started on port {self.__ser.name} with baudrate {self.__ser.baudrate}"
        )
        self.__ser.read_until(b"\55")
        while not self._stop_flag.is_set():
            try:
                # If there's messages in transmit queue send them
                while not self.transmit.empty():
                    packet = self.transmit.get(block=False)
                    self.logger.debug(f"Sending: {packet}")
                    self.__ser.write(bytearray(packet.build()))
                # Read chars from serial port as hex numbers
                self._buffer.extend(self.__ser.read())
            except serial.SerialException:
                self.logger.error(
                    f"Serial port exception! (device disconnected or multiple access on port {self.__ser.name} ?)"
                )
                self.stop()
            try:
                self.read()
            except FrameIncompleteError:
                time.sleep(self._wait_time)

        self.__ser.close()
        self.logger.info("SerialCommunicator stopped")
