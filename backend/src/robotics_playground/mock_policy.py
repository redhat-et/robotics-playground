from __future__ import annotations

import asyncio

import numpy as np


async def predict_action(observation: dict) -> np.ndarray:
    """Mock policy: random actions with simulated inference latency."""
    await asyncio.sleep(0.05)
    return np.random.uniform(-1.0, 1.0, size=(6,)).astype(np.float32)
