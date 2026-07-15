from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, TypedDict

import numpy as np


class Observation(TypedDict):
    step: int
    cameras: dict[str, np.ndarray]
    joint_positions: list[float]
    joint_velocities: list[float]


class Action(TypedDict):
    joint_positions: list[float]
    joint_velocities: list[float]
    gripper_position: float


class RobotBridge(Protocol):
    @property
    def bridge_status(self) -> str: ...

    async def start(self) -> None: ...

    async def get_observation(self) -> Observation: ...

    async def get_latest_observation(self) -> Observation | None: ...

    def observation_stream(self) -> AsyncIterator[Observation]: ...

    async def send_action(self, action: Action) -> None: ...

    async def sim_control(self, action: str, speed: float | None = None) -> None: ...

    async def close(self) -> None: ...
