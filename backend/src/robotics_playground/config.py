from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"


class RerunConfig(BaseModel):
    grpc_port: int = 9876
    web_port: int = 9090


class BridgeConfig(BaseModel):
    type: str = "mock"
    watchdog_timeout: float = 10.0
    reconnect_delay: float = 2.0
    max_reconnect_delay: float = 30.0


class ROS2Config(BaseModel):
    domain_id: int = 0
    discovery_server: str | None = None
    cameras: dict[str, str] = {}
    joint_state_topic: str = "/joint_states"
    joint_command_topic: str = "/joint_commands"
    physics_decimation: int = 10
    default_joint_positions: list[float] = []


class EmbodimentConfig(BaseModel):
    joint_names: list[str] = []
    training_order: list[str] = []
    joint_limits: dict[str, list[float]] = {}
    gripper_joint: str = ""
    gripper_limits: list[float] = [0.0, 0.04]
    camera_mapping: dict[str, str] = {}
    image_size: list[int] = [180, 320]


class PolicyConfig(BaseModel):
    type: str = "mock"
    endpoint: str = ""
    model_name: str = "dreamzero"
    action_horizon: int = Field(default=4, gt=0)
    embodiment: EmbodimentConfig = EmbodimentConfig()


class PlaygroundConfig(BaseModel):
    server: ServerConfig = ServerConfig()
    rerun: RerunConfig = RerunConfig()
    bridge: BridgeConfig = BridgeConfig()
    ros2: ROS2Config = ROS2Config()
    policy: PolicyConfig = PolicyConfig()


def load_config(path: str | None = None) -> PlaygroundConfig:
    if path is None:
        path = os.environ.get("PLAYGROUND_CONFIG")
    if path and Path(path).is_file():
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return PlaygroundConfig(**data)
    return PlaygroundConfig()
