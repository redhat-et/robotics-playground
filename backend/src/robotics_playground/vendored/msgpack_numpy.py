"""numpy array support for msgpack.

Supports two wire formats:
- **vllm-omni**: nd/type/kind markers (used by vLLM-Omni server)
- **openpi**: __ndarray__/dtype markers (used by the native OpenPI server)

The unpacker accepts both formats transparently. The packer emits one
format selected via ``make_packer(wire_format)``.
"""

from __future__ import annotations

import functools

import msgpack
import numpy as np

VLLM_OMNI = "vllm-omni"
OPENPI = "openpi"


def _pack_vllm_omni(obj):
    if isinstance(obj, (np.ndarray, np.generic)) and obj.dtype.kind in ("V", "O", "c"):
        raise ValueError(f"Unsupported dtype: {obj.dtype}")

    if isinstance(obj, np.ndarray):
        if not obj.flags.c_contiguous:
            obj = np.ascontiguousarray(obj)
        return {
            b"nd": True,
            b"data": obj.tobytes(),
            b"type": obj.dtype.str,
            b"kind": obj.dtype.kind,
            b"shape": obj.shape,
        }

    if isinstance(obj, np.generic):
        return {
            b"nd": False,
            b"data": obj.tobytes(),
            b"type": obj.dtype.str,
            b"kind": obj.dtype.kind,
        }

    return obj


def _pack_openpi(obj):
    if isinstance(obj, (np.ndarray, np.generic)) and obj.dtype.kind in ("V", "O", "c"):
        raise ValueError(f"Unsupported dtype: {obj.dtype}")

    if isinstance(obj, np.ndarray):
        if not obj.flags.c_contiguous:
            obj = np.ascontiguousarray(obj)
        return {
            b"__ndarray__": True,
            b"data": obj.tobytes(),
            b"dtype": obj.dtype.str,
            b"shape": obj.shape,
        }

    if isinstance(obj, np.generic):
        return {
            b"__npgeneric__": True,
            b"data": obj.item(),
            b"dtype": obj.dtype.str,
        }

    return obj


_PACK_FNS = {VLLM_OMNI: _pack_vllm_omni, OPENPI: _pack_openpi}


def make_packer(wire_format: str = VLLM_OMNI) -> msgpack.Packer:
    return msgpack.Packer(default=_PACK_FNS[wire_format])


def make_packb(wire_format: str = VLLM_OMNI):
    return functools.partial(msgpack.packb, default=_PACK_FNS[wire_format])


# ---------------------------------------------------------------------------
# Universal unpacker — accepts both wire formats
# ---------------------------------------------------------------------------


def _mapping_get(obj, key, default=None):
    return obj.get(key, obj.get(key.encode() if isinstance(key, str) else key, default))


_MISSING = object()


def _unpack_array(obj):
    # Try vLLM-Omni format (nd/type/kind)
    nd = _mapping_get(obj, b"nd", _MISSING)
    if nd is not _MISSING:
        dtype_str = _mapping_get(obj, b"type", _MISSING)
        data = _mapping_get(obj, b"data", _MISSING)
        if dtype_str is not _MISSING and data is not _MISSING:
            dtype_val = dtype_str.decode() if isinstance(dtype_str, bytes) else str(dtype_str)
            dtype_obj = np.dtype(dtype_val)
            if nd:
                shape = _mapping_get(obj, b"shape", (0,))
                if isinstance(shape, list):
                    shape = tuple(shape)
                return np.ndarray(buffer=data, dtype=dtype_obj, shape=shape)
            return dtype_obj.type(np.frombuffer(data, dtype=dtype_obj).item())

    # Try OpenPI format (__ndarray__)
    is_nd = _mapping_get(obj, b"__ndarray__", _MISSING)
    if is_nd is not _MISSING:
        dtype_str = _mapping_get(obj, b"dtype", _MISSING)
        data = _mapping_get(obj, b"data", _MISSING)
        if dtype_str is not _MISSING and data is not _MISSING:
            dtype_val = dtype_str.decode() if isinstance(dtype_str, bytes) else str(dtype_str)
            dtype_obj = np.dtype(dtype_val)
            shape = _mapping_get(obj, b"shape", (0,))
            if isinstance(shape, list):
                shape = tuple(shape)
            return np.frombuffer(data, dtype=dtype_obj).reshape(shape).copy()

    # Try OpenPI scalar format (__npgeneric__)
    is_generic = _mapping_get(obj, b"__npgeneric__", _MISSING)
    if is_generic is not _MISSING:
        dtype_str = _mapping_get(obj, b"dtype", _MISSING)
        data = _mapping_get(obj, b"data", _MISSING)
        if dtype_str is not _MISSING and data is not _MISSING:
            dtype_val = dtype_str.decode() if isinstance(dtype_str, bytes) else str(dtype_str)
            return np.dtype(dtype_val).type(data)

    return obj


def _collect_map_keys(obj, keys: set) -> None:
    if isinstance(obj, dict):
        keys.update(obj.keys())
        for v in obj.values():
            _collect_map_keys(v, keys)
    elif isinstance(obj, list):
        for v in obj:
            _collect_map_keys(v, keys)


_OPENPI_MARKERS = {b"__ndarray__", b"__npgeneric__"}
_VLLM_OMNI_MARKERS = {b"nd", b"type", b"kind"}


def detect_wire_format(raw_bytes: bytes, endpoint_hint: str = "") -> str:
    """Decode the metadata payload and match map-key sets to identify the
    wire format.  Falls back to the endpoint URL when the payload
    contains no numpy markers.
    """
    try:
        decoded = msgpack.unpackb(raw_bytes, raw=True)
        keys: set[bytes] = set()
        _collect_map_keys(decoded, keys)
        if keys & _OPENPI_MARKERS:
            return OPENPI
        if keys >= _VLLM_OMNI_MARKERS:
            return VLLM_OMNI
    except Exception:
        pass
    if "/v1/realtime/robot/openpi" in endpoint_hint:
        return VLLM_OMNI
    return OPENPI


# Default instances — vLLM-Omni format for backwards compatibility
Packer = functools.partial(msgpack.Packer, default=_pack_vllm_omni)
packb = functools.partial(msgpack.packb, default=_pack_vllm_omni)

Unpacker = functools.partial(msgpack.Unpacker, object_hook=_unpack_array)
unpackb = functools.partial(msgpack.unpackb, object_hook=_unpack_array)
