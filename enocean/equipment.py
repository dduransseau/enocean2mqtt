# -*- encoding: utf-8 -*-
import logging

from enocean.protocol.eep import EepLibrary


class Equipment(object):
    """Representation of device/sensor as EnOcean use the term Equipement"""

    eep = EepLibrary()
    logger = logging.getLogger("enocean.protocol.equipment")

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
        return self.profile.code

    def __str__(self) -> str:
        if self.name:
            return f"equipment {self.address} name {self.name} eep {self.eep_code}"
        return f"equipment {self.address} eep {self.eep_code}"

    def get_command_id(self, packet):
        """interpret packet to retrieve command id from VLD packets"""
        if self.profile.commands:
            self.logger.debug(
                f"Get command id in packet : {packet.data} {packet._bit_data}"
            )
            command_id = self.profile.commands.parse_raw(packet._bit_data)
            return command_id if command_id else None

    def get_message_form(self, **kwargs):
        return self.profile.get_message_form(**kwargs)

    def get_packet_fields(self, packet, direction=1):
        command_id = self.get_command_id(packet)
        return self.profile.get_message_form(command=command_id, direction=direction)
