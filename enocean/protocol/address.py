
from enocean.utils import to_hex_string

class Address:

    def __init__(self, val) -> None:
        if isinstance(val, int):
            if not (0 <= val <= 0xFFFFFFFF):
                raise ValueError(
                    f"Address out of range: must be between 0x00000000 and 0xFFFFFFFF, got {val}."
                )
            self._address = val
        elif isinstance(val, (bytes, bytearray)):
            if len(val) != 4:
                raise ValueError("Address must be composed of 4 bytes")
            self._address = int.from_bytes(val, "big")
        else:
            raise ValueError("Address must be an integer or bytearray")

    @property
    def is_eurid(self):
        return 0x00000000 <= self._address <= 0xFF7FFFFF

    @property
    def is_base_address(self):
        return 0xFF800000 <= self._address <= 0xFFFFFFFE

    @property
    def is_broadcast(self):
        return self._address == 0xFFFFFFFF

    @property
    def bytearray(self):
        return self._address.to_bytes(4, "big")

    def __int__(self):
        return self._address

    def __str__(self):
        return to_hex_string(self._address)

    def __eq__(self, target):
        if not isinstance(target, Address):
            return NotImplemented
        return int(self) == int(target)


