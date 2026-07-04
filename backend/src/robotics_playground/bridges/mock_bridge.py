from __future__ import annotations

import asyncio
import math
from collections.abc import AsyncIterator

import numpy as np

from robotics_playground.bridges.protocol import Action, Observation


class MockBridge:
    @property
    def bridge_status(self) -> str:
        return "mock"

    async def start(self) -> None:
        pass

    async def observation_stream(self) -> AsyncIterator[Observation]:
        step = 0
        dt = 0.1
        while True:
            t = step * dt
            image = np.zeros((240, 320, 3), dtype=np.uint8)
            image[:, :, 0] = np.arange(320) * 255 // 320
            image[:, :, 1] = int(127 + 127 * math.sin(t))

            positions = [math.sin(t + i * math.pi / 3) for i in range(6)]
            velocities = [math.cos(t + i * math.pi / 3) for i in range(6)]

            yield Observation(
                step=step,
                cameras={"wrist": image},
                joint_positions=positions,
                joint_velocities=velocities,
            )
            step += 1
            await asyncio.sleep(dt)

    async def send_action(self, action: Action) -> None:
        pass

    async def sim_control(self, action: str, speed: float | None = None) -> None:
        pass

    async def close(self) -> None:
        pass
