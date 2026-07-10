from __future__ import annotations

import asyncio

import numpy as np


class MockClient:
    async def connect(self) -> None:
        pass

    async def infer(self, obs: dict) -> dict:
        await asyncio.sleep(0.05)
        actions = np.random.uniform(-1.0, 1.0, size=(10, 8)).astype(np.float32)
        return {"actions": actions}

    async def reset(self) -> None:
        pass

    async def close(self) -> None:
        pass
