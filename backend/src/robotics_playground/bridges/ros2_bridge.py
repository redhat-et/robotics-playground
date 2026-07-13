from __future__ import annotations

import asyncio
import contextlib
import logging
import threading
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

import numpy as np

from robotics_playground.bridges.protocol import Action, Observation

if TYPE_CHECKING:
    from robotics_playground.config import ROS2Config

logger = logging.getLogger(__name__)


class ROS2Bridge:
    def __init__(self, config: ROS2Config):
        self._config = config
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

    @property
    def bridge_status(self) -> str:
        return self._status

    async def start(self) -> None:
        import rclpy
        from rclpy.executors import SingleThreadedExecutor
        from rclpy.node import Node

        self._loop = asyncio.get_running_loop()

        if not rclpy.ok():
            rclpy.init(domain_id=self._config.domain_id)
            self._owns_rclpy = True
        self._node = Node("robotics_playground_bridge")
        self._executor = SingleThreadedExecutor()
        self._executor.add_node(self._node)

        from sensor_msgs.msg import Image, JointState

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

        from std_msgs.msg import Int32

        self._Int32 = Int32
        self._sim_state_pub = self._node.create_publisher(Int32, "/sim_control/state", 10)
        self._step_pub = self._node.create_publisher(Int32, "/sim_control/step", 10)
        self._teleport_pub = self._node.create_publisher(Int32, "/sim_control/teleport", 10)

        self._spin_thread = threading.Thread(target=self._spin, daemon=True)
        self._spin_thread.start()
        self._status = "connected"

    def _spin(self):
        while (executor := self._executor) is not None:
            executor.spin_once(timeout_sec=0.1)

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
        # Drain stale observations, keep the freshest
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
        if self._executor is not None:
            self._executor.shutdown()
            self._executor = None
        if self._spin_thread is not None:
            self._spin_thread.join(timeout=2.0)
            self._spin_thread = None
        if self._node is not None:
            self._node.destroy_node()
            self._node = None
        if self._owns_rclpy:
            import rclpy

            rclpy.shutdown()
            self._owns_rclpy = False
        self._status = "disconnected"
