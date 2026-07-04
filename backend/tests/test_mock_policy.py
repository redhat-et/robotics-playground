from __future__ import annotations

import pytest

from robotics_playground.mock_policy import predict_action


@pytest.mark.anyio
async def test_predict_action_returns_action_dict():
    obs = {"step": 0, "cameras": {}, "joint_positions": [0.0] * 6, "joint_velocities": [0.0] * 6}
    action = await predict_action(obs)
    assert "joint_positions" in action
    assert len(action["joint_positions"]) == 6
    assert all(isinstance(v, float) for v in action["joint_positions"])
