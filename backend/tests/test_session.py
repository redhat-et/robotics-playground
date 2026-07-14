from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from robotics_playground.bridges.mock_bridge import MockBridge
from robotics_playground.config import EmbodimentConfig
from robotics_playground.policy.embodiment_adapter import EmbodimentAdapter
from robotics_playground.policy.mock_client import MockClient
from robotics_playground.session import DEFAULT_INSTRUCTION, Session

_SIMPLE_CONFIG = EmbodimentConfig(
    joint_names=["j1", "j2", "j3", "j4", "j5", "j6"],
    training_order=["j1", "j2", "j3", "j4", "j5", "j6"],
    joint_limits={f"j{i}": [-1, 1] for i in range(1, 7)},
    gripper_joint="g",
    gripper_limits=[0, 1],
    camera_mapping={"wrist": "observation/wrist_image_left"},
    image_size=[180, 320],
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


def test_session_initial_state():
    session = Session(
        bridge=MockBridge(),
        policy=MockClient(),
        adapter=EmbodimentAdapter(_SIMPLE_CONFIG),
        rerun_logger=_make_mock_logger(),
    )
    assert session.state == "idle"
    assert session.step == 0
    assert session.instruction == DEFAULT_INSTRUCTION


def test_send_instruction_stores_text():
    session = Session(
        bridge=MockBridge(),
        policy=MockClient(),
        adapter=EmbodimentAdapter(_SIMPLE_CONFIG),
        rerun_logger=_make_mock_logger(),
    )
    session.send_instruction("wave")
    assert session.instruction == "wave"


@pytest.mark.anyio
async def test_start_stop_lifecycle():
    session = Session(
        bridge=MockBridge(),
        policy=MockClient(),
        adapter=EmbodimentAdapter(_SIMPLE_CONFIG),
        rerun_logger=_make_mock_logger(),
    )
    await session.start()
    assert session.state == "running"
    await session.stop()
    assert session.state == "idle"


@pytest.mark.anyio
async def test_start_is_idempotent():
    session = Session(
        bridge=MockBridge(),
        policy=MockClient(),
        adapter=EmbodimentAdapter(_SIMPLE_CONFIG),
        rerun_logger=_make_mock_logger(),
    )
    await session.start()
    await session.start()
    assert session.state == "running"
    await session.stop()


@pytest.mark.anyio
async def test_stop_from_idle_is_noop():
    session = Session(
        bridge=MockBridge(),
        policy=MockClient(),
        adapter=EmbodimentAdapter(_SIMPLE_CONFIG),
        rerun_logger=_make_mock_logger(),
    )
    await session.stop()
    assert session.state == "idle"


@pytest.mark.anyio
async def test_pause_resume():
    session = Session(
        bridge=MockBridge(),
        policy=MockClient(),
        adapter=EmbodimentAdapter(_SIMPLE_CONFIG),
        rerun_logger=_make_mock_logger(),
    )
    await session.start()
    session.pause()
    assert session.state == "paused"
    session.resume()
    assert session.state == "running"
    await session.stop()


@pytest.mark.anyio
async def test_reset_clears_state():
    session = Session(
        bridge=MockBridge(),
        policy=MockClient(),
        adapter=EmbodimentAdapter(_SIMPLE_CONFIG),
        rerun_logger=_make_mock_logger(),
    )
    await session.start()
    session.send_instruction("pick up block")
    await session.reset()
    assert session.state == "idle"
    assert session.instruction == DEFAULT_INSTRUCTION


@pytest.mark.anyio
async def test_handle_sim_control_play_from_idle():
    session = Session(
        bridge=MockBridge(),
        policy=MockClient(),
        adapter=EmbodimentAdapter(_SIMPLE_CONFIG),
        rerun_logger=_make_mock_logger(),
    )
    await session.handle_sim_control("play")
    assert session.state == "running"
    await session.stop()


@pytest.mark.anyio
async def test_handle_sim_control_with_speed():
    session = Session(
        bridge=MockBridge(),
        policy=MockClient(),
        adapter=EmbodimentAdapter(_SIMPLE_CONFIG),
        rerun_logger=_make_mock_logger(),
    )
    await session.handle_sim_control("play", speed=2.0)
    assert session.state == "running"
    await session.stop()


@pytest.mark.anyio
async def test_handle_sim_control_step():
    session = Session(
        bridge=MockBridge(),
        policy=MockClient(),
        adapter=EmbodimentAdapter(_SIMPLE_CONFIG),
        rerun_logger=_make_mock_logger(),
    )
    await session.handle_sim_control("step")
    assert session.state == "paused"
    await session.stop()


@pytest.mark.anyio
async def test_bridge_status_exposed():
    bridge = MockBridge()
    session = Session(
        bridge=bridge,
        policy=MockClient(),
        adapter=EmbodimentAdapter(_SIMPLE_CONFIG),
        rerun_logger=_make_mock_logger(),
    )
    assert session.bridge_status == "mock"


@pytest.mark.anyio
async def test_observation_loop_logs_data():
    mock_logger = _make_mock_logger()
    session = Session(
        bridge=MockBridge(),
        policy=MockClient(),
        adapter=EmbodimentAdapter(_SIMPLE_CONFIG),
        rerun_logger=mock_logger,
    )
    await session.start()
    await asyncio.sleep(0.35)
    await session.stop()
    assert mock_logger.log_observation.call_count >= 1
    assert mock_logger.log_raw_action_tensor.call_count >= 1


@pytest.mark.anyio
async def test_stop_does_not_clear_rerun():
    mock_logger = _make_mock_logger()
    session = Session(
        bridge=MockBridge(),
        policy=MockClient(),
        adapter=EmbodimentAdapter(_SIMPLE_CONFIG),
        rerun_logger=mock_logger,
    )
    await session.start()
    await session.stop()
    mock_logger.clear.assert_not_called()


@pytest.mark.anyio
async def test_reset_clears_rerun_logger():
    mock_logger = _make_mock_logger()
    session = Session(
        bridge=MockBridge(),
        policy=MockClient(),
        adapter=EmbodimentAdapter(_SIMPLE_CONFIG),
        rerun_logger=mock_logger,
    )
    await session.start()
    await session.reset()
    mock_logger.clear.assert_called()


@pytest.mark.anyio
async def test_stop_does_not_close_bridge():
    bridge = MockBridge()
    await bridge.start()
    session = Session(
        bridge=bridge,
        policy=MockClient(),
        adapter=EmbodimentAdapter(_SIMPLE_CONFIG),
        rerun_logger=_make_mock_logger(),
    )
    await session.start()
    await session.stop()
    assert bridge.bridge_status == "connected"


@pytest.mark.anyio
async def test_reset_sends_teleport_command():
    bridge = MockBridge()
    await bridge.start()
    session = Session(
        bridge=bridge,
        policy=MockClient(),
        adapter=EmbodimentAdapter(_SIMPLE_CONFIG),
        rerun_logger=_make_mock_logger(),
    )
    await session.start()
    await session.reset()
    assert ("reset", None) in bridge.sim_control_calls
    assert bridge.bridge_status == "connected"


@pytest.mark.anyio
async def test_reset_from_idle_sends_teleport():
    bridge = MockBridge()
    await bridge.start()
    session = Session(
        bridge=bridge,
        policy=MockClient(),
        adapter=EmbodimentAdapter(_SIMPLE_CONFIG),
        rerun_logger=_make_mock_logger(),
    )
    await session.reset()
    assert ("reset", None) in bridge.sim_control_calls
    assert session.state == "idle"


@pytest.mark.anyio
async def test_bridge_disconnect_during_run_sets_error():
    bridge = MockBridge()
    await bridge.start()
    session = Session(
        bridge=bridge,
        policy=MockClient(),
        adapter=EmbodimentAdapter(_SIMPLE_CONFIG),
        rerun_logger=_make_mock_logger(),
        observation_timeout=0.5,
    )
    await session.start()
    assert session.state == "running"
    await asyncio.sleep(0.1)
    bridge.simulate_disconnect()
    for _ in range(30):
        await asyncio.sleep(0.1)
        if session.state == "error":
            break
    assert session.state == "error"
