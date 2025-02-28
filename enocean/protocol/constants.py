# -*- encoding: utf-8 -*-
from enum import IntEnum


# EnOceanSerialProtocol3.pdf / 12
class PacketType(IntEnum):
    RESERVED = 0x00
    RADIO_ERP1 = 0x01  # ERP1 -> ASK
    RESPONSE = 0x02
    RADIO_SUB_TEL = 0x03
    EVENT = 0x04
    COMMON_COMMAND = 0x05
    SMART_ACK_COMMAND = 0x06
    REMOTE_MAN_COMMAND = 0x07
    RADIO_MESSAGE = 0x09
    RADIO_ERP2 = 0x0A  # RADIO_ADVANCED -> FSK
    RADIO_802_15_4 = 0x10
    COMMAND_2_4 = 0x11


# EnOceanSerialProtocol3.pdf / 20
class EventCode(IntEnum):
    SA_RECLAIM_NOT_SUCCESSFUL = 0x01
    SA_CONFIRM_LEARN = 0x02
    SA_LEARN_ACK = 0x03
    CO_READY = 0x04
    CO_EVENT_SECUREDEVICES = 0x05
    CO_DUTYCYCLE_LIMIT = 0x06
    CO_TRANSMIT_FAILED = 0x07
    CO_TX_DONE = 0x08
    CO_LRN_MODE_DISABLED = 0x09


class CommandCode(IntEnum):
    CO_WR_SLEEP = 0x01
    CO_WR_RESET = 0x02
    CO_RD_VERSION = 0x03
    CO_RD_SYS_LOG = 0x4
    CO_WR_SYS_LOG = 0x5
    CO_WR_BIST = 0x6
    CO_WR_IDBASE = 0x7
    CO_RD_IDBASE = 0x8
    CO_WR_REPEATER = 0x9
    CO_RD_REPEATER = 0xA
    CO_WR_FILTER_ADD = 0xB
    CO_WR_FILTER_DEL = 0xC
    CO_WR_FILTER_DEL_ALL = 0xD
    CO_WR_FILTER_ENABLE = 0xE
    CO_RD_FILTER = 0xF
    CO_WR_WAIT_MATURITY = 0x10
    CO_WR_SUBTEL = 0x11
    CO_WR_MEM = 0x12
    CO_RD_MEM = 0x13
    CO_RD_MEM_ADDRESS = 0x14
    CO_RD_SECURITY = 0x15  # DEPRECATED
    CO_WR_SECURITY = 0x16  # DEPRECATED
    CO_WR_LEARNMODE = 0x17
    CO_RD_LEARNMODE = 0x18
    CO_WR_SECUREDEVICE_ADD = 0x19  # DEPRECATED
    CO_WR_SECUREDEVICE_DEL = 0x1A
    CO_RD_SECUREDEVICES_BY_INDEX = 0x1B  # DEPRECATED
    CO_WR_MODE = 0x1C
    CO_SET_BAUDRATE = 0x24
    CO_GET_FREQUENCY_INFO = 0x25
    CO_GET_STEPCODE = 0x27
    # 0x28 - 0x2d RESERVED
    CO_WR_REMAN_CODE = 0x2e
    CO_WR_STARTUP_DELAY = 0x2f
    CO_WR_REMAN_REPEATING = 0x30
    CO_RD_REMAN_REPEATING = 0x31
    CO_SET_NOISETHRESHOLD = 0x32
    CO_GET_NOISETHRESHOLD = 0x33
    # 0x34 - 0x35 RESERVED
    CO_WR_RLC_SAVE_PERIOD = 0x36
    CO_WR_RLC_LEGACY_MODE = 0x37
    CO_WR_SECUREDEVICEV2_ADD = 0x38
    CO_RD_SECUREDEVICEV2_BY_INDEX = 0x39
    CO_WR_RSSITEST_MODE = 0x3a
    CO_RD_RSSITEST_MODE = 0x3b
    CO_WR_SECUREDEVICE_MAINTENANCEKEY = 0x3c
    CO_RD_SECUREDEVICE_MAINTENANCEKEY = 0x3d
    CO_WR_TRANSPARENT_MODE = 0x3e
    CO_RD_TRANSPARENT_MODE = 0x3F
    CO_WR_TX_ONLY_MODE = 0x40
    CO_RD_TX_ONLY_MODE = 0x41


# EnOceanSerialProtocol3.pdf / 18
class ReturnCode(IntEnum):
    OK = 0x00
    ERROR = 0x01
    NOT_SUPPORTED = 0x02
    WRONG_PARAM = 0x03
    OPERATION_DENIED = 0x04
    RET_LOCK_SET = 0x05
    RET_BUFFER_TO_SMALL = 0x06
    RET_NO_FREE_BUFFER = 0x07


# EnOcean_Equipment_Profiles_EEP_V2.61_public.pdf / 8
class RORG(IntEnum):
    RPS = 0xF6
    BS4 = 0xA5
    ADT = 0xA6
    SM_REC = 0xA7
    GP_TI = 0xB0
    GP_TR = 0xB1
    GP_CD = 0xB2
    GP_SD = 0xB3
    SYS_EX = 0xC5
    SM_LRN_REQ = 0xC6
    SM_LRN_ANS = 0xC7
    SEC = 0x30
    SEC_ENCAP = 0x31
    DECRYPTED = 0x32
    SEC_CDM = 0x33
    SEC_TI = 0x35
    SIGNAL = 0xD0
    MSC = 0xD1
    VLD = 0xD2
    UTE = 0xD4
    BS1 = 0xD5


class ErpStatusHashType(IntEnum):
    CHECKSUM = 0
    CRC = 1

class UteTeachInQueryRequestType(IntEnum):
    REGISTRATION = 0b00
    DELETION = 0b01
    NOT_SPECIFIED = 0b10
    NOT_USED = 0b11


class UteTeachInResponseRequestType(IntEnum):
    REFUSED_GENERAL = 0b00
    ACCEPTED_REGISTRATION = 0b01
    ACCEPTED_DELETION = 0b10
    REFUSED_EEP_NOT_SUPPORTED = 0b11


class Direction(IntEnum):
    FROM = 1  # Outbound (device > controller)
    TO = 2  # Inbound (controller > device)


RESPONSE_REPEATER_MODE = {0: "OFF", 1: "ON", 2: "SELECTIVE"}

RESPONSE_REPEATER_LEVEL = {0: "OFF", 1: "1-level", 2: "2-level"}

RESPONSE_FREQUENCY_FREQUENCY = {
    0: "315Mhz",
    1: "868.3Mhz",
    2: "902.87Mhz",
    3: "925Mhz",
    4: "928Mhz",
    32: "2.4 Ghz",
}

RESPONSE_FREQUENCY_PROTOCOL = {
    0: "ERP1",
    1: "ERP2",
    16: "802.15.4",
    48: "Long Range",
}

ERP1_STATUS_REPEATER_LEVEL = {
    0: "Original Telegram",
    1: "One Hop Repeated Telegram",
    2: "Two Hop Repeated Telegram",
    15: "Telegram shall not be repeated",
}

MANUFACTURER_CODE = {
    0x0: "Reserved",
    0x1: "Peha",
    0x2: "Thermokon",
    0x3: "Servodan",
    0x4: "Echoflex Solutions",
    0x5: "Awag Elektrotechnik Ag",  # previously Omnio Ag
    0x6: "Hardmeier Electronics",
    0x7: "Regulvar Inc",
    0x8: "Ad Hoc Electronics",
    0x9: "Distech Controls",
    0xA: "Kieback And Peter",
    0xB: "EnOcean",
    0xC: "Vicos Gmbh",   # previously Probare
    0xD: "Eltako",
    0xE: "Leviton",
    0xF: "Honeywell",
    0x10: "Spartan Peripheral Devices",
    0x11: "Siemens",
    0x12: "T Mac",
    0x13: "Reliable Controls Corporation",
    0x14: "Elsner Elektronik Gmbh",
    0x15: "Diehl Controls",
    0x16: "Bsc Computer",
    0x17: "S And S Regeltechnik Gmbh",
    0x18: "Masco Corporation",  # previously Zeno Controls
    0x19: "Intesis Software Sl",
    0x1A: "Viessmann",
    0x1B: "Lutuo Technology",
    0x1C: "Can2Go",
    0x1D: "Sauter",
    0x1E: "Boot Up",
    0x1F: "Osram Sylvania",
    0x20: "Unotech",
    0x21: "Delta Controls Inc",
    0x22: "Unitronic Ag",
    0x23: "Nanosense",
    0x24: "The S4 Group",
    0x25: "Veissmann Hausatomation Gmbh",  # previously Msr Solutions
    0x26: "GE",
    0x27: "Maico",
    0x28: "Ruskin Company",
    0x29: "Magnum Energy Solutions",
    0x2A: "KMC Controls",
    0x2B: "Ecologix Controls",
    0x2C: "Trio 2 Sys",
    0x2D: "Afriso Euro Index",
    0x2E: "Waldmann Gmbh",
    0x30: "Nec Platforms Ltd",
    0x31: "Itec Corporation",
    0x32: "Simicx Co Ltd",
    0x33: "Permundo Gmbh",
    0x34: "Eurotronic Technology Gmbh",
    0x35: "Art Japan Co Ltd",
    0x36: "Tiansu Automation Control Syste Co Ltd",
    0x37: "Weinzierl Engineering Gmbh",
    0x38: "Gruppo Giordano Idea Spa",
    0x39: "Alphaeos Ag",
    0x3A: "Tag Technologies",
    0x3B: "Wattstopper",
    0x3C: "Pressac Communications Ltd",
    0x3E: "Giga Concept",
    0x3F: "Sensortec",
    0x40: "Jaeger Direkt",
    0x41: "Air System Components Inc",
    0x42: "Ermine Corp",
    0x43: "Soda Gmbh",
    0x44: "Eke Automation",
    0x45: "Holter Regelarmutren",
    0x46: "ID RF",
    0x47: "Deuta Controls Gmbh",
    0x48: "Ewattch",
    0x49: "Micropelt",
    0x4A: "Caleffi Spa",
    0x4B: "Digital Concepts",
    0x4C: "Emerson Climate Technologies",
    0x4D: "Adee Electronic",
    0x4E: "Altecon",
    0x4F: "Nanjing Putian Telecommunications",
    0x50: "Terralux",
    0x51: "Menred",
    0x52: "Iexergy Gmbh",
    0x53: "Oventrop Gmbh",
    0x54: "Building Automation Products Inc",
    0x55: "Functional Devices Inc",
    0x56: "Ogga",
    0x57: "Itho Daalderop",
    0x58: "Resol",
    0x59: "Advanced Devices",
    0x5A: "Autani Lcc",
    0x5B: "Dr Riedel Gmbh",
    0x5C: "Hoppe Holding Ag",
    0x5D: "Siegenia Aubi Kg",
    0x5E: "Adeo Services",
    0x5F: "Eimsig Efp Gmbh",
    0x60: "Vimar Spa",
    0x61: "Glen Dimlax Gmbh",
    0x62: "Pmdm Gmbh",
    0x63: "Hubbel Lightning",
    0x64: "Debflex",
    0x65: "Perifactory Sensorsystems",
    0x66: "Watty Corp",
    0x67: "Wago Kontakttechnik",
    0x68: "Kessel",
    0x69: "Aug Winkhaus",
    0x6A: "Decelect",
    0x6B: "Mst Industries",
    0x6C: "Becker Antriebe",
    0x6D: "Nexelec",
    0x6E: "Wieland Electric",
    0x6F: "Avidsen",
    0x70: "Cws Boco International",
    0x71: "Roto Frank",
    0x72: "Alm Contorls",
    0x73: "Tommaso Technologies",
    0x74: "Rehau",
    0x75: "Inaba Denki Sangyo Co Lt",
    0x76: "Hager Controls Sas",
    0x79: "Ventilairsec",
    0xFF: "Multiple",
    0x7FF: "Multi-user (test purpose)"
}
