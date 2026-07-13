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
        action_horizon: int = 4,
    ):
        self._bridge = bridge
        self._policy = policy
        self._adapter = adapter
        self._logger = rerun_logger
        self._action_horizon = action_horizon
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
        logger.info("Session starting: policy.connect()")
        self._paused.set()
        await self._policy.connect()
        self._state = "running"
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Session started, run loop task created")

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
        await self._bridge.sim_control("reset")
        self._logger.clear()
        self._instruction = ""

    async def handle_sim_control(self, action: str, speed: float | None = None):
        logger.info("handle_sim_control(%s), current state=%s", action, self._state)
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
            await self._bridge.sim_control("step")
            self.step_once()
        elif action == "reset":
            await self.reset()

    async def _run_loop(self):
        try:
            self._logger.clear()

            # Step until we get an observation with all expected cameras.
            # Early steps may be lost while Zenoh routes are being established,
            # so we retry with a short delay between attempts.
            logger.info("Run loop: waiting for first observation with cameras...")
            expected_cams = set(self._adapter.camera_names)
            max_camera_wait = 200
            wait_iters = 0
            while True:
                await self._bridge.sim_control("step")
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
            # This calls write_joint_state_to_sim on the Isaac Lab side —
            # instant, no physics stepping needed. Send multiple times to
            # ensure delivery through Zenoh.
            logger.info("Run loop: teleporting arm to home position...")
            for _ in range(3):
                await self._bridge.sim_control("reset")
            await self._bridge.sim_control("step")
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

                # Log current observation
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
                    "Calling policy.infer() at step %s, instruction=%r, obs_keys=%s",
                    self._step,
                    self._instruction,
                    list(openpi_obs.keys()),
                )
                t0 = time.monotonic()
                raw_action = await self._policy.infer(openpi_obs)
                inference_ms = (time.monotonic() - t0) * 1000
                logger.info(
                    "Inference returned in %.1fms, type=%s",
                    inference_ms,
                    type(raw_action).__name__,
                )

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
                    logger.info(
                        "Raw tensor[0]: %s",
                        np.array2string(actions_tensor[0], precision=4, suppress_small=True),
                    )

                # Log physical trajectory path
                self._logger.log_action_trajectory(action_chunk, display_step)

                # Execute action_horizon actions then re-infer
                for action in action_chunk[: self._action_horizon]:
                    await self._bridge.send_action(action)
                    await self._bridge.sim_control("step")
                    obs = await self._bridge.get_observation()
                    display_step += 1
                    self._step = display_step
                    self._logger.log_observation(obs, display_step)

                    if not self._paused.is_set() or stepping:
                        break

                if stepping:
                    self._paused.clear()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Run loop crashed")
            self._state = "error"
