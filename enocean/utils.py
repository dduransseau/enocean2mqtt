# -*- encoding: utf-8 -*-


# def get_bit(byte, bit):
#     """Get bit value from byte"""
#     return (byte >> bit) & 0x01

def read_bits_from_byte(byte, offset, num_bits=1):
    mask = (1 << num_bits) - 1
    extracted_bits = (byte >> offset) & mask
    return extracted_bits

def write_bits_to_byte(byte, offset, value, num_bits=1):
    mask = ((1 << num_bits) - 1) << offset
    byte &= ~mask
    byte |= (value << offset) & mask
    return byte

def set_bit(byte_array, bit_pos, value):
    byte_index = bit_pos // 8
    bit_index = bit_pos % 8
    if value:
        byte_array[byte_index] |= (1 << bit_index)
    else:
        byte_array[byte_index] &= ~(1 << bit_index)


def get_bit(byte_array, bit_pos):
    byte_index = bit_pos // 8
    bit_index = bit_pos % 8
    return (byte_array[byte_index] >> bit_index) & 1


def combine_hex(data):
    """Combine list of integer values to one big integer"""
    output = 0x00
    for i, value in enumerate(reversed(data)):
        output |= value << i * 8
    return output


def to_bitarray(data, width=8):
    """Convert data (list of integers, bytearray or integer) to bitarray"""
    if isinstance(data, list) or isinstance(data, bytearray):
        data = combine_hex(data)
    return [True if digit == "1" else False for digit in bin(data)[2:].zfill(width)]


def from_bitarray(data):
    """Convert bit array back to integer"""
    out = 0
    for bit in data:
        out = (out << 1) | bit
    return out


def to_hex_string(data):
    """Convert list of integers to a hex string, separated by ":" """
    if isinstance(data, int):
        return f"{data:X}"
    return "".join([f"{o:X}".zfill(2) for o in data])


def from_hex_string(hex_string):
    reval = [int(x, 16) for x in hex_string.split(":")]
    if len(reval) == 1:
        return reval[0]
    return reval


def address_to_bytes_list(a):
    return [(a >> i * 8) & 0xFF for i in reversed(range(4))]
