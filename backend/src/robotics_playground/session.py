from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from typing import TYPE_CHECKING

import numpy as np

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from robotics_playground.bridges.protocol import RobotBridge
    from robotics_playground.policy.embodiment_adapter import EmbodimentAdapter
    from robotics_playground.policy.protocol import PolicyClient
    from robotics_playground.rerun_logger import RerunLogger


class Session:
    def __init__(
        self,
        bridge: RobotBridge,
        policy: PolicyClient,
        adapter: EmbodimentAdapter,
        rerun_logger: RerunLogger,
    ):
        self._bridge = bridge
        self._policy = policy
        self._adapter = adapter
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

    @property
    def bridge_status(self) -> str:
        return self._bridge.bridge_status

    def send_instruction(self, text: str):
        self._instruction = text

    async def start(self):
        if self._task is not None:
            return
        self._paused.set()
        await self._bridge.start()
        await self._policy.connect()
        self._state = "running"
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
        await self._policy.close()
        await self._bridge.close()
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
        self._logger.clear()
        self._instruction = ""

    async def handle_sim_control(self, action: str, speed: float | None = None):
        if action == "play":
            if self._state == "idle":
                await self.start()
            else:
                self.resume()
            await self._bridge.sim_control("play", speed=speed)
        elif action == "pause":
            self.pause()
            await self._bridge.sim_control("pause")
        elif action == "stop":
            await self._bridge.sim_control("stop")
            await self.stop()
        elif action == "step":
            if self._state == "idle":
                await self.start()
                self.pause()
            await self._bridge.sim_control("step")
            self.step_once()
        elif action == "reset":
            await self._bridge.sim_control("reset")
            await self.reset()

    async def _run_loop(self):
        try:
            # Initial observation
            obs = await self._bridge.get_observation()

            while True:
                # Wait for unpause
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

                # Log current observation
                self._step = obs["step"]
                self._logger.log_observation(obs, obs["step"])

                if self._instruction:
                    self._logger.log_instruction(self._instruction, obs["step"])

                # Normalize and infer
                openpi_obs = self._adapter.observation_to_openpi(obs, self._instruction)
                t0 = time.monotonic()
                raw_action = await self._policy.infer(openpi_obs)
                inference_ms = (time.monotonic() - t0) * 1000

                # Normalize response: server may return a raw ndarray or a dict
                if isinstance(raw_action, np.ndarray):
                    actions_tensor = raw_action
                elif isinstance(raw_action, dict):
                    actions_tensor = raw_action.get("actions", next(iter(raw_action.values())))
                else:
                    actions_tensor = raw_action

                # Log ML debug path
                self._logger.log_raw_action_tensor(actions_tensor, self._step)
                self._logger.log_inference_latency(inference_ms, self._step)

                # Denormalize
                action_chunk = self._adapter.action_chunk_from_openpi(actions_tensor)

                # Log physical trajectory path
                self._logger.log_action_trajectory(action_chunk, self._step)

                # Execute action chunk and consume observations
                for action in action_chunk:
                    await self._bridge.send_action(action)
                    await self._bridge.sim_control("step")
                    obs = await self._bridge.get_observation()
                    self._step = obs["step"]

                    if not self._paused.is_set() or stepping:
                        break

                if stepping:
                    self._paused.clear()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Run loop crashed")
            self._state = "error"
