from __future__ import annotations

import math

import numpy as np
import pytest

from robotics_playground.bridges.protocol import Observation
from robotics_playground.config import EmbodimentConfig
from robotics_playground.policy.embodiment_adapter import EmbodimentAdapter

FRANKA_CONFIG = EmbodimentConfig(
    joint_names=["j1", "j2", "j3", "j4", "j5", "j6", "j7"],
    training_order=["j1", "j2", "j3", "j4", "j5", "j6", "j7"],
    joint_limits={
        "j1": [-2.0, 2.0],
        "j2": [-1.0, 1.0],
        "j3": [-2.0, 2.0],
        "j4": [-3.0, 0.0],
        "j5": [-2.0, 2.0],
        "j6": [0.0, 4.0],
        "j7": [-2.0, 2.0],
    },
    gripper_joint="grip",
    gripper_limits=[0.0, 0.04],
    camera_mapping={
        "wrist": "observation/wrist_image_left",
        "exterior_1": "observation/exterior_image_1_left",
    },
)


def _make_obs(
    positions: list[float] | None = None,
    velocities: list[float] | None = None,
) -> Observation:
    return Observation(
        step=0,
        cameras={
            "wrist": np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8),
            "exterior_1": np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8),
        },
        joint_positions=positions or [0.0] * 7,
        joint_velocities=velocities or [0.0] * 7,
    )


def test_observation_to_openpi_keys():
    adapter = EmbodimentAdapter(FRANKA_CONFIG)
    obs = _make_obs()
    result = adapter.observation_to_openpi(obs, "pick up block")
    assert "observation/wrist_image_left" in result
    assert "observation/exterior_image_1_left" in result
    assert "observation/joint_position" in result
    assert "observation/gripper_position" in result
    assert result["prompt"] == "pick up block"
    assert result["session_id"] == "default"


def test_images_passed_through_raw():
    adapter = EmbodimentAdapter(FRANKA_CONFIG)
    raw_img = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    obs = Observation(
        step=0,
        cameras={"wrist": raw_img, "exterior_1": raw_img},
        joint_positions=[0.0] * 7,
        joint_velocities=[0.0] * 7,
    )
    result = adapter.observation_to_openpi(obs, "")
    assert result["observation/wrist_image_left"].shape == (480, 640, 3)
    assert np.array_equal(result["observation/wrist_image_left"], raw_img)


def test_observation_joint_passthrough():
    adapter = EmbodimentAdapter(FRANKA_CONFIG)
    obs = _make_obs(positions=[0.0, 1.0, 0.0, -1.5, 0.0, 2.0, 0.0])
    result = adapter.observation_to_openpi(obs, "")
    joints = result["observation/joint_position"]
    assert joints.shape == (7,)
    assert abs(joints[0] - 0.0) < 1e-6
    assert abs(joints[1] - 1.0) < 1e-6
    assert abs(joints[3] - (-1.5)) < 1e-6


def test_observation_joint_reorder():
    config = EmbodimentConfig(
        joint_names=["a", "b", "c"],
        training_order=["c", "a", "b"],
        joint_limits={"a": [-1, 1], "b": [-1, 1], "c": [-1, 1]},
        gripper_joint="g",
        gripper_limits=[0, 1],
        camera_mapping={},
    )
    adapter = EmbodimentAdapter(config)
    obs = Observation(
        step=0,
        cameras={},
        joint_positions=[0.1, 0.2, 0.3],
        joint_velocities=[0.0, 0.0, 0.0],
    )
    result = adapter.observation_to_openpi(obs, "")
    joints = result["observation/joint_position"]
    # training_order=[c, a, b], so output should be [0.3, 0.1, 0.2] normalized
    assert abs(joints[0] - 0.3) < 1e-6
    assert abs(joints[1] - 0.1) < 1e-6
    assert abs(joints[2] - 0.2) < 1e-6


def test_action_chunk_from_openpi_shape():
    adapter = EmbodimentAdapter(FRANKA_CONFIG)
    actions = adapter.action_chunk_from_openpi(np.zeros((10, 8), dtype=np.float32))
    assert len(actions) == 10
    for a in actions:
        assert len(a["joint_positions"]) == 7
        assert len(a["joint_velocities"]) == 7
        assert isinstance(a["gripper_position"], float)


def test_action_chunk_nan_dispatch():
    adapter = EmbodimentAdapter(FRANKA_CONFIG)
    actions = adapter.action_chunk_from_openpi(np.zeros((10, 8), dtype=np.float32))
    for a in actions:
        # Arm joints: position has real values, velocity is NaN
        for i in range(7):
            assert not math.isnan(a["joint_positions"][i])
            assert math.isnan(a["joint_velocities"][i])
        # Gripper: position has real value
        assert not math.isnan(a["gripper_position"])


def test_action_passthrough():
    adapter = EmbodimentAdapter(FRANKA_CONFIG)
    action_row = np.array([0.1, 0.2, 0.3, -1.5, 1.0, 2.0, -0.5, 0.02], dtype=np.float32)
    actions = adapter.action_chunk_from_openpi(np.tile(action_row, (10, 1)))
    for a in actions:
        assert abs(a["joint_positions"][0] - 0.1) < 1e-5
        assert abs(a["gripper_position"] - 0.02) < 1e-5


def test_action_reorder_inverse():
    config = EmbodimentConfig(
        joint_names=["a", "b", "c"],
        training_order=["c", "a", "b"],
        joint_limits={"a": [-1, 1], "b": [-1, 1], "c": [-1, 1]},
        gripper_joint="g",
        gripper_limits=[0, 1],
        camera_mapping={},
    )
    adapter = EmbodimentAdapter(config)
    # Action in training order [c, a, b] = [0.3, 0.1, 0.2]
    action_row = np.array([0.3, 0.1, 0.2, 0.5], dtype=np.float32)
    actions = adapter.action_chunk_from_openpi(action_row.reshape(1, 4))
    positions = actions[0]["joint_positions"]
    # Should be reordered back to URDF [a, b, c] = [0.1, 0.2, 0.3]
    assert len(positions) == 3
    assert abs(positions[0] - 0.1) < 1e-5
    assert abs(positions[1] - 0.2) < 1e-5
    assert abs(positions[2] - 0.3) < 1e-5


def test_camera_mapping_override():
    override = {"cam_a": "observation/cam_a_custom"}
    adapter = EmbodimentAdapter(FRANKA_CONFIG, camera_mapping_override=override)
    assert adapter.camera_names == ["cam_a"]
    obs = Observation(
        step=0,
        cameras={"cam_a": np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)},
        joint_positions=[0.0] * 7,
        joint_velocities=[0.0] * 7,
    )
    result = adapter.observation_to_openpi(obs, "")
    assert "observation/cam_a_custom" in result


def test_action_clamped_to_joint_limits():
    adapter = EmbodimentAdapter(FRANKA_CONFIG)
    # Exceed limits: j1 limit [-2.0, 2.0], j4 limit [-3.0, 0.0]
    action_row = np.array([5.0, 0.0, 0.0, -5.0, 0.0, 2.0, 0.0, 0.1], dtype=np.float32)
    actions = adapter.action_chunk_from_openpi(action_row.reshape(1, 8))
    pos = actions[0]["joint_positions"]
    # Should be clamped to limit - margin (0.05)
    assert abs(pos[0] - 1.95) < 1e-5  # j1 upper 2.0 - 0.05
    assert abs(pos[3] - (-2.95)) < 1e-5  # j4 lower -3.0 + 0.05


def test_gripper_clamped_to_limits():
    adapter = EmbodimentAdapter(FRANKA_CONFIG)
    action_row = np.array([0.0, 0.0, 0.0, -1.0, 0.0, 2.0, 0.0, 0.5], dtype=np.float32)
    actions = adapter.action_chunk_from_openpi(action_row.reshape(1, 8))
    assert abs(actions[0]["gripper_position"] - 0.04) < 1e-5  # clamped to upper limit


def test_velocity_action_integration():
    adapter = EmbodimentAdapter(FRANKA_CONFIG, action_type="velocity")
    obs = _make_obs(positions=[0.0, 0.5, 0.0, -1.5, 0.0, 2.0, 0.0])
    delta_row = np.array([0.1, -0.1, 0.2, -0.2, 0.1, 0.1, -0.1, 0.02], dtype=np.float32)
    actions = adapter.action_chunk_from_openpi(delta_row.reshape(1, 8), current_obs=obs)
    pos = actions[0]["joint_positions"]
    assert abs(pos[0] - 0.1) < 1e-5  # 0.0 + 0.1
    assert abs(pos[1] - 0.4) < 1e-5  # 0.5 + (-0.1)
    assert abs(pos[3] - (-1.7)) < 1e-5  # -1.5 + (-0.2)


def test_velocity_action_accumulates_through_chunk():
    adapter = EmbodimentAdapter(FRANKA_CONFIG, action_type="velocity")
    obs = _make_obs(positions=[0.0, 0.0, 0.0, -1.0, 0.0, 1.0, 0.0])
    delta_row = np.array([0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.02], dtype=np.float32)
    actions_array = np.tile(delta_row, (3, 1))
    actions = adapter.action_chunk_from_openpi(actions_array, current_obs=obs)
    assert abs(actions[0]["joint_positions"][0] - 0.1) < 1e-5
    assert abs(actions[1]["joint_positions"][0] - 0.2) < 1e-5
    assert abs(actions[2]["joint_positions"][0] - 0.3) < 1e-5


def test_velocity_gripper_stays_absolute():
    adapter = EmbodimentAdapter(FRANKA_CONFIG, action_type="velocity")
    obs = _make_obs(positions=[0.0] * 7)
    action_row = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.03], dtype=np.float32)
    actions = adapter.action_chunk_from_openpi(action_row.reshape(1, 8), current_obs=obs)
    assert abs(actions[0]["gripper_position"] - 0.03) < 1e-5


def test_velocity_without_obs_raises():
    adapter = EmbodimentAdapter(FRANKA_CONFIG, action_type="velocity")
    action_row = np.array([0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.02], dtype=np.float32)
    with pytest.raises(ValueError, match="requires current_obs"):
        adapter.action_chunk_from_openpi(action_row.reshape(1, 8))


def test_absolute_action_ignores_current_obs():
    adapter = EmbodimentAdapter(FRANKA_CONFIG, action_type="absolute")
    obs = _make_obs(positions=[1.0, 1.0, 1.0, -1.0, 1.0, 2.0, 1.0])
    action_row = np.array([0.1, 0.2, 0.3, -1.5, 1.0, 2.0, -0.5, 0.02], dtype=np.float32)
    actions = adapter.action_chunk_from_openpi(action_row.reshape(1, 8), current_obs=obs)
    assert abs(actions[0]["joint_positions"][0] - 0.1) < 1e-5
