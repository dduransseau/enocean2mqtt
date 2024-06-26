# -*- encoding: utf-8 -*-
import logging
import serial
# import time

from enocean.controller.basecontroller import BaseController


class SerialController(BaseController):
    """Serial port communicator class for EnOcean radio"""

    logger = logging.getLogger("enocean.controller.SerialController")

    def __init__(self, port="/dev/ttyAMA0", baudrate=57600, timeout=0.1, **kwargs):
        super(SerialController, self).__init__(**kwargs)
        # Initialize serial port
        self.__port = port
        self.__baudrate = baudrate
        self.__ser = serial.Serial(port, baudrate, timeout=timeout)

    def run(self):
        self.logger.info(
            f"SerialCommunicator started on port {self.__ser.name} with baudrate {self.__ser.baudrate}"
        )
        self.__ser.read_until(b"\55")
        while not self._stop_flag.is_set():
            # If there's messages in transmit queue
            # send them
            while True:
                packet = self._get_from_send_queue()
                if not packet:
                    break
                try:
                    self.__ser.write(bytearray(packet.build()))
                except serial.SerialException:
                    self.stop()

            # Read chars from serial port as hex numbers
            try:
                self._buffer.extend(self.__ser.read(16))
            except serial.SerialException:
                self.logger.error(
                    f"Serial port exception! (device disconnected or multiple access on port {self.__port} ?)"
                )
                self.stop()
            # try:
            self.parse()
            # except Exception as e:
            #     self.logger.error(f'Exception occurred while parsing: {e}')
            # time.sleep(0) # TODO : need ?

        self.__ser.close()
        self.logger.info("SerialCommunicator stopped")
