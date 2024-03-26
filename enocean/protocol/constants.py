# -*- encoding: utf-8 -*-
from enum import IntEnum, StrEnum, auto


# EnOceanSerialProtocol3.pdf / 12
class PACKET(IntEnum):
    RESERVED = 0x00
    # RADIO == RADIO_ERP1
    # Kept for backwards compatibility reasons, for example custom packet
    # generation shouldn't be affected...
    RADIO = 0x01 # ERP1
    RESPONSE = 0x02
    RADIO_SUB_TEL = 0x03
    EVENT = 0x04
    COMMON_COMMAND = 0x05
    SMART_ACK_COMMAND = 0x06
    REMOTE_MAN_COMMAND = 0x07
    RADIO_MESSAGE = 0x09
    # RADIO_ADVANCED == RADIO_ERP2
    # Kept for backwards compatibility reasons
    RADIO_ADVANCED = 0x0A # ERP2
    RADIO_802_15_4 = 0x10
    COMMAND_2_4 = 0x11


# EnOceanSerialProtocol3.pdf / 18
class RETURN_CODE(IntEnum):
    OK = 0x00
    ERROR = 0x01
    NOT_SUPPORTED = 0x02
    WRONG_PARAM = 0x03
    OPERATION_DENIED = 0x04
    RET_LOCK_SET = 0x05
    RET_BUFFER_TO_SMALL = 0x06
    RET_NO_FREE_BUFFER = 0x07


# EnOceanSerialProtocol3.pdf / 20
class EVENT_CODE(IntEnum):
    SA_RECLAIM_NOT_SUCCESFUL = 0x01
    SA_CONFIRM_LEARN = 0x02
    SA_LEARN_ACK = 0x03
    CO_READY = 0x04
    CO_EVENT_SECUREDEVICES = 0x05
    CO_DUTYCYCLE_LIMIT = 0x06
    CO_TRANSMIT_FAILED = 0x07
    CO_TX_DONE = 0x08
    CO_LRN_MODE_DISABLED = 0x09


class COMMON_COMMAND(IntEnum):
    CO_WR_SLEEP = 0x01
    CO_WR_RESET = 0x02
    CO_RD_VERSION = 0x03
    CO_RD_SYS_LOG = 0x4
    CO_WR_SYS_LOG = 0x5
    CO_WR_BIST = 0x6
    CO_WR_IDBASE = 0x7
    CO_RD_IDBASE = 0x8
    CO_WR_REPEATER = 0x9
    CO_RD_REPEATER = 0xa
    CO_WR_FILTER_ADD = 0xb
    CO_WR_FILTER_DEL = 0xc
    CO_WR_FILTER_DEL_ALL = 0xd
    CO_WR_FILTER_ENABLE = 0xe
    CO_RD_FILTER = 0xf
    CO_WR_WAIT_MATURITY = 0x10
    CO_WR_SUBTEL = 0x11
    CO_WR_MEM = 0x12
    CO_RD_MEM = 0x13
    CO_RD_MEM_ADDRESS = 0x14
    CO_RD_SECURITY = 0x15
    CO_WR_SECURITY = 0x16
    CO_WR_LEARNMODE = 0x17
    CO_RD_LEARNMODE = 0x18
    CO_WR_SECUREDEVICE_ADD = 0x19
    CO_WR_SECUREDEVICE_DEL = 0x1a
    CO_RD_SECUREDEVICES = 0x1b


# EnOcean_Equipment_Profiles_EEP_V2.61_public.pdf / 8
class RORG(IntEnum):
    UNDEFINED = 0x00
    RPS = 0xF6
    BS1 = 0xD5
    BS4 = 0xA5
    VLD = 0xD2
    MSC = 0xD1
    ADT = 0xA6
    SM_LRN_REQ = 0xC6
    SM_LRN_ANS = 0xC7
    SM_REC = 0xA7
    SYS_EX = 0xC5
    SEC = 0x30
    SEC_ENCAPS = 0x31
    UTE = 0xD4


# Results for message parsing
class PARSE_RESULT(IntEnum):
    OK = 0x00
    INCOMPLETE = 0x01
    CRC_MISMATCH = 0x03


class DataFieldType(IntEnum):
    STATUS = 0
    VALUE = 1
    ENUM = 2


class SpecificShortcut(StrEnum):
    UNIT = 'UN'
    MULTIPLIER = 'SCM'
    DIVISOR = 'DIV'
    COMMAND = 'CMD'
    LEARN_BIT = 'LRNB'


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
