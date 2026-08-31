'''
DOCS at https://www.enocean.com/wp-content/uploads/downloads-produkte/en/products/enocean_modules/stm-550-multisensor-module/STM-550x-DB-DC-User-Manual-2.pdf
'''


from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from enocean.utils import get_bits_from_bytearray, to_hex_string

_TEACH_RESULT_LABELS = {
    0x0: "Tech-In of Device-ID successful",
    0x1: "Tech-In of Device-ID failed, Device-EEP not supported",
    0x2: "Tech-In of Device-ID failed, Number of devices of Device-EEP exceeded",
    0x3: "Tech-In of Device-ID failed, Number of devices exceeded",
    0x4: "Tech-Out of Device-ID successful",
    0x5: "Tech-Out of Device-ID failed, Device-ID unknown",
    0xf: "Not applicable",
}

_LEARN_MODE_TYPE_LABELS = {
    0: "Standard Learn Mode",
    1: "Extended Learn Mode #1",
    2: "Extended Learn Mode #2",
    3: "Not applicable",
}

class SignalDecodeError(Exception):
    """Raised when a signal telegram cannot be decoded"""

@dataclass(frozen=True)
class SignalTelegram:
    mid: int
    name: str
    fields: dict = field(default_factory=dict)

    def __str__(self):
        return f"SIGNAL 0x{self.mid:02X} ({self.name}): {self.fields}"

@dataclass(frozen=True)
class SignalDefinition:
    name: str
    decode: Callable[[bytes], dict]


def _decode_request_status_update(payload):
    request_status_code = get_bits_from_bytearray(payload, 8, num_bits=8)
    request_status = {
        0: "EEP status",
        1: "Energy status",
        2: "Revision of device",
        3: "RX channel quality",
        4: "Energy delivery of the harvester",
        5: "Date and Time",
        6: "Request for secure setup",
    }.get(request_status_code, "RESERVED")
    return dict(request_status=request_status)

def _decode_energy_status(payload):
    energy = payload[1]
    if energy == 0:
        return dict(energy="last_message")
    elif 1 <= energy <= 100:
        return dict(energy=f"{energy}%")
    return dict(energy="RESERVED")


def _decode_revision(payload):
    sw_version = ".".join(str(b) for b in payload[1:5])
    hw_version = ".".join(str(b) for b in payload[5:9])
    return dict(sw_version=sw_version, hw_version=hw_version)

def _no_optional_data(payload):
    return {}


def _dbm_from_raw(raw):
    return None if raw == 255 else 127 - raw


def _decode_rx_channel_quality(payload):
    telegram_id = get_bits_from_bytearray(payload, 8, num_bits=32)
    dbm_worst = _dbm_from_raw(payload[5])
    dbm_best = _dbm_from_raw(payload[6])
    subtelegram_count = get_bits_from_bytearray(payload, 56, num_bits=4)
    max_repeater_level = get_bits_from_bytearray(payload, 60, num_bits=4)
    return dict(
        id=telegram_id,
        dbm_worst=dbm_worst,
        dbm_best=dbm_best,
        subtelegram_count=None if subtelegram_count == 0 else subtelegram_count,
        max_repeater_level=None if max_repeater_level == 0xF else max_repeater_level,
    )

def _decode_duty_cycle_status(payload):
    status_flag_code = get_bits_from_bytearray(payload, 12, num_bits=4)
    status_flag = {
        0: "TX Duty cycle limit exceeded",
        1: "TX Duty cycle is available",
    }.get(status_flag_code, "reserved")
    return dict(status_flag=status_flag)

def _decode_energy_delivery(payload):
    charging_capabilities_code = get_bits_from_bytearray(payload, 12, num_bits=4)
    charging_capabilities = {
        0: "very good",
        1: "good",
        2: "average",
        3: "bad",
        4: "very bad",
    }.get(charging_capabilities_code, "reserved")
    return dict(chargin_capabilities=charging_capabilities)


def _decode_backup_battery(payload):
    energy = payload[1]
    if 0 <= energy <= 100:
        return dict(energy=f"{energy}%")
    elif energy == 255:
        return dict(energy="no backup battery")
    return dict(energy="reserved")

def _decode_learn_mode_status(payload):
    link_table_full = True if get_bits_from_bytearray(payload, 8, num_bits=1) else False
    reception_teach_in = "enabled" if get_bits_from_bytearray(payload, 9, num_bits=1) else "disabled"
    learn_mode_type = _LEARN_MODE_TYPE_LABELS.get(
        get_bits_from_bytearray(payload, 10, num_bits=2)
    )
    teach_result = _TEACH_RESULT_LABELS.get(
        get_bits_from_bytearray(payload, 12, num_bits=4), "reserved"
    )
    
    remaining_timeout_raw = payload[2]  
    if remaining_timeout_raw == 0x00:
        remaining_timeout = "Not defined"
    elif remaining_timeout_raw == 0xFF:
        remaining_timeout = "Not applicable"
    else:
        remaining_timeout = f"{remaining_timeout_raw * 10}s"

    device_id_bytes = payload[3:7]
    device_id = (
        "Not applicable" if all(b == 0xFF for b in device_id_bytes)
        else to_hex_string(device_id_bytes)
    )
    device_eep_bytes = payload[7:10]
    device_eep = (
        "Not applicable" if all(b == 0xFF for b in device_eep_bytes)
        else to_hex_string(device_eep_bytes)
    )

    return dict(
        link_table_full=link_table_full,
        reception_teach_in=reception_teach_in,
        learn_mode_type=learn_mode_type,
        teach_result=teach_result,
        remaining_timeout=remaining_timeout,
        device_id=device_id,
        device_eep=device_eep,
    )

def _decode_product_id(payload):
    product_id = get_bits_from_bytearray(payload, 8, num_bits=48)
    return dict(
        product_id=product_id,
        manufacturer_id=(product_id >> 32) & 0xFFFF,
        product_reference=product_id & 0xFFFFFFFF,
    )

def _decode_date_time(payload):
    year = payload[1] + 2000
    month = payload[2]
    day = payload[3]
    daylight_saving = get_bits_from_bytearray(payload, 32, num_bits=2)
    hour = get_bits_from_bytearray(payload, 34, num_bits=6)
    minute = payload[5]
    second = payload[6]
    dt = datetime(year, month, day, hour, minute, second)
    return dict(datetime=dt, daylight_saving=daylight_saving)

SIGNAL_DEFINITIONS = {
    0x01: SignalDefinition("SMART Ack Mailbox empty", _no_optional_data),
    0x02: SignalDefinition("SMART ACK Mailbox does not exist ", _no_optional_data),
    0x03: SignalDefinition("SMART ACK Reset", _no_optional_data),
    0x04: SignalDefinition("Trigger status message of device", _decode_request_status_update),
    0x05: SignalDefinition("Last unicast-message acknowledge", _no_optional_data),
    0x06: SignalDefinition("Energy status of device", _decode_energy_status),
    0x07: SignalDefinition("Revision of device", _decode_revision),
    0x08: SignalDefinition("Heartbeat", _no_optional_data),
    0x09: SignalDefinition("RX Window open", _no_optional_data),
    0x0a: SignalDefinition("RX-channel quality", _decode_rx_channel_quality),
    0x0b: SignalDefinition("Duty-cycle status", _decode_duty_cycle_status),
    0x0c: SignalDefinition("Configuration of device changed", _no_optional_data),
    0x0d: SignalDefinition("Energy delivery of the harvester", _decode_energy_delivery),
    0x0e: SignalDefinition("TX Mode OFF", _no_optional_data),
    0x0f: SignalDefinition("TX Mode OFF", _no_optional_data),
    0x10: SignalDefinition("Backup battery status", _decode_backup_battery),
    0x11: SignalDefinition("Learn mode status", _decode_learn_mode_status),
    0x12: SignalDefinition("Product ID", _decode_product_id),
    0x13: SignalDefinition("Date and Time", _decode_date_time),
}

class SignalMessage:

    @staticmethod
    def decode(payload):
        if not payload:
            raise SignalDecodeError("Empty SIGNAL payload")
        mid = payload[0]
        definition  = SIGNAL_DEFINITIONS.get(mid)
        if definition is None:
            raise NotImplementedError(f"Signal type 0x{mid:02X} is not supported")
        try:
            fields = definition.decode(payload)
        except (IndexError, ValueError) as e:
            raise SignalDecodeError(f"Unable to decode SIGNAL telegram MID 0x{mid:02X}: {e}")
        return SignalTelegram(mid=mid, name=definition.name, fields=fields)
