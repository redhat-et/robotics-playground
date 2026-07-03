from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from robotics_playground.session import Session


def _make_mock_logger():
    logger = MagicMock()
    logger.log_observation = MagicMock()
    logger.log_action = MagicMock()
    logger.log_instruction = MagicMock()
    return logger


def test_session_initial_state():
    session = Session(rerun_logger=_make_mock_logger())
    assert session.state == "idle"


def test_send_instruction_stores_text():
    session = Session(rerun_logger=_make_mock_logger())
    session.send_instruction("wave")
    assert session.instruction == "wave"


@pytest.mark.anyio
async def test_start_stop_lifecycle():
    session = Session(rerun_logger=_make_mock_logger())
    assert session.state == "idle"

    await session.start()
    assert session.state == "running"

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
