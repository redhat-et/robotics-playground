from __future__ import annotations

import time

import numpy as np
import pytest

from robotics_playground.mock_policy import predict_action


@pytest.mark.anyio
async def test_predict_action_returns_correct_shape():
    obs = {
        "image": np.zeros((240, 320, 3), dtype=np.uint8),
        "joint_positions": [0.0] * 6,
    }
    action = await predict_action(obs)
    assert isinstance(action, np.ndarray)
    assert action.shape == (6,)


@pytest.mark.anyio
async def test_predict_action_takes_approximately_50ms():
    obs = {
        "image": np.zeros((240, 320, 3), dtype=np.uint8),
        "joint_positions": [0.0] * 6,
    }
    start = time.monotonic()
    await predict_action(obs)
    elapsed = time.monotonic() - start
    assert 0.02 <= elapsed <= 0.1, f"Expected ~50ms, got {elapsed * 1000:.1f}ms"
