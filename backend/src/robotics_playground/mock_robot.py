from __future__ import annotations

import asyncio
import math
import time

import numpy as np


async def observation_stream():
    """Yield mock observations at ~10 Hz."""
    step = 0
    while True:
        t = time.monotonic()
        image = np.zeros((240, 320, 3), dtype=np.uint8)
        # Simple gradient that shifts over time
        image[:, :, 0] = np.arange(320) * 255 // 320  # red gradient
        image[:, :, 1] = int(127 + 127 * math.sin(t))  # green pulses

        joint_positions = [math.sin(t + i * math.pi / 3) for i in range(6)]

        yield {
            "image": image,
            "joint_positions": joint_positions,
            "step": step,
        }
        step += 1
        await asyncio.sleep(0.1)
