from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pytest


@pytest.fixture
def mock_rr():
    with patch("robotics_playground.rerun_logger.rr") as mock:
        yield mock


def test_log_observation_logs_all_cameras(mock_rr):
    from robotics_playground.rerun_logger import RerunLogger

    logger = RerunLogger()
    obs = {
        "step": 5,
        "cameras": {
            "wrist": np.zeros((240, 320, 3), dtype=np.uint8),
            "head": np.zeros((240, 320, 3), dtype=np.uint8),
        },
        "joint_positions": [0.1, 0.2, 0.3],
        "joint_velocities": [0.0, 0.0, 0.0],
    }
    logger.log_observation(obs, step=5)

    mock_rr.set_time.assert_called_with("step", sequence=5)

    logged_paths = [call.args[0] for call in mock_rr.log.call_args_list]
    assert "session/policy_0/camera/wrist" in logged_paths
    assert "session/policy_0/camera/head" in logged_paths


def test_log_observation_logs_joint_positions(mock_rr):
    from robotics_playground.rerun_logger import RerunLogger

    logger = RerunLogger()
    obs = {
        "step": 0,
        "cameras": {"wrist": np.zeros((240, 320, 3), dtype=np.uint8)},
        "joint_positions": [0.1, 0.2, 0.3],
        "joint_velocities": [0.4, 0.5, 0.6],
    }
    logger.log_observation(obs, step=0)

    logged_paths = [call.args[0] for call in mock_rr.log.call_args_list]
    assert "session/policy_0/joints/joint_0" in logged_paths
    assert "session/policy_0/joints/joint_2" in logged_paths


def test_log_action_logs_dimensions(mock_rr):
    from robotics_playground.rerun_logger import RerunLogger

    logger = RerunLogger()
    action = {"joint_positions": [0.1, 0.2, 0.3]}
    logger.log_action(action, step=1)

    mock_rr.set_time.assert_called_with("step", sequence=1)
    logged_paths = [call.args[0] for call in mock_rr.log.call_args_list]
    assert "session/policy_0/actions/dim_0" in logged_paths


def test_log_instruction(mock_rr):
    from robotics_playground.rerun_logger import RerunLogger

    logger = RerunLogger()
    logger.log_instruction("pick up block", step=3)
    mock_rr.set_time.assert_called_with("step", sequence=3)
    mock_rr.log.assert_called()


def test_clear_logs_clear_markers(mock_rr):
    from robotics_playground.rerun_logger import RerunLogger

    logger = RerunLogger(port=9876)
    logger._initialized = True
    logger._last_step = 10
    logger.clear()
    mock_rr.set_time.assert_called_with("step", sequence=11)
    logged_paths = [call.args[0] for call in mock_rr.log.call_args_list]
    assert "session/policy_0" in logged_paths
    assert "session/instructions" in logged_paths


def test_clear_advances_step_offset(mock_rr):
    from robotics_playground.rerun_logger import RerunLogger

    logger = RerunLogger()
    logger._initialized = True
    logger._last_step = 10
    logger.clear()
    assert logger._step_offset == 12
    assert logger._last_step == 0


def test_log_after_clear_uses_offset(mock_rr):
    from robotics_playground.rerun_logger import RerunLogger

    logger = RerunLogger()
    logger._initialized = True
    logger._last_step = 5
    logger.clear()
    mock_rr.reset_mock()

    obs = {
        "step": 0,
        "cameras": {"wrist": np.zeros((240, 320, 3), dtype=np.uint8)},
        "joint_positions": [0.1],
        "joint_velocities": [0.0],
    }
    logger.log_observation(obs, step=0)
    mock_rr.set_time.assert_called_with("step", sequence=7)


def test_clear_before_start_is_noop(mock_rr):
    from robotics_playground.rerun_logger import RerunLogger

    logger = RerunLogger()
    logger.clear()
    mock_rr.log.assert_not_called()
