from __future__ import annotations

import textwrap


def test_default_config_loads():
    from robotics_playground.config import PlaygroundConfig

    config = PlaygroundConfig()
    assert config.server.host == "0.0.0.0"
    assert config.server.port == 8000
    assert config.bridge.type == "mock"
    assert config.rerun.grpc_port == 9876


def test_load_config_from_yaml(tmp_path):
    from robotics_playground.config import load_config

    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        textwrap.dedent("""\
            server:
              port: 9000
              log_level: debug
            bridge:
              type: ros2
            ros2:
              domain_id: 5
              cameras:
                wrist: /cam/wrist
        """)
    )
    config = load_config(str(config_file))
    assert config.server.port == 9000
    assert config.server.log_level == "debug"
    assert config.bridge.type == "ros2"
    assert config.ros2.domain_id == 5
    assert config.ros2.cameras == {"wrist": "/cam/wrist"}


def test_load_config_missing_file_returns_defaults():
    from robotics_playground.config import load_config

    config = load_config("/nonexistent/path.yaml")
    assert config.server.port == 8000
    assert config.bridge.type == "mock"


def test_env_var_sets_config_path(tmp_path, monkeypatch):
    from robotics_playground.config import load_config

    config_file = tmp_path / "env.yaml"
    config_file.write_text("server:\n  port: 7777\n")
    monkeypatch.setenv("PLAYGROUND_CONFIG", str(config_file))
    config = load_config()
    assert config.server.port == 7777


def test_ros2_config_defaults():
    from robotics_playground.config import PlaygroundConfig

    config = PlaygroundConfig()
    assert config.ros2.domain_id == 0
    assert config.ros2.discovery_server is None
    assert config.ros2.cameras == {}
    assert config.ros2.joint_state_topic == "/joint_states"
    assert config.ros2.joint_command_topic == "/joint_commands"


def test_policy_config_defaults():
    from robotics_playground.config import PlaygroundConfig

    config = PlaygroundConfig()
    assert config.policy.type == "mock"
    assert config.policy.endpoint == ""
    assert config.policy.model_name == "dreamzero"
    assert config.policy.embodiment.joint_names == []
    assert config.policy.embodiment.image_size == [224, 224]
    assert config.policy.embodiment.gripper_limits == [0.0, 0.04]


def test_policy_config_from_dict():
    from robotics_playground.config import PlaygroundConfig

    data = {
        "policy": {
            "type": "openpi",
            "endpoint": "ws://localhost:8080/v1/realtime/robot/openpi",
            "embodiment": {
                "joint_names": ["j1", "j2"],
                "training_order": ["j2", "j1"],
                "joint_limits": {"j1": [-1.0, 1.0], "j2": [-2.0, 2.0]},
                "gripper_joint": "grip",
                "camera_mapping": {"wrist": "observation/wrist_image_left"},
            },
        }
    }
    config = PlaygroundConfig(**data)
    assert config.policy.type == "openpi"
    assert config.policy.embodiment.joint_names == ["j1", "j2"]
    assert config.policy.embodiment.training_order == ["j2", "j1"]
    assert config.policy.embodiment.camera_mapping == {"wrist": "observation/wrist_image_left"}


def test_ros2_config_physics_decimation():
    from robotics_playground.config import PlaygroundConfig

    config = PlaygroundConfig()
    assert config.ros2.physics_decimation == 10

    config2 = PlaygroundConfig(ros2={"physics_decimation": 5})
    assert config2.ros2.physics_decimation == 5
