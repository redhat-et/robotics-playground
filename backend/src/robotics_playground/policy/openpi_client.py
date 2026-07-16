from __future__ import annotations

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor

import websockets.exceptions
import websockets.sync.client

from robotics_playground.vendored import msgpack_numpy

logger = logging.getLogger(__name__)

CONNECT_TIMEOUT = 30  # seconds — TCP + WebSocket handshake
RECV_TIMEOUT = 300  # seconds — long inference is normal (22s+), allow for cold starts


def _new_executor() -> ThreadPoolExecutor:
    return ThreadPoolExecutor(max_workers=2, thread_name_prefix="openpi")


class OpenPIClient:
    def __init__(self, endpoint: str) -> None:
        self._endpoint = endpoint
        self._ws: websockets.sync.client.ClientConnection | None = None
        self._packer = msgpack_numpy.Packer()
        self._wire_format: str = msgpack_numpy.VLLM_OMNI
        self._server_metadata: dict = {}
        self._executor = _new_executor()
        self._closing = False

    @property
    def wire_format(self) -> str:
        return self._wire_format

    async def connect(self) -> None:
        self._closing = False
        try:
            self._executor.submit(lambda: None).cancel()
        except RuntimeError:
            self._executor = _new_executor()
        loop = asyncio.get_running_loop()
        self._ws, self._server_metadata = await loop.run_in_executor(
            self._executor, self._connect_sync
        )
        logger.info(
            "Connected to OpenPI server at %s (wire_format=%s)",
            self._endpoint,
            self._wire_format,
        )
        logger.info("Server metadata: %s", self._server_metadata)

    def _connect_sync(self) -> tuple:
        conn = websockets.sync.client.connect(
            self._endpoint,
            compression=None,
            max_size=None,
            open_timeout=CONNECT_TIMEOUT,
            ping_interval=None,
        )
        raw = conn.recv(timeout=RECV_TIMEOUT)
        self._wire_format = msgpack_numpy.detect_wire_format(
            raw,
            endpoint_hint=self._endpoint,
        )
        self._packer = msgpack_numpy.make_packer(self._wire_format)
        metadata = msgpack_numpy.unpackb(raw)
        return conn, metadata

    async def infer(self, obs: dict) -> dict:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, self._infer_sync, obs)

    def _infer_sync(self, obs: dict) -> dict:
        if self._ws is None:
            raise RuntimeError("Not connected")
        data = self._packer.pack(obs)
        try:
            self._ws.send(data)
            t0 = time.monotonic()
            logger.info("Waiting for inference response...")
            response = self._ws.recv(timeout=RECV_TIMEOUT)
            logger.info("Inference response received in %.1fs", time.monotonic() - t0)
        except TimeoutError:
            logger.error("OpenPI recv() timed out after %ds", RECV_TIMEOUT)
            raise
        except websockets.exceptions.ConnectionClosed:
            if self._closing:
                raise
            logger.warning("OpenPI connection lost, reconnecting (attempt 1/1)...")
            try:
                self._ws, self._server_metadata = self._connect_sync()
            except Exception:
                logger.error("Reconnect failed")
                raise
            data = self._packer.pack(obs)
            self._ws.send(data)
            t0 = time.monotonic()
            logger.info("Waiting for inference response (after reconnect)...")
            response = self._ws.recv(timeout=RECV_TIMEOUT)
            logger.info("Inference response received in %.1fs", time.monotonic() - t0)
        if isinstance(response, str):
            raise RuntimeError(f"Error in inference server:\n{response}")
        return msgpack_numpy.unpackb(response)

    async def reset(self) -> None:
        pass

    async def close(self) -> None:
        self._closing = True
        if self._ws is not None:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(self._executor, self._ws.close)
            self._ws = None
        self._executor.shutdown(wait=False)
