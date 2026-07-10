from __future__ import annotations

import asyncio
import logging

import websockets.sync.client

from robotics_playground.vendored import msgpack_numpy

logger = logging.getLogger(__name__)


class OpenPIClient:
    def __init__(self, endpoint: str) -> None:
        self._endpoint = endpoint
        self._ws: websockets.sync.client.ClientConnection | None = None
        self._packer = msgpack_numpy.Packer()
        self._server_metadata: dict = {}

    async def connect(self) -> None:
        self._ws, self._server_metadata = await asyncio.to_thread(self._connect_sync)
        logger.info("Connected to OpenPI server at %s", self._endpoint)

    def _connect_sync(self) -> tuple:
        conn = websockets.sync.client.connect(
            self._endpoint,
            compression=None,
            max_size=None,
        )
        metadata = msgpack_numpy.unpackb(conn.recv())
        return conn, metadata

    async def infer(self, obs: dict) -> dict:
        return await asyncio.to_thread(self._infer_sync, obs)

    def _infer_sync(self, obs: dict) -> dict:
        if self._ws is None:
            raise RuntimeError("Not connected")
        data = self._packer.pack(obs)
        self._ws.send(data)
        response = self._ws.recv()
        if isinstance(response, str):
            raise RuntimeError(f"Error in inference server:\n{response}")
        return msgpack_numpy.unpackb(response)

    async def reset(self) -> None:
        pass

    async def close(self) -> None:
        if self._ws is not None:
            await asyncio.to_thread(self._ws.close)
            self._ws = None
