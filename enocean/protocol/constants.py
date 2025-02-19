# -*- encoding: utf-8 -*-
from enum import IntEnum, StrEnum, auto


# EnOceanSerialProtocol3.pdf / 12
class PacketType(IntEnum):
    RESERVED = 0x00
    # RADIO == RADIO_ERP1
    # Kept for backwards compatibility reasons, for example custom packet
    # generation shouldn't be affected...
    RADIO_ERP1 = 0x01  # ERP1
    RESPONSE = 0x02
    RADIO_SUB_TEL = 0x03
    EVENT = 0x04
    COMMON_COMMAND = 0x05
    SMART_ACK_COMMAND = 0x06
    REMOTE_MAN_COMMAND = 0x07
    RADIO_MESSAGE = 0x09
    # RADIO_ADVANCED == RADIO_ERP2
    # Kept for backwards compatibility reasons
    RADIO_ERP2 = 0x0A  # RADIO_ADVANCED
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
    SYS_EX = 0xC5
    SM_LRN_REQ = 0xC6
    SM_LRN_ANS = 0xC7
    SEC = 0x30
    SEC_ENCAPS = 0x31
    DECRYPTED = 0x32
    SEC_CDM = 0x33
    SEC_TI = 0x35
    SIGNAL = 0xD0
    MSC = 0xD1
    VLD = 0xD2
    UTE = 0xD4
    BS1 = 0xD5


class DataFieldType(IntEnum):
    STATUS = 1
    VALUE = 2
    ENUM = 3

class ErpStatusHashType(IntEnum):
    CHECKSUM = 0
    CRC = 1


class FieldSetName(StrEnum):
    RAW_VALUE = auto()
    VALUE = auto()
    DESCRIPTION = auto()
    SHORTCUT = auto()
    TYPE = auto()
    UNIT = auto()


# Data byte indexing
# Starts from the end, so works on messages of all length.
class DB0:
    BIT_0 = -1
    BIT_1 = -2
    BIT_2 = -3
    BIT_3 = -4
    BIT_4 = -5
    BIT_5 = -6
    BIT_6 = -7
    BIT_7 = -8


class DB1:
    BIT_0 = -9
    BIT_1 = -10
    BIT_2 = -11
    BIT_3 = -12
    BIT_4 = -13
    BIT_5 = -14
    BIT_6 = -15
    BIT_7 = -16


class DB2:
    BIT_0 = -17
    BIT_1 = -18
    BIT_2 = -19
    BIT_3 = -20
    BIT_4 = -21
    BIT_5 = -22
    BIT_6 = -23
    BIT_7 = -24


class DB3:
    BIT_0 = -25
    BIT_1 = -26
    BIT_2 = -27
    BIT_3 = -28
    BIT_4 = -29
    BIT_5 = -30
    BIT_6 = -31
    BIT_7 = -32


class DB4:
    BIT_0 = -33
    BIT_1 = -34
    BIT_2 = -35
    BIT_3 = -36
    BIT_4 = -37
    BIT_5 = -38
    BIT_6 = -39
    BIT_7 = -40


class DB5:
    BIT_0 = -41
    BIT_1 = -42
    BIT_2 = -43
    BIT_3 = -44
    BIT_4 = -45
    BIT_5 = -46
    BIT_6 = -47
    BIT_7 = -48


class DB6:
    BIT_0 = -49
    BIT_1 = -50
    BIT_2 = -51
    BIT_3 = -52
    BIT_4 = -53
    BIT_5 = -54
    BIT_6 = -55
    BIT_7 = -56

class RadioDirection(IntEnum):
    FROM = 0
    TO = 1


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
    0: 'Reserved',
    1: 'Peha',
    2: 'Thermokon',
    3: 'Servodan',
    4: 'Echoflex Solutions',
    5: 'Awag Elektrotechnik Ag',  # previously Omnio Ag
    6: 'Hardmeier Electronics',
    7: 'Regulvar Inc',
    8: 'Ad Hoc Electronics',
    9: 'Distech Controls',
    10: 'Kieback And Peter',
    11: 'EnOcean',
    12: 'Vicos Gmbh',  # previously Probare
    13: 'Eltako',
    14: 'Leviton',
    15: 'Honeywell',
    16: 'Spartan Peripheral Devices',
    17: 'Siemens',
    18: 'T Mac',
    19: 'Reliable Controls Corporation',
    20: 'Elsner Elektronik Gmbh',
    21: 'Diehl Controls',
    22: 'Bsc Computer',
    23: 'S And S Regeltechnik Gmbh',
    24: 'Masco Corporation',  # previously Zeno Controls
    25: 'Intesis Software Sl',
    26: 'Viessmann',
    27: 'Lutuo Technology',
    28: 'Can2Go',
    29: 'Sauter',
    30: 'Boot Up',
    31: 'Osram Sylvania',
    32: 'Unotech',
    33: 'Delta Controls Inc',
    34: 'Unitronic Ag',
    35: 'Nanosense',
    36: 'The S4 Group',
    37: 'Veissmann Hausatomation Gmbh',  # previously Msr Solutions
    38: 'GE',
    39: 'Maico',
    40: 'Ruskin Company',
    41: 'Magnum Energy Solutions',
    42: 'KMC Controls',
    43: 'Ecologix Controls',
    44: 'Trio 2 Sys',
    45: 'Afriso Euro Index',
    46: 'Waldmann Gmbh',
    48: 'Nec Platforms Ltd',
    49: 'Itec Corporation',
    50: 'Simicx Co Ltd',
    51: 'Permundo Gmbh',
    52: 'Eurotronic Technology Gmbh',
    53: 'Art Japan Co Ltd',
    54: 'Tiansu Automation Control Syste Co Ltd',
    55: 'Weinzierl Engineering Gmbh',
    56: 'Gruppo Giordano Idea Spa',
    57: 'Alphaeos Ag',
    58: 'Tag Technologies',
    59: 'Wattstopper',
    60: 'Pressac Communications Ltd',
    62: 'Giga Concept',
    63: 'Sensortec',
    64: 'Jaeger Direkt',
    65: 'Air System Components Inc',
    66: 'Ermine Corp',
    67: 'Soda Gmbh',
    68: 'Eke Automation',
    69: 'Holter Regelarmutren',
    70: 'ID RF',
    71: 'Deuta Controls Gmbh',
    72: 'Ewattch',
    73: 'Micropelt',
    74: 'Caleffi Spa',
    75: 'Digital Concepts',
    76: 'Emerson Climate Technologies',
    77: 'Adee Electronic',
    78: 'Altecon',
    79: 'Nanjing Putian Telecommunications',
    80: 'Terralux',
    81: 'Menred',
    82: 'Iexergy Gmbh',
    83: 'Oventrop Gmbh',
    84: 'Building Automation Products Inc',
    85: 'Functional Devices Inc',
    86: 'Ogga',
    87: 'Itho Daalderop',
    88: 'Resol',
    89: 'Advanced Devices',
    90: 'Autani Lcc',
    91: 'Dr Riedel Gmbh',
    92: 'Hoppe Holding Ag',
    93: 'Siegenia Aubi Kg',
    94: 'Adeo Services',
    95: 'Eimsig Efp Gmbh',
    96: 'Vimar Spa',
    97: 'Glen Dimlax Gmbh',
    98: 'Pmdm Gmbh',
    99: 'Hubbel Lightning',
    100: 'Debflex',
    101: 'Perifactory Sensorsystems',
    102: 'Watty Corp',
    103: 'Wago Kontakttechnik',
    104: 'Kessel',
    105: 'Aug Winkhaus',
    106: 'Decelect',
    107: 'Mst Industries',
    108: 'Becker Antriebe',
    109: 'Nexelec',
    110: 'Wieland Electric',
    111: 'Avidsen',
    112: 'Cws Boco International',
    113: 'Roto Frank',
    114: 'Alm Contorls',
    115: 'Tommaso Technologies',
    116: 'Rehau',
    117: 'Inaba Denki Sangyo Co Lt',
    118: 'Hager Controls Sas',
    255: 'Multiple',
    2047: 'Multi-user (test purpose)'
}
