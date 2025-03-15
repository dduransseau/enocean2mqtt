# -*- encoding: utf-8 -*-
import logging

from enocean.protocol.eep import EepLibrary
from enocean.utils import to_hex_string


class Equipment(object):
    """Representation of device/sensor as EnOcean use the term Equipment"""

    eep = EepLibrary()
    logger = logging.getLogger("enocean.protocol.equipment")

    def __init__(self, address, rorg=None, func=None, variant=None) -> None:
        self.address = address
        self.rorg = rorg
        self.func = func
        self.variant = variant
        self.profile = self.eep.get_eep(rorg, func, variant)

    @property
    def description(self):
        return self.profile.description

    @property
    def eep_code(self):
        return self.profile.code

    def __str__(self) -> str:
        return f"equipment {to_hex_string(self.address)} eep {self.eep_code}"
