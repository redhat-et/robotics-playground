from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from typing import TYPE_CHECKING

import numpy as np

from robotics_playground.policy import create_policy
from robotics_playground.policy.embodiment_adapter import EmbodimentAdapter

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from robotics_playground.bridges.protocol import RobotBridge
    from robotics_playground.config import PolicyConfig
    from robotics_playground.policy.protocol import PolicyClient
    from robotics_playground.rerun_logger import RerunLogger


DEFAULT_INSTRUCTION = "Stay still and do not move."
ACTION_INTERVAL = 0.5  # seconds between waypoints — PD controller convergence time


class Session:
    def __init__(
        self,
        bridge: RobotBridge,
        policy_config: PolicyConfig,
        rerun_logger: RerunLogger,
        observation_timeout: float = 10.0,
    ):
        self._bridge = bridge
        self._policy_config = policy_config
        self._logger = rerun_logger
        self._model_id = policy_config.default_model
        self._policy: PolicyClient | None = None
        self._adapter: EmbodimentAdapter | None = None
        self._action_horizon: int = 4
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

    @property
    def model_id(self) -> str:
        return self._model_id

    def send_instruction(self, text: str):
        self._instruction = text

    def select_model(self, model_id: str) -> None:
        if self._state != "idle":
            raise ValueError("Model can only be changed while idle")
        if model_id not in self._policy_config.models:
            raise ValueError(f"Unknown model: {model_id}")
        self._model_id = model_id

    async def start(self):
        if self._task is not None:
            return

        model_config = self._policy_config.models.get(self._model_id)
        if model_config:
            self._action_horizon = model_config.action_horizon
            camera_override = model_config.camera_mapping
            self._adapter = EmbodimentAdapter(
                self._policy_config.embodiment,
                camera_mapping_override=camera_override,
                action_type=model_config.action_type,
            )
            self._policy = create_policy(self._policy_config.type, model_config.endpoint)
        elif not self._policy_config.models:
            # Mock mode: no models configured
            self._adapter = EmbodimentAdapter(self._policy_config.embodiment)
            self._policy = create_policy(self._policy_config.type, "")
        else:
            raise ValueError(
                f"Model '{self._model_id}' not found in config. "
                f"Available models: {list(self._policy_config.models.keys())}"
            )

        logger.info("Session starting: policy.connect() for model %s", self._model_id)
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
        if self._policy:
            await self._policy.close()
            self._policy = None
        self._adapter = None
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

    async def _dispatch_actions(self, horizon, start_step) -> int:
        dispatched = 0
        for i, action in enumerate(horizon):
            if i > 0 and not self._paused.is_set():
                break
            await self._bridge.send_action(action)
            dispatched = i + 1
            self._step = start_step + dispatched
            await asyncio.sleep(ACTION_INTERVAL)
        return dispatched

    async def _run_loop(self):
        try:
            assert self._adapter is not None
            assert self._policy is not None

            self._logger.clear()

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
            cycle = 0

            while True:
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

                obs = await asyncio.wait_for(
                    self._bridge.get_observation(),
                    timeout=self._observation_timeout,
                )
                self._step = display_step
                self._logger.log_observation(obs, display_step)

                if self._instruction:
                    self._logger.log_instruction(self._instruction, display_step)

                logger.info(
                    "Current joints: %s",
                    [round(p, 4) for p in obs["joint_positions"][:7]],
                )
                openpi_obs = self._adapter.observation_to_openpi(obs, self._instruction)
                cycle += 1
                logger.info(
                    "Inference cycle %d: starting at step %d, instruction=%r",
                    cycle,
                    self._step,
                    self._instruction,
                )

                t0 = time.monotonic()
                raw_action = await self._policy.infer(openpi_obs)
                inference_ms = (time.monotonic() - t0) * 1000
                logger.info(
                    "Inference cycle %d: completed in %.1fms",
                    cycle,
                    inference_ms,
                )

                if isinstance(raw_action, np.ndarray):
                    actions_tensor = raw_action
                elif isinstance(raw_action, dict):
                    actions_tensor = raw_action.get("actions", next(iter(raw_action.values())))
                else:
                    actions_tensor = raw_action

                self._logger.log_raw_action_tensor(actions_tensor, display_step)
                self._logger.log_inference_latency(inference_ms, display_step)

                action_chunk = self._adapter.action_chunk_from_openpi(
                    actions_tensor, current_obs=obs
                )
                logger.info("Action chunk: %d actions", len(action_chunk))
                if action_chunk:
                    a = action_chunk[0]
                    logger.info(
                        "First action: joints=%s, gripper=%.4f",
                        [round(p, 4) for p in a["joint_positions"]],
                        a["gripper_position"],
                    )

                self._logger.log_action_trajectory(action_chunk, display_step)

                horizon = action_chunk[: self._action_horizon]
                logger.info(
                    "Inference cycle %d: dispatching %d actions at %.1fs intervals",
                    cycle,
                    len(horizon),
                    ACTION_INTERVAL,
                )
                dispatched = await self._dispatch_actions(horizon, display_step)
                display_step += dispatched

                if stepping:
                    self._paused.clear()

        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Run loop crashed")
            self._state = "error"
