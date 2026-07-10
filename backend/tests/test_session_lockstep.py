from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from robotics_playground.bridges.mock_bridge import MockBridge
from robotics_playground.config import EmbodimentConfig
from robotics_playground.policy.embodiment_adapter import EmbodimentAdapter
from robotics_playground.policy.mock_client import MockClient
from robotics_playground.session import Session

SIMPLE_CONFIG = EmbodimentConfig(
    joint_names=["j1", "j2", "j3", "j4", "j5", "j6"],
    training_order=["j1", "j2", "j3", "j4", "j5", "j6"],
    joint_limits={f"j{i}": [-1, 1] for i in range(1, 7)},
    gripper_joint="g",
    gripper_limits=[0, 1],
    camera_mapping={"wrist": "observation/wrist_image_left"},
    image_size=[224, 224],
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
async def test_lockstep_session_runs_and_logs():
    mock_logger = _make_mock_logger()
    adapter = EmbodimentAdapter(SIMPLE_CONFIG)
    session = Session(
        bridge=MockBridge(),
        policy=MockClient(),
        adapter=adapter,
        rerun_logger=mock_logger,
    )
    await session.start()
    await asyncio.sleep(0.5)
    await session.stop()

    assert mock_logger.log_observation.call_count >= 1
    assert mock_logger.log_raw_action_tensor.call_count >= 1
    assert mock_logger.log_inference_latency.call_count >= 1
    assert mock_logger.log_action_trajectory.call_count >= 1


@pytest.mark.anyio
async def test_lockstep_session_initial_state():
    adapter = EmbodimentAdapter(SIMPLE_CONFIG)
    session = Session(
        bridge=MockBridge(),
        policy=MockClient(),
        adapter=adapter,
        rerun_logger=_make_mock_logger(),
    )
    assert session.state == "idle"
    assert session.step == 0


@pytest.mark.anyio
async def test_lockstep_session_pause_resume():
    adapter = EmbodimentAdapter(SIMPLE_CONFIG)
    session = Session(
        bridge=MockBridge(),
        policy=MockClient(),
        adapter=adapter,
        rerun_logger=_make_mock_logger(),
    )
    await session.start()
    session.pause()
    assert session.state == "paused"
    session.resume()
    assert session.state == "running"
    await session.stop()


@pytest.mark.anyio
async def test_lockstep_session_consumes_observations():
    adapter = EmbodimentAdapter(SIMPLE_CONFIG)
    session = Session(
        bridge=MockBridge(),
        policy=MockClient(),
        adapter=adapter,
        rerun_logger=_make_mock_logger(),
    )
    await session.start()
    await asyncio.sleep(0.5)
    step_after_execution = session.step
    await session.stop()

    # MockBridge generates step counter in observations
    # After executing action chunks, step should have advanced
    assert step_after_execution > 0
