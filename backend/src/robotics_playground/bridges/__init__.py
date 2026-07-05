from robotics_playground.bridges.mock_bridge import MockBridge
from robotics_playground.bridges.protocol import Action, Observation, RobotBridge
from robotics_playground.config import PlaygroundConfig

__all__ = ["Action", "MockBridge", "Observation", "RobotBridge", "create_bridge"]


def create_bridge(config: PlaygroundConfig) -> RobotBridge:
    if config.bridge.type == "mock":
        return MockBridge()
    if config.bridge.type == "ros2":
        from robotics_playground.bridges.ros2_bridge import ROS2Bridge

        return ROS2Bridge(config.ros2)
    raise ValueError(f"Unknown bridge type: {config.bridge.type!r} (expected 'mock' or 'ros2')")
