"""
Unit tests for binary protocol encoding and decoding (v10).
"""
import pytest
from max_library.transport.protocol import encode_packet, decode_packet, ext_hook
import msgpack


def test_encode_and_decode_simple_packet():
    payload = {"hello": "world", "num": 123}
    encoded = encode_packet(cmd=0, seq=42, opcode=6, payload=payload)
    assert len(encoded) >= 10
    assert encoded[0] == 10  # Proto version 10
    assert encoded[1] == 0   # cmd

    decoded = decode_packet(encoded)
    assert decoded["ver"] == 10
    assert decoded["cmd"] == 0
    assert decoded["seq"] == 42
    assert decoded["opcode"] == 6
    assert decoded["payload"] == payload


def test_encode_and_decode_none_payload():
    encoded = encode_packet(cmd=1, seq=100, opcode=1, payload=None)
    assert len(encoded) == 10
    decoded = decode_packet(encoded)
    assert decoded["cmd"] == 1
    assert decoded["seq"] == 100
    assert decoded["opcode"] == 1
    assert decoded["payload"] is None


def test_encode_and_decode_compressed_packet():
    # Long repetitive payload to ensure compression triggers
    payload = {"long_text": "A" * 1000, "list": list(range(100))}
    encoded = encode_packet(cmd=0, seq=7, opcode=19, payload=payload, compress=True)
    # Check that compression factor > 0
    comp_factor = encoded[6]
    assert comp_factor > 0

    decoded = decode_packet(encoded)
    assert decoded["payload"] == payload


def test_decode_ext_type_1():
    # ExtType 1 is used for BigInt / ID numbers
    packed_val = msgpack.packb(12345678)
    res = ext_hook(1, packed_val)
    assert res == 12345678
