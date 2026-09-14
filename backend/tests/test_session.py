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
        "mock-v2": ModelConfig(name="Mock v2", endpoint="", action_horizon=8),
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


def _make_session(**kwargs):
    defaults = dict(
        bridge=MockBridge(),
        policy_config=_POLICY_CONFIG,
        rerun_logger=_make_mock_logger(),
    )
    defaults.update(kwargs)
    return Session(**defaults)


def test_session_initial_state():
    session = _make_session()
    assert session.sim_state == "idle"
    assert session.step == 0
    assert session.instruction == ""
    assert session.policy_status == "disconnected"
    assert session.model_id == ""
    assert session.inferring is False


def test_set_instruction():
    session = _make_session()
    session.set_instruction("wave")
    assert session.instruction == "wave"


def test_clear_instruction():
    session = _make_session()
    session.set_instruction("wave")
    session.clear_instruction()
    assert session.instruction == ""
    assert session.step == 0


def test_sim_state_setter():
    session = _make_session()
    session.sim_state = "running"
    assert session.sim_state == "running"
    session.sim_state = "paused"
    assert session.sim_state == "paused"
    session.sim_state = "idle"
    assert session.sim_state == "idle"


def test_inferring_requires_all_conditions():
    session = _make_session()
    assert session.inferring is False

    session.sim_state = "running"
    assert session.inferring is False

    session.set_instruction("wave")
    assert session.inferring is False

    session._policy_status = "connected"
    assert session.inferring is True


def test_inferring_drops_when_any_condition_lost():
    session = _make_session()
    session.sim_state = "running"
    session.set_instruction("wave")
    session._policy_status = "connected"
    assert session.inferring is True

    session.sim_state = "paused"
    assert session.inferring is False

    session.sim_state = "running"
    assert session.inferring is True

    session.clear_instruction()
    assert session.inferring is False

    session.set_instruction("wave")
    assert session.inferring is True

    session._policy_status = "disconnected"
    assert session.inferring is False


@pytest.mark.anyio
async def test_select_model_connects_policy():
    session = _make_session()
    await session.start_loop()
    await session.select_model("mock-v1")
    await asyncio.sleep(0.2)
    assert session.policy_status == "connected"
    assert session.model_id == "mock-v1"
    await session.shutdown()


@pytest.mark.anyio
async def test_select_model_unknown_is_logged_not_raised():
    session = _make_session()
    await session.select_model("nonexistent")
    assert session.model_id == ""
    assert session.policy_status == "disconnected"


@pytest.mark.anyio
async def test_select_empty_model_disconnects():
    session = _make_session()
    await session.start_loop()
    await session.select_model("mock-v1")
    await asyncio.sleep(0.2)
    assert session.policy_status == "connected"

    await session.select_model("")
    assert session.policy_status == "disconnected"
    assert session.model_id == ""
    await session.shutdown()


@pytest.mark.anyio
async def test_select_same_model_is_noop():
    session = _make_session()
    await session.start_loop()
    await session.select_model("mock-v1")
    await asyncio.sleep(0.2)
    assert session.policy_status == "connected"

    await session.select_model("mock-v1")
    assert session.policy_status == "connected"
    await session.shutdown()


@pytest.mark.anyio
async def test_select_different_model_reconnects():
    session = _make_session()
    await session.start_loop()
    await session.select_model("mock-v1")
    await asyncio.sleep(0.2)
    assert session.model_id == "mock-v1"

    await session.select_model("mock-v2")
    await asyncio.sleep(0.2)
    assert session.model_id == "mock-v2"
    assert session.policy_status == "connected"
    await session.shutdown()


@pytest.mark.anyio
async def test_start_stop_loop():
    session = _make_session()
    await session.start_loop()
    assert session._loop_task is not None
    await session.stop_loop()
    assert session._loop_task is None


@pytest.mark.anyio
async def test_shutdown_disconnects_policy():
    session = _make_session()
    await session.start_loop()
    await session.select_model("mock-v1")
    await asyncio.sleep(0.2)
    assert session.policy_status == "connected"

    await session.shutdown()
    assert session.policy_status == "disconnected"
    assert session._loop_task is None


@pytest.mark.anyio
async def test_inference_runs_when_all_conditions_met():
    mock_logger = _make_mock_logger()
    session = _make_session(rerun_logger=mock_logger)
    await session.start_loop()
    await session.select_model("mock-v1")
    await asyncio.sleep(0.2)

    session.set_instruction("wave")
    session.sim_state = "running"
    await asyncio.sleep(0.8)

    assert session.step > 0
    assert mock_logger.log_raw_action_tensor.call_count >= 1
    assert mock_logger.log_inference_latency.call_count >= 1
    await session.shutdown()


@pytest.mark.anyio
async def test_inference_pauses_when_sim_stops():
    mock_logger = _make_mock_logger()
    session = _make_session(rerun_logger=mock_logger)
    await session.start_loop()
    await session.select_model("mock-v1")
    await asyncio.sleep(0.2)

    session.set_instruction("wave")
    session.sim_state = "running"
    await asyncio.sleep(0.5)
    step_before = session.step

    session.sim_state = "paused"
    await asyncio.sleep(0.3)
    assert session.step == step_before
    await session.shutdown()


@pytest.mark.anyio
async def test_inference_pauses_when_instruction_cleared():
    session = _make_session()
    await session.start_loop()
    await session.select_model("mock-v1")
    await asyncio.sleep(0.2)

    session.set_instruction("wave")
    session.sim_state = "running"
    await asyncio.sleep(0.5)
    assert session.step > 0

    session.clear_instruction()
    step_after_clear = session.step
    await asyncio.sleep(0.3)
    assert session.step == step_after_clear
    await session.shutdown()
