from __future__ import annotations

import asyncio
import contextlib
import logging
import threading
import time
from collections.abc import AsyncIterator, Callable
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
        self._float_array_publisher = None
        self._owns_rclpy = False
        self._reset_simulation_client = None
        self._set_simulation_state_client = None
        self._step_simulation_client = None
        self._get_simulation_state_client = None
        self._sim_state: int | None = None  # STATE_STOPPED=0, STATE_PLAYING=1, STATE_PAUSED=2
        self._last_obs_time: float = 0.0
        self._connect_time: float = 0.0
        self._watchdog_task: asyncio.Task | None = None
        self._sim_paused = False
        self._last_state_query_time: float = 0.0
        self._enqueue_interval: float = 0.033  # ~30 Hz cap on cross-thread handoff
        self._last_enqueue_time: float = 0.0
        self._obs_listeners: list[Callable[[Observation], None]] = []

    @property
    def bridge_status(self) -> str:
        return self._status

    @property
    def sim_state(self) -> str:
        """Return sim state as string: idle/running/paused."""
        if self._sim_state is None:
            return "idle"  # Unknown state = assume idle
        state_map = {0: "idle", 1: "running", 2: "paused"}  # STATE_STOPPED/PLAYING/PAUSED
        return state_map.get(self._sim_state, "idle")

    def _setup_node(self) -> None:
        from rclpy.executors import SingleThreadedExecutor
        from rclpy.node import Node
        from rclpy.qos import QoSProfile, ReliabilityPolicy
        from sensor_msgs.msg import Image, JointState
        from simulation_interfaces.srv import (
            GetSimulationState,
            ResetSimulation,
            SetSimulationState,
            StepSimulation,
        )
        from std_msgs.msg import Float32MultiArray

        sensor_qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
        )

        self._node = Node("robotics_playground_bridge")
        self._executor = SingleThreadedExecutor()
        self._executor.add_node(self._node)

        for name, topic in self._config.cameras.items():
            self._node.create_subscription(
                Image,
                topic,
                lambda msg, n=name: self._handle_image(n, msg),
                sensor_qos,
            )

        use_float_array = self._config.state_msg_type == "Float32MultiArray"
        if use_float_array:
            self._node.create_subscription(
                Float32MultiArray,
                self._config.joint_state_topic,
                self._handle_float_array_state,
                sensor_qos,
            )
        else:
            self._node.create_subscription(
                JointState,
                self._config.joint_state_topic,
                self._handle_joint_state,
                sensor_qos,
            )

        if use_float_array:
            self._float_array_publisher = self._node.create_publisher(
                Float32MultiArray,
                self._config.joint_command_topic,
                10,
            )
        else:
            self._publisher = self._node.create_publisher(
                JointState,
                self._config.joint_command_topic,
                10,
            )

        # Standard simulation_interfaces service clients
        self._reset_simulation_client = self._node.create_client(
            ResetSimulation, "/reset_simulation"
        )
        self._set_simulation_state_client = self._node.create_client(
            SetSimulationState, "/set_simulation_state"
        )
        self._step_simulation_client = self._node.create_client(StepSimulation, "/step_simulation")
        self._get_simulation_state_client = self._node.create_client(
            GetSimulationState, "/get_simulation_state"
        )

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
        self._float_array_publisher = None
        self._reset_simulation_client = None
        self._set_simulation_state_client = None
        self._step_simulation_client = None
        self._get_simulation_state_client = None
        self._sim_state = None
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

    async def _query_simulation_state(self) -> None:
        """Query GetSimulationState service to sync backend view with simulator."""
        if self._get_simulation_state_client is None or self._loop is None:
            return

        from simulation_interfaces.srv import GetSimulationState

        try:
            request = GetSimulationState.Request()

            def on_response(f):
                try:
                    response = f.result()
                    old_state = self._sim_state
                    self._sim_state = response.state
                    if old_state is not None and old_state != response.state:
                        state_names = {0: "STOPPED", 1: "PLAYING", 2: "PAUSED"}
                        logger.info(
                            "Simulation state changed: %s -> %s",
                            state_names.get(old_state, old_state),
                            state_names.get(response.state, response.state),
                        )
                except Exception as exc:
                    logger.debug("GetSimulationState query failed: %s", exc)

            # Thread-safe service call
            def _make_call():
                future = self._get_simulation_state_client.call_async(request)
                future.add_done_callback(on_response)

            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, _make_call)
        except Exception as exc:
            logger.debug("GetSimulationState call failed: %s", exc)

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

                # Poll GetSimulationState periodically to detect drift
                if (
                    self._get_simulation_state_client is not None
                    and now - self._last_state_query_time > 5.0
                ):
                    self._last_state_query_time = now
                    await self._query_simulation_state()

            except Exception:
                logger.exception("Watchdog reconnect attempt failed; will retry")

    def _spin(self):
        while (executor := self._executor) is not None:
            executor.spin_once(timeout_sec=0.01)
            # Yield the GIL so the asyncio event loop can run.
            # Without this, the spin thread monopolises the GIL when
            # DDS callbacks arrive continuously (realtime sim mode).
            time.sleep(0.01)

    def _handle_image(self, camera_name: str, msg):
        logger.debug("Image received: %s (%dx%d)", camera_name, msg.width, msg.height)
        data = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.width, -1)
        self._on_image_received(camera_name, data)

    def _handle_joint_state(self, msg):
        logger.debug("Joint state received: %d joints", len(msg.position))
        self._on_joint_state_received(list(msg.position), list(msg.velocity))

    def _handle_float_array_state(self, msg):
        logger.debug("Float array state received: %d values", len(msg.data))
        self._on_joint_state_received(list(msg.data), [])

    def _enqueue_observation(self):
        if self._loop is None or not self._latest_joint_positions:
            return

        now = time.monotonic()
        self._last_obs_time = now

        if self._status == "connecting":
            self._status = "connected"
            logger.info("First observation received, status=connected")
            # Query initial simulation state
            if self._loop is not None:
                self._loop.create_task(self._query_simulation_state())

        if now - self._last_enqueue_time < self._enqueue_interval:
            return
        self._last_enqueue_time = now

        obs = Observation(
            step=self._step,
            cameras=dict(self._latest_cameras),
            joint_positions=list(self._latest_joint_positions),
            joint_velocities=list(self._latest_joint_velocities),
        )
        self._step += 1
        for cb in list(self._obs_listeners):
            cb(obs)
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

    async def get_latest_observation(self) -> Observation | None:
        if not self._latest_joint_positions or not self._latest_cameras:
            return None
        return Observation(
            step=self._step,
            cameras=dict(self._latest_cameras),
            joint_positions=list(self._latest_joint_positions),
            joint_velocities=list(self._latest_joint_velocities),
        )

    async def observation_stream(self) -> AsyncIterator[Observation]:
        while True:
            obs = await self._obs_queue.get()
            yield obs

    async def send_action(self, action: Action) -> None:
        if self._node is None:
            return
        from sensor_msgs.msg import JointState
        from std_msgs.msg import Float32MultiArray

        if self._publisher is not None:
            positions = [float(p) for p in action["joint_positions"]] + [
                float(action["gripper_position"])
            ]
            velocities = [float(v) for v in action["joint_velocities"]] + [float("nan")]
            msg = JointState()
            msg.position = positions
            msg.velocity = velocities
            self._publisher.publish(msg)

        if self._float_array_publisher is not None:
            msg = Float32MultiArray()
            msg.data = [float(v) for v in action["joint_positions"]]
            self._float_array_publisher.publish(msg)

    async def _call_service_async(self, client, request, timeout: float = 5.0):
        """Thread-safe service call that bridges ROS2 to asyncio.

        The service client's call_async must be invoked from a thread-safe context
        to avoid GIL violations and segfaults. We use a lock to ensure only one
        service call happens at a time.
        """
        loop = asyncio.get_running_loop()
        asyncio_future = loop.create_future()
        ros_future = None

        # Thread-safe service call with lock
        lock = threading.Lock()

        def _make_call():
            nonlocal ros_future
            with lock:
                ros_future = client.call_async(request)

                def on_done(f):
                    """Called by rclpy executor when service completes."""
                    if asyncio_future.done():
                        return  # Already timed out or cancelled
                    try:
                        result = f.result()
                        loop.call_soon_threadsafe(asyncio_future.set_result, result)
                    except Exception as exc:
                        loop.call_soon_threadsafe(asyncio_future.set_exception, exc)

                ros_future.add_done_callback(on_done)

        # Run the call on the executor to avoid threading issues
        await loop.run_in_executor(None, _make_call)

        try:
            return await asyncio.wait_for(asyncio_future, timeout=timeout)
        except TimeoutError as exc:
            raise TimeoutError(f"Service call timed out after {timeout}s") from exc

    async def sim_control(self, action: str, speed: float | None = None) -> None:
        if self._node is None:
            return

        from simulation_interfaces.srv import (
            ResetSimulation,
            SetSimulationState,
            StepSimulation,
        )

        if action in ("play", "pause", "stop"):
            state_map = {"stop": 0, "play": 1, "pause": 2}
            if self._set_simulation_state_client is not None:
                request = SetSimulationState.Request()
                request.state = state_map[action]
                try:
                    response = await self._call_service_async(
                        self._set_simulation_state_client, request, timeout=5.0
                    )
                    if not response.success:
                        logger.warning("SetSimulationState(%s) returned failure", action)
                        raise RuntimeError(f"SetSimulationState({action}) failed")
                    # Only update state after confirmed success
                    self._sim_paused = action in ("pause", "stop")
                    logger.debug("SetSimulationState(%s) completed successfully", action)
                except TimeoutError:
                    logger.warning("SetSimulationState(%s) timed out", action)
                    raise
                except Exception as exc:
                    logger.warning("SetSimulationState(%s) failed: %s", action, exc)
                    raise

        elif action == "step":
            if self._step_simulation_client is not None:
                request = StepSimulation.Request()
                request.steps = self._config.physics_decimation
                try:
                    response = await self._call_service_async(
                        self._step_simulation_client, request, timeout=5.0
                    )
                    if not response.success:
                        logger.warning("StepSimulation returned failure")
                        raise RuntimeError("StepSimulation failed")
                    logger.debug("StepSimulation(%d) completed successfully", request.steps)
                except TimeoutError:
                    logger.warning("StepSimulation timed out")
                    raise
                except Exception as exc:
                    logger.warning("StepSimulation failed: %s", exc)
                    raise

        elif action == "reset":
            if self._reset_simulation_client is not None:
                request = ResetSimulation.Request()
                try:
                    response = await self._call_service_async(
                        self._reset_simulation_client, request, timeout=5.0
                    )
                    if not response.success:
                        logger.warning("ResetSimulation returned failure")
                        raise RuntimeError("ResetSimulation failed")
                    # Only reset step counter after confirmed success
                    self._step = 0
                    logger.info("ResetSimulation completed successfully")
                except TimeoutError:
                    logger.warning("ResetSimulation timed out")
                    raise
                except Exception as exc:
                    logger.warning("ResetSimulation failed: %s", exc)
                    raise

    def add_observation_listener(self, callback: Callable[[Observation], None]) -> None:
        self._obs_listeners.append(callback)

    def remove_observation_listener(self, callback: Callable[[Observation], None]) -> None:
        with contextlib.suppress(ValueError):
            self._obs_listeners.remove(callback)

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
