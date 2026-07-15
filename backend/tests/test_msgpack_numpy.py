from __future__ import annotations

import msgpack
import numpy as np

from robotics_playground.vendored import msgpack_numpy


def test_vllm_omni_round_trip_array():
    arr = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)
    packed = msgpack_numpy.packb(arr)
    result = msgpack_numpy.unpackb(packed)
    np.testing.assert_array_equal(result, arr)


def test_openpi_round_trip_array():
    arr = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)
    packb = msgpack_numpy.make_packb(msgpack_numpy.OPENPI)
    packed = packb(arr)
    result = msgpack_numpy.unpackb(packed)
    np.testing.assert_array_equal(result, arr)


def test_vllm_omni_round_trip_scalar():
    val = np.float32(3.14)
    packed = msgpack_numpy.packb(val)
    result = msgpack_numpy.unpackb(packed)
    assert isinstance(result, np.floating)
    np.testing.assert_almost_equal(result, 3.14, decimal=5)


def test_openpi_round_trip_scalar():
    val = np.float32(3.14)
    packb = msgpack_numpy.make_packb(msgpack_numpy.OPENPI)
    packed = packb(val)
    result = msgpack_numpy.unpackb(packed)
    assert isinstance(result, np.floating)
    np.testing.assert_almost_equal(result, 3.14, decimal=5)


def test_cross_format_unpack_openpi_packed_by_vllm_omni():
    """Unpacker handles vLLM-Omni packed data regardless of origin."""
    arr = np.arange(6, dtype=np.float64).reshape(2, 3)
    packed = msgpack_numpy.packb(arr)
    result = msgpack_numpy.unpackb(packed)
    np.testing.assert_array_equal(result, arr)


def test_cross_format_unpack_vllm_omni_packed_by_openpi():
    """Unpacker handles OpenPI packed data regardless of origin."""
    arr = np.arange(6, dtype=np.float64).reshape(2, 3)
    packb = msgpack_numpy.make_packb(msgpack_numpy.OPENPI)
    packed = packb(arr)
    result = msgpack_numpy.unpackb(packed)
    np.testing.assert_array_equal(result, arr)


def test_detect_wire_format_vllm_omni():
    arr = np.zeros(3, dtype=np.float32)
    packed = msgpack_numpy.packb(arr)
    assert msgpack_numpy.detect_wire_format(packed) == msgpack_numpy.VLLM_OMNI


def test_detect_wire_format_openpi():
    arr = np.zeros(3, dtype=np.float32)
    packb = msgpack_numpy.make_packb(msgpack_numpy.OPENPI)
    packed = packb(arr)
    assert msgpack_numpy.detect_wire_format(packed) == msgpack_numpy.OPENPI


def test_detect_wire_format_plain_dict_defaults_to_openpi():
    packed = msgpack.packb({"model": "test"})
    assert msgpack_numpy.detect_wire_format(packed) == msgpack_numpy.OPENPI


def test_detect_wire_format_plain_dict_with_vllm_omni_hint():
    packed = msgpack.packb({"model": "test"})
    fmt = msgpack_numpy.detect_wire_format(
        packed,
        endpoint_hint="ws://host/v1/realtime/robot/openpi",
    )
    assert fmt == msgpack_numpy.VLLM_OMNI


def test_make_packer_vllm_omni():
    packer = msgpack_numpy.make_packer(msgpack_numpy.VLLM_OMNI)
    arr = np.array([1, 2, 3], dtype=np.int32)
    packed = packer.pack(arr)
    result = msgpack_numpy.unpackb(packed)
    np.testing.assert_array_equal(result, arr)


def test_make_packer_openpi():
    packer = msgpack_numpy.make_packer(msgpack_numpy.OPENPI)
    arr = np.array([1, 2, 3], dtype=np.int32)
    packed = packer.pack(arr)
    assert msgpack_numpy.detect_wire_format(packed) == msgpack_numpy.OPENPI
    result = msgpack_numpy.unpackb(packed)
    np.testing.assert_array_equal(result, arr)


def test_dict_with_mixed_numpy_and_plain():
    obs = {
        "observation/joint_position": np.zeros(7, dtype=np.float32),
        "prompt": "pick up block",
        "step": 42,
    }
    for fmt in [msgpack_numpy.VLLM_OMNI, msgpack_numpy.OPENPI]:
        packb = msgpack_numpy.make_packb(fmt)
        packed = packb(obs)
        result = msgpack_numpy.unpackb(packed)
        expected = obs["observation/joint_position"]
        np.testing.assert_array_equal(result["observation/joint_position"], expected)
        assert result["prompt"] in (b"pick up block", "pick up block")
        assert result["step"] == 42


def test_uint8_image_round_trip():
    img = np.random.randint(0, 255, (180, 320, 3), dtype=np.uint8)
    for fmt in [msgpack_numpy.VLLM_OMNI, msgpack_numpy.OPENPI]:
        packb = msgpack_numpy.make_packb(fmt)
        packed = packb(img)
        result = msgpack_numpy.unpackb(packed)
        np.testing.assert_array_equal(result, img)


def test_non_contiguous_array():
    arr = np.arange(12, dtype=np.float32).reshape(3, 4)[:, ::2]
    assert not arr.flags.c_contiguous
    for fmt in [msgpack_numpy.VLLM_OMNI, msgpack_numpy.OPENPI]:
        packb = msgpack_numpy.make_packb(fmt)
        packed = packb(arr)
        result = msgpack_numpy.unpackb(packed)
        np.testing.assert_array_equal(result, arr)
