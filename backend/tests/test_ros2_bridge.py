from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest


@pytest.fixture
def mock_rclpy():
    mock_node = MagicMock()
    mock_node.create_subscription = MagicMock()
    mock_node.create_publisher = MagicMock()
    mock_node.create_client = MagicMock()
    mock_node.destroy_node = MagicMock()

    mock_rclpy_module = MagicMock()
    mock_rclpy_module.init = MagicMock()
    mock_rclpy_module.ok = MagicMock(return_value=False)
    mock_rclpy_module.shutdown = MagicMock()

    mock_node_class = MagicMock(return_value=mock_node)

    mocks = {
        "rclpy": mock_rclpy_module,
        "rclpy.node": MagicMock(Node=mock_node_class),
        "rclpy.executors": MagicMock(),
        "rclpy.qos": MagicMock(),
        "sensor_msgs": MagicMock(),
        "sensor_msgs.msg": MagicMock(),
        "std_msgs": MagicMock(),
        "std_msgs.msg": MagicMock(),
    }

    with patch.dict("sys.modules", mocks):
        yield {
            "rclpy": mock_rclpy_module,
            "node": mock_node,
            "node_class": mock_node_class,
        }


def test_ros2_bridge_initial_status_is_disconnected(mock_rclpy):
    from robotics_playground.bridges.ros2_bridge import ROS2Bridge
    from robotics_playground.config import ROS2Config

    bridge = ROS2Bridge(ROS2Config(cameras={"wrist": "/cam/wrist"}))
    assert bridge.bridge_status == "disconnected"


@pytest.mark.anyio
async def test_ros2_bridge_start_initializes_rclpy(mock_rclpy):
    from robotics_playground.bridges.ros2_bridge import ROS2Bridge
    from robotics_playground.config import ROS2Config

    bridge = ROS2Bridge(ROS2Config(cameras={"wrist": "/cam/wrist"}))
    await bridge.start()
    mock_rclpy["rclpy"].init.assert_called_once()
    assert bridge.bridge_status == "connected"
    await bridge.close()


@pytest.mark.anyio
async def test_ros2_bridge_close_shuts_down(mock_rclpy):
    from robotics_playground.bridges.ros2_bridge import ROS2Bridge
    from robotics_playground.config import ROS2Config

    bridge = ROS2Bridge(ROS2Config(cameras={"wrist": "/cam/wrist"}))
    await bridge.start()
    await bridge.close()
    mock_rclpy["rclpy"].shutdown.assert_called_once()
    assert bridge.bridge_status == "disconnected"


@pytest.mark.anyio
async def test_ros2_bridge_close_skips_shutdown_when_not_owner(mock_rclpy):
    from robotics_playground.bridges.ros2_bridge import ROS2Bridge
    from robotics_playground.config import ROS2Config

    mock_rclpy["rclpy"].ok = MagicMock(return_value=True)
    bridge = ROS2Bridge(ROS2Config(cameras={"wrist": "/cam/wrist"}))
    await bridge.start()
    mock_rclpy["rclpy"].init.assert_not_called()
    await bridge.close()
    mock_rclpy["rclpy"].shutdown.assert_not_called()
    assert bridge.bridge_status == "disconnected"


@pytest.mark.anyio
async def test_ros2_bridge_observation_from_callbacks(mock_rclpy):
    from robotics_playground.bridges.ros2_bridge import ROS2Bridge
    from robotics_playground.config import ROS2Config

    config = ROS2Config(cameras={"wrist": "/cam/wrist"})
    bridge = ROS2Bridge(config)
    await bridge.start()

    bridge._on_joint_state_received([0.1, 0.2, 0.3], [0.0, 0.0, 0.0])
    image_data = np.zeros((240, 320, 3), dtype=np.uint8)
    bridge._on_image_received("wrist", image_data)

    obs = None
    async for o in bridge.observation_stream():
        obs = o
        if "wrist" in obs.get("cameras", {}):
            break

    assert obs is not None
    assert "wrist" in obs["cameras"]
    assert obs["joint_positions"] == [0.1, 0.2, 0.3]
    await bridge.close()


@pytest.mark.anyio
async def test_ros2_bridge_get_observation(mock_rclpy):
    from robotics_playground.bridges.protocol import Observation
    from robotics_playground.bridges.ros2_bridge import ROS2Bridge
    from robotics_playground.config import ROS2Config

    config = ROS2Config(cameras={"wrist": "/cam/wrist"})
    bridge = ROS2Bridge(config)
    await bridge.start()

    # Directly enqueue a test observation
    image_data = np.zeros((240, 320, 3), dtype=np.uint8)
    test_obs = Observation(
        step=0,
        cameras={"wrist": image_data},
        joint_positions=[0.1, 0.2, 0.3],
        joint_velocities=[0.01, 0.02, 0.03],
    )
    await bridge._obs_queue.put(test_obs)

    obs = await bridge.get_observation()

    assert obs is not None
    assert "wrist" in obs["cameras"]
    assert obs["joint_positions"] == [0.1, 0.2, 0.3]
    assert obs["joint_velocities"] == [0.01, 0.02, 0.03]
    await bridge.close()


@pytest.mark.anyio
async def test_ros2_bridge_send_action_without_start_is_noop(mock_rclpy):
    from robotics_playground.bridges.ros2_bridge import ROS2Bridge
    from robotics_playground.config import ROS2Config

    bridge = ROS2Bridge(ROS2Config(cameras={"wrist": "/cam/wrist"}))
    await bridge.send_action(
        {
            "joint_positions": [0.0] * 6,
            "joint_velocities": [0.0] * 6,
            "gripper_position": 0.0,
        }
    )


@pytest.mark.anyio
async def test_ros2_bridge_sim_control_without_start_is_noop(mock_rclpy):
    from robotics_playground.bridges.ros2_bridge import ROS2Bridge
    from robotics_playground.config import ROS2Config

    bridge = ROS2Bridge(ROS2Config(cameras={"wrist": "/cam/wrist"}))
    await bridge.sim_control("play")


@pytest.mark.anyio
async def test_ros2_bridge_send_action_publishes(mock_rclpy):
    from robotics_playground.bridges.ros2_bridge import ROS2Bridge
    from robotics_playground.config import ROS2Config

    bridge = ROS2Bridge(ROS2Config(cameras={"wrist": "/cam/wrist"}))
    await bridge.start()

    mock_publisher = bridge._publisher
    await bridge.send_action(
        {
            "joint_positions": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7],
            "joint_velocities": [1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6],
            "gripper_position": 0.8,
        }
    )

    mock_publisher.publish.assert_called_once()
    published_msg = mock_publisher.publish.call_args[0][0]
    assert len(published_msg.position) == 8
    assert published_msg.position[:7] == [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]
    assert published_msg.position[7] == 0.8
    assert len(published_msg.velocity) == 8
    assert published_msg.velocity[:7] == [1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6]
    assert str(published_msg.velocity[7]) == "nan"

    await bridge.close()
