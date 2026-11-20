"""
Binary protocol packet encoder/decoder for MAX Messenger (Proto version 10).
Uses msgpack for payload serialization and optional lz4 block compression.
"""
import struct
from typing import Any, Tuple, Optional
import msgpack
import lz4.block


HEADER_LENGTH = 10
PROTO_VERSION = 10
MIN_COMPRESS_LENGTH = 32  # jC in MAX client source


def ext_hook(code: int, data: bytes) -> Any:
    """
    Handles MsgPack Extension types.
    Extension type 1 is used by MAX for 64-bit / BigInt values (e.g. user IDs, chat IDs, message IDs).
    """
    if code == 1:
        # ExtType 1 contains msgpack-encoded int/bigint
        return msgpack.unpackb(data, raw=False)
    return msgpack.ExtType(code, data)


def encode_packet(
    cmd: int,
    seq: int,
    opcode: int,
    payload: Any = None,
    compress: bool = False,
) -> bytes:
    """
    Encodes a MAX protocol binary packet.

    Header structure (10 bytes):
      Byte 0: Proto version (10)
      Byte 1: Command type (0: request, 1: response, 2: cancel, 3: ack/error)
      Bytes 2..3: Sequence number (int16 big-endian)
      Bytes 4..5: Opcode (int16 big-endian)
      Byte 6: Compression ratio factor (0 if uncompressed)
      Bytes 7..9: 24-bit payload byte length (big-endian)
    """
    if payload is not None:
        payload_bytes = msgpack.packb(payload, use_bin_type=True)
    else:
        payload_bytes = b""

    comp_factor = 0
    if compress and len(payload_bytes) > MIN_COMPRESS_LENGTH:
        compressed = lz4.block.compress(payload_bytes, store_size=False)
        if len(compressed) < len(payload_bytes):
            factor = min(int((len(payload_bytes) + len(compressed) - 1) // len(compressed)), 255)
            if factor > 0:
                payload_bytes = compressed
                comp_factor = factor

    length = len(payload_bytes)
    header = bytearray(HEADER_LENGTH)
    header[0] = PROTO_VERSION
    header[1] = cmd & 0xFF
    struct.pack_into(">h", header, 2, seq)
    struct.pack_into(">h", header, 4, opcode)
    header[6] = comp_factor & 0xFF
    header[7] = (length >> 16) & 0xFF
    header[8] = (length >> 8) & 0xFF
    header[9] = length & 0xFF

    return bytes(header) + payload_bytes


def decode_packet(data: bytes) -> dict[str, Any]:
    """
    Decodes a MAX protocol binary packet from bytes.
    """
    if len(data) < HEADER_LENGTH:
        raise ValueError(f"Packet too short: {len(data)} bytes (expected >= {HEADER_LENGTH})")

    proto = data[0]
    cmd = data[1]
    seq, opcode = struct.unpack_from(">hh", data, 2)
    comp_factor = data[6]
    length = (data[7] << 16) | (data[8] << 8) | data[9]

    if len(data) < HEADER_LENGTH + length:
        raise ValueError(f"Packet payload truncated: got {len(data) - HEADER_LENGTH}, expected {length}")

    payload_bytes = data[HEADER_LENGTH : HEADER_LENGTH + length]

    if comp_factor > 0 and payload_bytes:
        uncompressed_size = length * comp_factor
        payload_bytes = lz4.block.decompress(payload_bytes, uncompressed_size=uncompressed_size)

    if payload_bytes:
        payload = msgpack.unpackb(
            payload_bytes,
            raw=False,
            strict_map_key=False,
            ext_hook=ext_hook,
        )
    else:
        payload = None

    return {
        "ver": proto,
        "cmd": cmd,
        "seq": seq,
        "opcode": opcode,
        "payload": payload,
    }
