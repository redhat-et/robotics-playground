from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from robotics_playground.bridges.mock_bridge import MockBridge
from robotics_playground.config import EmbodimentConfig, ModelConfig, PolicyConfig
from robotics_playground.session import Session

_EMBODIMENT = EmbodimentConfig(
    joint_names=["j1", "j2", "j3", "j4", "j5", "j6"],
    training_order=["j1", "j2", "j3", "j4", "j5", "j6"],
    joint_limits={f"j{i}": [-1, 1] for i in range(1, 7)},
    gripper_joint="g",
    gripper_limits=[0, 1],
    camera_mapping={"wrist": "observation/wrist_image_left"},
)

_POLICY_CONFIG = PolicyConfig(
    type="mock",
    default_model="mock-v1",
    models={
        "mock-v1": ModelConfig(name="Mock", endpoint="", action_horizon=4),
    },
    embodiment=_EMBODIMENT,
)


def _make_mock_logger():
    logger = MagicMock()
    logger.log_observation = MagicMock()
    logger.log_action = MagicMock()
    logger.log_instruction = MagicMock()
    logger.log_raw_action_tensor = MagicMock()
    logger.log_inference_latency = MagicMock()
    logger.log_action_trajectory = MagicMock()
    return logger


@pytest.mark.anyio
async def test_inference_loop_logs_all_artifacts():
    mock_logger = _make_mock_logger()
    session = Session(
        bridge=MockBridge(),
        policy_config=_POLICY_CONFIG,
        rerun_logger=mock_logger,
    )
    await session.start_loop()
    await session.select_model("mock-v1")
    await asyncio.sleep(0.2)

    session.set_instruction("wave")
    session.sim_state = "running"
    await asyncio.sleep(0.8)
    await session.shutdown()

    assert mock_logger.log_instruction.call_count >= 1
    assert mock_logger.log_raw_action_tensor.call_count >= 1
    assert mock_logger.log_inference_latency.call_count >= 1
    assert mock_logger.log_action_trajectory.call_count >= 1


@pytest.mark.anyio
async def test_inference_loop_advances_step():
    session = Session(
        bridge=MockBridge(),
        policy_config=_POLICY_CONFIG,
        rerun_logger=_make_mock_logger(),
    )
    await session.start_loop()
    await session.select_model("mock-v1")
    await asyncio.sleep(0.2)

    session.set_instruction("pick up block")
    session.sim_state = "running"
    await asyncio.sleep(0.8)
    step_after = session.step
    await session.shutdown()

    assert step_after > 0


@pytest.mark.anyio
async def test_no_inference_without_instruction():
    mock_logger = _make_mock_logger()
    session = Session(
        bridge=MockBridge(),
        policy_config=_POLICY_CONFIG,
        rerun_logger=mock_logger,
    )
    await session.start_loop()
    await session.select_model("mock-v1")
    await asyncio.sleep(0.2)

    session.sim_state = "running"
    await asyncio.sleep(0.5)
    await session.shutdown()

    assert mock_logger.log_raw_action_tensor.call_count == 0
    assert session.step == 0


@pytest.mark.anyio
async def test_no_inference_without_policy():
    mock_logger = _make_mock_logger()
    session = Session(
        bridge=MockBridge(),
        policy_config=_POLICY_CONFIG,
        rerun_logger=mock_logger,
    )
    await session.start_loop()

    session.set_instruction("wave")
    session.sim_state = "running"
    await asyncio.sleep(0.5)
    await session.shutdown()

    assert mock_logger.log_raw_action_tensor.call_count == 0
    assert session.step == 0
