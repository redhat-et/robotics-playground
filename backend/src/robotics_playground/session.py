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
        self._paused = asyncio.Event()
        self._paused.set()
        self._step_once = asyncio.Event()

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
        self._paused.set()
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self):
        if self._task is None:
            return
        self._task.cancel()
        self._paused.set()
        self._step_once.clear()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None
        self._state = "idle"
        self._step = 0

    def pause(self):
        if self._state == "running":
            self._paused.clear()
            self._state = "paused"

    def resume(self):
        if self._state == "paused":
            self._paused.set()
            self._state = "running"

    def step_once(self):
        if self._state == "paused":
            self._step_once.set()

    async def reset(self):
        await self.stop()
        self._instruction = ""

    async def handle_sim_control(self, action: str):
        if action == "play":
            if self._state == "idle":
                await self.start()
            else:
                self.resume()
        elif action == "pause":
            self.pause()
        elif action == "stop":
            await self.stop()
        elif action == "step":
            if self._state == "idle":
                await self.start()
                self.pause()
            self.step_once()
        elif action == "reset":
            await self.reset()

    async def _run_loop(self):
        try:
            async for obs in observation_stream():
                paused_future = asyncio.ensure_future(self._paused.wait())
                step_future = asyncio.ensure_future(self._step_once.wait())
                try:
                    _, pending = await asyncio.wait(
                        [paused_future, step_future],
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    for f in pending:
                        f.cancel()
                finally:
                    paused_future.cancel()
                    step_future.cancel()

                stepping = self._step_once.is_set()
                if stepping:
                    self._step_once.clear()

                self._step = obs["step"]
                self._logger.log_observation(obs["image"], obs["joint_positions"], obs["step"])

                if self._instruction:
                    self._logger.log_instruction(self._instruction, obs["step"])

                action = await predict_action(obs)
                self._logger.log_action(action, obs["step"])

                if stepping:
                    self._paused.clear()
        except asyncio.CancelledError:
            raise
