from __future__ import annotations

import asyncio
import contextlib

from robotics_playground.mock_policy import predict_action
from robotics_playground.mock_robot import observation_stream
from robotics_playground.rerun_logger import RerunLogger


class Session:
    def __init__(self, rerun_logger: RerunLogger):
        self._logger = rerun_logger
        self._task: asyncio.Task | None = None
        self._instruction: str = ""
        self._state: str = "idle"
        self._step: int = 0

    @property
    def state(self) -> str:
        return self._state

    @property
    def step(self) -> int:
        return self._step

    @property
    def instruction(self) -> str:
        return self._instruction

    def send_instruction(self, text: str):
        self._instruction = text

    async def start(self):
        if self._task is not None:
            return
        self._state = "running"
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self):
        if self._task is None:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None
        self._state = "idle"
        self._step = 0

    async def _run_loop(self):
        try:
            async for obs in observation_stream():
                self._step = obs["step"]
                self._logger.log_observation(obs["image"], obs["joint_positions"], obs["step"])

                if self._instruction:
                    self._logger.log_instruction(self._instruction, obs["step"])

                action = await predict_action(obs)
                self._logger.log_action(action, obs["step"])
        except asyncio.CancelledError:
            raise
