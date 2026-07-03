from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from robotics_playground.session import Session


@pytest.fixture
def mock_rerun():
    return MagicMock()


@pytest.fixture
def mock_logger():
    logger = MagicMock()
    logger.log_observation = MagicMock()
    logger.log_action = MagicMock()
    logger.log_instruction = MagicMock()
    return logger


@pytest.fixture
def session(mock_logger):
    return Session(rerun_logger=mock_logger)
