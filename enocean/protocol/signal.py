
from dataclasses import dataclass
from datetime import datetime

from utils import get_bits_from_bytearray, get_bits_from_byte


@dataclass
class SignalTelegramDefinition:

    mid: int
    name: str
    optional_data: bool
    fields: dict = None

    def decode(self, payload):
        if self.optional_data:
            try:
                if self.mid == 0x06:
                    energy = int(payload[1])
                    if energy == 0:
                        self.fields = dict(energy="last_message")
                    elif 0 < energy < 101:
                        self.fields = dict(energy=f"{energy}%")
                    else:
                        self.fields = dict(energy="reserved")
                elif self.mid == 0x07:
                    sw_version = ".".join([str(b) for b in payload[1:5]])
                    hw_version = ".".join([str(b) for b in payload[5:9]])
                    self.fields = dict(sw_version=sw_version, hw_version=hw_version)
                elif self.mid == 0x0a:
                    id = get_bits_from_bytearray(payload, 8, num_bits=32)
                    dbm_worst = payload[5]
                    dbm_best = payload[5]
                    subtelegram_count = get_bits_from_bytearray(payload, 56, num_bits=4)
                    max_repeater_level = get_bits_from_bytearray(payload, 60, num_bits=4)
                    self.fields = dict(id=id, dbm_worst=dbm_worst, dbm_best=dbm_best,
                                subtelegram_count=subtelegram_count, max_repeater_level=max_repeater_level)
                elif self.mid == 0x10:
                    energy = int(payload[1])
                    if 0 <= energy < 101:
                        self.fields = dict(energy=f"{energy}%")
                    elif energy == 255:
                        self.fields = dict(energy="no backup battery")
                    else:
                        self.fields = dict(energy="reserved")
                elif self.mid == 0x12:
                    product_id = get_bits_from_bytearray(payload, 8, num_bits=48)
                    self.fields = {"product-id": product_id}
                elif self.mid == 0x13:
                    year = int(payload[1]) + 2000
                    month = int(payload[2])
                    day = int(payload[3])
                    daylight = get_bits_from_byte(payload[4], 2)
                    hour = get_bits_from_bytearray(payload, 34, num_bits=6)
                    minute = int(payload[5])
                    second = int(payload[6])
                    dt = datetime(year, month, day, hour, minute, second)
                    self.fields = dict(datetime=dt, daylight_saving=daylight)
            except ValueError:
                raise ValueError("Unable to decode Signal telegram")
        return self

SignalDefinitions = {
    0x06: SignalTelegramDefinition(0x06, "Energy status of device", True),
    0x07: SignalTelegramDefinition(0x07, "Revision of device", True),
    0x08: SignalTelegramDefinition(0x08, "Heartbeat", False),
    0x0a: SignalTelegramDefinition(0x0a, "RX-channel quality", True),
    0x10: SignalTelegramDefinition(0x10, "Backup battery status", True),
    # 0x11: SignalTelegramDefinition(0x11, "Learn mode status", True),
    0x12: SignalTelegramDefinition(0x12, "Product ID", True),
    0x13: SignalTelegramDefinition(0x13, "Date and Time", True),
}