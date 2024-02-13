# -*- encoding: utf-8 -*-
import logging

# Quick fix to avoid to read eep file twice
# from enocean.protocol.packet import Packet
from enocean.protocol.eep import EEP


class Equipment(object):
    ''' Representation of device/sensor as EnOcean use the term Equipement '''
    eep = EEP()
    # eep = Packet.eep
    logger = logging.getLogger('enocean.protocol.packet')

    def __init__(self, address, rorg=None, func=None, type_=None, name=None) -> None:
        self.address = address
        self.rorg = rorg
        self.func = func
        self.type = type_
        self.name = name
        self.profile = self.eep.get_eep(rorg, func, type_)

    @property
    def description(self):
        return self.profile.description

    @property
    def eep_code(self):
        return f"{hex(self.rorg)[2:].zfill(2)}-{hex(self.func)[2:].zfill(2)}-{hex(self.type)[2:].zfill(2)}".upper()

    def __str__(self) -> str:
        if self.name:
            return f"Device {self.name} address {self.address} eep {self.eep_code}"
        return f"Device {self.address} eep {self.eep_code}"

    def get_command_id(self, packet):
        '''interpret packet to retrieve command id from VLD packets'''
        if self.profile.commands:
            self.logger.debug(f"Get command id in packet : {packet.data} {packet._bit_data}")
            command_id = self.profile.commands.parse_raw(packet._bit_data)
            if command_id:
                return command_id

    def get_message_form(self, **kwargs):
        return self.profile.get_message_form(**kwargs)
