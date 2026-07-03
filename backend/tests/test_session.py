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
