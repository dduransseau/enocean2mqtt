
def get_bits_from_bytearray(data: bytearray, start_bit: int, num_bits: int) -> int:
    reversed_index_bit = len(data) * 8 - start_bit
    start_bit = reversed_index_bit - num_bits
    # Define the first byte we should target to read bits
    start_byte = (len(data) - 1) - (start_bit // 8)
    end_byte = (len(data) - 1) - ((start_bit + num_bits - 1) // 8)
    result = None
    for i in range(start_byte, end_byte - 1 if end_byte > 0 else -1, -1):
        if result is None:
            result = data[i]
        else:
            result = (data[i] << 8) | result
    # Calculate the number of bits to shift
    start_bit_in_byte = start_bit % 8
    # Shift to align starting bit and mask off unwanted bits
    result = result >> start_bit_in_byte
    mask = (1 << num_bits) - 1
    result = result & mask
    return result


def set_bits_in_bytearray(data: bytearray, start_bit: int, num_bits: int, value: int) -> None:
    """
    Set bits in a little-endian bytearray, where bits are numbered according to documentation format.

    Args:
        data: Target bytearray to modify (little-endian, lowest byte at end)
        start_bit: Starting bit position as per documentation (higher bit number)
        num_bits: Number of bits to set
        value: Value to set the bits to
    """
    # Ensure value fits in the specified number of bits
    max_value = (1 << num_bits) - 1
    if value > max_value:
        raise ValueError(f"Value {value} is too large for {num_bits} bits")

    # Reverse the bit indexing to match physical layout
    reversed_index_bit = len(data) * 8 - start_bit
    physical_start_bit = reversed_index_bit - num_bits

    # Calculate byte positions
    start_byte = (len(data) - 1) - (physical_start_bit // 8)
    end_byte = (len(data) - 1) - ((physical_start_bit + num_bits - 1) // 8)

    if start_byte < 0 or end_byte < 0 or start_byte >= len(data) or end_byte >= len(data):
        raise ValueError("Bit positions out of range")

    # Calculate bit positions within bytes
    start_bit_in_byte = physical_start_bit % 8

    # Handle single byte case
    if start_byte == end_byte:
        mask = ((1 << num_bits) - 1) << start_bit_in_byte
        data[start_byte] = (data[start_byte] & ~mask) | ((value << start_bit_in_byte) & mask)
        return

    # Handle multi-byte case
    remaining_bits = num_bits
    current_bit_pos = physical_start_bit
    value_pos = 0

    while remaining_bits > 0:
        byte_index = (len(data) - 1) - (current_bit_pos // 8)
        bit_in_byte = current_bit_pos % 8

        bits_this_byte = min(8 - bit_in_byte, remaining_bits)

        # Create mask for this section
        mask = ((1 << bits_this_byte) - 1) << bit_in_byte

        # Extract the relevant bits from the value
        bits_value = (value >> value_pos) & ((1 << bits_this_byte) - 1)

        # Place the bits in the correct position
        data[byte_index] = (data[byte_index] & ~mask) | ((bits_value << bit_in_byte) & mask)

        # Update positions
        value_pos += bits_this_byte
        current_bit_pos += bits_this_byte
        remaining_bits -= bits_this_byte


def get_bits_from_byte(byte, offset, num_bits=1):
    mask = (1 << num_bits) - 1
    extracted_bits = (byte >> offset) & mask
    return extracted_bits


def set_bits_to_byte(byte, offset, value, num_bits=1):
    mask = ((1 << num_bits) - 1) << offset
    byte &= ~mask
    byte |= (value << offset) & mask
    return byte


def combine_hex(data):
    """Combine list of integer values to one big integer"""
    output = 0x00
    for i, value in enumerate(reversed(data)):
        output |= value << i * 8
    return output


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
