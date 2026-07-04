from __future__ import annotations

import asyncio
import contextlib
import threading
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

import numpy as np

from robotics_playground.bridges.protocol import Action, Observation

if TYPE_CHECKING:
    from robotics_playground.config import ROS2Config


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
        self._sim_state_client = None
        self._step_client = None

    @property
    def bridge_status(self) -> str:
        return self._status

    async def start(self) -> None:
        import rclpy
        from rclpy.executors import SingleThreadedExecutor
        from rclpy.node import Node

        self._loop = asyncio.get_running_loop()

        rclpy.init(domain_id=self._config.domain_id)
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

        from trajectory_msgs.msg import JointTrajectory

        self._publisher = self._node.create_publisher(
            JointTrajectory,
            self._config.joint_command_topic,
            10,
        )

        from simulation_interfaces.srv import SetSimulationState, StepSimulation

        self._sim_state_client = self._node.create_client(
            SetSimulationState, "/set_simulation_state"
        )
        self._step_client = self._node.create_client(StepSimulation, "/step_simulation")

        self._spin_thread = threading.Thread(target=self._spin, daemon=True)
        self._spin_thread.start()
        self._status = "connected"

    def _spin(self):
        while self._executor is not None:
            self._executor.spin_once(timeout_sec=0.1)

    def _handle_image(self, camera_name: str, msg):
        data = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.width, -1)
        self._on_image_received(camera_name, data)

    def _handle_joint_state(self, msg):
        self._on_joint_state_received(list(msg.position), list(msg.velocity))

    def _on_image_received(self, camera_name: str, image: np.ndarray):
        self._latest_cameras[camera_name] = image
        if self._latest_joint_positions and self._loop is not None:
            obs = Observation(
                step=self._step,
                cameras=dict(self._latest_cameras),
                joint_positions=list(self._latest_joint_positions),
                joint_velocities=list(self._latest_joint_velocities),
            )
            self._step += 1
            with contextlib.suppress(asyncio.QueueFull):
                self._loop.call_soon_threadsafe(self._obs_queue.put_nowait, obs)

    def _on_joint_state_received(self, positions: list[float], velocities: list[float]):
        self._latest_joint_positions = positions
        self._latest_joint_velocities = velocities

    async def observation_stream(self) -> AsyncIterator[Observation]:
        while True:
            obs = await self._obs_queue.get()
            yield obs

    async def send_action(self, action: Action) -> None:
        if self._publisher is None or self._node is None:
            return
        from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint

        msg = JointTrajectory()
        point = JointTrajectoryPoint()
        point.positions = [float(p) for p in action["joint_positions"]]
        msg.points = [point]
        self._publisher.publish(msg)

    async def sim_control(self, action: str, speed: float | None = None) -> None:
        if self._node is None:
            return

        if action in ("play", "pause", "stop"):
            from simulation_interfaces.srv import SetSimulationState

            state_map = {"stop": 0, "play": 1, "pause": 2}
            req = SetSimulationState.Request()
            req.state.data = state_map[action]
            if self._sim_state_client is not None:
                await asyncio.get_running_loop().run_in_executor(
                    None, lambda: self._sim_state_client.call(req)
                )

        elif action == "step":
            from simulation_interfaces.srv import StepSimulation

            req = StepSimulation.Request()
            req.num_steps = 1
            if self._step_client is not None:
                await asyncio.get_running_loop().run_in_executor(
                    None, lambda: self._step_client.call(req)
                )

        elif action == "reset":
            from simulation_interfaces.srv import SetSimulationState

            req = SetSimulationState.Request()
            req.state.data = 0
            if self._sim_state_client is not None:
                await asyncio.get_running_loop().run_in_executor(
                    None, lambda: self._sim_state_client.call(req)
                )

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
        import rclpy

        rclpy.shutdown()
        self._status = "disconnected"
