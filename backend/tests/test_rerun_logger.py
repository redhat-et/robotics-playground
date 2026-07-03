from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np

from robotics_playground.rerun_logger import RerunLogger


@patch("robotics_playground.rerun_logger.rr")
def test_start_initializes_rerun(mock_rr: MagicMock):
    logger = RerunLogger(port=9876)
    logger.start()
    mock_rr.init.assert_called_once_with("robotics_playground")
    mock_rr.serve_grpc.assert_called_once_with(grpc_port=9876)


@patch("robotics_playground.rerun_logger.rr")
def test_start_is_idempotent(mock_rr: MagicMock):
    logger = RerunLogger(port=9876)
    logger.start()
    logger.start()
    assert mock_rr.init.call_count == 1


@patch("robotics_playground.rerun_logger.rr")
def test_log_observation_logs_image_and_joints(mock_rr: MagicMock):
    logger = RerunLogger(port=9876, policy_index=0)
    logger.start()
    image = np.zeros((240, 320, 3), dtype=np.uint8)
    joints = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]

    logger.log_observation(image, joints, step=5)

    mock_rr.set_time.assert_called_with("step", sequence=5)
    mock_rr.log.assert_any_call("session/policy_0/camera/wrist", mock_rr.Image.return_value)
    assert mock_rr.log.call_count == 7  # 1 image + 6 joints


@patch("robotics_playground.rerun_logger.rr")
def test_log_action_logs_all_dimensions(mock_rr: MagicMock):
    logger = RerunLogger(port=9876, policy_index=0)
    logger.start()
    action = np.array([0.1, -0.2, 0.3, -0.4, 0.5, -0.6], dtype=np.float32)

    logger.log_action(action, step=10)

    mock_rr.set_time.assert_called_with("step", sequence=10)
    assert mock_rr.log.call_count == 6


@patch("robotics_playground.rerun_logger.rr")
def test_log_instruction_logs_text(mock_rr: MagicMock):
    logger = RerunLogger(port=9876)
    logger.start()

    logger.log_instruction("pick up block", step=3)

    mock_rr.set_time.assert_called_with("step", sequence=3)
    mock_rr.log.assert_called_once_with("session/instructions", mock_rr.TextLog.return_value)


@patch("robotics_playground.rerun_logger.rr")
def test_policy_index_changes_entity_prefix(mock_rr: MagicMock):
    logger = RerunLogger(port=9876, policy_index=1)
    logger.start()
    image = np.zeros((240, 320, 3), dtype=np.uint8)

    logger.log_observation(image, [0.0] * 6, step=0)

    logged_paths = [call.args[0] for call in mock_rr.log.call_args_list]
    assert all("policy_1" in p for p in logged_paths)
