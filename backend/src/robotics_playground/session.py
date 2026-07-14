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


DEFAULT_INSTRUCTION = "Stay still and do not move."


class Session:
    def __init__(
        self,
        bridge: RobotBridge,
        policy: PolicyClient,
        adapter: EmbodimentAdapter,
        rerun_logger: RerunLogger,
        action_horizon: int = 4,
        observation_timeout: float = 10.0,
    ):
        self._bridge = bridge
        self._policy = policy
        self._adapter = adapter
        self._logger = rerun_logger
        self._action_horizon = action_horizon
        self._observation_timeout = observation_timeout
        self._task: asyncio.Task | None = None
        self._instruction: str = DEFAULT_INSTRUCTION
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
        logger.info("Session starting: policy.connect()")
        self._paused.set()
        await self._policy.connect()
        self._state = "running"
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Session started, run loop task created")

    async def stop(self):
        if self._task is None:
            return
        await self._bridge.sim_control("pause")
        self._task.cancel()
        self._paused.set()
        self._step_once.clear()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None
        await self._policy.close()
        self._state = "idle"
        self._step = 0

    async def pause(self):
        if self._state == "running":
            await self._bridge.sim_control("pause")
            self._paused.clear()
            self._state = "paused"

    async def resume(self):
        if self._state == "paused":
            await self._bridge.sim_control("play")
            self._paused.set()
            self._state = "running"

    def step_once(self):
        if self._state == "paused":
            self._step_once.set()

    async def reset(self):
        await self.stop()
        await self._bridge.sim_control("reset")
        self._logger.clear()
        self._instruction = DEFAULT_INSTRUCTION

    async def handle_sim_control(self, action: str, speed: float | None = None):
        logger.info("handle_sim_control(%s), current state=%s", action, self._state)
        if action == "play":
            if self._state == "idle":
                await self.start()
            else:
                await self.resume()
        elif action == "pause":
            await self.pause()
        elif action == "stop":
            await self.stop()
        elif action == "step":
            if self._state == "idle":
                await self.start()
                await self.pause()
            await self._bridge.sim_control("step")
            self.step_once()
        elif action == "reset":
            await self.reset()

    async def _run_loop(self):
        try:
            self._logger.clear()

            # Start sim in play mode and wait for observations with cameras.
            # The sim runs continuously; early observations may lack cameras
            # while Zenoh routes are being established.
            logger.info("Run loop: starting sim and waiting for camera data...")
            await self._bridge.sim_control("play")
            expected_cams = set(self._adapter.camera_names)
            max_camera_wait = 200
            wait_iters = 0
            while True:
                try:
                    obs = await asyncio.wait_for(self._bridge.get_observation(), timeout=2.0)
                except TimeoutError:
                    obs = {}
                if expected_cams and expected_cams <= set(obs.get("cameras", {})):
                    break
                if not expected_cams and obs.get("cameras"):
                    break
                wait_iters += 1
                if wait_iters > max_camera_wait:
                    logger.error(
                        "No camera data after %d attempts, aborting run loop",
                        max_camera_wait,
                    )
                    self._state = "error"
                    return
            logger.info("Run loop: got first observation at step %s", obs.get("step", "?"))

            # Teleport arm to manipulation-ready pose after Zenoh routes are up.
            # Send multiple times to ensure delivery through Zenoh.
            logger.info("Run loop: teleporting arm to home position...")
            for _ in range(3):
                await self._bridge.sim_control("reset")
            try:
                obs = await asyncio.wait_for(self._bridge.get_observation(), timeout=5.0)
            except TimeoutError:
                logger.error("No observation after teleport, aborting run loop")
                self._state = "error"
                return
            logger.info(
                "Run loop: arm reset complete, joints: %s",
                [round(p, 4) for p in obs.get("joint_positions", [])[:7]],
            )
            display_step = 0

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

                # Get latest observation from continuous stream
                obs = await asyncio.wait_for(
                    self._bridge.get_observation(),
                    timeout=self._observation_timeout,
                )
                self._step = display_step
                self._logger.log_observation(obs, display_step)

                if self._instruction:
                    self._logger.log_instruction(self._instruction, display_step)

                # Normalize and infer
                logger.info(
                    "Current joints: %s",
                    [round(p, 4) for p in obs["joint_positions"][:7]],
                )
                openpi_obs = self._adapter.observation_to_openpi(obs, self._instruction)
                logger.info(
                    "Calling policy.infer() at step %s, instruction=%r",
                    self._step,
                    self._instruction,
                )

                async def _keep_sim_alive():
                    while True:
                        await self._bridge.sim_control("step")
                        with contextlib.suppress(TimeoutError):
                            await asyncio.wait_for(self._bridge.get_observation(), timeout=2.0)
                        await asyncio.sleep(0.5)

                keepalive = asyncio.create_task(_keep_sim_alive())
                t0 = time.monotonic()
                try:
                    raw_action = await self._policy.infer(openpi_obs)
                finally:
                    keepalive.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await keepalive
                inference_ms = (time.monotonic() - t0) * 1000
                logger.info("Inference returned in %.1fms", inference_ms)

                # Normalize response: server may return a raw ndarray or a dict
                if isinstance(raw_action, np.ndarray):
                    actions_tensor = raw_action
                elif isinstance(raw_action, dict):
                    actions_tensor = raw_action.get("actions", next(iter(raw_action.values())))
                else:
                    actions_tensor = raw_action

                # Log ML debug path
                self._logger.log_raw_action_tensor(actions_tensor, display_step)
                self._logger.log_inference_latency(inference_ms, display_step)

                # Denormalize
                action_chunk = self._adapter.action_chunk_from_openpi(actions_tensor)
                logger.info("Action chunk: %d actions", len(action_chunk))
                if action_chunk:
                    a = action_chunk[0]
                    logger.info(
                        "First action: joints=%s, gripper=%.4f",
                        [round(p, 4) for p in a["joint_positions"]],
                        a["gripper_position"],
                    )

                # Log physical trajectory path
                self._logger.log_action_trajectory(action_chunk, display_step)

                # Send actions spaced apart so PD controller can track each
                # waypoint before receiving the next target.
                horizon = action_chunk[: self._action_horizon]
                action_interval = inference_ms / 1000 / max(len(horizon), 1)
                for action in horizon:
                    await self._bridge.send_action(action)
                    display_step += 1
                    self._step = display_step

                    if not self._paused.is_set() or stepping:
                        break
                    await asyncio.sleep(action_interval)

                if stepping:
                    self._paused.clear()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Run loop crashed")
            self._state = "error"
