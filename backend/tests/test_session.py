from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from robotics_playground.bridges.mock_bridge import MockBridge
from robotics_playground.session import Session


def _make_mock_logger():
    logger = MagicMock()
    logger.log_observation = MagicMock()
    logger.log_action = MagicMock()
    logger.log_instruction = MagicMock()
    return logger


def test_session_initial_state():
    session = Session(bridge=MockBridge(), rerun_logger=_make_mock_logger())
    assert session.state == "idle"
    assert session.step == 0
    assert session.instruction == ""


def test_send_instruction_stores_text():
    session = Session(bridge=MockBridge(), rerun_logger=_make_mock_logger())
    session.send_instruction("wave")
    assert session.instruction == "wave"


@pytest.mark.anyio
async def test_start_stop_lifecycle():
    session = Session(bridge=MockBridge(), rerun_logger=_make_mock_logger())
    await session.start()
    assert session.state == "running"
    await session.stop()
    assert session.state == "idle"


@pytest.mark.anyio
async def test_start_is_idempotent():
    session = Session(bridge=MockBridge(), rerun_logger=_make_mock_logger())
    await session.start()
    await session.start()
    assert session.state == "running"
    await session.stop()


@pytest.mark.anyio
async def test_stop_from_idle_is_noop():
    session = Session(bridge=MockBridge(), rerun_logger=_make_mock_logger())
    await session.stop()
    assert session.state == "idle"


@pytest.mark.anyio
async def test_pause_resume():
    session = Session(bridge=MockBridge(), rerun_logger=_make_mock_logger())
    await session.start()
    session.pause()
    assert session.state == "paused"
    session.resume()
    assert session.state == "running"
    await session.stop()


@pytest.mark.anyio
async def test_reset_clears_state():
    session = Session(bridge=MockBridge(), rerun_logger=_make_mock_logger())
    await session.start()
    session.send_instruction("pick up block")
    await session.reset()
    assert session.state == "idle"
    assert session.instruction == ""


@pytest.mark.anyio
async def test_handle_sim_control_play_from_idle():
    session = Session(bridge=MockBridge(), rerun_logger=_make_mock_logger())
    await session.handle_sim_control("play")
    assert session.state == "running"
    await session.stop()


@pytest.mark.anyio
async def test_handle_sim_control_with_speed():
    session = Session(bridge=MockBridge(), rerun_logger=_make_mock_logger())
    await session.handle_sim_control("play", speed=2.0)
    assert session.state == "running"
    await session.stop()


@pytest.mark.anyio
async def test_handle_sim_control_step():
    session = Session(bridge=MockBridge(), rerun_logger=_make_mock_logger())
    await session.handle_sim_control("step")
    assert session.state == "paused"
    await session.stop()


@pytest.mark.anyio
async def test_bridge_status_exposed():
    bridge = MockBridge()
    session = Session(bridge=bridge, rerun_logger=_make_mock_logger())
    assert session.bridge_status == "mock"


@pytest.mark.anyio
async def test_observation_loop_logs_data():
    mock_logger = _make_mock_logger()
    session = Session(bridge=MockBridge(), rerun_logger=mock_logger)
    await session.start()
    await asyncio.sleep(0.35)
    await session.stop()
    assert mock_logger.log_observation.call_count >= 2
    assert mock_logger.log_action.call_count >= 2


@pytest.mark.anyio
async def test_stop_does_not_clear_rerun():
    mock_logger = _make_mock_logger()
    session = Session(bridge=MockBridge(), rerun_logger=mock_logger)
    await session.start()
    await session.stop()
    mock_logger.clear.assert_not_called()


@pytest.mark.anyio
async def test_reset_clears_rerun_logger():
    mock_logger = _make_mock_logger()
    session = Session(bridge=MockBridge(), rerun_logger=mock_logger)
    await session.start()
    await session.reset()
    mock_logger.clear.assert_called_once()
