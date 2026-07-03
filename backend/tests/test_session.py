from __future__ import annotations

import asyncio

import pytest

from robotics_playground.session import Session


def _make_mock_logger():
    from unittest.mock import MagicMock

    logger = MagicMock()
    logger.log_observation = MagicMock()
    logger.log_action = MagicMock()
    logger.log_instruction = MagicMock()
    return logger


def test_session_initial_state():
    session = Session(rerun_logger=_make_mock_logger())
    assert session.state == "idle"
    assert session.step == 0
    assert session.instruction == ""


def test_send_instruction_stores_text():
    session = Session(rerun_logger=_make_mock_logger())
    session.send_instruction("wave")
    assert session.instruction == "wave"


def test_send_instruction_overwrites_previous():
    session = Session(rerun_logger=_make_mock_logger())
    session.send_instruction("wave")
    session.send_instruction("pick up block")
    assert session.instruction == "pick up block"


@pytest.mark.anyio
async def test_start_stop_lifecycle():
    session = Session(rerun_logger=_make_mock_logger())
    assert session.state == "idle"

    await session.start()
    assert session.state == "running"

    await session.stop()
    assert session.state == "idle"


@pytest.mark.anyio
async def test_start_is_idempotent():
    session = Session(rerun_logger=_make_mock_logger())
    await session.start()
    await session.start()
    assert session.state == "running"
    await session.stop()


@pytest.mark.anyio
async def test_stop_from_idle_is_noop():
    session = Session(rerun_logger=_make_mock_logger())
    await session.stop()
    assert session.state == "idle"


@pytest.mark.anyio
async def test_pause_resume():
    session = Session(rerun_logger=_make_mock_logger())
    await session.start()
    assert session.state == "running"

    session.pause()
    assert session.state == "paused"

    session.resume()
    assert session.state == "running"

    await session.stop()


@pytest.mark.anyio
async def test_pause_from_idle_is_noop():
    session = Session(rerun_logger=_make_mock_logger())
    session.pause()
    assert session.state == "idle"


@pytest.mark.anyio
async def test_resume_from_idle_is_noop():
    session = Session(rerun_logger=_make_mock_logger())
    session.resume()
    assert session.state == "idle"


@pytest.mark.anyio
async def test_reset_clears_state():
    session = Session(rerun_logger=_make_mock_logger())
    await session.start()
    session.send_instruction("pick up block")

    await session.reset()
    assert session.state == "idle"
    assert session.instruction == ""
    assert session.step == 0


@pytest.mark.anyio
async def test_handle_sim_control_play_from_idle():
    session = Session(rerun_logger=_make_mock_logger())
    await session.handle_sim_control("play")
    assert session.state == "running"
    await session.stop()


@pytest.mark.anyio
async def test_handle_sim_control_pause_and_resume():
    session = Session(rerun_logger=_make_mock_logger())
    await session.handle_sim_control("play")
    await session.handle_sim_control("pause")
    assert session.state == "paused"
    await session.handle_sim_control("play")
    assert session.state == "running"
    await session.stop()


@pytest.mark.anyio
async def test_handle_sim_control_stop():
    session = Session(rerun_logger=_make_mock_logger())
    await session.handle_sim_control("play")
    await session.handle_sim_control("stop")
    assert session.state == "idle"


@pytest.mark.anyio
async def test_handle_sim_control_reset():
    session = Session(rerun_logger=_make_mock_logger())
    await session.handle_sim_control("play")
    session.send_instruction("wave")
    await session.handle_sim_control("reset")
    assert session.state == "idle"
    assert session.instruction == ""


@pytest.mark.anyio
async def test_handle_sim_control_step_from_idle():
    session = Session(rerun_logger=_make_mock_logger())
    await session.handle_sim_control("step")
    assert session.state == "paused"
    await session.stop()


@pytest.mark.anyio
async def test_handle_sim_control_unknown_action_is_noop():
    session = Session(rerun_logger=_make_mock_logger())
    await session.handle_sim_control("unknown_action")
    assert session.state == "idle"


@pytest.mark.anyio
async def test_observation_loop_logs_data():
    mock_logger = _make_mock_logger()
    session = Session(rerun_logger=mock_logger)
    await session.start()

    await asyncio.sleep(0.35)

    await session.stop()

    assert mock_logger.log_observation.call_count >= 2
    assert mock_logger.log_action.call_count >= 2


@pytest.mark.anyio
async def test_observation_loop_logs_instruction_when_set():
    mock_logger = _make_mock_logger()
    session = Session(rerun_logger=mock_logger)
    session.send_instruction("wave")
    await session.start()

    await asyncio.sleep(0.25)

    await session.stop()

    assert mock_logger.log_instruction.call_count >= 1
