"""numpy array support for msgpack. Adapted from openpi-client (Apache 2.0)."""

from __future__ import annotations

import functools

import msgpack
import numpy as np


def _pack_array(obj):
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


def _mapping_get(obj, key, default=None):
    return obj.get(key, obj.get(key.encode() if isinstance(key, str) else key, default))


_MISSING = object()


def _unpack_array(obj):
    nd = _mapping_get(obj, b"nd", _MISSING)
    dtype_str = _mapping_get(obj, b"type", _MISSING)
    kind = _mapping_get(obj, b"kind", _MISSING)
    data = _mapping_get(obj, b"data", _MISSING)

    has_all = all(v is not _MISSING for v in (nd, dtype_str, kind, data))
    if has_all:
        dtype_val = dtype_str.decode() if isinstance(dtype_str, bytes) else str(dtype_str)
        dtype_obj = np.dtype(dtype_val)
        if nd:
            shape = _mapping_get(obj, b"shape", (0,))
            if isinstance(shape, list):
                shape = tuple(shape)
            return np.ndarray(buffer=data, dtype=dtype_obj, shape=shape)
        return dtype_obj.type(np.frombuffer(data, dtype=dtype_obj).item())

    return obj


Packer = functools.partial(msgpack.Packer, default=_pack_array)
packb = functools.partial(msgpack.packb, default=_pack_array)

Unpacker = functools.partial(msgpack.Unpacker, object_hook=_unpack_array)
unpackb = functools.partial(msgpack.unpackb, object_hook=_unpack_array)
