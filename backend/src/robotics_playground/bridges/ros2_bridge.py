from __future__ import annotations

import asyncio
import contextlib
import logging
import threading
import time
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

import numpy as np

from robotics_playground.bridges.protocol import Action, Observation
from robotics_playground.config import BridgeConfig

if TYPE_CHECKING:
    from robotics_playground.config import ROS2Config

logger = logging.getLogger(__name__)


class ROS2Bridge:
    def __init__(self, config: ROS2Config, bridge_config: BridgeConfig | None = None):
        self._config = config
        bc = bridge_config or BridgeConfig()
        self._watchdog_timeout = bc.watchdog_timeout
        self._reconnect_delay = bc.reconnect_delay
        self._max_reconnect_delay = bc.max_reconnect_delay

        self._node = None
        self._executor = None
        self._spin_thread: threading.Thread | None = None
        self._obs_queue: asyncio.Queue[Observation] = asyncio.Queue(maxsize=10)
        self._step = 0
        self._latest_cameras: dict[str, np.ndarray] = {}
        self._latest_joint_positions: list[float] = []
        self._latest_joint_velocities: list[float] = []
        self._loop: asyncio.AbstractEventLoop | None = None
        self._status = "disconnected"
        self._publisher = None
        self._owns_rclpy = False
        self._sim_state_pub = None
        self._step_pub = None
        self._teleport_pub = None
        self._Int32 = None
        self._last_obs_time: float = 0.0
        self._connect_time: float = 0.0
        self._watchdog_task: asyncio.Task | None = None
        self._sim_paused = False

    @property
    def bridge_status(self) -> str:
        return self._status

    def _setup_node(self) -> None:
        from rclpy.executors import SingleThreadedExecutor
        from rclpy.node import Node
        from sensor_msgs.msg import Image, JointState
        from std_msgs.msg import Int32

        self._node = Node("robotics_playground_bridge")
        self._executor = SingleThreadedExecutor()
        self._executor.add_node(self._node)

        for name, topic in self._config.cameras.items():
            self._node.create_subscription(
                Image,
                topic,
                lambda msg, n=name: self._handle_image(n, msg),
                10,
            )

        self._node.create_subscription(
            JointState,
            self._config.joint_state_topic,
            self._handle_joint_state,
            10,
        )

        self._publisher = self._node.create_publisher(
            JointState,
            self._config.joint_command_topic,
            10,
        )

        self._Int32 = Int32
        self._sim_state_pub = self._node.create_publisher(Int32, "/sim_control/state", 10)
        self._step_pub = self._node.create_publisher(Int32, "/sim_control/step", 10)
        self._teleport_pub = self._node.create_publisher(Int32, "/sim_control/teleport", 10)

        self._spin_thread = threading.Thread(target=self._spin, daemon=True)
        self._spin_thread.start()

        self._connect_time = time.monotonic()
        self._status = "connecting"
        logger.info("ROS 2 node created, status=connecting")

    def _teardown_node(self) -> None:
        if self._executor is not None:
            self._executor.shutdown()
            self._executor = None
        if self._spin_thread is not None:
            self._spin_thread.join(timeout=2.0)
            self._spin_thread = None
        if self._node is not None:
            self._node.destroy_node()
            self._node = None
        self._publisher = None
        self._sim_state_pub = None
        self._step_pub = None
        self._teleport_pub = None
        self._status = "disconnected"
        logger.info("ROS 2 node torn down, status=disconnected")

    async def start(self) -> None:
        import rclpy

        self._loop = asyncio.get_running_loop()

        if not rclpy.ok():
            rclpy.init(domain_id=self._config.domain_id)
            self._owns_rclpy = True

        self._setup_node()
        self._watchdog_task = asyncio.create_task(self._watchdog())

    async def _reconnect(self) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._teardown_node)
        await loop.run_in_executor(None, self._setup_node)

    async def _watchdog(self) -> None:
        delay = self._reconnect_delay
        while True:
            await asyncio.sleep(2.0)

            if self._status == "disconnected" or self._sim_paused:
                continue

            now = time.monotonic()

            try:
                if self._status == "connecting":
                    if now - self._connect_time > self._watchdog_timeout:
                        logger.warning(
                            "No observations received after %.1fs, reconnecting...",
                            now - self._connect_time,
                        )
                        await self._reconnect()
                        await asyncio.sleep(delay)
                        delay = min(delay * 2, self._max_reconnect_delay)
                    continue

                elapsed = now - self._last_obs_time
                if elapsed > self._watchdog_timeout:
                    logger.warning(
                        "No observations for %.1fs (timeout=%.1fs), reconnecting...",
                        elapsed,
                        self._watchdog_timeout,
                    )
                    await self._reconnect()
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, self._max_reconnect_delay)
                else:
                    delay = self._reconnect_delay
            except Exception:
                logger.exception("Watchdog reconnect attempt failed; will retry")

    def _spin(self):
        while (executor := self._executor) is not None:
            executor.spin_once(timeout_sec=0.1)
            # Yield the GIL so the uvloop event loop can run.
            # spin_once returns immediately when callbacks are pending
            # (the timeout only applies to the idle wait), so without
            # this sleep the loop busy-spins and starves the event loop.
            time.sleep(0.001)

    def _handle_image(self, camera_name: str, msg):
        logger.debug("Image received: %s (%dx%d)", camera_name, msg.width, msg.height)
        data = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.width, -1)
        self._on_image_received(camera_name, data)

    def _handle_joint_state(self, msg):
        logger.debug("Joint state received: %d joints", len(msg.position))
        self._on_joint_state_received(list(msg.position), list(msg.velocity))

    def _enqueue_observation(self):
        if self._loop is None or not self._latest_joint_positions:
            return

        self._last_obs_time = time.monotonic()

        if self._status == "connecting":
            self._status = "connected"
            logger.info("First observation received, status=connected")

        obs = Observation(
            step=self._step,
            cameras=dict(self._latest_cameras),
            joint_positions=list(self._latest_joint_positions),
            joint_velocities=list(self._latest_joint_velocities),
        )
        self._step += 1
        self._loop.call_soon_threadsafe(self._try_put, obs)

    def _try_put(self, obs: Observation):
        with contextlib.suppress(asyncio.QueueFull):
            self._obs_queue.put_nowait(obs)

    def _on_image_received(self, camera_name: str, image: np.ndarray):
        self._latest_cameras[camera_name] = image
        self._enqueue_observation()

    def _on_joint_state_received(self, positions: list[float], velocities: list[float]):
        self._latest_joint_positions = positions
        self._latest_joint_velocities = velocities
        self._enqueue_observation()

    async def get_observation(self) -> Observation:
        obs = await self._obs_queue.get()
        while not self._obs_queue.empty():
            obs = self._obs_queue.get_nowait()
        return obs

    async def observation_stream(self) -> AsyncIterator[Observation]:
        while True:
            obs = await self._obs_queue.get()
            yield obs

    async def send_action(self, action: Action) -> None:
        if self._publisher is None or self._node is None:
            return
        from sensor_msgs.msg import JointState

        msg = JointState()
        msg.position = [float(p) for p in action["joint_positions"]] + [
            float(action["gripper_position"])
        ]
        msg.velocity = [float(v) for v in action["joint_velocities"]] + [float("nan")]
        self._publisher.publish(msg)

    async def sim_control(self, action: str, speed: float | None = None) -> None:
        if self._node is None:
            return

        if action in ("play", "pause", "stop"):
            self._sim_paused = action in ("pause", "stop")
            state_map = {"stop": 0, "play": 1, "pause": 2}
            if self._sim_state_pub is not None:
                msg = self._Int32()
                msg.data = state_map[action]
                self._sim_state_pub.publish(msg)

        elif action == "step":
            if self._step_pub is not None:
                msg = self._Int32()
                msg.data = self._config.physics_decimation
                self._step_pub.publish(msg)

        elif action == "reset":
            if self._teleport_pub is not None:
                msg = self._Int32()
                msg.data = 1
                self._teleport_pub.publish(msg)
            self._step = 0

    async def close(self) -> None:
        if self._watchdog_task is not None:
            self._watchdog_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._watchdog_task
            self._watchdog_task = None
        self._teardown_node()
        if self._owns_rclpy:
            import rclpy

            rclpy.shutdown()
            self._owns_rclpy = False
