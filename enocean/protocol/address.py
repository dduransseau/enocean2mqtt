
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
            raise ValueError(f"Address must be an integer or bytearray, got {val}")

    @property
    def is_eurid(self):
        return 0x00000000 <= self._address <= 0xFF7FFFFF

    @property
    def is_base_address(self):
        return 0xFF800000 <= self._address <= 0xFFFFFFFE

    @property
    def is_broadcast(self):
        return self._address == 0xFFFFFFFF

    def __int__(self):
        return self._address

    def __add__(self, offset):
        if not isinstance(offset, int):
            raise ValueError("Addition offset must be an integer type")
        return Address(self._address+offset)
    
    def __hash__(self):
        return self._address

    def __str__(self):
        return to_hex_string(self._address)

    def __repr__(self):
        return str(self)

    def __bytes__(self):
        return self._address.to_bytes(4, "big")

    def __iter__(self):
        return iter(bytes(self))

    def __len__(self):
        return 4

    def __getitem__(self, index):
        return bytes(self)[index]

    def __eq__(self, target):
        if not isinstance(target, Address):
            return NotImplemented
        return int(self) == int(target)


Address.BROADCAST = Address(b'\xff\xff\xff\xff')