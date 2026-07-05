from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"


class RerunConfig(BaseModel):
    grpc_port: int = 9876
    web_port: int = 9090


class BridgeConfig(BaseModel):
    type: str = "mock"


class ROS2Config(BaseModel):
    domain_id: int = 0
    discovery_server: str | None = None
    cameras: dict[str, str] = {}
    joint_state_topic: str = "/joint_states"
    joint_command_topic: str = "/joint_commands"
    set_sim_state_service: str = "/isaacsim/SetSimulationState"
    step_simulation_service: str = "/isaacsim/StepSimulation"


class PlaygroundConfig(BaseModel):
    server: ServerConfig = ServerConfig()
    rerun: RerunConfig = RerunConfig()
    bridge: BridgeConfig = BridgeConfig()
    ros2: ROS2Config = ROS2Config()


def load_config(path: str | None = None) -> PlaygroundConfig:
    if path is None:
        path = os.environ.get("PLAYGROUND_CONFIG")
    if path and Path(path).is_file():
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return PlaygroundConfig(**data)
    return PlaygroundConfig()
