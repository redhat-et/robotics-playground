from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from robotics_playground.bridges.mock_bridge import MockBridge
from robotics_playground.config import EmbodimentConfig, ModelConfig, PolicyConfig
from robotics_playground.session import DEFAULT_INSTRUCTION, Session

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


def test_session_initial_state():
    session = Session(
        bridge=MockBridge(),
        policy_config=_POLICY_CONFIG,
        rerun_logger=_make_mock_logger(),
    )
    assert session.state == "idle"
    assert session.step == 0
    assert session.instruction == DEFAULT_INSTRUCTION


def test_send_instruction_stores_text():
    session = Session(
        bridge=MockBridge(),
        policy_config=_POLICY_CONFIG,
        rerun_logger=_make_mock_logger(),
    )
    session.send_instruction("wave")
    assert session.instruction == "wave"


@pytest.mark.anyio
async def test_start_stop_lifecycle():
    session = Session(
        bridge=MockBridge(),
        policy_config=_POLICY_CONFIG,
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
        policy_config=_POLICY_CONFIG,
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
        policy_config=_POLICY_CONFIG,
        rerun_logger=_make_mock_logger(),
    )
    await session.stop()
    assert session.state == "idle"


@pytest.mark.anyio
async def test_pause_resume():
    session = Session(
        bridge=MockBridge(),
        policy_config=_POLICY_CONFIG,
        rerun_logger=_make_mock_logger(),
    )
    await session.start()
    await session.pause()
    assert session.state == "paused"
    await session.resume()
    assert session.state == "running"
    await session.stop()


@pytest.mark.anyio
async def test_reset_clears_state():
    session = Session(
        bridge=MockBridge(),
        policy_config=_POLICY_CONFIG,
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
        policy_config=_POLICY_CONFIG,
        rerun_logger=_make_mock_logger(),
    )
    await session.handle_sim_control("play")
    assert session.state == "running"
    await session.stop()


@pytest.mark.anyio
async def test_handle_sim_control_with_speed():
    session = Session(
        bridge=MockBridge(),
        policy_config=_POLICY_CONFIG,
        rerun_logger=_make_mock_logger(),
    )
    await session.handle_sim_control("play", speed=2.0)
    assert session.state == "running"
    await session.stop()


@pytest.mark.anyio
async def test_handle_sim_control_step():
    session = Session(
        bridge=MockBridge(),
        policy_config=_POLICY_CONFIG,
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
        policy_config=_POLICY_CONFIG,
        rerun_logger=_make_mock_logger(),
    )
    assert session.bridge_status == "mock"


@pytest.mark.anyio
async def test_observation_loop_logs_data():
    mock_logger = _make_mock_logger()
    session = Session(
        bridge=MockBridge(),
        policy_config=_POLICY_CONFIG,
        rerun_logger=mock_logger,
    )
    await session.start()
    await asyncio.sleep(0.35)
    await session.stop()
    assert mock_logger.log_observation.call_count >= 1
    assert mock_logger.log_raw_action_tensor.call_count >= 1


@pytest.mark.anyio
async def test_observation_listener_removed_after_stop():
    bridge = MockBridge()
    await bridge.start()
    mock_logger = _make_mock_logger()
    session = Session(
        bridge=bridge,
        policy_config=_POLICY_CONFIG,
        rerun_logger=mock_logger,
    )
    await session.start()
    await asyncio.sleep(0.35)
    await session.stop()
    assert len(bridge._obs_listeners) == 0


@pytest.mark.anyio
async def test_stop_does_not_clear_rerun():
    mock_logger = _make_mock_logger()
    session = Session(
        bridge=MockBridge(),
        policy_config=_POLICY_CONFIG,
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
        policy_config=_POLICY_CONFIG,
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
        policy_config=_POLICY_CONFIG,
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
        policy_config=_POLICY_CONFIG,
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
        policy_config=_POLICY_CONFIG,
        rerun_logger=_make_mock_logger(),
    )
    await session.reset()
    assert ("reset", None) in bridge.sim_control_calls
    assert session.state == "idle"


def test_select_model_while_idle():
    session = Session(
        bridge=MockBridge(),
        policy_config=_POLICY_CONFIG,
        rerun_logger=_make_mock_logger(),
    )
    session.select_model("mock-v2")
    assert session.model_id == "mock-v2"


def test_select_model_invalid_raises():
    session = Session(
        bridge=MockBridge(),
        policy_config=_POLICY_CONFIG,
        rerun_logger=_make_mock_logger(),
    )
    with pytest.raises(ValueError, match="Unknown model"):
        session.select_model("nonexistent")


@pytest.mark.anyio
async def test_select_model_while_running_raises():
    session = Session(
        bridge=MockBridge(),
        policy_config=_POLICY_CONFIG,
        rerun_logger=_make_mock_logger(),
    )
    await session.start()
    with pytest.raises(ValueError, match="idle"):
        session.select_model("mock-v2")
    await session.stop()


def test_model_id_defaults_to_default_model():
    session = Session(
        bridge=MockBridge(),
        policy_config=_POLICY_CONFIG,
        rerun_logger=_make_mock_logger(),
    )
    assert session.model_id == "mock-v1"


@pytest.mark.anyio
async def test_start_sends_play_stop_sends_pause():
    bridge = MockBridge()
    await bridge.start()
    session = Session(
        bridge=bridge,
        policy_config=_POLICY_CONFIG,
        rerun_logger=_make_mock_logger(),
    )
    await session.start()
    await asyncio.sleep(0.1)
    assert ("play", None) in bridge.sim_control_calls
    await session.stop()
    assert ("pause", None) in bridge.sim_control_calls


@pytest.mark.anyio
async def test_bridge_disconnect_during_run_sets_error():
    bridge = MockBridge()
    await bridge.start()
    session = Session(
        bridge=bridge,
        policy_config=_POLICY_CONFIG,
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
