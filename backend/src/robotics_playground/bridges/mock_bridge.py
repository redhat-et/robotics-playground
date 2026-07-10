from __future__ import annotations

import asyncio
import math
from collections.abc import AsyncIterator

import numpy as np

from robotics_playground.bridges.protocol import Action, Observation


class MockBridge:
    def __init__(self) -> None:
        self._step = 0

    @property
    def bridge_status(self) -> str:
        return "mock"

    async def start(self) -> None:
        pass

    async def get_observation(self) -> Observation:
        t = self._step * 0.1
        image = np.zeros((240, 320, 3), dtype=np.uint8)
        image[:, :, 0] = np.arange(320) * 255 // 320
        image[:, :, 1] = int(127 + 127 * math.sin(t))

        positions = [math.sin(t + i * math.pi / 3) for i in range(6)]
        velocities = [math.cos(t + i * math.pi / 3) for i in range(6)]

        obs = Observation(
            step=self._step,
            cameras={"wrist": image},
            joint_positions=positions,
            joint_velocities=velocities,
        )
        self._step += 1
        await asyncio.sleep(0.01)
        return obs

    async def observation_stream(self) -> AsyncIterator[Observation]:
        while True:
            yield await self.get_observation()

    async def send_action(self, action: Action) -> None:
        pass

    async def sim_control(self, action: str, speed: float | None = None) -> None:
        pass

    async def close(self) -> None:
        pass
